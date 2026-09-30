from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from rag_app.lexical_index import ChineseBm25, LexicalIndex
from rag_app.reranker import Reranker
from rag_app.vector_index import Embedder, SearchHit, VectorIndex


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[SearchHit]], limit: int, *, rank_constant: int = 60,
) -> list[SearchHit]:
    scores: dict[str, float] = {}
    hits: dict[str, SearchHit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1 / (rank_constant + rank)
            hits[hit.chunk_id] = hit
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return [replace(hits[chunk_id], score=scores[chunk_id]) for chunk_id in ordered[:limit]]


def retrieve(
    query: str,
    allowed_version_ids: Sequence[str],
    limit: int,
    dense_index: VectorIndex,
    embedder: Embedder,
    lexical_index: LexicalIndex | None = None,
    bm25: ChineseBm25 | None = None,
    reranker: Reranker | None = None,
) -> list[SearchHit]:
    if not allowed_version_ids:
        return []
    candidate_limit = max(20, limit * 4) if lexical_index and bm25 else (max(10, limit * 2) if reranker else limit)
    rerank_limit = min(20, max(10, limit))
    dense_hits = dense_index.search(embedder.encode_query(query), allowed_version_ids, candidate_limit)
    if lexical_index is None or bm25 is None:
        return reranker.rerank(query, dense_hits[:rerank_limit], limit) if reranker else dense_hits
    lexical_hits = lexical_index.search(bm25.encode_query(query), allowed_version_ids, candidate_limit)
    fused = reciprocal_rank_fusion((dense_hits, lexical_hits), rerank_limit if reranker else limit)
    return reranker.rerank(query, fused, limit) if reranker else fused
