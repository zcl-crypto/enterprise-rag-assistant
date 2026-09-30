from __future__ import annotations

import os
from dataclasses import replace
from typing import Protocol, Sequence

from rag_app.vector_index import SearchHit


class Reranker(Protocol):
    model_name: str

    def rerank(self, query: str, hits: Sequence[SearchHit], limit: int) -> list[SearchHit]: ...


class BgeReranker:
    model_name = "BAAI/bge-reranker-base"

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        source = os.getenv("RERANKER_MODEL_PATH") or self.model_name
        self.model = CrossEncoder(source, max_length=512, device="cpu")

    def rerank(self, query: str, hits: Sequence[SearchHit], limit: int) -> list[SearchHit]:
        if not hits:
            return []
        pairs = [(query, " / ".join(hit.headings) + "\n" + hit.text) for hit in hits]
        scores = self.model.predict(pairs, batch_size=4, show_progress_bar=False)
        ranked = [replace(hit, score=float(score)) for hit, score in zip(hits, scores, strict=True)]
        ranked.sort(key=lambda hit: (-hit.score, hit.chunk_id))
        return ranked[:limit]
