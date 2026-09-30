from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import jieba
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

from rag_app.documents import Chunk
from rag_app.vector_index import SearchHit, chunk_point_id, scored_points_to_hits, version_filter


LEXICAL_COLLECTION = "knowledge_chunks_lexical"
SPARSE_VECTOR_NAME = "bm25"


class ChineseBm25:
    model_name = "Qdrant/bm25 + jieba"

    def __init__(self) -> None:
        cache = Path(os.getenv("FASTEMBED_CACHE_PATH", ".models/fastembed"))
        cache.mkdir(parents=True, exist_ok=True)
        self.model = SparseTextEmbedding(
            model_name="Qdrant/bm25", cache_dir=str(cache), disable_stemmer=True,
        )

    @staticmethod
    def prepare(text: str) -> str:
        return " ".join(token.strip() for token in jieba.lcut(text.lower()) if token.strip())

    @staticmethod
    def _as_vector(embedding) -> models.SparseVector:
        pairs = sorted(zip(embedding.indices, embedding.values, strict=True))
        return models.SparseVector(
            indices=[int(index) for index, _ in pairs],
            values=[float(value) for _, value in pairs],
        )

    def encode(self, texts: Sequence[str]) -> list[models.SparseVector]:
        return [self._as_vector(item) for item in self.model.embed([self.prepare(text) for text in texts])]

    def encode_query(self, text: str) -> models.SparseVector:
        return self._as_vector(next(self.model.query_embed(self.prepare(text))))


class LexicalIndex:
    def __init__(self, client: QdrantClient, collection: str = LEXICAL_COLLECTION):
        self.client = client
        self.collection = collection

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: models.SparseVectorParams(modifier=models.Modifier.IDF),
                },
            )
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="version_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        else:
            sparse = self.client.get_collection(self.collection).config.params.sparse_vectors or {}
            if SPARSE_VECTOR_NAME not in sparse:
                raise ValueError(f"Collection {self.collection} lacks the BM25 sparse vector")

    def upsert_chunks(
        self,
        document_id: str,
        version_id: str,
        chunks: Sequence[Chunk],
        vectors: Sequence[models.SparseVector],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and sparse vector counts differ")
        points = [
            models.PointStruct(
                id=chunk_point_id(version_id, chunk.index),
                vector={SPARSE_VECTOR_NAME: vector},
                payload={
                    "document_id": document_id,
                    "version_id": version_id,
                    "chunk_index": chunk.index,
                    "text": chunk.text,
                    "headings": list(chunk.headings),
                    "page_number": chunk.page_number,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def search(self, vector: models.SparseVector, allowed_version_ids: Sequence[str], limit: int = 5) -> list[SearchHit]:
        if not allowed_version_ids or not vector.indices or not self.client.collection_exists(self.collection):
            return []
        points = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            using=SPARSE_VECTOR_NAME,
            query_filter=version_filter(allowed_version_ids),
            limit=limit,
            with_payload=True,
        ).points
        return scored_points_to_hits(points)

    def purge_version(self, version_id: str) -> None:
        if not self.client.collection_exists(self.collection):
            return
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=[models.FieldCondition(
                key="version_id", match=models.MatchValue(value=version_id),
            )])),
            wait=True,
        )
