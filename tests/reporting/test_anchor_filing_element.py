"""The anchor filing element of the common strategy-document header: where it sits, who writes it, who writes null."""

import json
from typing import Any

import pytest

from investment_analysis_engine.reporting.documents.shared_parts import AnchorFilingPart
from investment_analysis_engine.reporting.documents.strategy_document import HEADER_KEYS, StrategyDocumentHeader
from investment_analysis_engine.strategy_wiring import STRATEGIES
from tests._strategy_document_output import cases, expected_path

_REPORTING = {"piotroski", "fcf-growth", "graham-number", "graham-growth"}


def _documents(alias: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (stem, json.loads(expected_path(stem).read_bytes()))
        for stem in cases()
        if stem.startswith(f"{alias}-") and "stored-" not in stem
    ]


def test_the_element_follows_the_effective_time_in_the_shared_header() -> None:
    assert HEADER_KEYS.index("anchor_filing") == HEADER_KEYS.index("effective_as_of") + 1
    assert list(AnchorFilingPart.model_fields) == [
        "year_end",
        "form",
        "accession",
        "filing_date",
        "next_report_due",
        "stale",
    ]
    assert StrategyDocumentHeader.model_fields["anchor_filing"].annotation == AnchorFilingPart | None


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_every_strategy_document_declares_the_element_from_the_shared_header(descriptor: Any) -> None:
    declared = descriptor.json_envelope.model_fields["anchor_filing"].annotation
    assert declared == StrategyDocumentHeader.model_fields["anchor_filing"].annotation
    assert list(descriptor.json_envelope.model_fields).index("anchor_filing") == HEADER_KEYS.index("anchor_filing")


@pytest.mark.parametrize("alias", [item.alias for item in STRATEGIES if item.alias not in _REPORTING])
def test_a_strategy_that_does_not_report_the_anchor_writes_null_direct_and_replayed(alias: str) -> None:
    documents = _documents(alias)
    assert documents
    assert {document["anchor_filing"] for _stem, document in documents if "anchor_filing" in document} == {None}
    assert all("anchor_filing" in document for _stem, document in documents)


def test_a_strategy_that_reports_the_anchor_writes_the_same_element_direct_and_replayed() -> None:
    direct = json.loads(expected_path("piotroski-success.direct").read_bytes())["anchor_filing"]
    replayed = json.loads(expected_path("piotroski-success.replay").read_bytes())["anchor_filing"]
    assert direct == replayed
    assert direct == {
        "year_end": "2024-09-28",
        "form": "10-K",
        "accession": "0000320193-24-000123",
        "filing_date": "2024-11-01",
        "next_report_due": "2026-01-18",
        "stale": False,
    }


def test_no_strategy_document_keeps_a_second_anchor_part() -> None:
    document = json.loads(expected_path("piotroski-success.direct").read_bytes())
    assert "anchor" not in document


@pytest.mark.parametrize("alias", ["graham-number", "graham-growth"])
@pytest.mark.parametrize("route", ["direct", "replay"])
def test_a_graham_strategy_writes_the_element_when_it_resolved_the_anchor_and_null_for_an_etf(
    alias: str, route: str
) -> None:
    element = json.loads(expected_path(f"{alias}-success.{route}").read_bytes())["anchor_filing"]
    assert element == {
        "year_end": "2024-06-30",
        "form": "10-K",
        "accession": "0000000001-24-000001",
        "filing_date": "2024-09-13",
        "next_report_due": "2025-10-20",
        "stale": False,
    }
    assert json.loads(expected_path(f"{alias}-etf.{route}").read_bytes())["anchor_filing"] is None
