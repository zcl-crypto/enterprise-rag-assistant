from pathlib import Path

import pytest

from rag_app.documents import ParsedBlock, embedding_text, make_chunks, parse_file


def test_markdown_preserves_heading_path(tmp_path: Path) -> None:
    source = tmp_path / "policy.md"
    source.write_text("# 费用制度\n\n## 报销时限\n\n30天内申请。\n\n## 审批\n\n主管审批。", encoding="utf-8")

    document = parse_file(source)

    assert document.title == "费用制度"
    assert [block.headings for block in document.blocks] == [
        ("费用制度", "报销时限"),
        ("费用制度", "审批"),
    ]
    assert document.sha256


def test_txt_rejects_empty_document(tmp_path: Path) -> None:
    source = tmp_path / "blank.txt"
    source.write_text(" \n ", encoding="utf-8")
    with pytest.raises(ValueError, match="no extractable text"):
        parse_file(source)


def test_chunks_preserve_provenance_and_size() -> None:
    blocks = [ParsedBlock("报销规则。" * 30, ("费用制度", "报销"), 2)]

    chunks = make_chunks(blocks, max_chars=60)

    assert len(chunks) > 1
    assert "".join(chunk.text for chunk in chunks) == blocks[0].text
    assert all(len(chunk.text) <= 60 for chunk in chunks)
    assert all(chunk.headings == blocks[0].headings and chunk.page_number == 2 for chunk in chunks)


def test_chunks_fit_embedding_token_limit_including_headings() -> None:
    block = ParsedBlock("abcdefghij" * 6, ("Policy", "Rules"), 3)
    token_length = lambda text: len(text) + 2

    chunks = make_chunks([block], max_chars=100, token_length=token_length, max_tokens=25)

    assert len(chunks) > 1
    assert "".join(chunk.text for chunk in chunks) == block.text
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.headings == block.headings and chunk.page_number == 3 for chunk in chunks)
    assert all(token_length(embedding_text(chunk)) <= 25 for chunk in chunks)


def test_token_chunking_rejects_headings_that_leave_no_room() -> None:
    block = ParsedBlock("document body", ("a very long heading",))
    with pytest.raises(ValueError, match="heading exceeds"):
        make_chunks([block], token_length=lambda text: len(text) + 2, max_tokens=10)
