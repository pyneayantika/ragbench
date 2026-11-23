"""
What it does: Finds the closest chunks to a question using dense, BM25, hybrid RRF, and cross-encoder re-ranking.
Why it exists: The generator only sees the chunks this step selects.
What breaks without it: The model answers from the wrong text, or keyword-specific queries fail.
Failure stage: retrieval.
"""

from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Any

from sentence_transformers import CrossEncoder

from src.chunk import cache_path as chunk_cache_path, chunk_sig
from src.index import bm25_path, collection_name, get_client, get_embedder, tokenize

logger = logging.getLogger(__name__)

BATCH_SIZE = 32
DEFAULT_RRF_K = 60
_CHUNKS_CACHE: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
_BM25_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_RERANKERS: dict[str, CrossEncoder] = {}


def get_chunks_lookup(doc_id: str, signature: str) -> dict[str, dict[str, Any]]:
    key = (doc_id, signature)
    if key not in _CHUNKS_CACHE:
        import json

        path = chunk_cache_path(doc_id, signature)
        if not path.is_file():
            raise FileNotFoundError(f"Chunk cache missing for {doc_id} {signature}: {path}")
        lookup: dict[str, dict[str, Any]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                lookup[str(item["chunk_id"])] = item
        _CHUNKS_CACHE[key] = lookup
    return _CHUNKS_CACHE[key]


def get_bm25_data(doc_id: str, signature: str) -> dict[str, Any]:
    key = (doc_id, signature)
    if key not in _BM25_CACHE:
        path = bm25_path(doc_id, signature)
        if not path.is_file():
            raise FileNotFoundError(f"BM25 index missing for {doc_id} {signature}: {path}")
        with path.open("rb") as handle:
            _BM25_CACHE[key] = pickle.load(handle)
    return _BM25_CACHE[key]


def get_reranker(model_name: str) -> CrossEncoder:
    if model_name not in _RERANKERS:
        started = time.perf_counter()
        logger.info("Loading cross-encoder model %s (loaded once per process)...", model_name)
        _RERANKERS[model_name] = CrossEncoder(model_name)
        elapsed = time.perf_counter() - started
        logger.info("Loaded cross-encoder %s in %.2fs", model_name, elapsed)
    return _RERANKERS[model_name]


def dense_search(
    doc_id: str,
    signature: str,
    model_name: str,
    query: str,
    top_k: int,
) -> list[dict[str, Any]]:
    model = get_embedder(model_name)
    encoded = model.encode(
        [query],
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    name = collection_name(doc_id, signature, model_name)
    collection = get_client().get_collection(name, embedding_function=None)
    found = collection.query(
        query_embeddings=[encoded[0].tolist()],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = found["ids"][0]
    distances = found["distances"][0]
    documents = found["documents"][0]
    metadatas = found["metadatas"][0]
    results: list[dict[str, Any]] = []
    for idx in range(min(top_k, len(ids))):
        metadata = metadatas[idx] or {}
        distance = float(distances[idx])
        results.append(
            {
                "chunk_id": str(metadata.get("chunk_id") or ids[idx]),
                "page_start": int(metadata.get("page_start", 0)),
                "page_end": int(metadata.get("page_end", 0)),
                "score": 1.0 - distance,
                "text": documents[idx] or "",
            }
        )
    return results


def bm25_search(
    doc_id: str,
    signature: str,
    query: str,
    top_k: int,
) -> list[dict[str, Any]]:
    bm25_data = get_bm25_data(doc_id, signature)
    bm25 = bm25_data["bm25"]
    chunk_ids = bm25_data["chunk_ids"]
    chunks_lookup = get_chunks_lookup(doc_id, signature)

    tokens = tokenize(query)
    if not tokens:
        tokens = ["empty"]
    scores = bm25.get_scores(tokens)

    indexed_scores = [(idx, float(score)) for idx, score in enumerate(scores)]
    indexed_scores.sort(key=lambda item: item[1], reverse=True)

    results: list[dict[str, Any]] = []
    for idx, score in indexed_scores[:top_k]:
        cid = str(chunk_ids[idx])
        chunk = chunks_lookup.get(cid, {})
        results.append(
            {
                "chunk_id": cid,
                "page_start": int(chunk.get("page_start", 0)),
                "page_end": int(chunk.get("page_end", 0)),
                "score": score,
                "text": str(chunk.get("text") or ""),
            }
        )
    return results


def reciprocal_rank_fusion(
    dense_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    rrf_k: int = DEFAULT_RRF_K,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Merge ranked lists using RRF: score = sum(1 / (rrf_k + rank)) with rank starting at 1."""
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict[str, Any]] = {}

    for ranked_list in (dense_results, bm25_results):
        for rank, hit in enumerate(ranked_list, start=1):
            cid = str(hit["chunk_id"])
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))
            if cid not in chunk_map:
                chunk_map[cid] = hit

    sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
    fused: list[dict[str, Any]] = []
    for cid in sorted_cids[:top_n]:
        item = dict(chunk_map[cid])
        item["score"] = rrf_scores[cid]
        fused.append(item)
    return fused


def rerank_candidates(
    model_name: str,
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    reranker = get_reranker(model_name)
    pairs = [[query, str(candidate["text"])] for candidate in candidates]
    scores = reranker.predict(pairs)
    ranked = sorted(
        zip(candidates, scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    results: list[dict[str, Any]] = []
    for candidate, score in ranked[:top_k]:
        item = dict(candidate)
        item["score"] = float(score)
        results.append(item)
    return results


def retrieve_chunks(doc_id: str, config: dict[str, Any], query: str) -> list[dict[str, Any]]:
    mode = str(config["retrieval"]["mode"])
    candidate_k = int(config["retrieval"]["candidate_k"])
    final_k = int(config["final_k"])
    rrf_k = int(config["retrieval"].get("rrf_k", DEFAULT_RRF_K))
    model_name = str(config["embedding_model"])
    sig = chunk_sig(config)
    rerank_cfg = config.get("rerank") or {}
    rerank_enabled = bool(rerank_cfg.get("enabled", False))
    rerank_model = str(rerank_cfg.get("model") or "")

    if mode == "dense":
        candidates = dense_search(doc_id, sig, model_name, query, candidate_k)
    elif mode == "hybrid":
        dense_hits = dense_search(doc_id, sig, model_name, query, candidate_k)
        bm25_hits = bm25_search(doc_id, sig, query, candidate_k)
        pool_size = candidate_k if rerank_enabled else final_k
        candidates = reciprocal_rank_fusion(dense_hits, bm25_hits, rrf_k=rrf_k, top_n=pool_size)
    else:
        raise ValueError(f"Unknown retrieval mode: {mode}")

    if rerank_enabled:
        return rerank_candidates(rerank_model, query, candidates, top_k=final_k)

    return candidates[:final_k]


# Backward-compatible alias for evaluate.py / callers
dense_retrieve = retrieve_chunks
