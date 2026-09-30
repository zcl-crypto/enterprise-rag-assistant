from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, inspect
from sqlalchemy.engine import Engine

from rag_app.db import Base, make_engine


INITIAL_TABLE_NAMES = {
    "users", "documents", "document_versions", "chunks", "ingestion_jobs", "audit_events",
}


def only_missing_effective_date(differences: list) -> bool:
    if len(differences) != 1:
        return False
    change = differences[0]
    return (
        isinstance(change, tuple) and len(change) == 4
        and change[0] == "add_column" and change[2] == "document_versions"
        and change[3].name == "effective_date"
    )


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def require_current_schema(engine: Engine) -> None:
    config = migration_config()
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.connect() as connection:
        revision = MigrationContext.configure(connection).get_current_revision()
    if revision != head:
        raise RuntimeError(f"Database schema is at {revision or 'base'}; run python -m rag_app.init_db")


def migrate_database(database_url: str | None = None) -> str:
    engine = make_engine(database_url)
    config = migration_config()
    try:
        with engine.begin() as connection:
            existing_tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
            revision = MigrationContext.configure(connection).get_current_revision()
            config.attributes["connection"] = connection
            if revision is None and existing_tables:
                difference = compare_metadata(
                    MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata
                )
                if not difference:
                    command.stamp(config, "head")
                    return "stamped existing schema"
                if only_missing_effective_date(difference):
                    command.stamp(config, "0002")
                    command.upgrade(config, "head")
                    return "upgraded existing previous schema to head"
                initial_metadata = MetaData()
                for table in Base.metadata.sorted_tables:
                    if table.name in INITIAL_TABLE_NAMES:
                        table.to_metadata(initial_metadata)
                initial_difference = compare_metadata(
                    MigrationContext.configure(connection, opts={"compare_type": True}), initial_metadata
                )
                if not initial_difference or only_missing_effective_date(initial_difference):
                    command.stamp(config, "0001")
                    command.upgrade(config, "head")
                    return "upgraded existing initial schema to head"
                raise RuntimeError(
                    "Unversioned database schema differs from known revisions; back up and migrate it manually"
                )
            command.upgrade(config, "head")
            return "upgraded to head"
    finally:
        engine.dispose()


def main() -> None:
    print(migrate_database())


if __name__ == "__main__":
    main()
