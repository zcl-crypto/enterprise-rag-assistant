from qdrant_client import QdrantClient

from rag_app.documents import Chunk
from rag_app.vector_index import VectorIndex


def test_upsert_filter_and_purge() -> None:
    index = VectorIndex(QdrantClient(":memory:"))
    index.ensure_collection(3)
    chunk = Chunk(index=0, text="报销时限三十天", headings=("报销",), page_number=2)
    index.upsert_chunks("doc-a", "version-a", [chunk], [[1.0, 0.0, 0.0]])
    index.upsert_chunks("doc-a", "version-a", [chunk], [[1.0, 0.0, 0.0]])
    index.upsert_chunks("doc-b", "version-b", [chunk], [[0.0, 1.0, 0.0]])

    hits = index.search([1.0, 0.0, 0.0], ["version-a"])
    assert len(hits) == 1
    assert hits[0].text == chunk.text
    assert hits[0].page_number == 2
    assert index.search([1.0, 0.0, 0.0], ["version-b"])[0].version_id == "version-b"

    index.purge_version("version-a")
    assert index.search([1.0, 0.0, 0.0], ["version-a"]) == []
    assert len(index.search([0.0, 1.0, 0.0], ["version-b"])) == 1
