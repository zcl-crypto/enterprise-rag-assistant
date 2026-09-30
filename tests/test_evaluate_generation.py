import json
from collections import Counter
from pathlib import Path

import pytest

import scripts.evaluate_generation as generation_eval
from scripts.evaluate_dense import EvalCase
from scripts.evaluate_generation import result_row, score_rows, select_cases, write_report


def test_stratified_selection_is_deterministic() -> None:
    counts = {"single_document": 3, "cross_document": 2, "no_answer": 4, "unauthorized": 2}
    first = select_cases(counts, seed=17)
    second = select_cases(counts, seed=17)
    assert first == second
    assert Counter(case.category for case in first) == counts


def test_generation_metrics_do_not_treat_model_errors_as_refusals(tmp_path: Path) -> None:
    positive = EvalCase("single_document", "What is the rule?", ("policy",), "Five days")
    no_answer = EvalCase("no_answer", "Unknown question", (), "Not specified")
    unavailable = EvalCase("no_answer", "Another unknown", (), "Not specified")
    unauthorized = EvalCase("unauthorized", "Restricted rule", (), username="employee", blocked_doc="secret")
    rows = [
        result_row(positive, {
            "status": "answered", "answer": "Five days [1]", "citations": [
                {"document_id": "doc", "text": "Five days", "headings": []}
            ], "input_tokens": 100, "output_tokens": 10, "total_ms": 25,
        }, {"doc": "policy", "blocked": "secret"}),
        result_row(no_answer, {"status": "insufficient_evidence", "citations": [], "total_ms": 30}, {}),
        result_row(unavailable, {"status": "model_unavailable", "citations": [], "total_ms": 40}, {}),
        result_row(unauthorized, {
            "status": "answered", "answer": "Leaked [1]", "citations": [
                {"document_id": "blocked", "text": "Secret", "headings": []}
            ], "total_ms": 50,
        }, {"blocked": "secret"}),
    ]
    summary = score_rows(rows)
    assert summary["positive_answered"] == 1
    assert summary["positive_evaluated"] == 1
    assert summary["positive_expected_docs_cited"] == 1
    assert summary["no_answer_refused"] == 1
    assert summary["no_answer_total"] == 2
    assert summary["no_answer_evaluated"] == 1
    assert summary["unauthorized_exposures"] == 1
    assert summary["reported_usage_cases"] == 1
    assert summary["input_tokens"] == 100
    assert summary["completed_count"] == 3
    assert summary["latency_p50_ms"] == 30
    assert summary["manual_answer_correctness"] is None

    output = tmp_path / "generation-eval.json"
    write_report(output, rows, seed=17, base_url="http://127.0.0.1:8766", selected_count=5)
    recorded = json.loads(output.read_text(encoding="utf-8"))["summary"]
    assert recorded["no_answer_refused"] == 1
    assert recorded["pending_count"] == 2
    assert "答案要点正确率" in output.with_suffix(".md").read_text(encoding="utf-8")


def test_evaluation_resumes_retryable_results_and_stops_at_quota(tmp_path: Path, monkeypatch) -> None:
    first = EvalCase("single_document", "First?", ("policy",), "First")
    second = EvalCase("no_answer", "Unknown?", (), "Not specified")
    third = EvalCase("single_document", "Third?", ("policy",), "Third")
    cases = [first, second, third]
    output = tmp_path / "generation-eval.json"
    base_url = "http://127.0.0.1:8766"
    first_answer = {
        "status": "answered", "answer": "First [1]", "citations": [
            {"document_id": "doc", "text": "First", "headings": []}
        ],
    }
    initial = [
        result_row(first, first_answer, {"doc": "policy"}),
        result_row(second, {"status": "quota_exceeded", "citations": []}, {"doc": "policy"}),
    ]
    write_report(output, initial, seed=17, base_url=base_url, selected_count=3)

    responses = {
        "Unknown?": {"status": "insufficient_evidence", "citations": []},
        "Third?": {"status": "quota_exceeded", "citations": []},
    }
    requested: list[str] = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return self.payload

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def get(self, path: str, **kwargs):
            assert path == "/api/v1/documents"
            return FakeResponse([{"id": "doc", "title": "Policy"}])

        def post(self, path: str, **kwargs):
            if path == "/api/v1/auth/login":
                return FakeResponse({"access_token": "test-token"})
            assert path == "/api/v1/chat"
            question = kwargs["json"]["query"]
            requested.append(question)
            return FakeResponse(responses[question])

    monkeypatch.setattr(generation_eval, "select_cases", lambda counts, seed: cases)
    monkeypatch.setattr(generation_eval, "load_manifest", lambda: [{"title": "Policy", "id": "policy"}])
    monkeypatch.setattr(generation_eval, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(generation_eval.httpx, "Client", FakeClient)

    summary = generation_eval.evaluate(base_url, output, {}, seed=17, delay=0)
    assert requested == ["Unknown?", "Third?"]
    assert summary["completed_count"] == 2
    assert summary["pending_count"] == 1

    requested.clear()
    responses["Third?"] = {
        "status": "answered", "answer": "Third [1]", "citations": [
            {"document_id": "doc", "text": "Third", "headings": []}
        ],
    }
    summary = generation_eval.evaluate(base_url, output, {}, seed=17, delay=0)
    assert requested == ["Third?"]
    assert summary["completed_count"] == 3
    assert summary["pending_count"] == 0


def test_evaluation_can_resume_from_new_endpoint_with_case_provenance(tmp_path: Path, monkeypatch) -> None:
    answered = EvalCase("single_document", "Answered?", ("policy",), "Yes")
    pending = EvalCase("single_document", "Pending?", ("policy",), "Now answered")
    cases = [answered, pending]
    output = tmp_path / "generation-eval.json"
    old_url = "http://127.0.0.1:8766"
    new_url = "http://127.0.0.1:8765"
    write_report(output, [
        result_row(answered, {
            "status": "answered", "answer": "Yes [1]",
            "citations": [{"document_id": "doc", "text": "Yes", "headings": []}],
        }, {"doc": "policy"}),
        result_row(pending, {"status": "quota_exceeded", "citations": []}, {"doc": "policy"}),
    ], seed=17, base_url=old_url)

    class FakeResponse:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return self.payload

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def get(self, path: str, **kwargs):
            return FakeResponse([{"id": "doc", "title": "Policy"}])

        def post(self, path: str, **kwargs):
            if path == "/api/v1/auth/login":
                return FakeResponse({"access_token": "test-token"})
            return FakeResponse({
                "status": "answered", "answer": "Now answered [1]",
                "citations": [{"document_id": "doc", "text": "Now answered", "headings": []}],
            })

    monkeypatch.setattr(generation_eval, "select_cases", lambda counts, seed: cases)
    monkeypatch.setattr(generation_eval, "load_manifest", lambda: [{"title": "Policy", "id": "policy"}])
    monkeypatch.setattr(generation_eval, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(generation_eval.httpx, "Client", FakeClient)

    with pytest.raises(ValueError, match="different case selection"):
        generation_eval.evaluate(new_url, output, {}, seed=17, delay=0)
    summary = generation_eval.evaluate(
        new_url, output, {}, seed=17, delay=0, allow_base_url_change=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert summary["run_base_urls"] == [new_url, old_url]
    assert [row["run_base_url"] for row in payload["cases"]] == [old_url, new_url]
