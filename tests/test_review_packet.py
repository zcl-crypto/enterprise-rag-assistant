from collections import Counter

import pytest

from scripts.export_review_packet import render_packet, select_review_rows


def _row(case_id: str, category: str, status: str) -> dict:
    return {
        "case_id": case_id,
        "category": category,
        "username": "employee",
        "question": f"Question {case_id}?",
        "status": status,
        "answer": "Answer [1]" if status == "answered" else "",
        "expected_answer": "Answer",
        "expected_docs": ["policy"] if category == "single_document" else [],
        "blocked_doc": "secret" if category == "unauthorized" else None,
        "citations": [{"slug": "policy", "headings": ["Rule"], "text": "Source text"}] if status == "answered" else [],
    }


def test_review_selection_is_fixed_and_excludes_pending() -> None:
    rows = (
        [_row(f"a{i}", "single_document", "answered") for i in range(25)]
        + [_row("r1", "single_document", "insufficient_evidence")]
        + [_row(f"n{i}", "no_answer", "insufficient_evidence") for i in range(7)]
        + [_row("u1", "unauthorized", "insufficient_evidence")]
        + [_row("p1", "single_document", "quota_exceeded")]
    )
    selected = select_review_rows(rows)
    assert selected == select_review_rows(rows)
    assert len(selected) == 27
    assert "p1" not in {row["case_id"] for row in selected}
    assert Counter(row["category"] for row in selected) == {
        "single_document": 21, "no_answer": 5, "unauthorized": 1,
    }
    with pytest.raises(ValueError, match="duplicate"):
        select_review_rows(rows + [rows[0]])


def test_review_packet_shows_evidence_but_no_prefilled_judgment() -> None:
    rows = [_row(f"a{i}", "single_document", "answered") for i in range(20)]
    rows += [_row(f"n{i}", "no_answer", "insufficient_evidence") for i in range(5)]
    report = {"summary": {"generated_at": "2026-09-18T00:00:00Z"}, "cases": rows}
    manifest = [{"id": "policy", "title": "Policy title", "sections": [["Rule", "Source text"]]}]
    content = render_packet(report, manifest, report_hash="a" * 64)
    assert "Source text" in content
    assert "a" * 64 in content
    assert "Reviewer" in content
    assert "Response or refusal correct: [ ]\n" in content
    assert "Access control respected: [ ]\n" in content
