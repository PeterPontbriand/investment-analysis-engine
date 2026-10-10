"""Every strategy ``--json`` document begins with the shared header and ends with the shared tail.

The header and tail are declared once in ``src/reporting/documents/strategy_document.py``. These tests iterate the
descriptors, so a strategy added later is checked without editing them: its document model must take both from that
declaration, in order, and the documents it writes must keep that order.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from src.core.analysis_status import CalculationStatus
from src.core.constants import TrendStatus
from src.reporting.documents.shared_parts import DocumentPart
from src.reporting.documents.strategy_document import (
    HEADER_KEYS,
    TAIL_KEYS,
    StrategyDocumentHeader,
    StrategyDocumentTail,
)
from src.strategy_wiring import STRATEGIES
from tests._strategy_document_output import CASES, Case, cases, expected_path, run_pair

_IDENTIFIERS = ("analysis", "method")


def shape_errors(model: type[BaseModel]) -> list[str]:
    """Return how ``model`` departs from the shared header and tail; empty when it takes both from their declaration."""
    errors: list[str] = []
    names = list(model.model_fields)
    if names[: len(HEADER_KEYS)] != list(HEADER_KEYS):
        errors.append(f"document does not begin with the header keys: {names[: len(HEADER_KEYS)]}")
    if names[-len(TAIL_KEYS) :] != list(TAIL_KEYS):
        errors.append(f"document does not end with the tail keys: {names[-len(TAIL_KEYS) :]}")
    for key in HEADER_KEYS:
        declared = StrategyDocumentHeader.model_fields[key].annotation
        actual = model.model_fields[key].annotation if key in model.model_fields else None
        if key in _IDENTIFIERS:
            continue  # each strategy pins its own identifier literal; the header only requires a string
        if actual != declared:
            errors.append(f"{key} is typed {actual}, not {declared}")
    for key in TAIL_KEYS:
        declared = StrategyDocumentTail.model_fields[key].annotation
        actual = model.model_fields[key].annotation if key in model.model_fields else None
        if actual != declared:
            errors.append(f"{key} is typed {actual}, not {declared}")
    if not (issubclass(model, StrategyDocumentHeader) and issubclass(model, StrategyDocumentTail)):
        errors.append("document does not derive from the shared header and tail")
    return errors


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_every_strategy_document_takes_the_shared_header_and_tail(descriptor: Any) -> None:
    """The model, its written schema's required list and its keys all follow the shared declaration."""
    model = descriptor.json_envelope
    assert shape_errors(model) == []
    required = model.model_json_schema(mode="serialization")["required"]
    assert required[: len(HEADER_KEYS)] == list(HEADER_KEYS)
    assert required[-len(TAIL_KEYS) :] == list(TAIL_KEYS)


def test_the_conformance_check_rejects_a_document_that_does_not_conform() -> None:
    """Negative control: models that drift from the declaration are reported, so the check can fail."""

    class _Misordered(DocumentPart):
        ticker: str
        schema_version: int
        warnings: tuple[str, ...]
        limitations: tuple[str, ...]
        diagnostics: tuple[str, ...]

    class _TailFirst(StrategyDocumentHeader[str, str]):
        warnings: tuple[str, ...]

    class _Conforming(StrategyDocumentTail, StrategyDocumentHeader[str, str]):
        pass

    assert shape_errors(_Misordered)
    assert shape_errors(_TailFirst)
    # A conforming composition passes, proving the failures above come from the drift and not from the check itself.
    assert shape_errors(_Conforming) == []


def _stored_documents() -> list[str]:
    return list(cases())


@pytest.mark.parametrize("stem", _stored_documents())
def test_the_written_keys_keep_the_header_and_tail_order(stem: str) -> None:
    """The text a command writes lists the keys in the declared order, not sorted."""
    document = json.loads(expected_path(stem).read_bytes())
    keys = list(document)
    assert keys[: len(HEADER_KEYS)] == list(HEADER_KEYS)
    assert keys[-len(TAIL_KEYS) :] == list(TAIL_KEYS)


@pytest.mark.parametrize("stem", _stored_documents())
def test_status_is_a_calculation_status_never_a_verdict(stem: str) -> None:
    """``status`` says whether the calculation ran; a trend or classification verdict never appears there."""
    document = json.loads(expected_path(stem).read_bytes())
    assert document["status"] in {item.value for item in CalculationStatus}
    assert document["status"] not in {item.value for item in TrendStatus}
    if document["analysis"] == "momentum":
        assert document["result"]["trend"] in {item.value for item in TrendStatus}


def differing_paths(direct: object, replayed: object, path: str = "$") -> list[str]:
    """Return the path of every value that differs between two parsed documents, including a missing key."""
    if isinstance(direct, dict) and isinstance(replayed, dict):
        paths: list[str] = []
        for key in dict.fromkeys([*direct, *replayed]):
            if key not in direct or key not in replayed:
                paths.append(f"{path}.{key}")
            else:
                paths.extend(differing_paths(direct[key], replayed[key], f"{path}.{key}"))
        return paths
    if isinstance(direct, list) and isinstance(replayed, list) and len(direct) == len(replayed):
        return [
            difference
            for index, (left, right) in enumerate(zip(direct, replayed, strict=True))
            for difference in differing_paths(left, right, f"{path}[{index}]")
        ]
    return [] if direct == replayed else [path]


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.name)
def test_the_direct_and_replayed_documents_agree(case: Case) -> None:
    """The document a command writes and the document of its saved run's replay are the same, key for key.

    Each case runs once with ``--save-run``; both documents come from that run and the same providers, so any
    difference means the stored evidence or the replay path lost or recomputed something.
    """
    direct, replayed = run_pair(case)
    assert replayed.exit_code == 0
    assert differing_paths(json.loads(direct.stdout), json.loads(replayed.stdout)) == []
    assert direct.stdout == replayed.stdout


def test_the_comparison_fails_when_a_body_key_differs() -> None:
    """Negative control: a changed, dropped or added value anywhere in the body is reported by path."""
    direct, replayed = run_pair(next(item for item in CASES if item.name == "graham-number-success"))
    document = json.loads(direct.stdout)
    assert differing_paths(document, json.loads(replayed.stdout)) == []

    changed = json.loads(replayed.stdout)
    changed["inputs"]["eps"]["value"] += 1
    assert differing_paths(document, changed) == ["$.inputs.eps.value"]

    dropped = json.loads(replayed.stdout)
    del dropped["quote"]
    assert differing_paths(document, dropped) == ["$.quote"]

    extended = json.loads(replayed.stdout)
    extended["diagnostics"].append("extra")
    assert differing_paths(document, extended) == ["$.diagnostics"]
