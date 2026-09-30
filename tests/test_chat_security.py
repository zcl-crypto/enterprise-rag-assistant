from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import select

from rag_app.api import create_app
from rag_app.db import ChatRequestRecord, DailyTokenBudget, User, now_utc
from rag_app.generation import GeneratedAnswer, cited_sources
from rag_app.ingestion import run_index_job
from rag_app.lifecycle import delete_document
from rag_app.quota import reserve_tokens
from rag_app.vector_index import SearchHit


class FakeEmbedder:
    model_name = "test-embedder"
    dimension = 3

    def encode(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def encode_query(self, text):
        return [1.0, 0.0, 0.0]


def test_citation_coverage_and_uncited_refusal() -> None:
    hit = SearchHit("chunk", "doc", "version", "Policy text", (), None, 0.9)
    assert cited_sources("现有资料不足，无法确认。", [hit]) == []
    assert cited_sources("有依据。[1]", [hit]) == [hit]
    with pytest.raises(ValueError, match="uncited sentence"):
        cited_sources("有依据[1]。第二句没有引用。", [hit])


def publish_policy(client: TestClient, app, headers: dict[str, str]) -> dict:
    uploaded = client.post(
        "/api/v1/documents", headers=headers,
        files={"file": ("policy.txt", "# Policy\nThis is the current rule.".encode(), "text/plain")},
        data={"title": "Policy"},
    )
    assert uploaded.status_code == 202
    ids = uploaded.json()
    assert run_index_job(app.state.sessions, app.state.index, FakeEmbedder(), ids["job_id"])
    activated = client.post(
        f"/api/v1/documents/{ids['document_id']}/versions/{ids['version_id']}/activate", headers=headers,
    )
    assert activated.status_code == 200
    return ids


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_model_factory_failure_is_reported_without_500(tmp_path: Path, monkeypatch, error_type) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")

    def fail_factory():
        raise error_type("model cannot start")

    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'factory.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"), embedder_factory=FakeEmbedder,
        answer_provider_factory=fail_factory, seed_demo=True,
    )
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        publish_policy(client, app, headers)
        result = client.post("/api/v1/chat", headers=headers, json={"query": "current rule"})
        assert result.status_code == 200
        assert result.json()["status"] == "model_unavailable"
        assert len(result.json()["citations"]) == 1


def test_failed_generation_does_not_leak_newly_deleted_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")
    state = {}

    class DeleteThenFail:
        model_name = "test-generator"

        def answer(self, question, sources):
            with state["app"].state.sessions.begin() as session:
                delete_document(session, state["document_id"])
            raise RuntimeError("upstream timeout")

    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'deleted.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"), embedder_factory=FakeEmbedder,
        answer_provider_factory=DeleteThenFail, seed_demo=True,
    )
    state["app"] = app
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        state["document_id"] = publish_policy(client, app, headers)["document_id"]
        result = client.post("/api/v1/chat", headers=headers, json={"query": "current rule"})
        assert result.status_code == 200
        body = result.json()
        assert {key: body[key] for key in ("status", "answer", "citations")} == {
            "status": "insufficient_evidence", "answer": None, "citations": [],
        }
        with app.state.sessions() as session:
            record = session.get(ChatRequestRecord, body["request_id"])
            assert record.status == "insufficient_evidence"
            assert record.charged_tokens == record.reserved_tokens
            assert not record.reservation_active


def test_model_refusal_has_insufficient_evidence_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")

    class RefusingProvider:
        model_name = "test-generator"

        def answer(self, question, sources):
            return GeneratedAnswer("现有资料不足，无法确认。")

    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'refusal.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"), embedder_factory=FakeEmbedder,
        answer_provider_factory=RefusingProvider, seed_demo=True,
    )
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        publish_policy(client, app, headers)
        result = client.post("/api/v1/chat", headers=headers, json={"query": "unknown rule"})
        assert result.status_code == 200
        body = result.json()
        assert {key: body[key] for key in ("status", "answer", "citations")} == {
            "status": "insufficient_evidence", "answer": None, "citations": [],
        }
        assert body["retrieval_ms"] >= 0
        assert body["generation_ms"] >= 0
        assert body["total_ms"] >= body["retrieval_ms"]
        with app.state.sessions() as session:
            record = session.get(ChatRequestRecord, body["request_id"])
            assert record.status == "insufficient_evidence"
            assert record.charged_tokens == record.reserved_tokens


def test_daily_limit_blocks_model_call_and_records_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")
    monkeypatch.setenv("LLM_DAILY_TOKEN_LIMIT", "1")
    calls = []

    class CountingProvider:
        model_name = "test-generator"

        def answer(self, question, sources):
            calls.append(question)
            return GeneratedAnswer("Answer [1]", 5, 5)

    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'quota.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"), embedder_factory=FakeEmbedder,
        answer_provider_factory=CountingProvider, seed_demo=True,
    )
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        publish_policy(client, app, headers)
        result = client.post("/api/v1/chat", headers=headers, json={"query": "current rule"})
        assert result.status_code == 200
        body = result.json()
        assert body["status"] == "quota_exceeded"
        assert body["citations"]
        assert calls == []
        with app.state.sessions() as session:
            record = session.get(ChatRequestRecord, body["request_id"])
            assert record.status == "quota_exceeded"
            assert record.charged_tokens == 0
            assert session.scalar(select(DailyTokenBudget)).reserved_tokens == 0


def test_disabled_generation_stays_search_only_even_with_a_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")
    monkeypatch.setenv("LLM_API_KEY", "disabled-local-demo")
    monkeypatch.setenv("LLM_ENABLED", "0")

    def forbidden_provider():
        raise AssertionError("Generation provider must not be initialized")

    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'disabled.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"), embedder_factory=FakeEmbedder,
        answer_provider_factory=forbidden_provider, seed_demo=True,
    )
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", data={"username": "admin", "password": "test-password"}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        publish_policy(client, app, headers)
        result = client.post("/api/v1/chat", headers=headers, json={"query": "current rule"})
        assert result.status_code == 200
        assert result.json()["status"] == "search_only"
        assert result.json()["citations"]
        with app.state.sessions() as session:
            record = session.get(ChatRequestRecord, result.json()["request_id"])
            assert record.status == "search_only"
            assert record.charged_tokens == 0


def test_restart_reconciles_interrupted_generation_for_admin_usage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_PASSWORD", "test-password")
    database_url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    first = create_app(database_url=database_url, qdrant_client=QdrantClient(":memory:"), seed_demo=True)
    with TestClient(first):
        with first.state.sessions() as session:
            actor_id = session.scalar(select(User.id).where(User.username == "admin"))
        assert actor_id is not None
        assert reserve_tokens(first.state.sessions, "interrupted", actor_id, 80, 100)
        with first.state.sessions.begin() as session:
            session.get(ChatRequestRecord, "interrupted").created_at = now_utc() - timedelta(hours=1)

    restarted = create_app(database_url=database_url, qdrant_client=QdrantClient(":memory:"), seed_demo=True)
    with TestClient(restarted) as client:
        token = client.post("/api/v1/auth/login", data={
            "username": "admin", "password": "test-password",
        }).json()["access_token"]
        usage = client.get("/api/v1/usage", headers={"Authorization": f"Bearer {token}"})
        assert usage.status_code == 200
        assert usage.json()["consumed_tokens"] == 80
        assert usage.json()["reserved_tokens"] == 0
        assert usage.json()["requests"][0]["status"] == "usage_unconfirmed"
        assert usage.json()["requests"][0]["charged_tokens"] == 80
