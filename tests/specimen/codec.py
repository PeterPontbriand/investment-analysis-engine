"""The specimen's strict codec for its evidence."""

from datetime import datetime

from investment_analysis_engine.analysis.run_models import StrictJsonMapping
from tests.specimen.analyzer import SpecimenResult

_FIELDS = frozenset({"ticker", "value", "multiplier", "scaled", "effective_as_of"})


def encode_specimen(evidence: SpecimenResult) -> StrictJsonMapping:
    """Capture a detached finite JSON snapshot of ``evidence``."""
    return {
        "ticker": evidence.ticker,
        "value": evidence.value,
        "multiplier": evidence.multiplier,
        "scaled": evidence.scaled,
        "effective_as_of": evidence.effective_as_of.isoformat(),
    }


def _number(payload: StrictJsonMapping, key: str) -> float:
    """Return the number stored under ``key``, rejecting any other kind of value."""
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise ValueError(f"Specimen {key} must be a number.")
    return float(value)


def decode_specimen(payload: StrictJsonMapping) -> SpecimenResult:
    """Reconstruct the evidence without any calculation, rejecting an unknown, missing or ill-typed key."""
    if set(payload) != _FIELDS:
        raise ValueError("Specimen evidence has unexpected keys.")
    ticker, stamp = payload["ticker"], payload["effective_as_of"]
    if not isinstance(ticker, str) or not ticker or ticker != ticker.strip().upper():
        raise ValueError("Specimen requires a normalized ticker.")
    if not isinstance(stamp, str):
        raise ValueError("Specimen effective_as_of must be text.")
    effective_as_of = datetime.fromisoformat(stamp)
    if effective_as_of.utcoffset() is None:
        raise ValueError("Specimen effective_as_of must be timezone-aware.")
    return SpecimenResult(
        ticker=ticker,
        value=_number(payload, "value"),
        multiplier=_number(payload, "multiplier"),
        scaled=_number(payload, "scaled"),
        effective_as_of=effective_as_of,
    )


def specimen_native_status(result: SpecimenResult, /) -> str:
    """Return the status recorded as telemetry evidence: the specimen's calculation always succeeds."""
    del result
    return "ok"


def specimen_ticker(result: SpecimenResult, /) -> str:
    """Return the ticker the evidence is about, which must equal its run envelope's ticker."""
    return result.ticker
