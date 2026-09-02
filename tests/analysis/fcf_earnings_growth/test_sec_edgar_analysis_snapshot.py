"""Step 2.5A B1-A tests for immutable SEC snapshots and regime locking."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.analysis.graham_value.service import run_graham_number_analysis
from src.data.financial.facts import FinancialFactRequest, FinancialField, ProviderFact
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

NOW = datetime(2026, 9, 1, 14, 0, tzinfo=UTC)
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "sec_edgar" / "step_2_5a_d0"


def _fixture(name: str) -> Any:
    """Load one approved D0 evidence fragment."""
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _SnapshotFetcher:
    """Serve versioned payloads and retain endpoint call counts."""

    def __init__(self, *, company_facts: object, submissions: object) -> None:
        self.company_facts = company_facts
        self.submissions = submissions
        self.calls: list[str] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        assert headers["User-Agent"] == "B1-A fixture tests@example.invalid"
        self.calls.append(url)
        if "company_tickers.json" in url:
            return _fixture("company_tickers.json")
        if "/companyfacts/" in url:
            return self.company_facts
        if "/submissions/" in url:
            return self.submissions
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _adapter(
    *, company_facts: object | None = None, submissions: object | None = None
) -> tuple[SecEdgarFinancialFactsAdapter, _SnapshotFetcher]:
    fetcher = _SnapshotFetcher(
        company_facts=company_facts or _fixture("asml_companyfacts.json"),
        submissions=submissions or _fixture("asml_submissions.json"),
    )
    return (
        SecEdgarFinancialFactsAdapter(
            json_fetcher=fetcher,
            clock=lambda: NOW,
            user_agent="B1-A fixture tests@example.invalid",
        ),
        fetcher,
    )


def _request(field: FinancialField, *, count: int = 1, as_of: datetime | None = None) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ASML",
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=count,
        as_of=as_of,
    )


def _transition_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    company_facts: dict[str, Any] = deepcopy(_fixture("asml_companyfacts.json"))
    older = deepcopy(company_facts["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"])
    observation = older["units"]["EUR"][0]
    observation.update(
        {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "accn": "ifrs-accession",
            "fy": 2024,
            "form": "20-F",
            "filed": "2025-02-20",
        }
    )
    company_facts["facts"]["ifrs-full"] = {"CashFlowsFromUsedInOperatingActivities": older}
    submissions: dict[str, Any] = deepcopy(_fixture("asml_submissions.json"))
    recent = submissions["filings"]["recent"]
    recent["accessionNumber"].append("ifrs-accession")
    recent["acceptanceDateTime"].append("2025-02-20T12:00:00Z")
    recent["filingDate"].append("2025-02-20")
    recent["reportDate"].append("2024-12-31")
    recent["form"].append("20-F")
    recent["primaryDocument"].append("older.htm")
    return company_facts, submissions


def test_scope_reuses_one_immutable_payload_pair_across_fields() -> None:
    adapter, fetcher = _adapter()

    with adapter.analysis_scope(subject_id="ASML", provider_id=SEC_PROVIDER_ID, as_of=None):
        operating_cash_flow = adapter.fetch_facts(_request(FinancialField.OPERATING_CASH_FLOW))
        capital_expenditures = adapter.fetch_facts(_request(FinancialField.CAPITAL_EXPENDITURES))

    assert len(operating_cash_flow) == len(capital_expenditures) == 1
    assert sum("/companyfacts/" in call for call in fetcher.calls) == 1
    assert sum("/submissions/" in call for call in fetcher.calls) == 1


def test_snapshot_records_stable_identity_taxonomy_and_payload_checksums() -> None:
    adapter, _ = _adapter()

    snapshot = adapter.create_analysis_snapshot(subject_id="asml", as_of=None)

    assert snapshot.subject_id == "ASML"
    assert snapshot.cik == "0000937966"
    assert snapshot.latest_annual_accession == "0001628280-26-011378"
    assert snapshot.taxonomy == "us-gaap"
    assert len(snapshot.company_facts_sha256) == len(snapshot.submissions_sha256) == 64
    with pytest.raises(TypeError):
        snapshot.company_facts["cik"] = 1  # type: ignore[index]


def test_historical_as_of_selects_the_latest_then_available_taxonomy() -> None:
    company_facts, submissions = _transition_payloads()
    adapter, _ = _adapter(company_facts=company_facts, submissions=submissions)

    historical = adapter.create_analysis_snapshot(
        subject_id="ASML",
        as_of=datetime(2025, 12, 31, tzinfo=UTC),
    )
    current = adapter.create_analysis_snapshot(subject_id="ASML", as_of=NOW)

    assert historical.latest_annual_accession == "ifrs-accession"
    assert historical.taxonomy == "ifrs-full"
    assert current.latest_annual_accession == "0001628280-26-011378"
    assert current.taxonomy == "us-gaap"


def test_later_filing_does_not_leak_across_historical_as_of() -> None:
    adapter, _ = _adapter()
    as_of = datetime(2025, 12, 31, tzinfo=UTC)

    with adapter.analysis_scope(subject_id="ASML", provider_id=SEC_PROVIDER_ID, as_of=as_of):
        facts = adapter.fetch_facts(_request(FinancialField.OPERATING_CASH_FLOW, as_of=as_of))

    assert facts == ()


def test_ambiguous_accession_taxonomy_fails_closed() -> None:
    company_facts: dict[str, Any] = deepcopy(_fixture("asml_companyfacts.json"))
    company_facts["facts"]["ifrs-full"] = {
        "CashFlowsFromUsedInOperatingActivities": deepcopy(
            company_facts["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]
        )
    }
    adapter, _ = _adapter(company_facts=company_facts)

    snapshot = adapter.create_analysis_snapshot(subject_id="ASML", as_of=None)

    assert snapshot.taxonomy is None
    with adapter.analysis_scope(subject_id="ASML", provider_id=SEC_PROVIDER_ID, as_of=None):
        assert adapter.fetch_facts(_request(FinancialField.OPERATING_CASH_FLOW)) == ()


def test_requested_span_crossing_unproved_regime_transition_is_unavailable() -> None:
    company_facts, submissions = _transition_payloads()
    adapter, _ = _adapter(company_facts=company_facts, submissions=submissions)

    with adapter.analysis_scope(subject_id="ASML", provider_id=SEC_PROVIDER_ID, as_of=None):
        facts = adapter.fetch_facts(_request(FinancialField.OPERATING_CASH_FLOW, count=2))

    assert facts == ()


def test_missing_accession_evidence_cannot_establish_regime() -> None:
    adapter, _ = _adapter(submissions={"filings": {"recent": {}}})

    snapshot = adapter.create_analysis_snapshot(subject_id="ASML", as_of=None)

    assert snapshot.latest_annual_accession is None
    assert snapshot.taxonomy is None


class _ScopeSpyProvider:
    """Prove the Graham execution boundary enters the shared provider scope."""

    def __init__(self) -> None:
        self.scope_entries = 0

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        _ = request
        return ()

    @contextmanager
    def analysis_scope(
        self,
        *,
        subject_id: str,
        provider_id: str,
        as_of: datetime | None,
    ) -> Iterator[None]:
        assert subject_id == "ASML"
        assert provider_id == SEC_PROVIDER_ID
        assert as_of == NOW
        self.scope_entries += 1
        yield


def test_graham_analysis_enters_the_same_optional_snapshot_boundary() -> None:
    provider = _ScopeSpyProvider()
    resolver = GrahamInputResolver(provider)

    analysis = run_graham_number_analysis(
        resolver=resolver,
        ticker="ASML",
        security_provider_id=SEC_PROVIDER_ID,
        quote_provider_id="yfinance",
        eps_basis="invalid",
        eps_override=None,
        bvps_override=None,
        quote_override=None,
        as_of=NOW,
        use_cache=False,
    )

    assert provider.scope_entries == 1
    assert analysis.assembly.status.value == "invalid_input"
