from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.db import Document, DocumentVersion, IngestionJob, now_utc


class LifecycleError(ValueError):
    pass


def activate_version(session: Session, document_id: str, version_id: str) -> None:
    document = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or document.deleted_at is not None:
        raise LifecycleError("Document is not available")
    version = session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    if version is None or version.status != "READY":
        raise LifecycleError("Version is not ready")
    if document.active_version_id:
        old = session.get(DocumentVersion, document.active_version_id)
        if old is not None:
            old.status = "RETIRED"
            session.add(IngestionJob(version_id=old.id, kind="purge", status="PENDING"))
    document.active_version_id = version.id
    version.status = "ACTIVE"
    version.activated_at = now_utc()
    session.flush()


def delete_document(session: Session, document_id: str) -> None:
    document = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or document.deleted_at is not None:
        raise LifecycleError("Document is not available")
    document.deleted_at = now_utc()
    document.active_version_id = None
    versions = session.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document_id)).all()
    for version in versions:
        if version.status != "RETIRED":
            version.status = "RETIRED"
        pending_indexes = session.scalars(select(IngestionJob).where(
            IngestionJob.version_id == version.id,
            IngestionJob.kind == "index",
            IngestionJob.status == "PENDING",
        )).all()
        for job in pending_indexes:
            job.status = "CANCELLED"
            job.finished_at = now_utc()
        session.add(IngestionJob(version_id=version.id, kind="purge", status="PENDING"))
    session.flush()


def retry_job(session: Session, job_id: str) -> IngestionJob:
    job = session.scalar(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
    if job is None or job.status != "FAILED":
        raise LifecycleError("Job is not failed")
    version = session.get(DocumentVersion, job.version_id)
    if version is None:
        raise LifecycleError("Version is missing")
    document = session.get(Document, version.document_id)
    if job.kind == "index":
        if document is None or document.deleted_at is not None or version.status != "FAILED":
            raise LifecycleError("Version cannot be retried")
        version.status = "UPLOADED"
    elif job.kind == "purge":
        if document is not None and document.active_version_id == version.id:
            raise LifecycleError("Active version cannot be purged")
    else:
        raise LifecycleError("Unsupported job kind")
    job.status = "PENDING"
    job.error = None
    job.finished_at = None
    session.flush()
    return job


def visible_version_ids(session: Session, role: str, department: str | None) -> list[str]:
    documents = session.scalars(
        select(Document).where(Document.deleted_at.is_(None), Document.active_version_id.is_not(None))
    )
    return [
        document.active_version_id
        for document in documents
        if role == "admin"
        or (
            role in document.allowed_roles
            and (document.department is None or document.department == department)
        )
    ]
