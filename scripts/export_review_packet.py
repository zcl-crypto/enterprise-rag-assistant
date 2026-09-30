from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

from scripts.generate_corpus import MANIFEST, ROOT, load_manifest


DEFAULT_REPORT = ROOT / "reports" / "generation-eval-full.json"
DEFAULT_OUTPUT = ROOT / "reports" / "independent-review-pack.md"
POSITIVE_CATEGORIES = {"single_document", "cross_document"}
PENDING_STATUSES = {"quota_exceeded", "model_unavailable", "search_only"}


def _inline(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def select_review_rows(rows: list[dict], *, seed: int = 20260918) -> list[dict]:
    randomizer = random.Random(seed)
    answered = [row for row in rows if row["category"] in POSITIVE_CATEGORIES and row["status"] == "answered"]
    refusals = [
        row for row in rows
        if row["category"] in POSITIVE_CATEGORIES and row["status"] not in PENDING_STATUSES | {"answered"}
    ]
    no_answer = [
        row for row in rows if row["category"] == "no_answer" and row["status"] not in PENDING_STATUSES
    ]
    unauthorized = [
        row for row in rows if row["category"] == "unauthorized" and row["status"] not in PENDING_STATUSES
    ]
    if len(answered) < 20 or len(no_answer) < 5:
        raise ValueError("Report needs at least 20 answered and 5 no-answer cases")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("Report contains duplicate case IDs")
    chosen_answered = set(row["case_id"] for row in randomizer.sample(answered, 20))
    chosen_no_answer = set(row["case_id"] for row in randomizer.sample(no_answer, 5))
    chosen = chosen_answered | chosen_no_answer | {row["case_id"] for row in refusals + unauthorized}
    return [row for row in rows if row["case_id"] in chosen]


def render_packet(report: dict, manifest: list[dict], *, report_hash: str, seed: int = 20260918) -> str:
    rows = select_review_rows(report["cases"], seed=seed)
    policies = {record["id"]: record for record in manifest}
    lines = [
        "# Independent RAG Review Packet", "",
        "This is an unreviewed, fixed sample from a fictional-policy evaluation. It is not a quality certification.",
        "The reviewer must be a person who did not develop this project. Do not edit the source JSON report.",
        "Review each factual claim against the cited text and the policy source. For no-answer cases, check the full corpus manifest.",
        "Use yes, no, unclear, or N/A in each field. Record a reason for every no or unclear judgment.", "",
        f"- Report generated at: `{report['summary']['generated_at']}`",
        f"- Report SHA-256: `{report_hash}`",
        f"- Sampling seed: `{seed}`",
        f"- Selected: {len(rows)} cases (20 answered, all completed positive refusals, 5 no-answer, all unauthorized).",
        f"- Corpus manifest: `{MANIFEST.relative_to(ROOT).as_posix()}`", "",
        "## Reviewer", "",
        "- Name or identifier: [ ]",
        "- Date: [ ]",
        "- Report version confirmed: [ ]", "",
        "## Case Index", "",
        "| Case ID | Category | Model status | Question clear | Response correct | Citation supported | Access safe | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| `{row['case_id']}` | {row['category']} | {row['status']} |  |  |  |  |  |")
    lines += ["", "## Case Details", ""]
    for number, row in enumerate(rows, start=1):
        lines += [
            f"### {number}. `{row['case_id']}`", "",
            f"- Category / user: `{row['category']}` / `{row['username']}`",
            f"- Question: {_inline(row['question'])}",
            f"- Model status: `{row['status']}`",
            f"- Model answer: {_inline(row.get('answer') or '(no answer returned)')}",
            f"- Reference answer: {_inline(row.get('expected_answer') or '(not specified in the corpus)')}",
            f"- Expected policy IDs: {', '.join(row.get('expected_docs') or []) or '(none)'}",
            f"- Restricted policy ID: {row.get('blocked_doc') or '(none)'}", "",
            "Citations returned:", "",
        ]
        citations = row.get("citations") or []
        if citations:
            for citation in citations:
                slug = citation.get("slug") or "unknown"
                headings = _inline(" / ".join(citation.get("headings") or []))
                lines.append(f"- `{slug}` ({headings}): {_inline(citation['text'])}")
        else:
            lines.append("- (none)")
        lines += ["", "Reference policy excerpts:", ""]
        expected = row.get("expected_docs") or []
        if expected:
            for slug in expected:
                policy = policies.get(slug)
                if policy is None:
                    raise ValueError(f"Missing corpus policy: {slug}")
                lines.append(f"- `{slug}` {_inline(policy['title'])}")
                for heading, body in policy["sections"]:
                    lines.append(f"  - {_inline(heading)}: {_inline(body)}")
        else:
            lines.append("- No expected policy. Check the full manifest before judging evidence absent.")
        lines += [
            "", "Review notes:", "",
            "- Question and reference label clear: [ ]",
            "- Response or refusal correct: [ ]",
            "- Every factual claim supported by its citation: [ ]",
            "- Access control respected: [ ]",
            "- Evidence and correction needed: [ ]", "",
        ]
    return "\n".join(lines)


def export_packet(report_path: Path, output_path: Path, *, seed: int = 20260918) -> int:
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    content = render_packet(
        report, load_manifest(), report_hash=hashlib.sha256(report_bytes).hexdigest(), seed=seed
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return content.count("### ")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export an unreviewed human evaluation packet")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260918)
    args = parser.parse_args()
    count = export_packet(args.report, args.output, seed=args.seed)
    print(f"Exported {count} unreviewed cases to {args.output}")
