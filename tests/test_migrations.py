from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from rag_app.api import create_app
from rag_app.db import Base, User
from rag_app.init_db import migrate_database, migration_config, require_current_schema


def database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def test_initial_migration_matches_models_and_is_repeatable(tmp_path: Path) -> None:
    url = database_url(tmp_path, "fresh.db")
    assert migrate_database(url) == "upgraded to head"
    engine = create_engine(url)
    require_current_schema(engine)
    with engine.connect() as connection:
        assert not compare_metadata(MigrationContext.configure(connection), Base.metadata)
    with Session(engine) as session:
        session.add(User(username="preserved", password_hash="hash", role="admin", is_active=True))
        session.commit()
    assert migrate_database(url) == "upgraded to head"
    with Session(engine) as session:
        assert session.scalar(select(User.username)) == "preserved"
    engine.dispose()


def test_matching_unversioned_database_is_stamped_without_data_loss(tmp_path: Path) -> None:
    url = database_url(tmp_path, "existing.db")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(username="existing", password_hash="hash", role="admin", is_active=True))
        session.commit()
    with pytest.raises(RuntimeError, match="run python -m rag_app.init_db"):
        require_current_schema(engine)
    assert migrate_database(url) == "stamped existing schema"
    require_current_schema(engine)
    with Session(engine) as session:
        assert session.scalar(select(User.username)) == "existing"
    engine.dispose()


def test_mismatched_unversioned_database_is_not_stamped(tmp_path: Path) -> None:
    url = database_url(tmp_path, "mismatch.db")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE documents (id VARCHAR(36) PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="differs from known revisions"):
        migrate_database(url)
    assert "alembic_version" not in inspect(engine).get_table_names()
    assert "documents" in inspect(engine).get_table_names()
    engine.dispose()


def test_api_rejects_outdated_versioned_sqlite_database(tmp_path: Path) -> None:
    url = database_url(tmp_path, "outdated.db")
    migrate_database(url)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'outdated'"))
    engine.dispose()

    app = create_app(database_url=url, qdrant_client=QdrantClient(":memory:"), seed_demo=False)
    with pytest.raises(RuntimeError, match="run python -m rag_app.init_db"):
        with TestClient(app):
            pass


@pytest.mark.parametrize("unversioned", [False, True])
def test_existing_initial_schema_upgrades_without_losing_data(tmp_path: Path, unversioned: bool) -> None:
    url = database_url(tmp_path, "initial.db")
    engine = create_engine(url)
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    with Session(engine) as session:
        session.add(User(username="before-upgrade", password_hash="hash", role="admin", is_active=True))
        session.commit()
    if unversioned:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    result = migrate_database(url)
    assert result == ("upgraded existing initial schema to head" if unversioned else "upgraded to head")
    require_current_schema(engine)
    assert "chat_requests" in inspect(engine).get_table_names()
    with Session(engine) as session:
        assert session.scalar(select(User.username)) == "before-upgrade"
    engine.dispose()


@pytest.mark.parametrize("unversioned", [False, True])
def test_previous_schema_gains_effective_date_without_losing_data(tmp_path: Path, unversioned: bool) -> None:
    url = database_url(tmp_path, "previous.db")
    engine = create_engine(url)
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
    with Session(engine) as session:
        session.add(User(username="before-date", password_hash="hash", role="admin", is_active=True))
        session.commit()
    if unversioned:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    result = migrate_database(url)
    assert result == ("upgraded existing previous schema to head" if unversioned else "upgraded to head")
    require_current_schema(engine)
    assert "effective_date" in {column["name"] for column in inspect(engine).get_columns("document_versions")}
    with Session(engine) as session:
        assert session.scalar(select(User.username)) == "before-date"
    engine.dispose()
