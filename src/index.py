"""
What it does: Embeds chunk text into Chroma and builds a BM25 keyword index.
Why it exists: Retrieval can only search chunks that have been stored.
What breaks without it: Dense search has no vectors, and later keyword search has no index.
Failure stage: indexing.
"""

from __future__ import annotations

import pickle
import re
import time
from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import NotFoundError
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from src.chunk import chunk_sig

ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = ROOT / "cache" / "chroma"
BM25_DIR = ROOT / "cache" / "bm25"
BATCH_SIZE = 32
TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
_MODELS: dict[str, SentenceTransformer] = {}
_CLIENT: chromadb.ClientAPI | None = None


def short_model_name(model_name: str) -> str:
    return model_name.rsplit("/", 1)[-1]


def collection_name(doc_id: str, signature: str, model_name: str) -> str:
    raw = f"{doc_id}__{signature}__{short_model_name(model_name)}"
    cleaned = NAME_RE.sub("_", raw).strip("_-")
    if len(cleaned) < 3:
        cleaned = (cleaned + "xxx")[:3]
    cleaned = cleaned[:63]
    if not cleaned[-1].isalnum():
        cleaned = cleaned[:-1] + "0"
    return cleaned


def get_embedder(model_name: str) -> SentenceTransformer:
    if model_name not in _MODELS:
        _MODELS[model_name] = SentenceTransformer(model_name)
    return _MODELS[model_name]


def get_client() -> chromadb.ClientAPI:
    global _CLIENT
    if _CLIENT is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _CLIENT


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def embed_texts(model_name: str, texts: list[str]) -> list[list[float]]:
    model = get_embedder(model_name)
    vectors: list[list[float]] = []
    steps = range(0, len(texts), BATCH_SIZE)
    for start in tqdm(steps, desc=f"embed {short_model_name(model_name)}", unit="batch"):
        batch = texts[start : start + BATCH_SIZE]
        encoded = model.encode(
            batch,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors.extend(row.tolist() for row in encoded)
    return vectors


def bm25_path(doc_id: str, signature: str) -> Path:
    return BM25_DIR / f"{doc_id}__{signature}.pkl"


def _open_collection(name: str) -> Any | None:
    try:
        return get_client().get_collection(name, embedding_function=None)
    except NotFoundError:
        return None


def _store_embeddings(name: str, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> None:
    collection = get_client().create_collection(
        name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        collection.add(
            ids=[str(chunk["chunk_id"]) for chunk in batch],
            embeddings=vectors[start : start + BATCH_SIZE],
            documents=[str(chunk["text"]) or " " for chunk in batch],
            metadatas=[
                {
                    "page_start": int(chunk["page_start"]),
                    "page_end": int(chunk["page_end"]),
                    "section_heading": str(chunk.get("section_heading") or ""),
                    "chunk_id": str(chunk["chunk_id"]),
                }
                for chunk in batch
            ],
        )


def _store_bm25(path: Path, chunks: list[dict[str, Any]]) -> None:
    tokenised = [tokenize(str(chunk["text"])) for chunk in chunks]
    if any(len(tokens) == 0 for tokens in tokenised):
        tokenised = [tokens or ["empty"] for tokens in tokenised]
    payload = {
        "chunk_ids": [str(chunk["chunk_id"]) for chunk in chunks],
        "bm25": BM25Okapi(tokenised),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pkl.tmp")
    with temporary.open("wb") as handle:
        pickle.dump(payload, handle)
    temporary.replace(path)


def index_document(doc_id: str, config: dict[str, Any], chunks: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    signature = chunk_sig(config)
    model_name = str(config["embedding_model"])
    name = collection_name(doc_id, signature, model_name)
    existing = _open_collection(name)
    chroma_hit = existing is not None and not force and existing.count() == len(chunks)
    embed_seconds = 0.0
    if not chroma_hit:
        if existing is not None:
            get_client().delete_collection(name)
        embed_started = time.perf_counter()
        vectors = embed_texts(model_name, [str(chunk["embed_text"]) for chunk in chunks])
        embed_seconds = time.perf_counter() - embed_started
        _store_embeddings(name, chunks, vectors)
    path = bm25_path(doc_id, signature)
    bm25_hit = path.is_file() and not force
    if not bm25_hit:
        _store_bm25(path, chunks)
    return {
        "collection": name,
        "count": len(chunks),
        "chroma_hit": chroma_hit,
        "bm25_hit": bm25_hit,
        "embed_seconds": embed_seconds,
        "seconds": time.perf_counter() - started,
        "model": short_model_name(model_name),
    }
