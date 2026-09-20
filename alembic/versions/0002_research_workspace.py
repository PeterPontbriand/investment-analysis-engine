"""Create the Step 3.4 research-workspace tables.

Revision ID: 0002_research_workspace
Revises: 0001_persistence

This revision is a frozen schema snapshot; never import mutable application metadata.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0002_research_workspace"
down_revision: str = "0001_persistence"
branch_labels: str | None = None
depends_on: str | None = None

_UTC = (
    "length({0}) = 27 AND {0} GLOB "
    "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]."
    "[0-9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime({0}) IS NOT NULL"
)


def upgrade() -> None:
    """Create watchlist and append-only Analysis Run storage."""
    op.create_table(
        "watchlists",
        sa.Column("watchlist_id", sa.TEXT(), nullable=False),
        sa.Column("normalized_name", sa.TEXT(), nullable=False),
        sa.Column("display_name", sa.TEXT(), nullable=False),
        sa.Column("created_at", sa.TEXT(), nullable=False),
        sa.Column("updated_at", sa.TEXT(), nullable=True),
        sa.PrimaryKeyConstraint("watchlist_id", name="pk_watchlists"),
        sa.UniqueConstraint("normalized_name", name="uq_watchlists_1"),
        sa.CheckConstraint("length(trim(watchlist_id)) > 0", name="ck_watchlists_watchlist_id_nonempty"),
        sa.CheckConstraint("length(trim(normalized_name)) > 0", name="ck_watchlists_normalized_name_nonempty"),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_watchlists_display_name_nonempty"),
        sa.CheckConstraint(_UTC.format("created_at"), name="ck_watchlists_created_at_utc"),
        sa.CheckConstraint(f"updated_at IS NULL OR ({_UTC.format('updated_at')})", name="ck_watchlists_updated_at_utc"),
        sa.CheckConstraint("updated_at IS NULL OR updated_at >= created_at", name="ck_watchlists_timestamp_order"),
    )
    op.create_table(
        "watchlist_members",
        sa.Column("watchlist_id", sa.TEXT(), nullable=False),
        sa.Column("ticker", sa.TEXT(), nullable=False),
        sa.Column("position", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("watchlist_id", "ticker", name="pk_watchlist_members"),
        sa.UniqueConstraint("watchlist_id", "position", name="uq_watchlist_members_1"),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.watchlist_id"],
            ondelete="CASCADE",
            name="fk_watchlist_members_watchlist_id",
        ),
        sa.CheckConstraint("length(trim(watchlist_id)) > 0", name="ck_watchlist_members_watchlist_id_nonempty"),
        sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_watchlist_members_ticker_nonempty"),
        sa.CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0", name="ck_watchlist_members_position_range"
        ),
    )
    op.create_table(
        "watchlist_selections",
        sa.Column("watchlist_id", sa.TEXT(), nullable=False),
        sa.Column("method_id", sa.TEXT(), nullable=False),
        sa.Column("position", sa.INTEGER(), nullable=False),
        sa.Column("config_schema_version", sa.INTEGER(), nullable=False),
        sa.Column("selection_json", sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint("watchlist_id", "method_id", name="pk_watchlist_selections"),
        sa.UniqueConstraint("watchlist_id", "position", name="uq_watchlist_selections_1"),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.watchlist_id"],
            ondelete="CASCADE",
            name="fk_watchlist_selections_watchlist_id",
        ),
        sa.CheckConstraint("length(trim(watchlist_id)) > 0", name="ck_watchlist_selections_watchlist_id_nonempty"),
        sa.CheckConstraint("length(trim(method_id)) > 0", name="ck_watchlist_selections_method_id_nonempty"),
        sa.CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0", name="ck_watchlist_selections_position_range"
        ),
        sa.CheckConstraint(
            "typeof(config_schema_version) = 'integer' AND config_schema_version >= 1",
            name="ck_watchlist_selections_config_schema_version_range",
        ),
        sa.CheckConstraint(
            "json_valid(selection_json) AND json_type(selection_json) = 'object'",
            name="ck_watchlist_selections_selection_json_object",
        ),
    )
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
        sa.CheckConstraint(
            "outcome IN ('completed', 'unavailable', 'not_applicable', 'failed', 'cancelled')",
            name="ck_analysis_runs_outcome_enum",
        ),
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
    op.create_index("ix_analysis_runs_ticker", "analysis_runs", ["ticker"])
    op.create_index("ix_analysis_runs_method_id", "analysis_runs", ["method_id"])
    op.create_index("ix_analysis_runs_outcome", "analysis_runs", ["outcome"])
    op.create_index("ix_analysis_runs_completed", "analysis_runs", ["completed_at", "analysis_run_id"])
    op.create_index("ix_analysis_runs_refresh", "analysis_runs", ["refresh_id", "batch_position"])


def downgrade() -> None:
    """Remove workspace tables while retaining predecessor persistence data."""
    op.drop_table("analysis_runs")
    op.drop_table("watchlist_selections")
    op.drop_table("watchlist_members")
    op.drop_table("watchlists")
