from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from rag_app.generation import MAX_OUTPUT_TOKENS, REFUSAL_TEXT, build_messages, cited_sources
from rag_app.vector_index import SearchHit
from scripts.generate_corpus import ROOT, load_manifest


def as_hit(payload: dict) -> SearchHit:
    return SearchHit(
        chunk_id=payload["chunk_id"],
        document_id=payload["document_id"],
        version_id=payload["version_id"],
        text=payload["text"],
        headings=tuple(payload["headings"]),
        page_number=payload.get("page_number"),
        score=payload["score"],
    )


def score(rows: list[dict]) -> dict:
    positives = [row for row in rows if row["category"] in {"single_document", "cross_document"}]
    negatives = [row for row in rows if row["category"] == "no_answer"]
    return {
        "case_count": len(rows),
        "positive_count": len(positives),
        "positive_answered": sum(row["status"] == "answered" for row in positives),
        "positive_expected_docs_cited": sum(row["expected_docs_cited"] is True for row in positives),
        "no_answer_count": len(negatives),
        "no_answer_refused": sum(row["status"] == "insufficient_evidence" for row in negatives),
        "invalid_answer_count": sum(row["status"] == "invalid_answer" for row in rows),
        "input_tokens": sum(row["input_tokens"] or 0 for row in rows),
        "output_tokens": sum(row["output_tokens"] or 0 for row in rows),
    }


def write_report(output: Path, payload: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = payload["summary"]
    lines = [
        "# 拒答复核提示词 A/B", "",
        f"- 时间：{payload['generated_at']}",
        f"- 模型：`{payload['model']}`；API：`{payload['base_url']}`。",
        "- 范围：当前完整评测中的 7 道有答案拒答题，以及全部 25 道无答案题。",
        "- 本实验直接测试候选复核提示词，不改变线上问答逻辑；结果仍需人工检查。", "",
        "| 指标 | 结果 |", "| --- | ---: |",
        f"| 正例回答 | {summary['positive_answered']}/{summary['positive_count']} |",
        f"| 正例引用全部预期文档 | {summary['positive_expected_docs_cited']}/{summary['positive_count']} |",
        f"| 无答案题保持拒答 | {summary['no_answer_refused']}/{summary['no_answer_count']} |",
        f"| 引用格式无效答案 | {summary['invalid_answer_count']} |",
        f"| 输入 / 输出 Token | {summary['input_tokens']} / {summary['output_tokens']} |", "",
        "## 逐题结果", "", "| 类别 | 问题 | 状态 | 预期文档已引用 |", "| --- | --- | --- | ---: |",
    ]
    for row in payload["cases"]:
        lines.append(
            f"| {row['category']} | {row['question'].replace('|', '&#124;')} | "
            f"{row['status']} | {row['expected_docs_cited'] if row['expected_docs_cited'] is not None else '-'} |"
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate(base_url: str, source: Path, output: Path, delay: float) -> dict:
    if delay < 0:
        raise ValueError("Delay must be nonnegative")
    load_dotenv(ROOT / ".env", override=False)
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not configured")
    model = os.getenv("LLM_MODEL", "glm-4.7-flash")
    report = json.loads(source.read_text(encoding="utf-8"))
    selected = [
        row for row in report["cases"]
        if row["category"] == "no_answer"
        or row["category"] in {"single_document", "cross_document"} and row["status"] == "insufficient_evidence"
    ]
    titles = {record["title"]: record["id"] for record in load_manifest()}
    llm = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
        timeout=30,
        max_retries=1,
    )
    rows = []
    with httpx.Client(base_url=base_url, timeout=120, trust_env=False) as api:
        tokens: dict[str, str] = {}

        def headers(username: str) -> dict[str, str]:
            if username not in tokens:
                response = api.post(
                    "/api/v1/auth/login",
                    data={"username": username, "password": os.getenv("DEMO_PASSWORD", "demo12345")},
                )
                response.raise_for_status()
                tokens[username] = response.json()["access_token"]
            return {"Authorization": f"Bearer {tokens[username]}"}

        documents = api.get("/api/v1/documents", headers=headers("admin"))
        documents.raise_for_status()
        slugs = {doc["id"]: titles[doc["title"]] for doc in documents.json() if doc["title"] in titles}
        for index, original in enumerate(selected, start=1):
            response = api.post(
                "/api/v1/search", headers=headers(original["username"]),
                json={"query": original["question"], "limit": 6},
            )
            response.raise_for_status()
            sources = [as_hit(item) for item in response.json()]
            started = time.perf_counter()
            completion = llm.chat.completions.create(
                model=model,
                messages=build_messages(original["question"], sources, refusal_retry=True),
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            answer = (completion.choices[0].message.content or "").strip()
            cited = []
            status = "insufficient_evidence" if answer == REFUSAL_TEXT else "answered"
            if status == "answered":
                try:
                    cited = cited_sources(answer, sources)
                    if not cited:
                        status = "invalid_answer"
                except ValueError:
                    status = "invalid_answer"
            cited_docs = list(dict.fromkeys(slugs.get(hit.document_id) for hit in cited if slugs.get(hit.document_id)))
            positive = original["category"] in {"single_document", "cross_document"}
            usage = completion.usage
            rows.append({
                "case_id": original["case_id"],
                "category": original["category"],
                "username": original["username"],
                "question": original["question"],
                "expected_answer": original["expected_answer"],
                "expected_docs": original["expected_docs"],
                "status": status,
                "answer": answer,
                "cited_docs": cited_docs,
                "expected_docs_cited": set(original["expected_docs"]).issubset(cited_docs) if positive else None,
                "sources": [
                    {"slug": slugs.get(hit.document_id), "text": hit.text, "headings": list(hit.headings)}
                    for hit in sources
                ],
                "latency_ms": elapsed_ms,
                "input_tokens": usage.prompt_tokens if usage else None,
                "output_tokens": usage.completion_tokens if usage else None,
            })
            print(f"{index}/{len(selected)} {original['category']}: {status}", flush=True)
            if delay and index < len(selected):
                time.sleep(delay)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "model": model,
        "source_report": str(source),
        "summary": score(rows),
        "cases": rows,
    }
    write_report(output, payload)
    return payload["summary"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A/B test a refusal recheck prompt")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--source", type=Path, default=ROOT / "reports" / "generation-eval-full.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "refusal-retry-experiment.json")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.base_url, args.source, args.output, args.delay), ensure_ascii=False, indent=2))
