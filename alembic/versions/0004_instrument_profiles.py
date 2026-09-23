"""Create the durable instrument_profiles table (P2-Profiles).

Revision ID: 0004_instrument_profiles
Revises: 0003_watchlist_entries

Only identity-anchored resolutions are durable (P2-Profiles Gate A, §9-4 of
docs/project/milestones/v0.2/p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md):
this table has no "unverified" row shape. Ticker reuse is represented by
superseding the prior row (superseded_at/superseded_reason) and inserting a
new profile_id rather than mutating identity in place; "current profile for a
ticker" is `ticker = ? AND superseded_at IS NULL`, enforced by the repository
inside one transaction rather than a partial/expression unique index, since
this project's readiness contract (Step 3.3A) treats such indexes as not
interchangeable with the supported schema signature.

This revision is a frozen schema snapshot; never import mutable application
metadata.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0004_instrument_profiles"
down_revision: str = "0003_watchlist_entries"
branch_labels: str | None = None
depends_on: str | None = None

_UTC = (
    "length({0}) = 27 AND {0} GLOB "
    "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]."
    "[0-9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime({0}) IS NOT NULL"
)


def upgrade() -> None:
    """Create instrument_profiles and its ticker lookup index."""
    op.create_table(
        "instrument_profiles",
        sa.Column("profile_id", sa.TEXT(), nullable=False),
        sa.Column("ticker", sa.TEXT(), nullable=False),
        sa.Column("identity_anchor", sa.TEXT(), nullable=False),
        sa.Column("cached_at", sa.TEXT(), nullable=False),
        sa.Column("refreshed_at", sa.TEXT(), nullable=False),
        sa.Column("superseded_at", sa.TEXT(), nullable=True),
        sa.Column("superseded_reason", sa.TEXT(), nullable=True),
        sa.Column("schema_version", sa.INTEGER(), nullable=False),
        sa.Column("evidence_json", sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", name="pk_instrument_profiles"),
        sa.CheckConstraint("length(trim(profile_id)) > 0", name="ck_instrument_profiles_profile_id_nonempty"),
        sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_instrument_profiles_ticker_nonempty"),
        sa.CheckConstraint("length(trim(identity_anchor)) > 0", name="ck_instrument_profiles_identity_anchor_nonempty"),
        sa.CheckConstraint(_UTC.format("cached_at"), name="ck_instrument_profiles_cached_at_utc"),
        sa.CheckConstraint(_UTC.format("refreshed_at"), name="ck_instrument_profiles_refreshed_at_utc"),
        sa.CheckConstraint(
            f"superseded_at IS NULL OR ({_UTC.format('superseded_at')})",
            name="ck_instrument_profiles_superseded_at_utc",
        ),
        sa.CheckConstraint("refreshed_at >= cached_at", name="ck_instrument_profiles_refreshed_after_cached"),
        sa.CheckConstraint(
            "superseded_at IS NULL OR superseded_at >= refreshed_at",
            name="ck_instrument_profiles_superseded_after_refreshed",
        ),
        sa.CheckConstraint(
            "(superseded_at IS NULL AND superseded_reason IS NULL) OR "
            "(superseded_at IS NOT NULL AND length(trim(superseded_reason)) > 0)",
            name="ck_instrument_profiles_supersede_pair",
        ),
        sa.CheckConstraint(
            "typeof(schema_version) = 'integer' AND schema_version >= 1",
            name="ck_instrument_profiles_schema_version_range",
        ),
        sa.CheckConstraint(
            "json_valid(evidence_json) AND json_type(evidence_json) = 'object'",
            name="ck_instrument_profiles_evidence_json_object",
        ),
    )
    op.create_index("ix_instrument_profiles_ticker", "instrument_profiles", ["ticker"])


def downgrade() -> None:
    """Drop instrument_profiles; no predecessor data depends on it."""
    op.drop_table("instrument_profiles")
