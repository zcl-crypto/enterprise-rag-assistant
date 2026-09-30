from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from scripts.evaluate_dense import EvalCase, load_cases, percentile
from scripts.generate_corpus import ROOT, load_manifest


CATEGORIES = ("single_document", "cross_document", "no_answer", "unauthorized")
RETRYABLE_STATUSES = frozenset({"quota_exceeded", "model_unavailable", "search_only"})
DEFAULT_OUTPUT = ROOT / "reports" / "generation-eval.json"


def case_id(case: EvalCase) -> str:
    value = f"{case.category}\n{case.username}\n{case.question}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:16]


def select_cases(counts: dict[str, int | None], seed: int) -> list[EvalCase]:
    grouped = {category: [] for category in CATEGORIES}
    for case in load_cases():
        grouped[case.category].append(case)
    randomizer = random.Random(seed)
    selected = []
    for category in CATEGORIES:
        group = grouped[category]
        limit = counts.get(category)
        if limit is not None and limit < 0:
            raise ValueError("Case limits must be nonnegative")
        if limit is not None and limit < len(group):
            chosen = set(randomizer.sample(range(len(group)), limit))
            group = [case for index, case in enumerate(group) if index in chosen]
        selected.extend(group)
    return selected


def result_row(
    case: EvalCase, response: dict, document_slugs: dict[str, str], *, run_base_url: str | None = None,
) -> dict:
    citations = [
        {
            "document_id": hit["document_id"],
            "slug": document_slugs.get(hit["document_id"]),
            "text": hit["text"],
            "headings": hit["headings"],
        }
        for hit in response.get("citations", [])
    ]
    cited_docs = list(dict.fromkeys(hit["slug"] for hit in citations if hit["slug"]))
    positive = case.category in {"single_document", "cross_document"}
    status = response["status"]
    return {
        "case_id": case_id(case),
        "category": case.category,
        "username": case.username,
        "question": case.question,
        "expected_answer": case.answer,
        "expected_docs": list(case.expected_docs),
        "blocked_doc": case.blocked_doc,
        "request_id": response.get("request_id"),
        "status": status,
        "answer": response.get("answer"),
        "model": response.get("model"),
        "citations": citations,
        "cited_docs": cited_docs,
        "unknown_citation_count": sum(hit["slug"] is None for hit in citations),
        "expected_docs_cited": status == "answered" and set(case.expected_docs).issubset(cited_docs) if positive else None,
        "no_answer_refused": status == "insufficient_evidence" if case.category == "no_answer" else None,
        "blocked_doc_exposed": case.blocked_doc in cited_docs if case.blocked_doc else None,
        "retrieval_ms": response.get("retrieval_ms"),
        "generation_ms": response.get("generation_ms"),
        "total_ms": response.get("total_ms"),
        "input_tokens": response.get("input_tokens"),
        "output_tokens": response.get("output_tokens"),
        "run_base_url": run_base_url,
        "manual_review": {"answer_correct": None, "citation_supported": None, "notes": ""},
    }


def score_rows(rows: list[dict]) -> dict:
    positive = [row for row in rows if row["category"] in {"single_document", "cross_document"}]
    no_answer = [row for row in rows if row["category"] == "no_answer"]
    unauthorized = [row for row in rows if row["category"] == "unauthorized"]
    evaluated_positive = [row for row in positive if row["status"] not in RETRYABLE_STATUSES]
    evaluated_no_answer = [row for row in no_answer if row["status"] not in RETRYABLE_STATUSES]
    latencies = [
        row["total_ms"] for row in rows
        if row["status"] not in RETRYABLE_STATUSES and row.get("total_ms") is not None
    ]
    usage = [row for row in rows if row.get("input_tokens") is not None and row.get("output_tokens") is not None]
    return {
        "case_count": len(rows),
        "completed_count": sum(row["status"] not in RETRYABLE_STATUSES for row in rows),
        "category_counts": dict(Counter(row["category"] for row in rows)),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "positive_answered": sum(row["status"] == "answered" for row in positive),
        "positive_total": len(positive),
        "positive_evaluated": len(evaluated_positive),
        "positive_expected_docs_cited": sum(row["expected_docs_cited"] is True for row in positive),
        "no_answer_refused": sum(row["no_answer_refused"] is True for row in no_answer),
        "no_answer_total": len(no_answer),
        "no_answer_evaluated": len(evaluated_no_answer),
        "unauthorized_exposures": sum(row["blocked_doc_exposed"] is True for row in unauthorized),
        "unknown_citations": sum(row.get("unknown_citation_count", 0) for row in rows),
        "reported_usage_cases": len(usage),
        "input_tokens": sum(row["input_tokens"] for row in usage),
        "output_tokens": sum(row["output_tokens"] for row in usage),
        "latency_p50_ms": round(percentile(latencies, 0.5), 2) if latencies else None,
        "latency_p95_ms": round(percentile(latencies, 0.95), 2) if latencies else None,
        "manual_answer_correctness": None,
        "manual_citation_support": None,
    }


def write_report(
    output: Path, rows: list[dict], *, seed: int, base_url: str, selected_count: int | None = None,
) -> dict:
    selected_count = len(rows) if selected_count is None else selected_count
    if selected_count < len(rows):
        raise ValueError("Selected case count cannot be smaller than recorded rows")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "run_base_urls": sorted({row.get("run_base_url") or base_url for row in rows}),
        "sampling_seed": seed,
        "selected_case_count": selected_count,
        **score_rows(rows),
    }
    summary["pending_count"] = selected_count - summary["completed_count"]
    payload = {"summary": summary, "cases": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    lines = [
        "# 真实模型问答抽样评测", "",
        f"- 时间：{summary['generated_at']}",
        f"- API：{'、'.join(f'`{url}`' for url in summary['run_base_urls'])}；"
        f"采样种子：`{seed}`；已记录 {len(rows)}/{selected_count} 题，"
        f"获得非暂时性结果 {summary['completed_count']}/{selected_count} 题，待重试 {summary['pending_count']} 题。",
        "- 数据：虚构制度与尚未独立复核的题目；本报告不能外推到真实企业。",
        "- 判定：自动指标只检查 API 状态、预期文档是否被引用、无答案状态和越权暴露。",
        "- **答案要点正确率和引用语义支持率尚未人工复核，不能用自动指标替代。**", "",
        "| 指标 | 结果 |", "| --- | ---: |",
        f"| 待重试题目 | {summary['pending_count']} |",
        f"| 有答案题返回回答（已评测） | {summary['positive_answered']}/{summary['positive_evaluated']} |",
        f"| 有答案题引用全部预期文档（已评测） | "
        f"{summary['positive_expected_docs_cited']}/{summary['positive_evaluated']} |",
        f"| 无答案题拒答（已评测） | {summary['no_answer_refused']}/{summary['no_answer_evaluated']} |",
        f"| 越权文档引用次数 | {summary['unauthorized_exposures']} |",
        f"| 未知来源引用次数 | {summary['unknown_citations']} |",
        f"| 返回 Token 用量的请求 | {summary['reported_usage_cases']}/{len(rows)} |",
        f"| 输入 / 输出 Token | {summary['input_tokens']} / {summary['output_tokens']} |",
        f"| 端到端 p50 / p95 | {summary['latency_p50_ms']} / {summary['latency_p95_ms']} ms |", "",
        "`model_unavailable`、`quota_exceeded` 等状态不计为成功拒答；逐题答案、预期要点与引用正文见 JSON。",
        "端到端延迟统计排除待重试请求。",
        "Token 用量是接口报告值，不是供应商账单或费用保证。", "",
    ]
    failures = [row for row in rows if (
        row["category"] in {"single_document", "cross_document"} and not row["expected_docs_cited"]
        or row["category"] == "no_answer" and not row["no_answer_refused"]
        or row["blocked_doc_exposed"]
        or row["status"] in RETRYABLE_STATUSES
    )]
    if failures:
        lines += ["## 待复核题目", "", "| 类别 | 问题 | 状态 | 请求 ID |", "| --- | --- | --- | --- |"]
        for row in failures:
            lines.append(
                f"| {row['category']} | {row['question'].replace('|', '&#124;')} | "
                f"{row['status']} | `{row['request_id'] or '-'}` |"
            )
        lines.append("")
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def evaluate(
    base_url: str, output: Path, counts: dict[str, int | None], *, seed: int, delay: float,
    allow_base_url_change: bool = False,
) -> dict:
    if delay < 0:
        raise ValueError("Delay must be nonnegative")
    load_dotenv(ROOT / ".env", override=False)
    password = os.getenv("DEMO_PASSWORD", "demo12345")
    cases = select_cases(counts, seed)
    manifest = load_manifest()
    titles = {record["title"]: record["id"] for record in manifest}
    if len(titles) != len(manifest):
        raise ValueError("Corpus titles must be unique for API evaluation")
    previous = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else None
    existing = previous["cases"] if previous else []
    previous_base_url = previous["summary"]["base_url"] if previous else base_url
    if previous:
        for row in existing:
            if not row.get("run_base_url"):
                row["run_base_url"] = previous_base_url
    rows_by_id = {row["case_id"]: row for row in existing}
    requested_ids = {case_id(case) for case in cases}
    if previous and (
        previous["summary"]["sampling_seed"] != seed
        or previous_base_url != base_url and not allow_base_url_change
        or not set(rows_by_id).issubset(requested_ids)
        or len(existing) != len(rows_by_id)
    ):
        raise ValueError("Existing report uses a different case selection; choose another output path")

    with httpx.Client(base_url=base_url, timeout=120, trust_env=False) as client:
        tokens = {}

        def headers(username: str) -> dict[str, str]:
            if username not in tokens:
                response = client.post("/api/v1/auth/login", data={"username": username, "password": password})
                response.raise_for_status()
                tokens[username] = response.json()["access_token"]
            return {"Authorization": f"Bearer {tokens[username]}"}

        documents = client.get("/api/v1/documents", headers=headers("admin"))
        documents.raise_for_status()
        document_slugs = {doc["id"]: titles[doc["title"]] for doc in documents.json() if doc["title"] in titles}
        missing = set(titles.values()) - set(document_slugs.values())
        if missing:
            raise RuntimeError(f"Corpus not fully published in API: {sorted(missing)}")
        for index, case in enumerate(cases, start=1):
            key = case_id(case)
            if key in rows_by_id and rows_by_id[key]["status"] not in RETRYABLE_STATUSES:
                continue
            response = client.post(
                "/api/v1/chat", headers=headers(case.username), json={"query": case.question, "limit": 6}
            )
            response.raise_for_status()
            rows_by_id[key] = result_row(case, response.json(), document_slugs, run_base_url=base_url)
            rows = [rows_by_id[case_id(selected)] for selected in cases if case_id(selected) in rows_by_id]
            write_report(output, rows, seed=seed, base_url=base_url, selected_count=len(cases))
            print(f"{index}/{len(cases)} {case.category}: {rows_by_id[key]['status']}", flush=True)
            if rows_by_id[key]["status"] in {"quota_exceeded", "search_only"}:
                break
            if delay and index < len(cases):
                time.sleep(delay)
    rows = [rows_by_id[case_id(case)] for case in cases if case_id(case) in rows_by_id]
    return write_report(output, rows, seed=seed, base_url=base_url, selected_count=len(cases))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate live RAG answers against fictional policy questions")
    parser.add_argument("--base-url", default="http://127.0.0.1:8766")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--single", type=int, default=8)
    parser.add_argument("--cross", type=int, default=3)
    parser.add_argument("--no-answer", type=int, default=8)
    parser.add_argument("--unauthorized", type=int, default=5)
    parser.add_argument("--full", action="store_true", help="Evaluate all 110 cases")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between model calls")
    parser.add_argument(
        "--allow-base-url-change", action="store_true",
        help="Resume from another API endpoint and retain per-case endpoint provenance",
    )
    args = parser.parse_args()
    counts = {
        "single_document": args.single, "cross_document": args.cross,
        "no_answer": args.no_answer, "unauthorized": args.unauthorized,
    }
    if args.full:
        counts = {category: None for category in CATEGORIES}
    print(json.dumps(evaluate(
        args.base_url, args.output, counts, seed=args.seed, delay=args.delay,
        allow_base_url_change=args.allow_base_url_change,
    ), ensure_ascii=False, indent=2))
