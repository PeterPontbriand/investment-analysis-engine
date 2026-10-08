"""Shared test access to the declared strategies' alias vocabulary, evidence encoding and the failure classifier."""

from collections.abc import Callable, Mapping
from dataclasses import replace

from src.core.strategy_errors import find
from src.reporting.failure_classification import classify_failure
from src.strategy_wiring import BY_METHOD_ID, BY_RESULT_TYPE, EVIDENCE_BY_KEY, RUN_SPECS_BY_KEY
from src.workspace.codecs import EvidenceCodec
from src.workspace.models import StrictJsonMapping
from src.workspace.strategy_types import NativeEvidence


def encode_native(evidence: NativeEvidence) -> StrictJsonMapping:
    """Encode declared evidence as a run would: through its strategy's run spec, found by its exact result type."""
    descriptor = BY_RESULT_TYPE[type(evidence)]
    return RUN_SPECS_BY_KEY[(descriptor.analysis_id, descriptor.method_id)].encode(evidence)


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
