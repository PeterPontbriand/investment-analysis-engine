"""The typed strategy documents: required keys, exact numbers, enumerations kept in step and versions kept distinct."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.security_identity import IdentityResolutionStatus, SecurityIdentity, SecurityIdentityResolution
from src.reporting.documents.shared_parts import (
    DiagnosticPart,
    MetricResultPart,
    resolved_input_part,
    security_identity_part,
)
from src.strategies.fcf_growth import envelope as fcf_envelope
from src.strategies.momentum import envelope as momentum_envelope
from src.strategy_wiring import FCF_GROWTH, STRATEGIES
from tests._strategy_document_output import expected_path

_STAMP = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _models(model: type[BaseModel], seen: set[type[BaseModel]]) -> set[type[BaseModel]]:
    """Return ``model`` and every document model nested in it."""
    if model in seen:
        return seen
    seen.add(model)
    for field in model.model_fields.values():
        stack = [field.annotation]
        while stack:
            node = stack.pop()
            if isinstance(node, type) and issubclass(node, BaseModel):
                _models(node, seen)
            stack.extend(getattr(node, "__args__", ()))
    return seen


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_every_field_of_a_strategy_document_is_required(descriptor: object) -> None:
    """An absent value is an explicit null, never an omitted key, so no field carries a default."""
    models = _models(descriptor.json_envelope, set())  # type: ignore[attr-defined]
    optional = sorted(
        f"{model.__name__}.{name}"
        for model in models
        for name, field in model.model_fields.items()
        if not field.is_required()
    )
    assert optional == []


def test_a_document_model_rejects_a_key_it_does_not_declare() -> None:
    """The documents are closed: an undeclared key fails validation instead of being written."""
    with pytest.raises(ValidationError, match="Extra inputs"):
        DiagnosticPart.model_validate(
            {"field_name": "a", "stage": "b", "outcome": "c", "message": "d", "provider_id": "e"}
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_document_never_carries_a_non_finite_number(value: float) -> None:
    """NaN and infinity are rejected at the output boundary, as the JSON writer already rejects them."""
    with pytest.raises(ValidationError):
        MetricResultPart(status="ok", value=value, reason_code=None, reason=None)  # type: ignore[arg-type]


@pytest.mark.parametrize(("value", "written"), [(5, "5"), (5.0, "5.0"), (0.1, "0.1")])
def test_a_resolved_input_value_is_written_as_the_source_holds_it(value: float, written: str) -> None:
    """A float-typed source may hold an integer; the document writes ``5``, not ``5.0``, as the builders always did."""
    source = ResolvedInput("eps", value, SourceKind.OVERRIDE, _STAMP)
    part = resolved_input_part(source)
    assert part is not None
    assert json.dumps(part.model_dump(mode="json")["value"]) == written


def test_a_momentum_data_date_is_a_date_and_an_analysis_instant_carries_its_offset() -> None:
    """The data's last observation is a calendar date; the analysis time is an instant written with ``+00:00``."""
    stored = json.loads(expected_path("momentum-success.direct").read_bytes())
    assert "as_of" not in stored
    assert stored["source"]["data_as_of"] == "2026-01-06"
    assert momentum_envelope.MomentumSourcePart.model_fields["data_as_of"].annotation == (
        momentum_envelope.date | None  # type: ignore[attr-defined]
    )


def test_the_document_version_the_method_version_and_the_result_schema_version_are_distinct() -> None:
    """FCF Growth's document writes three unrelated versions; each is read from its own declaration."""
    document = json.loads(expected_path("fcf-growth-success.direct").read_bytes())
    assert document["schema_version"] == fcf_envelope.DOCUMENT_SCHEMA_VERSION == 7
    assert document["method_version"] == FCF_GROWTH.method_version == 2
    assert document["result_schema_version"] == FCF_GROWTH.result_schema_version == 4
    assert len({document["schema_version"], document["method_version"], document["result_schema_version"]}) == 3


def test_each_stored_document_declares_the_version_of_its_envelope() -> None:
    """The version a presenter writes is the envelope's constant, for every strategy."""
    for descriptor in STRATEGIES:
        import importlib  # noqa: PLC0415 - read per strategy

        module = importlib.import_module(descriptor.json_envelope.__module__)
        stored = json.loads(expected_path(f"{descriptor.alias}-success.direct").read_bytes())
        assert stored["schema_version"] == module.DOCUMENT_SCHEMA_VERSION


def test_the_identity_part_rejects_a_blank_ticker_and_an_identity_for_another_ticker() -> None:
    """The ticker a document names must be the ticker of the identity it carries."""
    resolution = SecurityIdentityResolution(
        IdentityResolutionStatus.RESOLVED, SecurityIdentity("KO", "yfinance", _STAMP), "Resolved."
    )
    assert security_identity_part(" ko ", resolution).ticker == "KO"
    with pytest.raises(ValueError, match="non-empty"):
        security_identity_part("  ", None)
    with pytest.raises(ValueError, match="does not match"):
        security_identity_part("PEP", resolution)
