from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".txt", ".html", ".htm"}


class NeedsOcrError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    headings: tuple[str, ...] = ()
    page_number: int | None = None


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    source_format: str
    sha256: str
    blocks: tuple[ParsedBlock, ...]


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    headings: tuple[str, ...]
    page_number: int | None


def parse_file(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported document format: {suffix}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    if suffix == ".txt":
        content = path.read_text(encoding="utf-8-sig")
        blocks = (ParsedBlock(text=content.strip()),)
        title = path.stem
    elif suffix == ".md":
        title, blocks = _parse_markdown(path.read_text(encoding="utf-8-sig"), path.stem)
    elif suffix == ".pdf":
        title, blocks = _parse_pdf_text(path)
    else:
        title, blocks = _parse_with_docling(path)

    blocks = tuple(block for block in blocks if block.text.strip())
    if not blocks:
        raise ValueError("Document contains no extractable text")
    return ParsedDocument(title=title, source_format=suffix.lstrip("."), sha256=digest, blocks=blocks)


def _parse_markdown(content: str, fallback_title: str) -> tuple[str, tuple[ParsedBlock, ...]]:
    headings: list[str] = []
    blocks: list[ParsedBlock] = []
    paragraphs: list[str] = []
    title = fallback_title

    def flush() -> None:
        if paragraphs:
            blocks.append(ParsedBlock("\n".join(paragraphs).strip(), tuple(headings)))
            paragraphs.clear()

    for line in content.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            level = len(match.group(1))
            heading = match.group(2).strip()
            if level == 1 and title == fallback_title:
                title = heading
            headings = headings[: level - 1] + [heading]
        elif line.strip():
            paragraphs.append(line.strip())
        else:
            flush()
    flush()
    return title, tuple(blocks)


def _parse_with_docling(path: Path) -> tuple[str, tuple[ParsedBlock, ...]]:
    try:
        from docling.chunking import HierarchicalChunker
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError("Install the 'parsing' extra to parse PDF, DOCX, or HTML") from exc

    document = DocumentConverter().convert(str(path)).document
    blocks: list[ParsedBlock] = []
    for item in HierarchicalChunker().chunk(document):
        text = item.text.strip()
        if not text:
            continue
        meta = item.meta
        headings = tuple(meta.headings or ())
        pages = [
            prov.page_no
            for doc_item in meta.doc_items or ()
            for prov in getattr(doc_item, "prov", ())
            if getattr(prov, "page_no", None) is not None
        ]
        blocks.append(ParsedBlock(text, headings, min(pages) if pages else None))
    return path.stem, tuple(blocks)


def _parse_pdf_text(path: Path) -> tuple[str, tuple[ParsedBlock, ...]]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("Install the 'parsing' extra to parse PDF") from exc

    blocks: list[ParsedBlock] = []
    with pdfium.PdfDocument(str(path)) as pdf:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            textpage = page.get_textpage()
            text = textpage.get_text_range().strip()
            if text:
                blocks.append(ParsedBlock(text=text, page_number=page_index + 1))
            textpage.close()
            page.close()
    if not blocks:
        raise NeedsOcrError("PDF contains no text layer; OCR is required")
    return path.stem, tuple(blocks)


def embedding_text(chunk: Chunk) -> str:
    return " / ".join(chunk.headings) + "\n" + chunk.text


def make_chunks(
    blocks: Iterable[ParsedBlock], max_chars: int = 450, *,
    token_length: Callable[[str], int] | None = None, max_tokens: int | None = None,
) -> list[Chunk]:
    if max_chars < 50:
        raise ValueError("max_chars must be at least 50")
    if (token_length is None) != (max_tokens is None):
        raise ValueError("Token counter and limit must be supplied together")
    if max_tokens is not None and max_tokens < 2:
        raise ValueError("max_tokens must be at least 2")
    chunks: list[Chunk] = []
    for block in blocks:
        for part in _split_text(block.text.strip(), max_chars):
            parts = [part] if token_length is None else _split_by_tokens(
                part, block.headings, token_length, max_tokens
            )
            for sized in parts:
                chunks.append(Chunk(len(chunks), sized, block.headings, block.page_number))
    return chunks


def _split_by_tokens(
    text: str, headings: tuple[str, ...], token_length: Callable[[str], int], max_tokens: int,
) -> list[str]:
    prefix = " / ".join(headings) + "\n"
    parts: list[str] = []
    remaining = text
    while remaining:
        if token_length(prefix + remaining) <= max_tokens:
            parts.append(remaining)
            break
        if token_length(prefix + remaining[:1]) > max_tokens:
            raise ValueError("Document heading exceeds embedding token limit")
        low, high = 1, len(remaining)
        while low < high:
            middle = (low + high + 1) // 2
            if token_length(prefix + remaining[:middle]) <= max_tokens:
                low = middle
            else:
                high = middle - 1
        cut = low
        while token_length(prefix + remaining[:cut]) > max_tokens:
            cut -= 1
        parts.append(remaining[:cut])
        remaining = remaining[cut:]
    return parts


def _split_text(text: str, max_chars: int) -> list[str]:
    if not text:
        return []
    result: list[str] = []
    while len(text) > max_chars:
        window = text[: max_chars + 1]
        candidates = [window.rfind(mark) for mark in ("\n", "。", "！", "？", ";", "；", " ")]
        split = max(candidates) + 1
        if split < max_chars // 2:
            split = max_chars
        result.append(text[:split].strip())
        text = text[split:].strip()
    if text:
        result.append(text)
    return result
