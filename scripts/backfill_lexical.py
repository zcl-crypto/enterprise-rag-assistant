from __future__ import annotations

import os
from collections import defaultdict

from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from rag_app.db import ChunkRecord, Document, DocumentVersion, make_engine, make_session_factory
from rag_app.documents import Chunk
from rag_app.lexical_index import ChineseBm25, LexicalIndex


def backfill_active_chunks(sessions: sessionmaker, index: LexicalIndex, bm25: ChineseBm25) -> tuple[int, int]:
    with sessions() as session:
        rows = session.execute(
            select(Document.id, DocumentVersion.id, ChunkRecord)
            .join(DocumentVersion, Document.active_version_id == DocumentVersion.id)
            .join(ChunkRecord, ChunkRecord.version_id == DocumentVersion.id)
            .where(Document.deleted_at.is_(None), DocumentVersion.status == "ACTIVE")
            .order_by(DocumentVersion.id, ChunkRecord.ordinal)
        ).all()
    by_version: dict[tuple[str, str], list[Chunk]] = defaultdict(list)
    for document_id, version_id, row in rows:
        by_version[(document_id, version_id)].append(
            Chunk(index=row.ordinal, text=row.text, headings=tuple(row.headings), page_number=row.page_number)
        )

    index.ensure_collection()
    for (document_id, version_id), chunks in by_version.items():
        vectors = bm25.encode([" / ".join(chunk.headings) + "\n" + chunk.text for chunk in chunks])
        index.upsert_chunks(document_id, version_id, chunks, vectors)
        with sessions() as session:
            active_version_id = session.scalar(
                select(Document.active_version_id).where(Document.id == document_id, Document.deleted_at.is_(None))
            )
        if active_version_id != version_id:
            index.purge_version(version_id)
    return len(by_version), sum(len(chunks) for chunks in by_version.values())


if __name__ == "__main__":
    engine = make_engine()
    sessions = make_session_factory(engine)
    local_path = os.getenv("QDRANT_LOCAL_PATH")
    client = QdrantClient(path=local_path) if local_path else QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    try:
        versions, chunks = backfill_active_chunks(sessions, LexicalIndex(client), ChineseBm25())
        print(f"Backfilled {versions} active versions and {chunks} chunks into BM25")
    finally:
        client.close()
        engine.dispose()
