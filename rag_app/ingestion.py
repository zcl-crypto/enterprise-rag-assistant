from __future__ import annotations

import hashlib
import uuid
import zipfile
from datetime import date
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from rag_app.db import ChunkRecord, Document, DocumentVersion, IngestionJob, now_utc
from rag_app.documents import NeedsOcrError, SUPPORTED_SUFFIXES, embedding_text, parse_file
from rag_app.lexical_index import ChineseBm25, LexicalIndex
from rag_app.vector_index import Embedder, VectorIndex, chunk_point_id, chunks_for_embedder


MAX_FILE_BYTES = 20 * 1024 * 1024


def validate_upload_format(path: Path, suffix: str) -> None:
    if suffix == ".pdf":
        with path.open("rb") as source:
            if source.read(5) != b"%PDF-":
                raise ValueError("File content is not a PDF")
    elif suffix == ".docx":
        if not zipfile.is_zipfile(path):
            raise ValueError("File content is not a DOCX")
        with zipfile.ZipFile(path) as source:
            names = set(source.namelist())
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                raise ValueError("File content is not a DOCX")
    else:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text document must be UTF-8") from exc
        if "\x00" in content:
            raise ValueError("Text document contains binary data")


def stage_document(
    session: Session,
    content: BinaryIO,
    filename: str,
    title: str,
    storage_root: Path,
    *,
    document_id: str | None = None,
    department: str | None = None,
    allowed_roles: list[str] | None = None,
    effective_date: date | None = None,
) -> tuple[DocumentVersion, IngestionJob]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Unsupported document format")
    if not title.strip() or len(title) > 255:
        raise ValueError("Invalid document title")

    if document_id is None:
        document = Document(title=title.strip(), department=department, allowed_roles=allowed_roles or ["employee"])
        session.add(document)
        session.flush()
    else:
        document = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
        if document is None or document.deleted_at is not None:
            raise ValueError("Document is not available")

    storage_root.mkdir(parents=True, exist_ok=True)
    version_id = str(uuid.uuid4())
    target = storage_root / f"{version_id}{suffix}"
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("wb") as output:
            while block := content.read(1024 * 1024):
                size += len(block)
                if size > MAX_FILE_BYTES:
                    raise ValueError("Document exceeds 20 MB")
                digest.update(block)
                output.write(block)
        if size == 0:
            raise ValueError("Document is empty")
        validate_upload_format(target, suffix)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    next_number = (session.scalar(select(func.max(DocumentVersion.version_number)).where(
        DocumentVersion.document_id == document.id
    )) or 0) + 1
    version = DocumentVersion(
        id=version_id,
        document_id=document.id,
        version_number=next_number,
        filename=Path(filename).name,
        source_format=suffix.lstrip("."),
        sha256=digest.hexdigest(),
        effective_date=effective_date,
        storage_path=str(target),
        status="UPLOADED",
    )
    job = IngestionJob(version_id=version_id, kind="index", status="PENDING")
    session.add_all([version, job])
    session.flush()
    return version, job


def run_index_job(
    sessions: sessionmaker,
    index: VectorIndex,
    embedder: Embedder,
    job_id: str,
    *,
    lexical_index: LexicalIndex | None = None,
    bm25: ChineseBm25 | None = None,
) -> bool:
    if (lexical_index is None) != (bm25 is None):
        raise ValueError("Lexical index and encoder must be supplied together")
    with sessions.begin() as session:
        job = session.scalar(
            select(IngestionJob).where(IngestionJob.id == job_id).with_for_update(skip_locked=True)
        )
        if job is None:
            return False
        if job.kind != "index":
            raise ValueError("Job is not an index job")
        if job.status != "PENDING":
            return False
        version = session.get(DocumentVersion, job.version_id)
        if version is None:
            raise ValueError("Version is missing")
        document = session.get(Document, version.document_id)
        if document is None or document.deleted_at is not None:
            job.status = "CANCELLED"
            job.finished_at = now_utc()
            return False
        job.status = "RUNNING"
        job.attempts += 1
        job.error = None
        version.status = "PROCESSING"
        version_id = version.id
        document_id = version.document_id
        source = Path(version.storage_path)

    try:
        parsed = parse_file(source)
        chunks = chunks_for_embedder(parsed.blocks, embedder)
        vectors = embedder.encode([embedding_text(chunk) for chunk in chunks])
        index.ensure_collection(embedder.dimension)
        index.upsert_chunks(document_id, version_id, chunks, vectors)
        if lexical_index is not None and bm25 is not None:
            sparse_vectors = bm25.encode([embedding_text(chunk) for chunk in chunks])
            lexical_index.ensure_collection()
            lexical_index.upsert_chunks(document_id, version_id, chunks, sparse_vectors)
    except Exception as exc:
        with sessions.begin() as session:
            job = session.get(IngestionJob, job_id)
            version = session.get(DocumentVersion, version_id)
            document = session.get(Document, document_id)
            deleted = document is None or document.deleted_at is not None
            job.status = "CANCELLED" if deleted else "FAILED"
            job.error = None if deleted else str(exc)[:2000]
            job.finished_at = now_utc()
            version.status = "RETIRED" if deleted else ("NEEDS_OCR" if isinstance(exc, NeedsOcrError) else "FAILED")
            if deleted:
                session.add(IngestionJob(version_id=version_id, kind="purge", status="PENDING"))
        return False

    with sessions.begin() as session:
        session.execute(delete(ChunkRecord).where(ChunkRecord.version_id == version_id))
        session.add_all([
            ChunkRecord(
                id=chunk_point_id(version_id, chunk.index),
                version_id=version_id,
                ordinal=chunk.index,
                text=chunk.text,
                headings=list(chunk.headings),
                page_number=chunk.page_number,
                embedding_model=embedder.model_name,
            )
            for chunk in chunks
        ])
        version = session.get(DocumentVersion, version_id)
        job = session.scalar(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
        document = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
        deleted = document is None or document.deleted_at is not None
        version.status = "RETIRED" if deleted else "READY"
        job.status = "DONE"
        job.finished_at = now_utc()
        if deleted:
            session.add(IngestionJob(version_id=version_id, kind="purge", status="PENDING"))
    return not deleted


def run_purge_job(
    sessions: sessionmaker, index: VectorIndex, job_id: str, *, lexical_index: LexicalIndex | None = None,
) -> bool:
    with sessions.begin() as session:
        job = session.scalar(
            select(IngestionJob).where(IngestionJob.id == job_id).with_for_update(skip_locked=True)
        )
        if job is None:
            return False
        if job.kind != "purge":
            raise ValueError("Job is not a purge job")
        if job.status not in ("PENDING", "FAILED"):
            return False
        version = session.get(DocumentVersion, job.version_id)
        if version is None:
            raise ValueError("Version is missing")
        document = session.get(Document, version.document_id)
        job.status = "RUNNING"
        job.attempts += 1
        job.error = None
        version_id = version.id
        source = Path(version.storage_path)
        remove_source = document is not None and document.deleted_at is not None

    try:
        index.purge_version(version_id)
        if lexical_index is not None:
            lexical_index.purge_version(version_id)
        if remove_source:
            source.unlink(missing_ok=True)
    except Exception as exc:
        with sessions.begin() as session:
            job = session.get(IngestionJob, job_id)
            job.status = "FAILED"
            job.error = str(exc)[:2000]
            job.finished_at = now_utc()
        return False

    with sessions.begin() as session:
        session.execute(delete(ChunkRecord).where(ChunkRecord.version_id == version_id))
        job = session.get(IngestionJob, job_id)
        job.status = "DONE"
        job.finished_at = now_utc()
    return True
