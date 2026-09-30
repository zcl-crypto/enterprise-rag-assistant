from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import select

from rag_app.api import create_app
from rag_app.db import Document, DocumentVersion, IngestionJob
from rag_app.generation import GeneratedAnswer
from rag_app.ingestion import run_index_job


class FakeEmbedder:
    model_name = "test-embedder"
    dimension = 3

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def encode_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_http_permissions_upload_search_and_delete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"),
        embedder_factory=FakeEmbedder,
        seed_demo=True,
    )

    with TestClient(app) as client:
        def token(username: str) -> str:
            response = client.post("/api/v1/auth/login", data={"username": username, "password": "demo-password"})
            assert response.status_code == 200
            return response.json()["access_token"]

        admin = {"Authorization": f"Bearer {token('admin')}"}
        employee = {"Authorization": f"Bearer {token('employee')}"}
        procurement = {"Authorization": f"Bearer {token('procurement')}"}
        assert client.get("/api/v1/auth/me", headers=procurement).json()["department"] == "采购部"
        upload = {
            "files": {"file": ("policy.md", "# 采购制度\n\n## 报价\n\n超过一万元比较三家。".encode("utf-8"), "text/markdown")},
            "data": {"title": "采购制度", "department": "采购部"},
        }

        assert client.post("/api/v1/documents", headers=employee, **upload).status_code == 403
        created = client.post("/api/v1/documents", headers=admin, **upload)
        assert created.status_code == 202
        ids = created.json()
        versions_url = f"/api/v1/documents/{ids['document_id']}/versions"
        assert client.get(versions_url, headers=employee).status_code == 403
        assert client.get(versions_url, headers=admin).json()[0]["job_status"] == "PENDING"
        assert client.get(f"/api/v1/jobs/{ids['job_id']}", headers=admin).json()["status"] == "PENDING"
        assert run_index_job(app.state.sessions, app.state.index, FakeEmbedder(), ids["job_id"])
        assert client.post(
            f"/api/v1/documents/{ids['document_id']}/versions/{ids['version_id']}/activate",
            headers=admin,
        ).status_code == 200
        assert client.get(versions_url, headers=admin).json()[0]["status"] == "ACTIVE"

        assert client.get("/api/v1/documents", headers=employee).json() == []
        assert len(client.get("/api/v1/documents", headers=procurement).json()) == 1
        assert client.post("/api/v1/search", headers=employee, json={"query": "报价"}).json() == []
        search = client.post("/api/v1/search", headers=procurement, json={"query": "报价"})
        assert search.status_code == 200
        assert search.json()[0]["version_id"] == ids["version_id"]
        assert client.post("/api/v1/chat", headers=procurement, json={"query": "报价"}).json()["status"] == "search_only"
        assert client.get("/api/v1/usage", headers=employee).status_code == 403
        usage = client.get("/api/v1/usage", headers=admin).json()
        assert usage["limit"] == 50000
        assert usage["consumed_tokens"] == 0
        assert usage["requests"][0]["status"] == "search_only"
        source_url = f"/api/v1/documents/{ids['document_id']}/source"
        assert client.get(source_url, headers=employee).status_code == 404
        assert client.get(source_url, headers=procurement).status_code == 200

        assert client.delete(f"/api/v1/documents/{ids['document_id']}", headers=admin).status_code == 200
        assert client.get(source_url, headers=procurement).status_code == 404
        assert client.post("/api/v1/search", headers=procurement, json={"query": "报价"}).json() == []
        with app.state.sessions() as session:
            assert session.scalars(select(IngestionJob).where(IngestionJob.kind == "purge")).first() is not None


def test_upload_rejects_mismatched_pdf_before_creating_a_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'upload.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"),
        embedder_factory=FakeEmbedder,
        seed_demo=True,
    )
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", data={"username": "admin", "password": "demo-password"})
        admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
        result = client.post(
            "/api/v1/documents", headers=admin,
            files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
            data={"title": "Fake"},
        )
        assert result.status_code == 400
        assert "not a PDF" in result.json()["detail"]
        assert client.get("/api/v1/documents", headers=admin).json() == []
        assert list((tmp_path / "uploads").iterdir()) == []


class FakeAnswerProvider:
    model_name = "test-generator"

    def answer(self, question, sources):
        return GeneratedAnswer("单笔超过一万元需要比较三家供应商。[1]", 20, 15)


def test_chat_validates_citations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'chat.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"),
        embedder_factory=FakeEmbedder,
        answer_provider_factory=FakeAnswerProvider,
        seed_demo=True,
    )
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", data={"username": "admin", "password": "demo-password"})
        admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
        upload = client.post(
            "/api/v1/documents", headers=admin,
            files={"file": ("policy.md", "# 采购\n\n超过一万元比较三家供应商。".encode(), "text/markdown")},
            data={"title": "采购"},
        )
        ids = upload.json()
        assert run_index_job(app.state.sessions, app.state.index, FakeEmbedder(), ids["job_id"])
        client.post(
            f"/api/v1/documents/{ids['document_id']}/versions/{ids['version_id']}/activate",
            headers=admin,
        )
        answer = client.post("/api/v1/chat", headers=admin, json={"query": "如何报价"}).json()
        assert answer["status"] == "answered"
        assert answer["citations"][0]["version_id"] == ids["version_id"]
        assert answer["input_tokens"] == 20
        assert answer["output_tokens"] == 15
        usage = client.get("/api/v1/usage", headers=admin).json()
        assert usage["consumed_tokens"] == 35
        assert usage["reserved_tokens"] == 0
        assert usage["requests"][0]["id"] == answer["request_id"]
        assert usage["requests"][0]["charged_tokens"] == 35
        assert usage["requests"][0]["status"] == "answered"


class FlakyEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.fail_next = True

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("temporary embedding failure")
        return super().encode(texts)


def test_failed_replacement_can_retry_without_hiding_old_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'replace.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"),
        embedder_factory=FakeEmbedder,
        seed_demo=True,
    )
    with TestClient(app) as client:
        def headers(username: str) -> dict[str, str]:
            response = client.post("/api/v1/auth/login", data={"username": username, "password": "demo-password"})
            return {"Authorization": f"Bearer {response.json()['access_token']}"}

        admin = headers("admin")
        employee = headers("employee")
        first = client.post(
            "/api/v1/documents", headers=admin,
            files={"file": ("v1.md", b"# Policy\n\nOld rule applies.", "text/markdown")},
            data={"title": "Policy", "effective_date": "2026-09-01"},
        ).json()
        assert run_index_job(app.state.sessions, app.state.index, FakeEmbedder(), first["job_id"])
        assert client.post(
            f"/api/v1/documents/{first['document_id']}/versions/{first['version_id']}/activate",
            headers=admin,
        ).status_code == 200
        source_url = f"/api/v1/documents/{first['document_id']}/source"
        assert client.get(source_url, headers=employee, params={"version_id": first["version_id"]}).status_code == 200

        second = client.post(
            f"/api/v1/documents/{first['document_id']}/versions", headers=admin,
            files={"file": ("v2.md", b"# Policy\n\nNew rule applies.", "text/markdown")},
            data={"effective_date": "2026-10-01"},
        ).json()
        versions = client.get(f"/api/v1/documents/{first['document_id']}/versions", headers=admin).json()
        assert [(version["version_number"], version["effective_date"]) for version in versions] == [
            (2, "2026-10-01"), (1, "2026-09-01"),
        ]
        flaky = FlakyEmbedder()
        assert not run_index_job(app.state.sessions, app.state.index, flaky, second["job_id"])
        assert client.post(
            f"/api/v1/documents/{first['document_id']}/versions/{second['version_id']}/activate",
            headers=admin,
        ).status_code == 409
        assert client.post(f"/api/v1/jobs/{second['job_id']}/retry", headers=employee).status_code == 403
        old_hits = client.post("/api/v1/search", headers=employee, json={"query": "rule"}).json()
        assert old_hits and all(hit["version_id"] == first["version_id"] for hit in old_hits)

        retry = client.post(f"/api/v1/jobs/{second['job_id']}/retry", headers=admin)
        assert retry.status_code == 200
        assert retry.json()["status"] == "PENDING"
        assert run_index_job(app.state.sessions, app.state.index, flaky, second["job_id"])
        assert client.post(
            f"/api/v1/documents/{first['document_id']}/versions/{second['version_id']}/activate",
            headers=admin,
        ).status_code == 200
        new_hits = client.post("/api/v1/search", headers=employee, json={"query": "rule"}).json()
        assert new_hits and all(hit["version_id"] == second["version_id"] for hit in new_hits)
        assert client.get(source_url, headers=employee, params={"version_id": first["version_id"]}).status_code == 404
        current_source = client.get(source_url, headers=employee, params={"version_id": second["version_id"]})
        assert current_source.status_code == 200
        assert b"New rule applies" in current_source.content
        assert client.get(source_url, headers=employee, params={"version_id": "not-a-version"}).status_code == 404
        with app.state.sessions() as session:
            assert session.get(Document, first["document_id"]).active_version_id == second["version_id"]
            assert session.get(DocumentVersion, first["version_id"]).status == "RETIRED"
            assert session.get(IngestionJob, second["job_id"]).attempts == 2
        audit = client.get("/api/v1/audit", headers=admin)
        assert audit.status_code == 200
        assert {event["action"] for event in audit.json()} >= {
            "document.upload", "version.upload", "version.activate", "job.retry",
        }
        assert client.get("/api/v1/audit", headers=employee).status_code == 403


def test_local_demo_processes_jobs_after_http_mutations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "qdrant"))
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password")
    monkeypatch.setenv("LLM_API_KEY", "")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'local.db').as_posix()}",
        embedder_factory=FakeEmbedder,
        seed_demo=True,
    )
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", data={"username": "admin", "password": "demo-password"})
        admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
        created = client.post(
            "/api/v1/documents", headers=admin,
            files={"file": ("policy.md", b"# Local policy\n\nA verifiable rule.", "text/markdown")},
            data={"title": "Local policy"},
        )
        assert created.status_code == 202
        ids = created.json()
        assert client.get(f"/api/v1/jobs/{ids['job_id']}", headers=admin).json()["status"] == "DONE"
        assert client.post(
            f"/api/v1/documents/{ids['document_id']}/versions/{ids['version_id']}/activate", headers=admin,
        ).status_code == 200
        assert client.post("/api/v1/search", headers=admin, json={"query": "rule"}).json()
        assert client.delete(f"/api/v1/documents/{ids['document_id']}", headers=admin).status_code == 200
        assert client.post("/api/v1/search", headers=admin, json={"query": "rule"}).json() == []
        assert not (tmp_path / "uploads" / f"{ids['version_id']}.md").exists()
