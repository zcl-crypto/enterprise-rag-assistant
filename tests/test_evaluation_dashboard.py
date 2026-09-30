import json
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from rag_app.api import create_app
from rag_app.evaluation_dashboard import load_evaluation_dashboard


def write_reports(directory: Path) -> None:
    retrieval = {
        "summary": {
            "generated_at": "2026-09-18T00:00:00+00:00",
            "document_count": 2, "chunk_count": 4, "question_count": 5,
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "dense": {"recall_at_5": 0.8, "mrr": 0.7, "latency_p50_ms": 20},
            "hybrid": {"recall_at_5": 1.0, "mrr": 0.9, "latency_p50_ms": 30},
        },
        "cases": [],
    }
    generation = {
        "summary": {
            "generated_at": "2026-09-18T01:00:00+00:00",
            "selected_case_count": 5, "completed_count": 4, "pending_count": 1,
            "positive_answered": 1, "positive_evaluated": 2,
            "no_answer_refused": 0, "no_answer_evaluated": 1,
            "unauthorized_exposures": 1,
        },
        "cases": [
            {"case_id": "a", "category": "single_document", "question": "Known?", "status": "answered",
             "expected_docs_cited": True, "model": "test-model"},
            {"case_id": "b", "category": "single_document", "question": "Missed?",
             "status": "insufficient_evidence", "expected_docs_cited": False},
            {"case_id": "c", "category": "no_answer", "question": "Unknown?", "status": "answered"},
            {"case_id": "d", "category": "unauthorized", "question": "Secret?", "status": "answered",
             "blocked_doc_exposed": True},
            {"case_id": "e", "category": "single_document", "question": "Pending?", "status": "quota_exceeded"},
        ],
    }
    (directory / "hybrid-eval.json").write_text(json.dumps(retrieval), encoding="utf-8")
    (directory / "generation-eval-full.json").write_text(json.dumps(generation), encoding="utf-8")


def test_dashboard_reports_missing_and_issue_types(tmp_path: Path) -> None:
    assert load_evaluation_dashboard(tmp_path) == {"retrieval": None, "generation": None}
    write_reports(tmp_path)

    dashboard = load_evaluation_dashboard(tmp_path)
    assert [mode["id"] for mode in dashboard["retrieval"]["modes"]] == ["dense", "hybrid"]
    assert dashboard["generation"]["model"] == "test-model"
    assert [issue["issue_type"] for issue in dashboard["generation"]["issues"]] == [
        "missed_answer", "false_answer", "unauthorized", "pending",
    ]


def test_evaluation_api_is_admin_only(tmp_path: Path, monkeypatch) -> None:
    write_reports(tmp_path)
    monkeypatch.setenv("EVALUATION_REPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'evaluation.db').as_posix()}",
        qdrant_client=QdrantClient(":memory:"),
        seed_demo=True,
    )
    with TestClient(app) as client:
        def headers(username: str) -> dict[str, str]:
            login = client.post("/api/v1/auth/login", data={"username": username, "password": "demo-password"})
            assert login.status_code == 200
            return {"Authorization": f"Bearer {login.json()['access_token']}"}

        assert client.get("/api/v1/evaluations").status_code == 401
        assert client.get("/api/v1/evaluations", headers=headers("employee")).status_code == 403
        response = client.get("/api/v1/evaluations", headers=headers("admin"))
        assert response.status_code == 200
        assert response.json()["generation"]["pending_count"] == 1
        assert len(response.json()["generation"]["issues"]) == 4
