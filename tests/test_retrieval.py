from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag_app.api import create_app
from rag_app.db import Base, ChunkRecord, Document, DocumentVersion
from rag_app.lexical_index import LexicalIndex
from rag_app.reranker import BgeReranker
from rag_app.retrieval import reciprocal_rank_fusion
from rag_app.vector_index import SearchHit
from scripts.backfill_lexical import backfill_active_chunks


class FakeEmbedder:
    model_name = "test-embedder"
    dimension = 3

    def encode(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def encode_query(self, text):
        return [1.0, 0.0, 0.0]


class FakeBm25:
    def encode(self, texts):
        return [models.SparseVector(indices=[1], values=[1.0]) for _ in texts]

    def encode_query(self, text):
        return models.SparseVector(indices=[1], values=[1.0])


class FakeReranker:
    model_name = "test-reranker"

    def rerank(self, query, hits, limit):
        return [replace(hit, score=42.0) for hit in hits[:limit]]


def test_rrf_rewards_agreement_and_deduplicates() -> None:
    first = SearchHit("a", "doc-a", "version-a", "A", (), None, 0.9)
    second = replace(first, chunk_id="b", document_id="doc-b", score=0.8)
    third = replace(first, chunk_id="c", document_id="doc-c", score=0.7)
    fused = reciprocal_rank_fusion(([first, second], [second, third]), 3)
    assert [hit.chunk_id for hit in fused] == ["b", "a", "c"]
    assert fused[0].score > fused[1].score


def test_reranker_sorts_model_scores_and_limits_results() -> None:
    first = SearchHit("a", "doc-a", "version-a", "First", (), None, 0.9)
    second = replace(first, chunk_id="b", text="Second", score=0.2)

    class FakeCrossEncoder:
        def predict(self, pairs, **kwargs):
            assert pairs == [("question", "\nFirst"), ("question", "\nSecond")]
            return [0.1, 0.8]

    reranker = BgeReranker.__new__(BgeReranker)
    reranker.model = FakeCrossEncoder()
    results = reranker.rerank("question", [first, second], 1)
    assert [hit.chunk_id for hit in results] == ["b"]
    assert results[0].score == 0.8


def test_hybrid_api_indexes_and_purges_both_collections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_MODE", "hybrid")
    monkeypatch.setenv("ENABLE_RERANKER", "1")
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "qdrant"))
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")
    monkeypatch.setenv("LLM_API_KEY", "")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'hybrid.db').as_posix()}",
        embedder_factory=FakeEmbedder,
        bm25_factory=FakeBm25,
        reranker_factory=FakeReranker,
        seed_demo=True,
    )
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        uploaded = client.post(
            "/api/v1/documents", headers=headers,
            files={"file": ("policy.md", b"# Policy\n\nThe current policy.", "text/markdown")},
            data={"title": "Policy"},
        )
        assert uploaded.status_code == 202
        ids = uploaded.json()
        assert client.get(f"/api/v1/jobs/{ids['job_id']}", headers=headers).json()["status"] == "DONE"
        assert app.state.lexical_index.client.count(app.state.lexical_index.collection).count == 1
        assert client.post(
            f"/api/v1/documents/{ids['document_id']}/versions/{ids['version_id']}/activate", headers=headers,
        ).status_code == 200
        hits = client.post("/api/v1/search", headers=headers, json={"query": "policy"}).json()
        assert len(hits) == 1
        assert hits[0]["version_id"] == ids["version_id"]
        assert hits[0]["score"] == 42.0
        assert client.delete(f"/api/v1/documents/{ids['document_id']}", headers=headers).status_code == 200
        assert client.post("/api/v1/search", headers=headers, json={"query": "policy"}).json() == []
        assert app.state.index.client.count(app.state.index.collection).count == 0
        assert app.state.lexical_index.client.count(app.state.lexical_index.collection).count == 0


def test_dense_mode_still_purges_old_lexical_points(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_MODE", "hybrid")
    monkeypatch.setenv("ENABLE_RERANKER", "0")
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "qdrant"))
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")
    kwargs = {
        "database_url": f"sqlite:///{(tmp_path / 'switch.db').as_posix()}",
        "embedder_factory": FakeEmbedder,
        "bm25_factory": FakeBm25,
        "seed_demo": True,
    }
    with TestClient(create_app(**kwargs)) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        ids = client.post(
            "/api/v1/documents", headers=headers,
            files={"file": ("a.txt", b"Current rule.", "text/plain")}, data={"title": "Rule"},
        ).json()
        assert client.post(
            f"/api/v1/documents/{ids['document_id']}/versions/{ids['version_id']}/activate", headers=headers,
        ).status_code == 200
    monkeypatch.setenv("RETRIEVAL_MODE", "dense")
    with TestClient(create_app(**kwargs)) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        assert client.delete(f"/api/v1/documents/{ids['document_id']}", headers=headers).status_code == 200
        lexical = client.app.state.purge_lexical_index
        assert lexical.client.count(lexical.collection).count == 0


def test_backfill_ignores_retired_and_deleted_versions() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        for status, deleted in (("ACTIVE", False), ("RETIRED", False), ("ACTIVE", True)):
            document = Document(title=status, allowed_roles=["employee"])
            session.add(document)
            session.flush()
            version = DocumentVersion(
                document_id=document.id, version_number=1, filename="a.txt", source_format="txt",
                sha256="0" * 64, storage_path="a.txt", status=status,
            )
            session.add(version)
            session.flush()
            session.add(ChunkRecord(
                version_id=version.id, ordinal=0, text=status, headings=[], embedding_model="fake",
            ))
            document.active_version_id = version.id
            if deleted:
                from rag_app.db import now_utc

                document.deleted_at = now_utc()
    index = LexicalIndex(QdrantClient(":memory:"))
    assert backfill_active_chunks(sessions, index, FakeBm25()) == (1, 1)
    assert backfill_active_chunks(sessions, index, FakeBm25()) == (1, 1)
    assert index.client.count(index.collection).count == 1
