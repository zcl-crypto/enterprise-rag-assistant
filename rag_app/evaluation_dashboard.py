from __future__ import annotations

import json
from pathlib import Path


RETRYABLE_STATUSES = {"quota_exceeded", "model_unavailable", "search_only"}
RETRIEVAL_MODES = (
    ("dense", "Dense"),
    ("hybrid", "Hybrid"),
    ("hybrid_rerank", "Hybrid + Reranker"),
)


def _read_report(directory: Path, name: str) -> dict | None:
    path = directory / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("summary"), dict) else None


def _issue_type(case: dict) -> str | None:
    status = case.get("status")
    category = case.get("category")
    if status in RETRYABLE_STATUSES:
        return "pending"
    if case.get("blocked_doc_exposed"):
        return "unauthorized"
    if category in {"single_document", "cross_document"}:
        if status != "answered":
            return "missed_answer"
        if not case.get("expected_docs_cited") or case.get("unknown_citation_count", 0):
            return "citation"
    if category == "no_answer" and status != "insufficient_evidence":
        return "false_answer"
    return None


def load_evaluation_dashboard(directory: Path) -> dict:
    retrieval_report = _read_report(directory, "hybrid-eval.json")
    generation_report = _read_report(directory, "generation-eval-full.json")

    retrieval = None
    if retrieval_report is not None:
        summary = retrieval_report["summary"]
        retrieval = {
            "generated_at": summary.get("generated_at"),
            "document_count": summary.get("document_count"),
            "chunk_count": summary.get("chunk_count"),
            "question_count": summary.get("question_count"),
            "embedding_model": summary.get("embedding_model"),
            "modes": [
                {"id": key, "label": label, **summary[key]}
                for key, label in RETRIEVAL_MODES if isinstance(summary.get(key), dict)
            ],
        }

    generation = None
    if generation_report is not None:
        summary = generation_report["summary"]
        cases = generation_report.get("cases") or []
        issues = [
            {
                "case_id": case.get("case_id"),
                "category": case.get("category"),
                "question": case.get("question"),
                "status": case.get("status"),
                "issue_type": issue_type,
                "expected_docs": case.get("expected_docs") or [],
            }
            for case in cases if isinstance(case, dict)
            if (issue_type := _issue_type(case)) is not None
        ]
        generation = {
            "generated_at": summary.get("generated_at"),
            "model": next((case.get("model") for case in cases if isinstance(case, dict) and case.get("model")), None),
            "selected_case_count": summary.get("selected_case_count", summary.get("case_count")),
            "completed_count": summary.get("completed_count"),
            "pending_count": summary.get("pending_count"),
            "positive_answered": summary.get("positive_answered"),
            "positive_evaluated": summary.get("positive_evaluated"),
            "no_answer_refused": summary.get("no_answer_refused"),
            "no_answer_evaluated": summary.get("no_answer_evaluated"),
            "unauthorized_exposures": summary.get("unauthorized_exposures"),
            "latency_p50_ms": summary.get("latency_p50_ms"),
            "latency_p95_ms": summary.get("latency_p95_ms"),
            "input_tokens": summary.get("input_tokens"),
            "output_tokens": summary.get("output_tokens"),
            "manual_answer_correctness": summary.get("manual_answer_correctness"),
            "manual_citation_support": summary.get("manual_citation_support"),
            "issues": issues,
        }

    return {"retrieval": retrieval, "generation": generation}
