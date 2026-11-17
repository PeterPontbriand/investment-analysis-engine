"""Every selection field carries the label its form shows, as the JSON Schema ``title``, and one label per name."""

import copy
from typing import Any

import pytest
from pydantic import BaseModel, Field

from investment_analysis_engine.application.selections import selection_schema
from investment_analysis_engine.strategy_wiring import FCF_GROWTH, MOMENTUM, STRATEGIES, StrategyDescriptor
from scripts import strategy_conformance as conformance
from tests.test_selection_conformance import _entry_of

_LABELS = {
    "as_of": "As of",
    "use_cache": "Use cached data",
    "short_window": "Short window",
    "long_window": "Long window",
    "rsi_period": "RSI period",
    "bvps_override": "Book value per share override",
    "eps_override": "Earnings per share override",
    "quote_override": "Share price override",
    "expected_growth": "Expected growth rate",
    "aaa_yield_override": "AAA corporate bond yield",
    "eps_basis": "EPS basis",
    "currency": "Reporting currency",
    "policy": "Growth policy",
    "policy.classification_basis": "Classification basis",
    "policy.forward_policy": "Forward policy",
    "policy.historical_horizon": "Historical horizon",
}


def _titles(schema: dict[str, Any], properties: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Return the title of every property by dotted name, following a nested group through its ``$ref``."""
    found: dict[str, str] = {}
    for name, prop in properties.items():
        found[f"{prefix}{name}"] = prop["title"]
        ref = prop.get("$ref") or next((item["$ref"] for item in prop.get("allOf", []) if "$ref" in item), None)
        if ref is not None:
            nested = schema["$defs"][ref.rsplit("/", 1)[1]]
            if "properties" in nested:
                found.update(_titles(schema, nested["properties"], f"{prefix}{name}."))
    return found


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_every_served_selection_field_carries_its_label_as_the_schema_title(descriptor: StrategyDescriptor) -> None:
    schema = selection_schema(descriptor)

    titles = _titles(schema, schema["properties"])

    assert titles
    assert titles == {name: _LABELS[name] for name in titles}


def _untitled_model() -> type[BaseModel]:
    class Untitled(BaseModel):
        threshold: int = Field(default=1, description="A threshold.")

    return Untitled


def test_a_selection_field_without_a_title_or_with_a_blank_one_is_reported() -> None:
    gaps: list[str] = []
    titles: dict[str, dict[str, list[str]]] = {}
    info = _untitled_model().model_fields["threshold"]

    gaps.extend(conformance._record_title(titles, "demo", "threshold", info.title))
    gaps.extend(conformance._record_title(titles, "demo", "other", "   "))

    assert gaps == [
        "strategy demo: the selection field threshold declares no title",
        "strategy demo: the selection field other declares no title",
    ]
    assert titles == {}


def test_a_field_name_with_different_titles_in_two_strategies_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    real = conformance._selection_field_infos

    def retitled(model: type[BaseModel], prefix: str = "") -> dict[str, Any]:
        infos = real(model, prefix)
        if model is MOMENTUM.behavior.selection_type and not prefix:
            infos = dict(infos)
            infos["as_of"] = copy.copy(infos["as_of"])
            infos["as_of"].title = "Date"
        return infos

    monkeypatch.setattr(conformance, "_selection_field_infos", retitled)
    entries = (_entry_of(MOMENTUM), _entry_of(FCF_GROWTH))

    gaps = conformance.selection_options_gaps((MOMENTUM, FCF_GROWTH), entries)

    assert any(gap.startswith("the selection field as_of has different titles in different strategies") for gap in gaps)


def test_a_selection_field_the_model_leaves_untitled_is_reported_through_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = conformance._selection_field_infos

    def untitled(model: type[BaseModel], prefix: str = "") -> dict[str, Any]:
        infos = dict(real(model, prefix))
        infos["use_cache"] = copy.copy(infos["use_cache"])
        infos["use_cache"].title = None
        return infos

    monkeypatch.setattr(conformance, "_selection_field_infos", untitled)

    gaps = conformance.selection_options_gaps((MOMENTUM,), (_entry_of(MOMENTUM),))

    assert any("the selection field use_cache declares no title" in gap for gap in gaps)
