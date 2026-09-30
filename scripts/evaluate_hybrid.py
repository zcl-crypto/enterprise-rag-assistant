from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient

from rag_app.documents import embedding_text, parse_file
from rag_app.lexical_index import ChineseBm25, LexicalIndex
from rag_app.reranker import BgeReranker
from rag_app.retrieval import reciprocal_rank_fusion
from rag_app.vector_index import BgeEmbedder, VectorIndex, chunks_for_embedder
from scripts.evaluate_dense import load_cases, percentile
from scripts.generate_corpus import DEFAULT_OUTPUT, ROOT, generate_corpus, load_manifest


def score_cases(rows: list[dict], key: str) -> dict:
    positives = [row for row in rows if row["category"] in {"single_document", "cross_document"}]
    unauthorized = [row for row in rows if row["category"] == "unauthorized"]
    no_answer = [row for row in rows if row["category"] == "no_answer"]
    return {
        "recall_at_5": round(statistics.mean(row[key]["recall"] for row in positives), 4),
        "full_support_at_5": round(statistics.mean(row[key]["recall"] == 1 for row in positives), 4),
        "mrr": round(statistics.mean(row[key]["reciprocal_rank"] for row in positives), 4),
        "unauthorized_exposures": sum(row[key]["blocked_doc_exposed"] for row in unauthorized),
        "no_answer_queries_with_hits": sum(bool(row[key]["retrieved_docs"]) for row in no_answer),
        "latency_p50_ms": round(percentile([row[key]["latency_ms"] for row in rows], 0.5), 2),
        "latency_p95_ms": round(percentile([row[key]["latency_ms"] for row in rows], 0.95), 2),
    }


def score_separation(rows: list[dict], key: str) -> dict:
    positive = [
        row[key]["retrieved_scores"][0]
        for row in rows if row["category"] in {"single_document", "cross_document"}
    ]
    negative = [row[key]["retrieved_scores"][0] for row in rows if row["category"] == "no_answer"]
    positive_min = min(positive)
    negative_max = max(negative)
    return {
        "positive_top1_min": positive_min,
        "no_answer_top1_max": negative_max,
        "single_threshold_separates_all": positive_min > negative_max,
    }


def evaluate(output: Path, *, rerank: bool = False) -> dict:
    model_path = ROOT / ".models" / "bge-small-zh-v1.5"
    if model_path.is_dir():
        os.environ.setdefault("EMBEDDING_MODEL_PATH", str(model_path))
    embedder = BgeEmbedder()
    bm25 = ChineseBm25()
    reranker_path = ROOT / ".models" / "bge-reranker-base"
    if rerank and reranker_path.is_dir():
        os.environ.setdefault("RERANKER_MODEL_PATH", str(reranker_path))
    reranker = BgeReranker() if rerank else None
    client = QdrantClient(":memory:")
    dense = VectorIndex(client, collection="hybrid_eval_dense")
    lexical = LexicalIndex(client, collection="hybrid_eval_lexical")
    dense.ensure_collection(embedder.dimension)
    lexical.ensure_collection()
    records = load_manifest()
    cases = load_cases()
    paths = {path.stem: path for path in generate_corpus(DEFAULT_OUTPUT)}
    version_to_slug = {}
    document_to_slug = {}
    record_by_slug = {record["id"]: record for record in records}
    chunk_count = 0

    started = time.perf_counter()
    for record in records:
        slug = record["id"]
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fictional-document:{slug}"))
        version_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fictional-version:{slug}"))
        chunks = chunks_for_embedder(parse_file(paths[slug]).blocks, embedder)
        text = [embedding_text(chunk) for chunk in chunks]
        dense.upsert_chunks(document_id, version_id, chunks, embedder.encode(text))
        lexical.upsert_chunks(document_id, version_id, chunks, bm25.encode(text))
        version_to_slug[version_id] = slug
        document_to_slug[document_id] = slug
        chunk_count += len(chunks)
    ingestion_seconds = round(time.perf_counter() - started, 2)

    rows = []
    for case in cases:
        allowed = [
            version_id for version_id, slug in version_to_slug.items()
            if case.username == "admin" or record_by_slug[slug]["department"] is None
        ]
        start = time.perf_counter()
        dense_vector = embedder.encode_query(case.question)
        dense_hits = dense.search(dense_vector, allowed, limit=5)
        dense_ms = round((time.perf_counter() - start) * 1000, 2)
        dense_candidates = dense.search(dense_vector, allowed, limit=20)
        lexical_hits = lexical.search(bm25.encode_query(case.question), allowed, limit=20)
        fused = reciprocal_rank_fusion((dense_candidates, lexical_hits), 10 if reranker else 5)
        hybrid_hits = fused[:5]
        hybrid_ms = round((time.perf_counter() - start) * 1000, 2)
        reranked_hits = reranker.rerank(case.question, fused, 5) if reranker else []
        reranked_ms = round((time.perf_counter() - start) * 1000, 2)

        row = {"category": case.category, "question": case.question, "expected_docs": list(case.expected_docs)}
        variants = [("dense", dense_hits, dense_ms), ("hybrid", hybrid_hits, hybrid_ms)]
        if reranker:
            variants.append(("hybrid_rerank", reranked_hits, reranked_ms))
        for name, hits, latency in variants:
            found = [document_to_slug[hit.document_id] for hit in hits]
            expected = set(case.expected_docs)
            row[name] = {
                "retrieved_docs": found,
                "retrieved_scores": [round(hit.score, 5) for hit in hits],
                "recall": len(expected.intersection(found)) / len(expected) if expected else None,
                "reciprocal_rank": next((1 / rank for rank, slug in enumerate(found, 1) if slug in expected), 0.0)
                if expected else None,
                "blocked_doc_exposed": case.blocked_doc in found if case.blocked_doc else None,
                "latency_ms": latency,
            }
        rows.append(row)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_count": len(records), "chunk_count": chunk_count, "question_count": len(cases),
        "embedding_model": embedder.model_name, "lexical_model": bm25.model_name,
        "ingestion_seconds": ingestion_seconds,
        "dense": score_cases(rows, "dense"),
        "hybrid": score_cases(rows, "hybrid"),
    }
    if reranker:
        summary["reranker_model"] = reranker.model_name
        summary["hybrid_rerank"] = score_cases(rows, "hybrid_rerank")
        summary["reranker_score_separation"] = score_separation(rows, "hybrid_rerank")
    output.mkdir(parents=True, exist_ok=True)
    (output / "hybrid-eval.json").write_text(
        json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    lines = [
        "# Dense 与 Hybrid 检索对照", "",
        f"- 时间：{summary['generated_at']}",
        f"- 数据：{len(records)} 份虚构制度，{chunk_count} 个 chunk，{len(cases)} 道问题。",
        "- 方法：相同语料、问题与权限范围；Hybrid 使用本地 BM25（jieba 分词）+ Dense，RRF(k=60) 融合前 20 个候选。",
        "- 环境：本地 CPU + Qdrant local；没有调用生成 API。", "",
    ]
    if reranker:
        lines.append("- Reranker：`BAAI/bge-reranker-base`，对融合后的前 10 个候选重排。")
        lines += ["", "| 指标 | Dense | Hybrid | Hybrid + Reranker |", "| --- | ---: | ---: | ---: |"]
    else:
        lines += ["| 指标 | Dense | Hybrid |", "| --- | ---: | ---: |"]
    labels = {
        "recall_at_5": "Recall@5", "full_support_at_5": "完整支持文档命中@5",
        "mrr": "MRR", "unauthorized_exposures": "越权文档暴露数",
        "no_answer_queries_with_hits": "无答案但返回片段的问题数",
        "latency_p50_ms": "查询延迟 p50 (ms)", "latency_p95_ms": "查询延迟 p95 (ms)",
    }
    for metric, label in labels.items():
        values = [str(summary[mode][metric]) for mode in (
            ("dense", "hybrid", "hybrid_rerank") if reranker else ("dense", "hybrid")
        )]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    lines += [
        "", "这里的无答案指标只衡量召回是否产生候选，不等于回答拒答率。",
        "评估集由本项目虚构语料衍生，规模小且尚未经独立人工复核；结果不能外推到真实企业数据。",
        "未包含生成答案正确率或引用支持率。逐题结果见 `hybrid-eval.json`。", "",
    ]
    if reranker:
        separation = summary["reranker_score_separation"]
        lines += [
            "## 证据门控观察", "",
            f"有答案问题 Top-1 重排分最低为 {separation['positive_top1_min']:.5f}；"
            f"无答案问题 Top-1 最高为 {separation['no_answer_top1_max']:.5f}。",
            "两类分数交叠，单一固定阈值无法同时保留所有有答案问题并拒绝所有无答案问题。",
            "Reranker 分数是相关性信号，不是答案受证据支持的证明；本项目尚未实现可靠的自动证据门控。", "",
        ]
    (output / "hybrid-eval.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare dense and hybrid retrieval on fictional policies")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    parser.add_argument("--rerank", action="store_true", help="Include local BGE reranker comparison")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.output, rerank=args.rerank), ensure_ascii=False, indent=2))
