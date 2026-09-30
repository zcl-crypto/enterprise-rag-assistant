from __future__ import annotations

import os
import time

from qdrant_client import QdrantClient
from sqlalchemy import select

from rag_app.db import IngestionJob, make_engine, make_session_factory
from rag_app.ingestion import run_index_job, run_purge_job
from rag_app.init_db import require_current_schema
from rag_app.lexical_index import ChineseBm25, LexicalIndex
from rag_app.vector_index import BgeEmbedder, VectorIndex


def run_forever(poll_seconds: float = 2.0) -> None:
    engine = make_engine()
    require_current_schema(engine)
    sessions = make_session_factory(engine)
    index = VectorIndex(QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333")))
    hybrid = os.getenv("RETRIEVAL_MODE", "dense") == "hybrid"
    lexical_index = LexicalIndex(index.client) if hybrid else None
    embedder = None
    bm25 = None

    for attempt in range(30):
        try:
            index.client.get_collections()
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(2)

    while True:
        with sessions() as session:
            job = session.scalar(
                select(IngestionJob)
                .where(IngestionJob.status == "PENDING")
                .order_by(IngestionJob.created_at, IngestionJob.id)
                .limit(1)
            )
            job_id, kind = (job.id, job.kind) if job else (None, None)
        if job_id is None:
            time.sleep(poll_seconds)
            continue
        try:
            if kind == "index":
                if embedder is None:
                    embedder = BgeEmbedder()
                if hybrid and bm25 is None:
                    bm25 = ChineseBm25()
                run_index_job(sessions, index, embedder, job_id, lexical_index=lexical_index, bm25=bm25)
            elif kind == "purge":
                run_purge_job(sessions, index, job_id, lexical_index=LexicalIndex(index.client))
            else:
                raise ValueError(f"Unknown job kind: {kind}")
        except Exception as exc:
            print(f"Job {job_id} failed unexpectedly: {exc}", flush=True)
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
