from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image, ImageDraw
from qdrant_client import QdrantClient
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from rag_app.db import Base, ChunkRecord, DocumentVersion, IngestionJob
from rag_app.ingestion import run_index_job, run_purge_job, stage_document
from rag_app.lifecycle import activate_version, delete_document, retry_job, visible_version_ids
from rag_app.vector_index import VectorIndex


class FakeEmbedder:
    model_name = "test-embedder"
    dimension = 3

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def encode_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_image_only_pdf_is_marked_needs_ocr(tmp_path: Path) -> None:
    image = Image.new("RGB", (300, 100), "white")
    ImageDraw.Draw(image).text((12, 40), "Scanned policy", fill="black")
    content = BytesIO()
    pdf = canvas.Canvas(content)
    pdf.drawImage(ImageReader(image), 72, 650, width=300, height=100)
    pdf.save()
    content.seek(0)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    index = VectorIndex(QdrantClient(":memory:"))
    with sessions.begin() as session:
        version, job = stage_document(session, content, "scan.pdf", "扫描制度", tmp_path)
        version_id, job_id = version.id, job.id

    assert not run_index_job(sessions, index, FakeEmbedder(), job_id)
    with Session(engine) as session:
        version = session.get(DocumentVersion, version_id)
        job = session.get(IngestionJob, job_id)
        assert version.status == "NEEDS_OCR"
        assert job.status == "FAILED"
        assert "OCR" in job.error
        assert session.scalars(select(ChunkRecord)).all() == []


@pytest.mark.parametrize(
    ("filename", "payload", "message"),
    [
        ("fake.pdf", b"plain text", "not a PDF"),
        ("fake.docx", b"plain text", "not a DOCX"),
        ("fake.txt", b"\x00binary", "binary data"),
        ("fake.md", b"\xff\xfe", "UTF-8"),
    ],
)
def test_stage_rejects_mismatched_content_without_leaving_files(
    tmp_path: Path, filename: str, payload: bytes, message: str,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with pytest.raises(ValueError, match=message), sessionmaker(bind=engine).begin() as session:
        stage_document(session, BytesIO(payload), filename, "Policy", tmp_path)
    assert list(tmp_path.iterdir()) == []
    with Session(engine) as session:
        assert session.scalars(select(DocumentVersion)).all() == []
        assert session.scalars(select(IngestionJob)).all() == []


def test_stage_rejects_zip_disguised_as_docx(tmp_path: Path) -> None:
    archive = BytesIO()
    with ZipFile(archive, "w") as content:
        content.writestr("unrelated.txt", "not a Word document")
    archive.seek(0)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with pytest.raises(ValueError, match="not a DOCX"), sessionmaker(bind=engine).begin() as session:
        stage_document(session, archive, "archive.docx", "Fake", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_stage_index_and_activate(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    index = VectorIndex(QdrantClient(":memory:"))

    with sessions.begin() as session:
        version, job = stage_document(
            session, BytesIO("# 报销制度\n\n## 时限\n\n三十天内提交。".encode()),
            "policy.md", "报销制度", tmp_path, allowed_roles=["employee"],
        )
        version_id, job_id, document_id = version.id, job.id, version.document_id

    assert run_index_job(sessions, index, FakeEmbedder(), job_id)
    assert not run_index_job(sessions, index, FakeEmbedder(), job_id)
    with Session(engine) as session:
        version = session.get(DocumentVersion, version_id)
        job = session.get(IngestionJob, job_id)
        assert version.status == "READY"
        assert job.status == "DONE"
        assert job.attempts == 1
        assert len(session.scalars(select(ChunkRecord)).all()) == 1
        activate_version(session, document_id, version_id)
        session.commit()

    hits = index.search([1.0, 0.0, 0.0], [version_id])
    assert len(hits) == 1
    assert "三十天" in hits[0].text

    with sessions.begin() as session:
        delete_document(session, document_id)
        assert visible_version_ids(session, "employee", None) == []
        purge_job = session.scalar(select(IngestionJob).where(IngestionJob.kind == "purge"))
        purge_job_id = purge_job.id

    assert run_purge_job(sessions, index, purge_job_id)
    assert not run_purge_job(sessions, index, purge_job_id)
    assert index.search([1.0, 0.0, 0.0], [version_id]) == []
    assert not (tmp_path / f"{version_id}.md").exists()
    with Session(engine) as session:
        assert session.get(IngestionJob, purge_job_id).attempts == 1


def test_index_job_splits_chunks_for_embedder_token_limit(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    index = VectorIndex(QdrantClient(":memory:"))

    class LimitedEmbedder(FakeEmbedder):
        max_tokens = 20

        def token_length(self, text: str) -> int:
            return len(text) + 2

        def encode(self, texts: list[str]) -> list[list[float]]:
            assert all(self.token_length(text) <= self.max_tokens for text in texts)
            return super().encode(texts)

    original = "abcdefghij" * 7
    with sessions.begin() as session:
        version, job = stage_document(session, BytesIO(original.encode()), "long.txt", "Long", tmp_path)
        version_id, job_id = version.id, job.id

    assert run_index_job(sessions, index, LimitedEmbedder(), job_id)
    with sessions() as session:
        chunks = session.scalars(select(ChunkRecord).where(ChunkRecord.version_id == version_id).order_by(
            ChunkRecord.ordinal
        )).all()
        assert len(chunks) > 1
        assert "".join(chunk.text for chunk in chunks) == original
        assert session.get(DocumentVersion, version_id).status == "READY"


def test_delete_while_indexing_schedules_final_vector_cleanup(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    index = VectorIndex(QdrantClient(":memory:"))
    with sessions.begin() as session:
        version, job = stage_document(
            session, BytesIO(b"# Policy\n\nThis rule is obsolete."),
            "policy.md", "Policy", tmp_path,
        )
        version_id, job_id, document_id = version.id, job.id, version.document_id

    class DeleteDuringEmbedding(FakeEmbedder):
        def encode(self, texts: list[str]) -> list[list[float]]:
            with sessions.begin() as session:
                delete_document(session, document_id)
            return super().encode(texts)

    assert not run_index_job(sessions, index, DeleteDuringEmbedding(), job_id)
    assert index.search([1.0, 0.0, 0.0], [version_id])
    with sessions() as session:
        purge_jobs = session.scalars(select(IngestionJob).where(IngestionJob.kind == "purge")).all()
        assert len(purge_jobs) == 2
        assert session.get(DocumentVersion, version_id).status == "RETIRED"
    for purge_job in purge_jobs:
        assert run_purge_job(sessions, index, purge_job.id)
    assert index.search([1.0, 0.0, 0.0], [version_id]) == []
    assert not (tmp_path / f"{version_id}.md").exists()


def test_delete_cancels_pending_index_and_purges_without_collection(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    index = VectorIndex(QdrantClient(":memory:"))
    with sessions.begin() as session:
        version, job = stage_document(
            session, BytesIO(b"Not indexed yet."), "draft.txt", "Draft", tmp_path,
        )
        version_id, job_id, document_id = version.id, job.id, version.document_id
    with sessions.begin() as session:
        delete_document(session, document_id)
    assert not run_index_job(sessions, index, FakeEmbedder(), job_id)
    with sessions() as session:
        assert session.get(IngestionJob, job_id).status == "CANCELLED"
        purge_job = session.scalar(select(IngestionJob).where(IngestionJob.kind == "purge"))
        purge_job_id = purge_job.id
    assert run_purge_job(sessions, index, purge_job_id)
    assert not (tmp_path / f"{version_id}.txt").exists()


def test_failed_purge_can_be_retried_without_restoring_visibility(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    class FailOncePurgeIndex(VectorIndex):
        fail_next = True

        def purge_version(self, version_id: str) -> None:
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError("temporary vector-store outage")
            super().purge_version(version_id)

    index = FailOncePurgeIndex(QdrantClient(":memory:"))
    with sessions.begin() as session:
        version, job = stage_document(
            session, BytesIO(b"# Policy\n\nThis must disappear."), "policy.md", "Policy", tmp_path,
        )
        version_id, job_id, document_id = version.id, job.id, version.document_id
    assert run_index_job(sessions, index, FakeEmbedder(), job_id)
    with sessions.begin() as session:
        activate_version(session, document_id, version_id)
        delete_document(session, document_id)
        purge_job = session.scalar(select(IngestionJob).where(IngestionJob.kind == "purge"))
        purge_job_id = purge_job.id
        assert visible_version_ids(session, "admin", None) == []

    assert not run_purge_job(sessions, index, purge_job_id)
    with sessions.begin() as session:
        assert session.get(IngestionJob, purge_job_id).status == "FAILED"
        retry_job(session, purge_job_id)
    assert run_purge_job(sessions, index, purge_job_id)
    assert index.search([1.0, 0.0, 0.0], [version_id]) == []
    assert not (tmp_path / f"{version_id}.md").exists()
    with sessions() as session:
        assert session.get(IngestionJob, purge_job_id).attempts == 2
