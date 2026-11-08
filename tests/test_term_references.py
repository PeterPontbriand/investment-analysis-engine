"""Every code, label and field the API returns names a glossary term, and every named term is served.

The walk reads ``schemas/openapi.json``: each enumeration of more than one value resolves to the term table of its code
set, and every value of it has a term the help bundle holds. The orphan check requires every served term to be named by
a table, a headline cell, a strategy or a selection field, or to be linked from served content.
"""

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import replace
from typing import Any, Final

import pytest

from investment_analysis_engine.api.term_references import EXEMPT_CODE_SETS, EXEMPT_LOCATIONS, SHARED_CODE_TERMS
from investment_analysis_engine.help.bundle import TERM_LINK_PREFIX, HelpBundle, load_help_bundle
from investment_analysis_engine.reporting.headline import CELL_STATUS_TERMS
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from scripts.generate_openapi import openapi_description
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_conformance import PRODUCTION, SiteContext, site_glossary_terms
from scripts.strategy_sites import strategy_names

_SELECTION_DIRECTORY: Final = "schemas/selections"


def _bundle() -> HelpBundle:
    return load_help_bundle()


type Path = tuple[str | int, ...]


def _enumerations(node: Any, path: Path = ()) -> Iterator[tuple[Path, list[Any]]]:
    """Yield the path and values of every enumeration of more than one value in a JSON document."""
    if isinstance(node, dict):
        values = node.get("enum")
        if isinstance(values, list) and len(values) > 1:
            yield path, values
        for key, item in node.items():
            yield from _enumerations(item, (*path, key))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _enumerations(item, (*path, index))


def _location(path: Path, description: dict[str, Any]) -> str:
    """Name where an enumeration sits: its component, or its parameter as ``<location>:<name>``."""
    if path[:2] == ("components", "schemas") and len(path) == 3:
        return str(path[2])
    if path[0] == "paths" and "parameters" in path:
        node: Any = description
        for step in path[: path.index("parameters") + 2]:
            node = node[step]
        return f"{node['in']}:{node['name']}"
    return f"inline:{'/'.join(map(str, path))}"


def _tables() -> dict[str, Mapping[str, str]]:
    """Return every code-set table by OpenAPI component name: the shared ones and each strategy's own."""
    tables: dict[str, Mapping[str, str]] = dict(SHARED_CODE_TERMS)
    for descriptor in STRATEGIES:
        for component, table in descriptor.code_terms.items():
            assert component not in tables, f"the component {component} has two term tables"
            tables[component] = table
    return tables


def test_every_enumeration_in_the_api_names_a_term_for_each_value() -> None:
    description = openapi_description()
    tables = _tables()
    served = set(_bundle().terms)
    problems: list[str] = []
    seen_components: set[str] = set()
    for path, values in _enumerations(description):
        location = _location(path, description)
        if location in EXEMPT_LOCATIONS:
            assert EXEMPT_LOCATIONS[location] in EXEMPT_CODE_SETS
            continue
        seen_components.add(location)
        table = tables.get(location)
        if table is None:
            problems.append(f"{location}: a code set of {len(values)} values has no term table")
            continue
        if set(table) != {str(value) for value in values}:
            problems.append(f"{location}: the table's values {sorted(table)} differ from the schema's {sorted(values)}")
        problems.extend(
            f"{location}: the value {value!r} names the term {term!r}, which the help bundle does not hold"
            for value, term in table.items()
            if term not in served
        )
    assert problems == []
    assert set(tables) == seen_components, "a term table names a component the API description does not hold"


def test_the_exemptions_are_exactly_the_four_decided_and_each_is_used() -> None:
    assert set(EXEMPT_CODE_SETS) == {
        "schema_version",
        "headline cell kind",
        "replay text mode",
        "method_id path parameter",
    }
    assert all(reason.strip() for reason in EXEMPT_CODE_SETS.values())
    description = openapi_description()
    locations = {_location(path, description) for path, _values in _enumerations(description)}
    assert set(EXEMPT_LOCATIONS) <= locations
    assert set(EXEMPT_LOCATIONS.values()) | {"schema_version"} == set(EXEMPT_CODE_SETS)


def test_no_schema_version_is_an_enumeration() -> None:
    versions = [
        schema["properties"]["schema_version"]
        for schema in openapi_description()["components"]["schemas"].values()
        if "schema_version" in schema.get("properties", {})
    ]
    assert versions
    assert all("enum" not in item for item in versions)


def test_the_cell_status_table_gives_a_value_both_status_types_share_the_same_term() -> None:
    calculation = SHARED_CODE_TERMS["CalculationStatus"]
    metric = SHARED_CODE_TERMS["MetricStatus"]
    shared = set(calculation) & set(metric)
    assert shared == {"ok", "not_applicable"}
    assert all(calculation[value] == metric[value] for value in shared)
    assert set(CELL_STATUS_TERMS) == set(calculation) | set(metric)
    merged = {**calculation, **metric}
    assert all(CELL_STATUS_TERMS[value] == merged[value] for value in CELL_STATUS_TERMS)


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_strategys_headline_cells_carry_the_terms_it_declares(descriptor: StrategyDescriptor) -> None:
    stored = PRODUCTION.stored_run(descriptor)
    assert stored is not None
    cells = descriptor.behavior.headline_for(stored.result).cells
    served = set(_bundle().terms)
    assert cells
    for cell in cells:
        assert cell.term == descriptor.headline_terms[cell.key]
        assert cell.term in served
    assert set(descriptor.headline_terms) >= {cell.key for cell in cells}


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_strategys_own_term_and_selection_fields_name_served_terms(descriptor: StrategyDescriptor) -> None:
    served = set(_bundle().terms)
    assert descriptor.term in served
    schema = json.loads(
        (REPOSITORY_ROOT / _SELECTION_DIRECTORY / f"{descriptor.alias}.schema.json").read_text(encoding="utf-8")
    )
    fields = list(_selection_properties(schema))
    assert fields
    for name, definition in fields:
        assert definition.get("x-term") in served, f"the selection field {name} names no served term"


def _selection_properties(schema: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield every property of the selection schema and of each model defined inside it."""
    for name, definition in schema.get("properties", {}).items():
        yield name, definition
    for model in schema.get("$defs", {}).values():
        for name, definition in model.get("properties", {}).items():
            yield name, definition


def _named_terms() -> set[str]:
    """Return every term a table, a headline cell, a strategy or a selection field names."""
    named: set[str] = set()
    for table in _tables().values():
        named.update(table.values())
    for descriptor in STRATEGIES:
        named.add(descriptor.term)
        named.update(descriptor.headline_terms.values())
        schema = json.loads(
            (REPOSITORY_ROOT / _SELECTION_DIRECTORY / f"{descriptor.alias}.schema.json").read_text(encoding="utf-8")
        )
        named.update(str(definition["x-term"]) for _name, definition in _selection_properties(schema))
    return named


def _linked_terms(bundle: HelpBundle) -> set[str]:
    """Return the terms that served content links to, a term's links to itself left out."""
    pattern = re.compile(r"\]\(" + re.escape(TERM_LINK_PREFIX) + r"([a-z0-9-]+)")
    linked: set[str] = set()
    for term_id, term in bundle.terms.items():
        linked.update(item for item in pattern.findall(f"{term.definition}\n{term.body}") if item != term_id)
    for document in bundle.documents.values():
        linked.update(pattern.findall(document.introduction))
        for section in document.sections:
            linked.update(pattern.findall(section.markdown))
    return linked


def test_no_served_term_is_an_orphan() -> None:
    bundle = _bundle()
    referenced = _named_terms() | _linked_terms(bundle)
    assert sorted(set(bundle.terms) - referenced) == []


def test_the_glossary_site_fails_a_missing_or_unknown_term() -> None:
    names = strategy_names("momentum")
    assert site_glossary_terms(names) == []

    def context_with(descriptor: StrategyDescriptor) -> SiteContext:
        others = tuple(item for item in STRATEGIES if item.alias != descriptor.alias)
        return replace(
            PRODUCTION,
            descriptors=(descriptor, *others),
            stored_run=lambda _item: PRODUCTION.stored_run(
                next(item for item in STRATEGIES if item.alias == "momentum")
            ),
        )

    momentum = next(item for item in STRATEGIES if item.alias == "momentum")
    unknown_strategy = site_glossary_terms(names, context_with(replace(momentum, term="no-such-term")))
    assert any("the strategy names the term 'no-such-term'" in gap.message for gap in unknown_strategy)
    blank_cell = site_glossary_terms(
        names, context_with(replace(momentum, headline_terms={"trend": " ", "rsi": "rsi"}))
    )
    assert any("the headline cell trend names no term" in gap.message for gap in blank_cell)
    unknown_value = site_glossary_terms(
        names, context_with(replace(momentum, code_terms={"PriceBasis": {"latest_historical_close": "nowhere"}}))
    )
    assert any(
        "PriceBasis value latest_historical_close names the term 'nowhere'" in gap.message for gap in unknown_value
    )
    wrong_cell = site_glossary_terms(
        names, context_with(replace(momentum, headline_terms={"trend": "rsi", "rsi": "rsi"}))
    )
    assert any("headline cell trend carries the term" in gap.message for gap in wrong_cell)
