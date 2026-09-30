from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.db import Base, Document, DocumentVersion, IngestionJob
from rag_app.lifecycle import activate_version, delete_document, visible_version_ids


def test_replace_and_delete_keep_search_scope_current() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = Document(title="采购制度", department="采购部", allowed_roles=["employee"])
        session.add(document)
        session.flush()
        first = DocumentVersion(
            document_id=document.id, version_number=1, filename="v1.md", source_format="md",
            sha256="a" * 64, storage_path="v1.md", status="READY",
        )
        second = DocumentVersion(
            document_id=document.id, version_number=2, filename="v2.md", source_format="md",
            sha256="b" * 64, storage_path="v2.md", status="READY",
        )
        session.add_all([first, second])
        session.flush()

        activate_version(session, document.id, first.id)
        assert visible_version_ids(session, "employee", "采购部") == [first.id]
        assert visible_version_ids(session, "employee", "财务部") == []

        activate_version(session, document.id, second.id)
        assert visible_version_ids(session, "employee", "采购部") == [second.id]
        assert first.status == "RETIRED"
        assert session.scalar(select(IngestionJob).where(IngestionJob.version_id == first.id)).kind == "purge"

        delete_document(session, document.id)
        assert visible_version_ids(session, "admin", None) == []
        assert document.deleted_at is not None
