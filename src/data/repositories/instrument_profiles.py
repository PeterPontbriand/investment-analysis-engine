"""Durable instrument-profile storage with identity anchoring and ticker-reuse.

Only identity-anchored resolutions are durable, per the accepted P2-Profiles
contract (docs/project/milestones/v0.2/p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md,
Gate A §9-4): a caller that cannot supply an ``identity_anchor`` must not call
:meth:`SQLiteInstrumentProfileRepository.put` and continues to resolve live for
that ticker, exactly as ``compose_instrument_profile`` does today. This module
owns only the storage shape and the identity/supersession invariant ("at most
one current row per ticker"); provider precedence, freshness/TTL policy, and
live-resolution orchestration belong to the caller (P2-Profiles Slice C).
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import Connection, RowMapping

from src.data.repositories.schema import instrument_profiles
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.security_identity import _normalized_required

_SCHEMA_VERSION = 1


def _utc(value: datetime) -> str:
    """Encode a timezone-aware instant without guessing a missing timezone."""
    if value.utcoffset() is None:
        raise ValueError("Storage timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: Mapping[str, Any]) -> str:
    """Encode canonical Unicode JSON evidence without non-finite values."""
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class InstrumentProfileRecord:
    """One durable instrument-profile row: the current entry or a superseded one.

    ``evidence`` is an opaque, caller-supplied JSON-serializable payload (raw
    per-provider evidence and diagnostics); this repository stores and returns
    it without interpreting its shape.
    """

    profile_id: UUID
    ticker: str
    identity_anchor: str
    cached_at: datetime
    refreshed_at: datetime
    schema_version: int
    evidence: Mapping[str, Any]
    superseded_at: datetime | None = None
    superseded_reason: str | None = None

    @property
    def is_current(self) -> bool:
        """Return whether this row is the live profile for its ticker."""
        return self.superseded_at is None


def _record_from_row(row: RowMapping) -> InstrumentProfileRecord:
    """Reconstruct one typed record from a stored row, decoding its evidence."""
    return InstrumentProfileRecord(
        profile_id=UUID(row["profile_id"]),
        ticker=row["ticker"],
        identity_anchor=row["identity_anchor"],
        cached_at=datetime.fromisoformat(row["cached_at"]),
        refreshed_at=datetime.fromisoformat(row["refreshed_at"]),
        schema_version=row["schema_version"],
        evidence=json.loads(row["evidence_json"]),
        superseded_at=None if row["superseded_at"] is None else datetime.fromisoformat(row["superseded_at"]),
        superseded_reason=row["superseded_reason"],
    )


class SQLiteInstrumentProfileRepository:
    """Persist durable instrument-identity profiles with ticker-reuse supersession.

    Every public method is one short transaction; nothing is left partially
    written on failure. ``put`` reads and writes the current row for a ticker
    within a single transaction, so two overlapping refreshes cannot both
    observe "no current row" and mint two competing profiles for the same
    ticker.
    """

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        """Retain a caller-owned, already-migrated database and injected clock/ID generator."""
        self._database = database
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._id_factory = id_factory if id_factory is not None else uuid4

    def get(self, ticker: str) -> InstrumentProfileRecord | None:
        """Return the current (non-superseded) profile for ``ticker``, or None."""
        normalized_ticker = _normalized_required(ticker, "ticker", uppercase=True)
        with self._database.read() as connection:
            row = self._current_row(connection, normalized_ticker)
            return None if row is None else _record_from_row(row)

    def get_by_id(self, profile_id: UUID) -> InstrumentProfileRecord | None:
        """Return the profile with this ``profile_id``, current or superseded."""
        with self._database.read() as connection:
            statement = select(instrument_profiles).where(instrument_profiles.c.profile_id == str(profile_id))
            row = connection.execute(statement).mappings().one_or_none()
            return None if row is None else _record_from_row(row)

    def put(self, ticker: str, *, identity_anchor: str, evidence: Mapping[str, Any]) -> InstrumentProfileRecord:
        """Mint, update in place, or supersede-and-mint, per the resolved anchor.

        A matching anchor for the current row updates it in place (refreshing
        ``refreshed_at`` and the stored evidence). A disagreeing anchor is a
        ticker-reuse event: the current row is superseded and a new profile is
        minted. No current row simply mints the first profile for the ticker.

        Args:
            ticker: The instrument ticker; normalized before lookup/storage.
            identity_anchor: The resolved durable anchor (e.g. issuer CIK).
                Required and non-blank; only anchored profiles are durable.
            evidence: Opaque JSON-serializable raw evidence/diagnostics payload.

        Raises:
            ValueError: If ``ticker`` or ``identity_anchor`` normalize to empty,
                or the repository clock is not timezone-aware.
        """
        normalized_ticker = _normalized_required(ticker, "ticker", uppercase=True)
        normalized_anchor = _normalized_required(identity_anchor, "identity_anchor")
        payload = _json(evidence)
        now = self._now()
        with self._database.transaction() as connection:
            current = self._current_row(connection, normalized_ticker)
            if current is None:
                return self._insert(connection, normalized_ticker, normalized_anchor, payload, now)
            if current["identity_anchor"] == normalized_anchor:
                return self._update_in_place(connection, current, payload, now)
            return self._supersede_and_insert(connection, current, normalized_ticker, normalized_anchor, payload, now)

    def _now(self) -> datetime:
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("Instrument profile repository clock must be timezone-aware.")
        return now

    @staticmethod
    def _current_row(connection: Connection, ticker: str) -> RowMapping | None:
        """Return the non-superseded row for ``ticker``, if one exists."""
        return (
            connection.execute(
                select(instrument_profiles).where(
                    instrument_profiles.c.ticker == ticker,
                    instrument_profiles.c.superseded_at.is_(None),
                )
            )
            .mappings()
            .one_or_none()
        )

    def _insert(
        self, connection: Connection, ticker: str, anchor: str, payload: str, now: datetime
    ) -> InstrumentProfileRecord:
        """Mint a brand-new profile row; used both for first resolution and supersession."""
        profile_id = self._id_factory()
        connection.execute(
            instrument_profiles.insert().values(
                profile_id=str(profile_id),
                ticker=ticker,
                identity_anchor=anchor,
                cached_at=_utc(now),
                refreshed_at=_utc(now),
                superseded_at=None,
                superseded_reason=None,
                schema_version=_SCHEMA_VERSION,
                evidence_json=payload,
            )
        )
        return InstrumentProfileRecord(profile_id, ticker, anchor, now, now, _SCHEMA_VERSION, json.loads(payload))

    @staticmethod
    def _update_in_place(
        connection: Connection, current: RowMapping, payload: str, now: datetime
    ) -> InstrumentProfileRecord:
        """Refresh an existing row whose anchor still matches; identity is unchanged."""
        connection.execute(
            update(instrument_profiles)
            .where(instrument_profiles.c.profile_id == current["profile_id"])
            .values(refreshed_at=_utc(now), evidence_json=payload)
        )
        return InstrumentProfileRecord(
            profile_id=UUID(current["profile_id"]),
            ticker=current["ticker"],
            identity_anchor=current["identity_anchor"],
            cached_at=datetime.fromisoformat(current["cached_at"]),
            refreshed_at=now,
            schema_version=current["schema_version"],
            evidence=json.loads(payload),
        )

    def _supersede_and_insert(  # noqa: PLR0913, PLR0917
        self,
        connection: Connection,
        current: RowMapping,
        ticker: str,
        anchor: str,
        payload: str,
        now: datetime,
    ) -> InstrumentProfileRecord:
        """Retire the disagreeing current row and mint its replacement."""
        reason = f"Identity anchor changed from {current['identity_anchor']!r} to {anchor!r} for ticker {ticker!r}."
        connection.execute(
            update(instrument_profiles)
            .where(instrument_profiles.c.profile_id == current["profile_id"])
            .values(superseded_at=_utc(now), superseded_reason=reason)
        )
        return self._insert(connection, ticker, anchor, payload, now)


__all__ = ["InstrumentProfileRecord", "SQLiteInstrumentProfileRepository"]
