"""
What it does: Finds the closest chunks to a question using dense search.
Why it exists: The generator only sees the chunks this step selects.
What breaks without it: The model answers from the wrong text.
Failure stage: retrieval.
"""

from __future__ import annotations

from typing import Any

from src.chunk import chunk_sig
from src.index import collection_name, get_client, get_embedder

BATCH_SIZE = 32


def dense_retrieve(doc_id: str, config: dict[str, Any], query: str) -> list[dict[str, Any]]:
    mode = str(config["retrieval"]["mode"])
    if mode != "dense":
        raise ValueError(f"This step only runs dense retrieval, not {mode}")
    candidate_k = int(config["retrieval"]["candidate_k"])
    final_k = int(config["final_k"])
    model_name = str(config["embedding_model"])
    model = get_embedder(model_name)
    encoded = model.encode(
        [query],
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    name = collection_name(doc_id, chunk_sig(config), model_name)
    collection = get_client().get_collection(name, embedding_function=None)
    found = collection.query(
        query_embeddings=[encoded[0].tolist()],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = found["ids"][0]
    distances = found["distances"][0]
    documents = found["documents"][0]
    metadatas = found["metadatas"][0]
    rows: list[dict[str, Any]] = []
    for index in range(min(final_k, len(ids))):
        metadata = metadatas[index] or {}
        distance = float(distances[index])
        rows.append(
            {
                "chunk_id": str(metadata.get("chunk_id") or ids[index]),
                "page_start": int(metadata["page_start"]),
                "page_end": int(metadata["page_end"]),
                "score": 1.0 - distance,
                "text": documents[index] or "",
            }
        )
    return rows
