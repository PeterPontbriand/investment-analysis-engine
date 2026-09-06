"""Inspect and exercise the approved schema through its actual Alembic revision."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import BigInteger, bindparam, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from alembic import command, op
from src.config import ProjectSettings
from src.data.repositories import SQLiteDatabase
from src.data.repositories.schema import metadata

ROOT = Path(__file__).resolve().parents[3]
STAMP = "2026-09-05T12:00:00.000000Z"
EXPECTED_COLUMNS = {
    "schema_metadata": "metadata_key metadata_value",
    "trajectory_events": (
        "event_id run_id session_id sequence timestamp event_type component schema_version mode span_id "
        "parent_span_id model_tag provider step_index tool_name tool_args_json tool_result_summary_json "
        "prompt_tokens completion_tokens latency_ms payload_json payload_hash error_json"
    ),
    "resolved_input_cache": (
        "cache_key subject_kind subject_id field_name basis provider_id analysis_as_of schema_version "
        "key_period_start key_period_end cached_at value source_kind resolved_at units currency input_provider_id "
        "provider_field input_period_start input_period_end observed_at available_at retrieved_at lineage_json "
        "notes_json fiscal_year period_kind accounting_scope capital_expenditure_sign provider_fact_id"
    ),
    "market_data_cache_entries": (
        "entry_key ticker request_provider_id request_start request_end request_variant schema_version cached_at "
        "fetch_completed_at row_count frame_metadata_json context_provider_id observation_interval data_as_of "
        "currency observation_count price_adjustment"
    ),
    "market_price_observations": "entry_key row_position index_value open high low close adj_close volume",
}


def config_for(path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    path = tmp_path / "schema.sqlite3"
    command.upgrade(config_for(path), "head")
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        yield database
    finally:
        database.close()


def schema_signature(connection: Connection) -> dict[str, object]:
    inspector = inspect(connection)
    result: dict[str, object] = {}
    for table in EXPECTED_COLUMNS:
        result[table] = {
            "columns": [
                (column["name"], str(column["type"]), column["nullable"], column["default"])
                for column in inspector.get_columns(table)
            ],
            "pk": inspector.get_pk_constraint(table),
            "unique": inspector.get_unique_constraints(table),
            "fk": inspector.get_foreign_keys(table),
            "indexes": inspector.get_indexes(table),
            "checks": inspector.get_check_constraints(table),
        }
    return result


def test_migration_matches_core_metadata_and_approved_column_inventory(
    database: SQLiteDatabase,
    tmp_path: Path,
) -> None:
    reference = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'core.sqlite3').as_posix()}"))
    try:
        with reference.transaction() as connection:
            metadata.create_all(connection)
        with database.read() as actual, reference.read() as expected:
            assert set(inspect(actual).get_table_names()) == set(EXPECTED_COLUMNS) | {"alembic_version"}
            assert set(metadata.tables) == set(EXPECTED_COLUMNS)
            for table, columns in EXPECTED_COLUMNS.items():
                assert [column["name"] for column in inspect(actual).get_columns(table)] == columns.split()
            assert schema_signature(actual) == schema_signature(expected)
            assert actual.exec_driver_sql(
                "SELECT metadata_key, metadata_value FROM schema_metadata"
            ).tuples().all() == [("persistence_encoding_version", 1)]
    finally:
        reference.close()


def base_row(table: str) -> dict[str, object]:
    rows: dict[str, dict[str, object]] = {
        "schema_metadata": {"metadata_key": "test_version", "metadata_value": 1},
        "trajectory_events": {
            "event_id": "event-1",
            "run_id": "run-1",
            "session_id": "session-1",
            "sequence": 1,
            "timestamp": STAMP,
            "event_type": "run_start",
            "component": "test",
            "schema_version": 1,
            "mode": "light",
            "span_id": "span-1",
        },
        "resolved_input_cache": {
            "cache_key": '["security","AAPL","eps",null,"test",null,1,null,null]',
            "subject_kind": "security",
            "subject_id": "AAPL",
            "field_name": "eps",
            "provider_id": "test",
            "schema_version": 1,
            "cached_at": STAMP,
            "value": 1.0,
            "source_kind": "provider",
            "resolved_at": STAMP,
            "notes_json": "[]",
        },
        "market_data_cache_entries": {
            "entry_key": "snapshot-1",
            "ticker": "AAPL",
            "request_provider_id": "test",
            "request_start": "2026-01-01",
            "request_variant": "1d:adjusted",
            "schema_version": 1,
            "cached_at": STAMP,
            "row_count": 1,
            "frame_metadata_json": "{}",
        },
    }
    return rows[table].copy()


@pytest.mark.parametrize(
    ("table", "field", "value"),
    [
        ("schema_metadata", "metadata_value", 0),
        ("trajectory_events", "sequence", 0),
        ("trajectory_events", "sequence", 1.5),
        ("trajectory_events", "schema_version", 0),
        ("trajectory_events", "run_id", " "),
        ("trajectory_events", "mode", "other"),
        ("trajectory_events", "event_type", "invented"),
        ("trajectory_events", "prompt_tokens", -1),
        ("trajectory_events", "latency_ms", -1),
        ("resolved_input_cache", "subject_kind", "watchlist"),
        ("resolved_input_cache", "source_kind", "cache"),
        ("resolved_input_cache", "subject_id", ""),
        ("resolved_input_cache", "basis", " "),
        ("resolved_input_cache", "cached_at", "2026-09-05T12:00:00"),
        ("resolved_input_cache", "cached_at", "2026-99-05T12:00:00.000000Z"),
        ("resolved_input_cache", "key_period_start", STAMP),
        ("resolved_input_cache", "period_kind", "monthly"),
        ("resolved_input_cache", "accounting_scope", "unknown"),
        ("resolved_input_cache", "capital_expenditure_sign", "unknown"),
        ("market_data_cache_entries", "row_count", 0),
        ("market_data_cache_entries", "observation_count", -1),
        ("market_data_cache_entries", "request_end", "2025-01-01"),
        ("market_data_cache_entries", "request_start", "not-a-date"),
    ],
)
def test_database_checks_reject_invalid_rows(
    database: SQLiteDatabase,
    table: str,
    field: str,
    value: object,
) -> None:
    row = base_row(table)
    row[field] = value
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(metadata.tables[table].insert(), row)


def test_duplicate_event_identity_and_run_sequence_are_rejected(database: SQLiteDatabase) -> None:
    row = base_row("trajectory_events")
    table = metadata.tables["trajectory_events"]
    with database.transaction() as connection:
        connection.execute(table.insert(), row)
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(table.insert(), row)
    row["event_id"] = "event-2"
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(table.insert(), row)


def test_nullable_cache_key_identity_and_period_checks(database: SQLiteDatabase) -> None:
    row = base_row("resolved_input_cache")
    table = metadata.tables["resolved_input_cache"]
    with database.transaction() as connection:
        connection.execute(table.insert(), row)
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(table.insert(), row)
    historical = dict(
        row,
        cache_key='["security","AAPL","eps",null,"test","2026-09-05T12:00:00.000000Z",1,null,null]',
        analysis_as_of=STAMP,
    )
    with database.transaction() as connection:
        connection.execute(table.insert(), historical)
    invalid = dict(row, cache_key="reversed", key_period_start=STAMP, key_period_end="2025-09-05T12:00:00.000000Z")
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(table.insert(), invalid)


def test_observations_are_snapshot_scoped_with_cascade_and_integer_volume(database: SQLiteDatabase) -> None:
    entries = metadata.tables["market_data_cache_entries"]
    observations = metadata.tables["market_price_observations"]
    row = {
        "entry_key": "snapshot-1",
        "row_position": 0,
        "index_value": "2026-01-01",
        "close": 10.0,
        "volume": 2**60 + 1,
    }
    # NUMERIC's default bind processor converts integers through float. E1 must
    # bind volume according to the retained frame dtype, preserving int64 here.
    integer_volume_insert = observations.insert().values(volume=bindparam("volume", type_=BigInteger()))
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(observations.insert(), row)
    with database.transaction() as connection:
        connection.execute(entries.insert(), base_row("market_data_cache_entries"))
        connection.execute(entries.insert(), dict(base_row("market_data_cache_entries"), entry_key="snapshot-2"))
        connection.execute(integer_volume_insert, row)
        connection.execute(integer_volume_insert, dict(row, entry_key="snapshot-2"))
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(observations.insert(), dict(row, row_position=1))
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(observations.insert(), dict(row, row_position=0, index_value="2026-01-02"))
    with pytest.raises(IntegrityError), database.transaction() as connection:
        connection.execute(observations.insert(), dict(row, row_position=-1, index_value="2026-01-02"))
    with database.transaction() as connection:
        connection.execute(entries.delete().where(entries.c.entry_key == "snapshot-1"))
    with database.read() as connection:
        assert connection.execute(text("SELECT entry_key FROM market_price_observations")).scalars().all() == [
            "snapshot-2"
        ]
        assert connection.execute(observations.select()).mappings().one()["volume"] == 2**60 + 1


def test_failed_initial_revision_rolls_back_all_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "failure.sqlite3"

    def fail_seed(_statement: object) -> None:
        raise RuntimeError("seed failed")

    monkeypatch.setattr(op, "execute", fail_seed)
    with pytest.raises(RuntimeError, match="seed failed"):
        command.upgrade(config_for(path), "head")
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        with database.read() as connection:
            assert inspect(connection).get_table_names() == []
    finally:
        database.close()
