"""Remove the unproduced ``cancelled`` value from the analysis-run outcome check constraint.

Revision ID: 0005_remove_cancelled_outcome
Revises: 0004_instrument_profiles

No code ever wrote a cancelled run. SQLite cannot alter a check constraint in place, so this revision
recreates ``analysis_runs`` with an outcome constraint that omits ``cancelled``, keeps every row, and recreates
the indexes. Nothing references ``analysis_runs``, so no other table is affected.

Upgrade refuses, and the shared migration transaction rolls back, if a stored run still holds the outcome
``cancelled``: such a row cannot satisfy the new constraint and is never silently dropped or rewritten.
Downgrade restores the wider constraint; every row satisfies it.

This revision is a frozen schema snapshot; never import mutable application metadata.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_remove_cancelled_outcome"
down_revision: str = "0004_instrument_profiles"
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
_OUTCOMES = ("completed", "unavailable", "not_applicable", "failed")


def _outcome_constraint(outcomes: Sequence[str]) -> str:
    return "outcome IN (" + ", ".join(f"'{item}'" for item in outcomes) + ")"


def _replace_analysis_runs(outcomes: Sequence[str]) -> None:
    """Rebuild ``analysis_runs`` with the given outcome values, keeping every row and index.

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
        sa.PrimaryKeyConstraint("analysis_run_id", name="pk_analysis_runs"),
        sa.CheckConstraint("length(trim(analysis_run_id)) > 0", name="ck_analysis_runs_analysis_run_id_nonempty"),
        sa.CheckConstraint(
            "refresh_id IS NULL OR length(trim(refresh_id)) > 0", name="ck_analysis_runs_refresh_id_nonempty"
        ),
        sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_analysis_runs_ticker_nonempty"),
        sa.CheckConstraint("length(trim(analysis_id)) > 0", name="ck_analysis_runs_analysis_id_nonempty"),
        sa.CheckConstraint("length(trim(method_id)) > 0", name="ck_analysis_runs_method_id_nonempty"),
        sa.CheckConstraint(_outcome_constraint(outcomes), name="ck_analysis_runs_outcome_enum"),
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
    )
    op.execute(f"INSERT INTO analysis_runs ({columns}) SELECT {columns} FROM analysis_runs_backup")  # noqa: S608
    op.drop_table("analysis_runs_backup")
    op.create_index("ix_analysis_runs_ticker", "analysis_runs", ["ticker"])
    op.create_index("ix_analysis_runs_method_id", "analysis_runs", ["method_id"])
    op.create_index("ix_analysis_runs_outcome", "analysis_runs", ["outcome"])
    op.create_index("ix_analysis_runs_completed", "analysis_runs", ["completed_at", "analysis_run_id"])
    op.create_index("ix_analysis_runs_refresh", "analysis_runs", ["refresh_id", "batch_position"])


def upgrade() -> None:
    """Rebuild ``analysis_runs`` without ``cancelled``, refusing if a stored run still has it."""
    held = op.get_bind().exec_driver_sql("SELECT count(*) FROM analysis_runs WHERE outcome = 'cancelled'").scalar_one()
    if held:
        msg = f"{held} stored analysis run(s) hold the outcome 'cancelled', which no longer exists."
        raise RuntimeError(msg)
    _replace_analysis_runs(_OUTCOMES)


def downgrade() -> None:
    """Rebuild ``analysis_runs`` with the wider outcome constraint."""
    _replace_analysis_runs((*_OUTCOMES, "cancelled"))
