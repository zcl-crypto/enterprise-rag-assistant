from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient

from rag_app.documents import embedding_text, parse_file
from rag_app.vector_index import BgeEmbedder, VectorIndex, chunks_for_embedder
from scripts.generate_corpus import DEFAULT_OUTPUT, ROOT, generate_corpus, load_manifest


EXTRAS = ROOT / "data" / "corpus" / "eval_extras.json"


@dataclass(frozen=True)
class EvalCase:
    category: str
    question: str
    expected_docs: tuple[str, ...]
    answer: str | None = None
    username: str = "admin"
    blocked_doc: str | None = None


def load_cases() -> list[EvalCase]:
    cases = [
        EvalCase("single_document", question, (record["id"],), answer)
        for record in load_manifest()
        for question, answer in record["qa"]
    ]
    extras = json.loads(EXTRAS.read_text(encoding="utf-8"))
    cases += [
        EvalCase("cross_document", entry["question"], tuple(entry["expected_docs"]), entry["answer"])
        for entry in extras["cross_document"]
    ]
    cases += [
        EvalCase("no_answer", entry["question"], (), entry["answer"])
        for entry in extras["no_answer"]
    ]
    cases += [
        EvalCase("unauthorized", entry["question"], (), username=entry["username"], blocked_doc=entry["blocked_doc"])
        for entry in extras["unauthorized"]
    ]
    ids = {record["id"] for record in load_manifest()}
    for case in cases:
        if not set(case.expected_docs).issubset(ids) or (case.blocked_doc and case.blocked_doc not in ids):
            raise ValueError(f"Unknown expected document in question: {case.question}")
    return cases


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def evaluate(output: Path) -> dict:
    model_path = ROOT / ".models" / "bge-small-zh-v1.5"
    if model_path.is_dir():
        os.environ.setdefault("EMBEDDING_MODEL_PATH", str(model_path))
    embedder = BgeEmbedder()
    index = VectorIndex(QdrantClient(":memory:"), collection="fictional_policy_eval")
    index.ensure_collection(embedder.dimension)
    records = load_manifest()
    cases = load_cases()
    generated_paths = {path.stem: path for path in generate_corpus(DEFAULT_OUTPUT)}
    version_to_slug: dict[str, str] = {}
    document_to_slug: dict[str, str] = {}
    record_by_slug = {record["id"]: record for record in records}

    ingestion_started = time.perf_counter()
    chunk_count = 0
    for record in records:
        slug = record["id"]
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fictional-document:{slug}"))
        version_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fictional-version:{slug}"))
        parsed = parse_file(generated_paths[slug])
        chunks = chunks_for_embedder(parsed.blocks, embedder)
        vectors = embedder.encode([embedding_text(chunk) for chunk in chunks])
        index.upsert_chunks(document_id, version_id, chunks, vectors)
        version_to_slug[version_id] = slug
        document_to_slug[document_id] = slug
        chunk_count += len(chunks)
    ingestion_seconds = time.perf_counter() - ingestion_started

    results: list[dict] = []
    latencies: list[float] = []
    for case in cases:
        allowed_versions = [
            version_id for version_id, slug in version_to_slug.items()
            if case.username == "admin" or record_by_slug[slug]["department"] is None
        ]
        started = time.perf_counter()
        hits = index.search(embedder.encode_query(case.question), allowed_versions, limit=5)
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)
        found = [document_to_slug[hit.document_id] for hit in hits]
        expected = set(case.expected_docs)
        recall = len(expected.intersection(found)) / len(expected) if expected else None
        reciprocal_rank = next((1 / rank for rank, slug in enumerate(found, start=1) if slug in expected), 0.0) if expected else None
        results.append({
            **asdict(case),
            "expected_docs": list(case.expected_docs),
            "retrieved_docs": found,
            "retrieved_scores": [round(hit.score, 4) for hit in hits],
            "recall_at_5": recall,
            "reciprocal_rank": reciprocal_rank,
            "blocked_doc_exposed": case.blocked_doc in found if case.blocked_doc else None,
            "latency_ms": round(latency_ms, 2),
        })

    positives = [result for result in results if result["category"] in {"single_document", "cross_document"}]
    unauthorized = [result for result in results if result["category"] == "unauthorized"]
    no_answer = [result for result in results if result["category"] == "no_answer"]
    positive_top_scores = [result["retrieved_scores"][0] for result in positives]
    no_answer_top_scores = [result["retrieved_scores"][0] for result in no_answer]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieval_mode": "dense",
        "embedding_model": embedder.model_name,
        "document_count": len(records),
        "chunk_count": chunk_count,
        "question_count": len(cases),
        "category_counts": {name: sum(case.category == name for case in cases) for name in (
            "single_document", "cross_document", "no_answer", "unauthorized"
        )},
        "recall_at_5": round(statistics.mean(result["recall_at_5"] for result in positives), 4),
        "full_support_at_5": round(statistics.mean(result["recall_at_5"] == 1 for result in positives), 4),
        "mrr": round(statistics.mean(result["reciprocal_rank"] for result in positives), 4),
        "unauthorized_exposures": sum(result["blocked_doc_exposed"] for result in unauthorized),
        "no_answer_queries_with_hits": sum(bool(result["retrieved_docs"]) for result in no_answer),
        "positive_top1_min_score": min(positive_top_scores),
        "no_answer_top1_max_score": max(no_answer_top_scores),
        "latency_p50_ms": round(percentile(latencies, 0.5), 2),
        "latency_p95_ms": round(percentile(latencies, 0.95), 2),
        "ingestion_seconds": round(ingestion_seconds, 2),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dense-eval.json").write_text(
        json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Dense 检索基线评测", "",
        f"- 时间：{summary['generated_at']}",
        f"- 模型：`{summary['embedding_model']}`；文档 {len(records)} 份，chunk {chunk_count} 个，问题 {len(cases)} 道。",
        "- 环境：本地 CPU Embedding + Qdrant local；未调用生成 API，token 费用为 0。", "",
        "| 指标 | 实测 |", "| --- | ---: |",
        f"| Recall@5（{len(positives)} 道有答案问题） | {summary['recall_at_5']:.3f} |",
        f"| 全部支持文档命中@5 | {summary['full_support_at_5']:.3f} |",
        f"| MRR（首个相关文档） | {summary['mrr']:.3f} |",
        f"| 越权文档暴露数（{len(unauthorized)} 道） | {summary['unauthorized_exposures']} |",
        f"| 无答案问题仍返回片段（{len(no_answer)} 道） | {summary['no_answer_queries_with_hits']} |",
        f"| 有答案 Top-1 最低分 / 无答案 Top-1 最高分 | {summary['positive_top1_min_score']:.3f} / {summary['no_answer_top1_max_score']:.3f} |",
        f"| 查询延迟 p50 / p95 | {summary['latency_p50_ms']:.0f} / {summary['latency_p95_ms']:.0f} ms |",
        f"| 建索引时间 | {summary['ingestion_seconds']:.1f} s |", "",
        "Recall@5 对跨文档问题按所需文档命中比例计算；MRR 取首个相关文档的排名倒数。",
        "无答案问题仅检查 dense 检索是否返回候选，**不代表答案拒答率**。两个分数区间重叠，不能从本数据集直接选出可靠的固定拒答阈值。答案正确率、引用支持率和生成费用未测量。",
        "BM25 与 Reranker 对照另见 `hybrid-eval.md`；本结果仅是虚构语料基线，不代表真实企业数据表现。",
        "详细逐题结果见 `dense-eval.json`。", "",
    ]
    (output / "dense-eval.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate dense retrieval on fictional policies")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.output), ensure_ascii=False, indent=2))
