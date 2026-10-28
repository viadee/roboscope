"""Issue #66: every model column must reach an *existing* DB through the startup
migrations, not only through Alembic (which never runs on boot)."""

from sqlalchemy import create_engine, inspect, text

from src.database import _EXEC_COLUMNS, Base, _migrate_sqlite
from src.main import app  # noqa: F401 — registers every model on Base.metadata


def test_startup_migration_adds_columns_missing_from_a_pre_0_15_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, col in _EXEC_COLUMNS:  # simulate a DB created by 0.8.2
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {col}"))
        _migrate_sqlite(conn)

    insp = inspect(engine)
    missing = [
        (table.name, col.name)
        for table in Base.metadata.sorted_tables
        for col in table.columns
        if col.name not in {c["name"] for c in insp.get_columns(table.name)}
    ]
    assert missing == []
