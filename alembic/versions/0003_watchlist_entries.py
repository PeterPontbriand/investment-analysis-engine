"""Replace watchlist_members/watchlist_selections with one watchlist_entries table.

Revision ID: 0003_watchlist_entries
Revises: 0002_research_workspace

Amendment A1 (docs/project/milestones/v0.2/step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md,
section 12): a watchlist holds one ordered list of (ticker, selection) entries
instead of a separate ticker-membership list and a one-selection-per-method
list. This revision is a frozen schema snapshot; never import mutable
application metadata.

Upgrade is lossless: every existing watchlist's member-position-then-
selection-position cross product becomes its entries list, in that exact
order, so a watchlist created under the superseded model is unaffected.

Downgrade first verifies every watchlist's entries still form a clean
ticker x selection cross product (each ticker paired with every selection,
each method configured identically across every ticker that has it, no
duplicates). A watchlist that has since diverged - the same method
configured differently for different tickers, a ticker missing a selection
another ticker has, or a method appearing more than once for one ticker -
cannot be represented in the superseded shape at all, so the downgrade
raises rather than silently dropping or corrupting that data.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0003_watchlist_entries"
down_revision: str = "0002_research_workspace"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create watchlist_entries, migrate existing rows, then drop the old tables."""
    op.create_table(
        "watchlist_entries",
        sa.Column("watchlist_id", sa.TEXT(), nullable=False),
        sa.Column("position", sa.INTEGER(), nullable=False),
        sa.Column("ticker", sa.TEXT(), nullable=False),
        sa.Column("method_id", sa.TEXT(), nullable=False),
        sa.Column("config_schema_version", sa.INTEGER(), nullable=False),
        sa.Column("selection_json", sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint("watchlist_id", "position", name="pk_watchlist_entries"),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.watchlist_id"],
            ondelete="CASCADE",
            name="fk_watchlist_entries_watchlist_id",
        ),
        sa.CheckConstraint("length(trim(watchlist_id)) > 0", name="ck_watchlist_entries_watchlist_id_nonempty"),
        sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_watchlist_entries_ticker_nonempty"),
        sa.CheckConstraint("length(trim(method_id)) > 0", name="ck_watchlist_entries_method_id_nonempty"),
        sa.CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0", name="ck_watchlist_entries_position_range"
        ),
        sa.CheckConstraint(
            "typeof(config_schema_version) = 'integer' AND config_schema_version >= 1",
            name="ck_watchlist_entries_config_schema_version_range",
        ),
        sa.CheckConstraint(
            "json_valid(selection_json) AND json_type(selection_json) = 'object'",
            name="ck_watchlist_entries_selection_json_object",
        ),
    )

    connection = op.get_bind()
    watchlist_ids = [row[0] for row in connection.exec_driver_sql("SELECT watchlist_id FROM watchlists").fetchall()]
    for watchlist_id in watchlist_ids:
        members = connection.exec_driver_sql(
            "SELECT ticker FROM watchlist_members WHERE watchlist_id = ? ORDER BY position", (watchlist_id,)
        ).fetchall()
        selections = connection.exec_driver_sql(
            "SELECT method_id, config_schema_version, selection_json FROM watchlist_selections "
            "WHERE watchlist_id = ? ORDER BY position",
            (watchlist_id,),
        ).fetchall()
        position = 0
        for (ticker,) in members:
            for method_id, config_schema_version, selection_json in selections:
                connection.exec_driver_sql(
                    "INSERT INTO watchlist_entries "
                    "(watchlist_id, position, ticker, method_id, config_schema_version, selection_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (watchlist_id, position, ticker, method_id, config_schema_version, selection_json),
                )
                position += 1

    op.drop_table("watchlist_selections")
    op.drop_table("watchlist_members")


def downgrade() -> None:
    """Recreate watchlist_members/watchlist_selections, rejecting a diverged watchlist."""
    connection = op.get_bind()
    watchlist_ids = [row[0] for row in connection.exec_driver_sql("SELECT watchlist_id FROM watchlists").fetchall()]

    per_watchlist_rows: dict[str, list[tuple[str, str, int, str]]] = {}
    for watchlist_id in watchlist_ids:
        rows = connection.exec_driver_sql(
            "SELECT ticker, method_id, config_schema_version, selection_json FROM watchlist_entries "
            "WHERE watchlist_id = ? ORDER BY position",
            (watchlist_id,),
        ).fetchall()
        per_watchlist_rows[watchlist_id] = [tuple(row) for row in rows]  # type: ignore[misc]

        tickers = sorted({row[0] for row in rows})
        selection_by_method: dict[str, tuple[int, str]] = {}
        for _ticker, method_id, config_schema_version, selection_json in rows:
            key = (config_schema_version, selection_json)
            if method_id in selection_by_method and selection_by_method[method_id] != key:
                raise RuntimeError(
                    f"Watchlist {watchlist_id} has method {method_id!r} configured differently across "
                    "tickers and cannot be downgraded to the one-selection-per-method schema."
                )
            selection_by_method[method_id] = key
        if len(rows) != len(tickers) * len(selection_by_method):
            raise RuntimeError(
                f"Watchlist {watchlist_id} does not form a clean ticker x selection cross product "
                "(a ticker is missing a selection another ticker has, or an entry is duplicated) and "
                "cannot be downgraded to the one-selection-per-method schema."
            )

    op.create_table(
        "watchlist_members",
        sa.Column("watchlist_id", sa.TEXT(), nullable=False),
        sa.Column("ticker", sa.TEXT(), nullable=False),
        sa.Column("position", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("watchlist_id", "ticker", name="pk_watchlist_members"),
        sa.UniqueConstraint("watchlist_id", "position", name="uq_watchlist_members_1"),
        sa.ForeignKeyConstraint(
            ["watchlist_id"], ["watchlists.watchlist_id"], ondelete="CASCADE", name="fk_watchlist_members_watchlist_id"
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

    for watchlist_id, rows in per_watchlist_rows.items():
        seen_tickers: dict[str, int] = {}
        seen_methods: dict[str, int] = {}
        for ticker, method_id, config_schema_version, selection_json in rows:
            if ticker not in seen_tickers:
                seen_tickers[ticker] = len(seen_tickers)
                connection.exec_driver_sql(
                    "INSERT INTO watchlist_members (watchlist_id, ticker, position) VALUES (?, ?, ?)",
                    (watchlist_id, ticker, seen_tickers[ticker]),
                )
            if method_id not in seen_methods:
                seen_methods[method_id] = len(seen_methods)
                connection.exec_driver_sql(
                    "INSERT INTO watchlist_selections "
                    "(watchlist_id, method_id, position, config_schema_version, selection_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (watchlist_id, method_id, seen_methods[method_id], config_schema_version, selection_json),
                )

    op.drop_table("watchlist_entries")
