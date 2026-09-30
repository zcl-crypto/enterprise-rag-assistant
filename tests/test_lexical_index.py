from qdrant_client import QdrantClient

from rag_app.documents import Chunk
from rag_app.lexical_index import ChineseBm25, LexicalIndex


def test_chinese_bm25_upsert_filter_and_purge(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", ".models/fastembed")
    bm25 = ChineseBm25()
    index = LexicalIndex(QdrantClient(":memory:"))
    index.ensure_collection()
    first = Chunk(index=0, text="员工差旅报销必须在三十天内提交。", headings=("差旅",), page_number=2)
    second = Chunk(index=0, text="采购合同必须经过法务审批。", headings=("采购",), page_number=3)
    index.upsert_chunks("doc-a", "version-a", [first], bm25.encode([first.text]))
    index.upsert_chunks("doc-a", "version-a", [first], bm25.encode([first.text]))
    index.upsert_chunks("doc-b", "version-b", [second], bm25.encode([second.text]))

    query = bm25.encode_query("差旅报销期限")
    hits = index.search(query, ["version-a"])
    assert len(hits) == 1
    assert hits[0].text == first.text
    assert hits[0].page_number == 2
    assert index.search(query, ["version-b"]) == []

    index.purge_version("version-a")
    assert index.search(query, ["version-a"]) == []
    assert index.search(bm25.encode_query("采购合同法务审批"), ["version-b"])
