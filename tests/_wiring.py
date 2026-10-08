"""Shared test access to the declared strategies' alias vocabulary, evidence and selection views, failure classifier."""

from collections.abc import Callable, Mapping
from dataclasses import replace

from src.core.strategy_errors import find
from src.reporting.failure_classification import classify_failure
from src.strategy_wiring import BY_METHOD_ID, EVIDENCE_BY_KEY, STRATEGIES, evidence_by_type, parsers_by_alias
from src.workspace.codecs import EvidenceCodec
from src.workspace.models import StrictJsonMapping
from src.workspace.strategy_types import NativeEvidence

EVIDENCE_BY_TYPE = evidence_by_type(STRATEGIES)
PARSERS_BY_ALIAS = parsers_by_alias(STRATEGIES)


def alias_for(method_id: str) -> str | None:
    """Return the CLI alias of a declared method identifier, or ``None`` for an undeclared one."""
    descriptor = find(BY_METHOD_ID, method_id)
    return None if descriptor is None else descriptor.alias


def codecs_with_decode(
    decode: Callable[[StrictJsonMapping, str], NativeEvidence],
) -> Mapping[tuple[str, str], EvidenceCodec]:
    """Return the declared codecs with every decoder replaced, to prove a path never reaches decoding."""
    return {key: replace(codec, decode=decode) for key, codec in EVIDENCE_BY_KEY.items()}


def failure_code(exception: BaseException) -> str:
    """Return the stable reason code the command line assigns to ``exception``, as ``refresh_watchlist`` receives it."""
    return classify_failure(exception).reason_code.value
