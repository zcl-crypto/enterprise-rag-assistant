from __future__ import annotations

import uuid
import os
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from qdrant_client import QdrantClient, models

from rag_app.documents import Chunk, ParsedBlock, make_chunks


COLLECTION_NAME = "knowledge_chunks"


class Embedder(Protocol):
    model_name: str
    dimension: int

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...

    def encode_query(self, text: str) -> list[float]: ...


class BgeEmbedder:
    model_name = "BAAI/bge-small-zh-v1.5"
    dimension = 512

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        source = os.environ.get("EMBEDDING_MODEL_PATH") or self.model_name
        self.model = SentenceTransformer(source, device="cpu")
        self.max_tokens = min(int(self.model.max_seq_length or 512), 512)

    def token_length(self, text: str) -> int:
        return len(self.model.tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False))

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(list(texts), normalize_embeddings=True, batch_size=16)
        return vectors.tolist()

    def encode_query(self, text: str) -> list[float]:
        instruction = "为这个句子生成表示以用于检索相关文章："
        return self.encode([instruction + text])[0]


def chunks_for_embedder(blocks: Iterable[ParsedBlock], embedder: Embedder) -> list[Chunk]:
    token_length = getattr(embedder, "token_length", None)
    max_tokens = getattr(embedder, "max_tokens", None)
    if token_length is None and max_tokens is None:
        return make_chunks(blocks)
    if not callable(token_length) or not isinstance(max_tokens, int):
        raise ValueError("Embedder token counter and limit must be supplied together")
    return make_chunks(blocks, token_length=token_length, max_tokens=max_tokens)


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    version_id: str
    text: str
    headings: tuple[str, ...]
    page_number: int | None
    score: float


def version_filter(allowed_version_ids: Sequence[str]) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(
            key="version_id", match=models.MatchAny(any=list(allowed_version_ids)),
        )]
    )


def scored_points_to_hits(points: Sequence[models.ScoredPoint]) -> list[SearchHit]:
    return [
        SearchHit(
            chunk_id=str(point.id),
            document_id=str(point.payload["document_id"]),
            version_id=str(point.payload["version_id"]),
            text=str(point.payload["text"]),
            headings=tuple(point.payload.get("headings") or []),
            page_number=point.payload.get("page_number"),
            score=point.score,
        )
        for point in points
    ]


class VectorIndex:
    def __init__(self, client: QdrantClient, collection: str = COLLECTION_NAME):
        self.client = client
        self.collection = collection

    def ensure_collection(self, dimension: int) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="version_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        else:
            config = self.client.get_collection(self.collection).config.params.vectors
            if config.size != dimension:
                raise ValueError(f"Collection dimension {config.size} does not match embedder {dimension}")

    def upsert_chunks(
        self,
        document_id: str,
        version_id: str,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts differ")
        points = [
            models.PointStruct(
                id=chunk_point_id(version_id, chunk.index),
                vector=list(vector),
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

    def search(self, vector: Sequence[float], allowed_version_ids: Sequence[str], limit: int = 5) -> list[SearchHit]:
        if not allowed_version_ids:
            return []
        results = self.client.query_points(
            collection_name=self.collection,
            query=list(vector),
            query_filter=version_filter(allowed_version_ids),
            limit=limit,
            with_payload=True,
        ).points
        return scored_points_to_hits(results)

    def purge_version(self, version_id: str) -> None:
        if not self.client.collection_exists(self.collection):
            return
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(
                    key="version_id", match=models.MatchValue(value=version_id)
                )])
            ),
            wait=True,
        )


def chunk_point_id(version_id: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rag-chunk:{version_id}:{index}"))
