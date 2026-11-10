"""Add the run's watchlist id and name as indexed summary columns of ``analysis_runs``.

Revision ID: 0006_run_watchlist_columns
Revises: 0005_remove_cancelled_outcome

A refresh's watchlist was stored only inside each run's ``envelope_json``, so listing refreshes would have had to
decode every envelope. The two nullable columns are copies of the envelope's immutable ``watchlist_id`` and
``watchlist_name`` fields, as ``ticker`` is, and the envelope stays the source of truth. Upgrade fills them for every
stored run in SQL with ``json_extract``; a run whose envelope names no watchlist, or cannot be read as one, keeps both
null. An index on ``watchlist_id`` is added.

SQLite cannot add a column inside the stored table definition, which the readiness check compares exactly, so this
revision recreates ``analysis_runs`` in both directions, keeps every row and recreates the indexes. Nothing references
``analysis_runs``, so no other table is affected. Downgrade drops the two columns and their values.

This revision is a frozen schema snapshot; never import mutable application metadata.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_run_watchlist_columns"
down_revision: str = "0005_remove_cancelled_outcome"
branch_labels: str | None = None
depends_on: str | None = None

_UTC = (
    "length({0}) = 27 AND {0} GLOB "
    "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]."
    "[0-9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime({0}) IS NOT NULL"
)
_COLUMNS = (
    "analysis_run_id",
    "refresh_id",
    "batch_position",
    "ticker",
    "analysis_id",
    "method_id",
    "outcome",
    "completed_at",
    "run_schema_version",
    "config_schema_version",
    "method_version",
    "result_schema_version",
    "evidence_codec_version",
    "projection_version",
    "envelope_json",
)
_WATCHLIST_COLUMNS = ("watchlist_id", "watchlist_name")
_OUTCOMES = ("completed", "unavailable", "not_applicable", "failed")


def _outcome_constraint(outcomes: Sequence[str]) -> str:
    return "outcome IN (" + ", ".join(f"'{item}'" for item in outcomes) + ")"


def _envelope_text(field: str) -> str:
    """Return SQL that reads a top-level envelope field only when both watchlist fields are stored as text."""
    return (
        "CASE WHEN json_valid(envelope_json) THEN "
        "CASE WHEN json_type(envelope_json, '$.watchlist_id') = 'text' "
        "AND json_type(envelope_json, '$.watchlist_name') = 'text' "
        f"THEN json_extract(envelope_json, '$.{field}') END END"
    )


def _replace_analysis_runs(*, with_watchlist: bool) -> None:
    """Rebuild ``analysis_runs`` with or without the watchlist columns, keeping every row and index.

    The rows wait in a plain backup table while ``analysis_runs`` is dropped and created again under its own
    name: SQLite rewrites the stored definition of a renamed table, and the readiness check compares that
    definition text exactly.
    """
    columns = ", ".join(_COLUMNS)
    op.execute(f"CREATE TABLE analysis_runs_backup AS SELECT {columns} FROM analysis_runs")  # noqa: S608
    op.drop_table("analysis_runs")
    op.create_table(
        "analysis_runs",
        sa.Column("analysis_run_id", sa.TEXT(), nullable=False),
        sa.Column("refresh_id", sa.TEXT(), nullable=True),
        sa.Column("batch_position", sa.INTEGER(), nullable=True),
        sa.Column("ticker", sa.TEXT(), nullable=False),
        sa.Column("analysis_id", sa.TEXT(), nullable=False),
        sa.Column("method_id", sa.TEXT(), nullable=False),
        sa.Column("outcome", sa.TEXT(), nullable=False),
        sa.Column("completed_at", sa.TEXT(), nullable=False),
        sa.Column("run_schema_version", sa.INTEGER(), nullable=False),
        sa.Column("config_schema_version", sa.INTEGER(), nullable=False),
        sa.Column("method_version", sa.INTEGER(), nullable=False),
        sa.Column("result_schema_version", sa.INTEGER(), nullable=False),
        sa.Column("evidence_codec_version", sa.INTEGER(), nullable=False),
        sa.Column("projection_version", sa.INTEGER(), nullable=False),
        sa.Column("envelope_json", sa.TEXT(), nullable=False),
        *(
            (
                sa.Column("watchlist_id", sa.TEXT(), nullable=True),
                sa.Column("watchlist_name", sa.TEXT(), nullable=True),
            )
            if with_watchlist
            else ()
        ),
        sa.PrimaryKeyConstraint("analysis_run_id", name="pk_analysis_runs"),
        sa.CheckConstraint("length(trim(analysis_run_id)) > 0", name="ck_analysis_runs_analysis_run_id_nonempty"),
        sa.CheckConstraint(
            "refresh_id IS NULL OR length(trim(refresh_id)) > 0", name="ck_analysis_runs_refresh_id_nonempty"
        ),
        sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_analysis_runs_ticker_nonempty"),
        sa.CheckConstraint("length(trim(analysis_id)) > 0", name="ck_analysis_runs_analysis_id_nonempty"),
        sa.CheckConstraint("length(trim(method_id)) > 0", name="ck_analysis_runs_method_id_nonempty"),
        sa.CheckConstraint(_outcome_constraint(_OUTCOMES), name="ck_analysis_runs_outcome_enum"),
        sa.CheckConstraint(_UTC.format("completed_at"), name="ck_analysis_runs_completed_at_utc"),
        sa.CheckConstraint(
            "(refresh_id IS NULL AND batch_position IS NULL) OR "
            "(refresh_id IS NOT NULL AND typeof(batch_position) = 'integer' AND batch_position >= 0)",
            name="ck_analysis_runs_refresh_position_pair",
        ),
        *(
            sa.CheckConstraint(f"typeof({field}) = 'integer' AND {field} >= 1", name=f"ck_analysis_runs_{field}_range")
            for field in (
                "run_schema_version",
                "config_schema_version",
                "method_version",
                "result_schema_version",
                "evidence_codec_version",
                "projection_version",
            )
        ),
        sa.CheckConstraint(
            "json_valid(envelope_json) AND json_type(envelope_json) = 'object'",
            name="ck_analysis_runs_envelope_json_object",
        ),
        *(
            (
                sa.CheckConstraint(
                    "(watchlist_id IS NULL) = (watchlist_name IS NULL)",
                    name="ck_analysis_runs_watchlist_pair",
                ),
            )
            if with_watchlist
            else ()
        ),
    )
    if with_watchlist:
        values = ", ".join((*_COLUMNS, *(_envelope_text(field) for field in _WATCHLIST_COLUMNS)))
        target = ", ".join((*_COLUMNS, *_WATCHLIST_COLUMNS))
        op.execute(f"INSERT INTO analysis_runs ({target}) SELECT {values} FROM analysis_runs_backup")  # noqa: S608
    else:
        op.execute(f"INSERT INTO analysis_runs ({columns}) SELECT {columns} FROM analysis_runs_backup")  # noqa: S608
    op.drop_table("analysis_runs_backup")
    op.create_index("ix_analysis_runs_ticker", "analysis_runs", ["ticker"])
    op.create_index("ix_analysis_runs_method_id", "analysis_runs", ["method_id"])
    op.create_index("ix_analysis_runs_outcome", "analysis_runs", ["outcome"])
    op.create_index("ix_analysis_runs_completed", "analysis_runs", ["completed_at", "analysis_run_id"])
    op.create_index("ix_analysis_runs_refresh", "analysis_runs", ["refresh_id", "batch_position"])


def upgrade() -> None:
    """Rebuild ``analysis_runs`` with the watchlist columns, filled from each stored envelope."""
    _replace_analysis_runs(with_watchlist=True)
    op.create_index("ix_analysis_runs_watchlist", "analysis_runs", ["watchlist_id"])


def downgrade() -> None:
    """Rebuild ``analysis_runs`` without the watchlist columns."""
    _replace_analysis_runs(with_watchlist=False)
