"""The as-filed SIC code: header transport, header parser and the adapter's single anchor-filing request."""

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from investment_analysis_engine.analysis.shared.applicability import IndustryClass, industry_class_of_sic
from investment_analysis_engine.analysis.shared.metric_inputs import (
    IndustryClassResolution,
    MetricInputsFailure,
    resolve_industry_class,
)
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.filing_document import (
    FilingHeaderPolicy,
    FilingReaderPolicy,
    fetch_filing,
    fetch_filing_header,
    filing_header_url,
)
from investment_analysis_engine.data.sec_edgar.filing_header import (
    AsFiledSic,
    AsFiledSicResolution,
    SicUnavailableReason,
    parse_filing_header,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter

FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "filing_headers"
NOW = datetime(2026, 10, 25, tzinfo=UTC)
FAR = datetime(2030, 1, 1, tzinfo=UTC)
_HEADERS = {"User-Agent": "Synthetic"}
_KEYWORDS: dict[str, Any] = {"not_found": ProviderFailureKind.NO_DATA, "provider_id": "sec_edgar"}


def _read(name: str) -> str:
    return (FIXTURES / f"{name}.hdr.sgml").read_text(encoding="utf-8")


def _parse(  # noqa: PLR0913
    name_or_text: str,
    *,
    cik: str,
    accession: str,
    filing_date: date | None,
    boundary: datetime = FAR,
    literal: bool = False,
) -> AsFiledSicResolution:
    text = name_or_text if literal else _read(name_or_text)
    return parse_filing_header(
        text,
        cik=cik,
        accession=accession,
        filing_date=filing_date,
        boundary=boundary,
        source_url="https://www.sec.gov/Archives/edgar/data/1/000000000000000001/x.hdr.sgml",
        retrieved_at=NOW,
    )


# (fixture, cik, accession, filing date, header code, class under the shared definitions)
_CASES = [
    ("jpm_fy2025", "19617", "0001628280-26-008131", date(2026, 2, 13), 6021, IndustryClass.FINANCIAL),
    ("trv_fy2025", "86312", "0000086312-26-000065", date(2026, 2, 12), 6331, IndustryClass.FINANCIAL),
    ("pld_fy2025", "1045609", "0001193125-26-051453", date(2026, 2, 13), 6798, IndustryClass.FINANCIAL),
    ("duk_fy2025", "1326160", "0001326160-26-000014", date(2026, 2, 26), 4931, IndustryClass.UTILITY),
    ("de_fy2025", "315189", "0001104659-25-122321", date(2025, 12, 18), 3523, IndustryClass.MANUFACTURER),
    ("sap_fy2025", "1000184", "0001104659-26-020058", date(2026, 2, 26), 7372, IndustryClass.OTHER),
    ("ntr_fy2025", "1725964", "0001193125-26-081326", date(2026, 2, 27), 2870, IndustryClass.MANUFACTURER),
    ("riot_fy2015", "1167419", "0001079973-16-000870", date(2016, 3, 23), 2835, IndustryClass.MANUFACTURER),
    ("riot_fy2022", "1167419", "0001558370-23-002704", date(2023, 3, 2), 6199, IndustryClass.FINANCIAL),
    ("mara_fy2015", "1507605", "0001104659-16-108696", date(2016, 3, 30), 6794, IndustryClass.FINANCIAL),
    ("mara_fy2022", "1507605", "0001493152-23-007879", date(2023, 3, 16), 7374, IndustryClass.OTHER),
]


@pytest.mark.parametrize(("name", "cik", "accession", "filed", "code", "industry"), _CASES)
def test_a_captured_header_gives_its_code_and_class(  # noqa: PLR0913, PLR0917
    name: str, cik: str, accession: str, filed: date, code: int, industry: IndustryClass
) -> None:
    resolution = _parse(name, cik=cik, accession=accession, filing_date=filed)
    assert resolution.reason is None
    sic = resolution.sic
    assert isinstance(sic, AsFiledSic)
    assert (sic.code, sic.accession, sic.filing_date, sic.cik) == (code, accession, filed, cik.zfill(10))
    assert sic.accepted_at.utcoffset() == timedelta(0)
    assert industry_class_of_sic(sic.code) is industry


def test_an_issuer_whose_code_changed_has_the_code_of_each_filing() -> None:
    codes = {name: _parse(name, cik=cik, accession=acc, filing_date=filed) for name, cik, acc, filed, *_ in _CASES}
    assert [codes[n].sic.code for n in ("riot_fy2015", "riot_fy2022")] == [2835, 6199]  # type: ignore[union-attr]
    assert [codes[n].sic.code for n in ("mara_fy2015", "mara_fy2022")] == [6794, 7374]  # type: ignore[union-attr]


def test_acceptance_time_is_eastern_time_converted_to_utc() -> None:
    sic = _parse("riot_fy2015", cik="1167419", accession="0001079973-16-000870", filing_date=date(2016, 3, 23)).sic
    assert sic is not None
    assert sic.accepted_at == datetime(2016, 3, 23, 20, 33, 16, tzinfo=UTC)  # 16:33:16 EDT


@pytest.mark.parametrize(
    ("cik", "code"),
    [("1045609", 6798), ("1045610", 6500)],
)
def test_a_combined_filing_gives_the_code_of_the_issuers_own_block(cik: str, code: int) -> None:
    resolution = _parse("pld_fy2025", cik=cik, accession="0001193125-26-051453", filing_date=date(2026, 2, 13))
    assert resolution.sic is not None
    assert resolution.sic.code == code


@pytest.mark.parametrize(("cik", "code"), [("30371", 4911), ("1326160", 4931), ("78460", 4924), ("37637", 4911)])
def test_the_block_is_chosen_by_cik_not_by_position(cik: str, code: int) -> None:
    text = _read("duk_fy2025")
    head, _, tail = text.partition("<FILER>")
    blocks = [
        block for block in ("<FILER>" + tail).split("</FILER>\n") if block.strip() and "</SEC-HEADER>" not in block
    ]
    reversed_text = head + "".join(f"{block}</FILER>\n" for block in reversed(blocks)) + "</SEC-HEADER>\n"
    for candidate in (text, reversed_text):
        resolution = _parse(
            candidate, cik=cik, accession="0001326160-26-000014", filing_date=date(2026, 2, 26), literal=True
        )
        assert resolution.sic is not None
        assert resolution.sic.code == code


def _single(*, code_line: str = "<ASSIGNED-SIC>6021", cik: str = "0000019617", extra: str = "") -> str:
    return (
        "<SEC-HEADER>0001628280-26-008131.hdr.sgml : 20260213\n"
        "<ACCEPTANCE-DATETIME>20260213162000\n"
        "<ACCESSION-NUMBER>0001628280-26-008131\n"
        "<FILING-DATE>20260213\n"
        f"<FILER>\n<COMPANY-DATA>\n<CIK>{cik}\n{code_line}\n</COMPANY-DATA>\n</FILER>\n{extra}"
        "</SEC-HEADER>\n"
    )


def _resolve(text: str, **overrides: Any) -> AsFiledSicResolution:
    arguments: dict[str, Any] = {"cik": "19617", "accession": "0001628280-26-008131", "filing_date": date(2026, 2, 13)}
    arguments.update(overrides)
    return _parse(text, literal=True, **arguments)


def test_the_verbatim_first_line_and_surrounding_whitespace_are_accepted() -> None:
    text = _single().replace("<ASSIGNED-SIC>6021", "  <ASSIGNED-SIC>6021  ")
    assert _resolve(text).sic is not None


@pytest.mark.parametrize(
    ("code_line", "reason"),
    [
        ("", SicUnavailableReason.CODE_MISSING),
        ("<ASSIGNED-SIC>", SicUnavailableReason.CODE_MISSING),
        ("<ASSIGNED-SIC>0000", SicUnavailableReason.CODE_MALFORMED),
        ("<ASSIGNED-SIC>602", SicUnavailableReason.CODE_MALFORMED),
        ("<ASSIGNED-SIC>60211", SicUnavailableReason.CODE_MALFORMED),
        ("<ASSIGNED-SIC>60A1", SicUnavailableReason.CODE_MALFORMED),
        ("<ASSIGNED-SIC>-021", SicUnavailableReason.CODE_MALFORMED),
    ],
)
def test_a_missing_or_malformed_code_is_unavailable(code_line: str, reason: SicUnavailableReason) -> None:
    resolution = _resolve(_single(code_line=code_line))
    assert (resolution.sic, resolution.reason) == (None, reason)


def test_a_header_with_no_block_for_the_issuer_is_unavailable() -> None:
    assert _resolve(_single(cik="0000019618")).reason is SicUnavailableReason.NO_FILER_BLOCK
    assert _resolve(_single(cik="not-a-cik")).reason is SicUnavailableReason.NO_FILER_BLOCK


def test_two_blocks_for_one_issuer_with_different_codes_are_ambiguous() -> None:
    extra_block = "<FILER>\n<COMPANY-DATA>\n<CIK>0000019617\n<ASSIGNED-SIC>6022\n</COMPANY-DATA>\n</FILER>\n"
    text = _single().replace("</SEC-HEADER>\n", extra_block + "</SEC-HEADER>\n")
    assert _resolve(text).reason is SicUnavailableReason.AMBIGUOUS_FILER_BLOCK
    same = text.replace("6022", "6021")
    assert _resolve(same).sic is not None


def test_a_header_for_another_accession_is_unavailable() -> None:
    assert _resolve(_single(), accession="0001628280-26-008132").reason is SicUnavailableReason.ACCESSION_MISMATCH


def test_the_filing_date_must_match_the_submissions_date() -> None:
    assert _resolve(_single(), filing_date=date(2026, 2, 12)).reason is SicUnavailableReason.FILING_DATE_MISMATCH
    assert _resolve(_single(), filing_date=None).reason is SicUnavailableReason.FILING_DATE_UNAVAILABLE


@pytest.mark.parametrize(
    "old",
    ["<ACCEPTANCE-DATETIME>20260213162000\n", "<ACCESSION-NUMBER>0001628280-26-008131\n", "<FILING-DATE>20260213\n"],
)
def test_a_header_missing_a_top_level_field_is_incomplete(old: str) -> None:
    assert _resolve(_single().replace(old, "")).reason is SicUnavailableReason.HEADER_INCOMPLETE


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("20260213162000", "2026021316"),
        ("20260213162000", "20261313162000"),
        ("<FILING-DATE>20260213", "<FILING-DATE>2026-02-13"),
    ],
)
def test_a_malformed_top_level_field_is_incomplete(old: str, new: str) -> None:
    assert _resolve(_single().replace(old, new)).reason is SicUnavailableReason.HEADER_INCOMPLETE


def test_an_empty_text_is_incomplete() -> None:
    assert _resolve("").reason is SicUnavailableReason.HEADER_INCOMPLETE


def test_the_boundary_is_inclusive_and_one_second_after_is_rejected() -> None:
    accepted = datetime(2026, 2, 13, 21, 20, 0, tzinfo=UTC)  # 16:20:00 EST
    kept = _resolve(_single(), boundary=accepted)
    assert kept.sic is not None
    assert kept.sic.accepted_at == accepted
    rejected = _resolve(_single(), boundary=accepted - timedelta(seconds=1))
    assert rejected.reason is SicUnavailableReason.ACCEPTED_AFTER_BOUNDARY


def test_a_resolution_holds_exactly_one_of_evidence_and_reason() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        AsFiledSicResolution()
    sic = _resolve(_single()).sic
    with pytest.raises(ValueError, match="exactly one"):
        AsFiledSicResolution(sic=sic, reason=SicUnavailableReason.CODE_MISSING)


def test_the_evidence_type_rejects_a_bad_code_cik_accession_and_naive_time() -> None:
    good = _resolve(_single()).sic
    assert good is not None
    for change in (
        {"code": 0},
        {"code": 10000},
        {"cik": "19617"},
        {"accession": "000162828026008131"},
        {"accepted_at": datetime(2026, 1, 1)},  # noqa: DTZ001
        {"retrieved_at": datetime(2026, 1, 1)},  # noqa: DTZ001
        {"source_url": ""},
    ):
        with pytest.raises(ValueError, match="SIC|CIK|accession|timestamps|URL"):
            replace(good, **change)


def test_the_fixture_checksums_match_the_files() -> None:
    lines = (FIXTURES / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {line.split("  ")[1]: line.split("  ")[0] for line in lines}
    files = {path.name for path in FIXTURES.glob("*.hdr.sgml")}
    assert set(listed) == files
    for name, digest in listed.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


# --- transport ---------------------------------------------------------------------------------------------------

_ACCESSION = "0001628280-26-008131"
_URL = "https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/0001628280-26-008131.hdr.sgml"


def _header(url: str = _URL, *, policy: FilingHeaderPolicy | None = None, headers: Mapping[str, str] = _HEADERS) -> str:
    return fetch_filing_header(url, headers=headers, policy=policy or FilingHeaderPolicy(), **_KEYWORDS)


def test_the_url_is_built_only_from_validated_identifiers() -> None:
    assert filing_header_url("0000019617", _ACCESSION) == _URL
    assert filing_header_url("19617", _ACCESSION) == _URL
    for cik, accession in (("0", _ACCESSION), ("1x", _ACCESSION), ("19617", "0001628280-26-00813"), ("19617", "../x")):
        with pytest.raises(ValueError, match="Invalid filing"):
            filing_header_url(cik, accession)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/Archives/edgar/data/19617/000162828026008131/0001628280-26-008131.hdr.sgml",
        "http://www.sec.gov/Archives/edgar/data/19617/000162828026008131/0001628280-26-008131.hdr.sgml",
        _URL + "?x=1",
        _URL.replace("19617/", "19617/../"),
        _URL.replace(".hdr.sgml", ".htm"),
        _URL.replace("000162828026008131/", "000162828026008132/"),
        _URL.replace("19617", "abc"),
        _URL.replace("/Archives", "//Archives"),
    ],
)
def test_the_transport_enforces_the_exact_url_pattern(url: str) -> None:
    with pytest.raises(ValueError, match="Unsupported filing header URL"):
        _header(url)


def test_the_transport_requires_an_identity() -> None:
    with pytest.raises(ValueError, match="User-Agent"):
        _header(headers={})


def _opener(body: bytes | None = None, error: BaseException | None = None) -> MagicMock:
    opener = MagicMock()
    if error is not None:
        opener.open.side_effect = error
    else:
        opener.open.return_value.__enter__.return_value.read.return_value = body
    return opener


def test_the_transport_is_bounded_without_redirects() -> None:
    opener = _opener(b"<SEC-HEADER>")
    with patch(
        "investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=opener
    ) as builder:
        assert _header(policy=FilingHeaderPolicy(timeout_seconds=3, max_header_bytes=64)) == "<SEC-HEADER>"
    assert opener.open.call_args.kwargs["timeout"] == 3
    assert opener.open.call_args.args[0].get_header("Accept") == "text/plain"
    opener.open.return_value.__enter__.return_value.read.assert_called_once_with(65)
    assert builder.call_args.args[0].redirect_request() is None


def test_an_oversized_or_undecodable_header_is_an_unexpected_response() -> None:
    for body, match in ((b"x" * 9, "size limit"), (b"\xff\xfe\xfa", "UTF-8")):
        with (
            patch("investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=_opener(body)),
            pytest.raises(FinancialProviderError, match=match) as caught,
        ):
            _header(policy=FilingHeaderPolicy(max_header_bytes=8))
        assert caught.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE


def test_a_404_takes_the_kind_the_caller_passes_and_a_server_fault_is_unreachable() -> None:
    not_found = HTTPError(_URL, 404, "Not Found", {}, BytesIO(b""))  # type: ignore[arg-type]
    with (
        patch(
            "investment_analysis_engine.data.sec_edgar.filing_document.build_opener",
            return_value=_opener(error=not_found),
        ),
        pytest.raises(FinancialProviderError) as missing,
    ):
        _header()
    assert missing.value.kind is ProviderFailureKind.NO_DATA
    fault = HTTPError(_URL, 503, "Unavailable", {}, BytesIO(b""))  # type: ignore[arg-type]
    with (
        patch(
            "investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=_opener(error=fault)
        ),
        pytest.raises(FinancialProviderError) as down,
    ):
        _header()
    assert down.value.kind is ProviderFailureKind.UNREACHABLE


def test_the_policy_rejects_unbounded_settings() -> None:
    for kwargs in ({"timeout_seconds": 0.0}, {"timeout_seconds": float("inf")}, {"max_header_bytes": 0}):
        with pytest.raises(ValueError, match="Filing header"):
            FilingHeaderPolicy(**kwargs)


def test_the_filing_transport_is_unchanged_by_the_shared_read() -> None:
    with pytest.raises(ValueError, match="Unsupported filing URL"):
        fetch_filing(_URL, headers=_HEADERS, policy=FilingReaderPolicy(), **_KEYWORDS)


# --- the adapter -------------------------------------------------------------------------------------------------

_BOUNDARY = datetime(2026, 3, 1, tzinfo=UTC)


class _Sec:
    """Serve one issuer's submissions and count the header and document requests."""

    def __init__(self, *, sic: str = "9999", header: str | BaseException | None = None) -> None:
        self.header_urls: list[str] = []
        self.document_urls: list[str] = []
        self._header = header if header is not None else _read("jpm_fy2025")
        self.submissions: dict[str, Any] = {
            "cik": "0000019617",
            "sic": sic,
            "tickers": ["JPM"],
            "filings": {
                "recent": {
                    "accessionNumber": [_ACCESSION],
                    "form": ["10-K"],
                    "filingDate": ["2026-02-13"],
                    "acceptanceDateTime": ["2026-02-13T21:20:00.000Z"],
                    "primaryDocument": ["jpm-20251231.htm"],
                }
            },
        }

    def json(self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str) -> object:  # noqa: ARG002
        assert headers["User-Agent"]
        if url.endswith("company_tickers.json"):
            return {"0": {"ticker": "JPM", "cik_str": 19617, "title": "JPMorgan Chase"}}
        if "/companyfacts/" in url:
            return {"cik": 19617, "entityName": "JPM", "facts": {"us-gaap": {}}}
        return self.submissions

    def header(
        self,
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG002
        policy: FilingHeaderPolicy,  # noqa: ARG002
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> str:
        self.header_urls.append(url)
        if isinstance(self._header, BaseException):
            raise self._header
        return self._header

    def document(
        self,
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG002
        policy: FilingReaderPolicy,  # noqa: ARG002
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> str:
        self.document_urls.append(url)
        return ""

    def adapter(self) -> SecEdgarFinancialFactsAdapter:
        return SecEdgarFinancialFactsAdapter(
            json_fetcher=self.json,
            clock=lambda: NOW,
            user_agent="Synthetic",
            filing_fetcher=self.document,
            header_fetcher=self.header,
        )


def test_the_adapter_reads_the_anchor_header_once_however_often_the_class_is_asked_for() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    first = adapter.resolve_as_filed_sic(snapshot)
    second = adapter.resolve_as_filed_sic(snapshot)
    assert first == second
    assert first.sic is not None
    assert first.sic.code == 6021
    assert sec.header_urls == [_URL]
    assert first.sic.retrieved_at == NOW


def test_the_current_submissions_sic_is_never_used() -> None:
    for current in ("1000", "6199", ""):
        sec = _Sec(sic=current)
        adapter = sec.adapter()
        snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
        assert adapter.resolve_as_filed_sic(snapshot).sic is not None
        assert adapter.resolve_as_filed_sic(snapshot).sic.code == 6021  # type: ignore[union-attr]


def test_the_header_is_outside_the_four_document_limit() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    policy = FilingReaderPolicy()
    for _ in range(policy.max_documents):
        sec.document("https://www.sec.gov/x", headers=_HEADERS, policy=policy, **_KEYWORDS)
    assert adapter.resolve_as_filed_sic(snapshot).sic is not None
    assert len(sec.document_urls) == policy.max_documents
    assert len(sec.header_urls) == 1


def test_a_filing_accepted_after_the_boundary_is_not_an_anchor_so_the_class_is_unknown() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=datetime(2026, 2, 13, 21, 19, 59, tzinfo=UTC))
    resolution = adapter.resolve_as_filed_sic(snapshot)
    assert resolution.reason is SicUnavailableReason.ACCEPTED_AFTER_BOUNDARY
    assert sec.header_urls == []


def test_a_missing_header_is_an_unknown_class_and_a_fault_is_a_provider_error() -> None:
    missing = FinancialProviderError("gone", kind=ProviderFailureKind.NO_DATA, provider_id="sec_edgar")
    sec = _Sec(header=missing)
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    assert adapter.resolve_as_filed_sic(snapshot).reason is SicUnavailableReason.HEADER_MISSING
    fault = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
    sec = _Sec(header=fault)
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    with pytest.raises(FinancialProviderError) as caught:
        adapter.resolve_as_filed_sic(snapshot)
    assert caught.value.kind is ProviderFailureKind.UNREACHABLE


def test_a_submissions_filing_date_that_differs_from_the_header_is_an_unknown_class() -> None:
    sec = _Sec()
    sec.submissions["filings"]["recent"]["filingDate"] = ["2026-02-12"]
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    assert adapter.resolve_as_filed_sic(snapshot).reason is SicUnavailableReason.FILING_DATE_MISMATCH


def test_an_unknown_ticker_has_no_anchor_filing() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="NOPE", as_of=_BOUNDARY)
    assert adapter.resolve_as_filed_sic(snapshot).reason is SicUnavailableReason.NO_ANCHOR_FILING


def test_the_fixtures_hold_no_identity_and_only_the_lines_the_reader_uses() -> None:
    allowed = {
        "<SEC-HEADER>",
        "</SEC-HEADER>",
        "<FILER>",
        "</FILER>",
        "<COMPANY-DATA>",
        "</COMPANY-DATA>",
    }
    prefixes = ("<ACCEPTANCE-DATETIME>", "<ACCESSION-NUMBER>", "<FILING-DATE>", "<CIK>", "<ASSIGNED-SIC>")
    for path in Path(FIXTURES).glob("*.hdr.sgml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            assert line in allowed or line.startswith(prefixes), (path.name, line)


# --- the as-filed SIC code at the anchor of the active scope, and the industry class built on it ---------------------

_PROVIDER = "sec_edgar"


def test_the_adapter_resolves_the_sic_of_the_active_scopes_anchor_filing() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY):
        bounded = adapter.resolve_as_filed_sic_at_anchor("jpm", _BOUNDARY)
        current = adapter.resolve_as_filed_sic_at_anchor("JPM", None)
    assert bounded.sic is not None
    assert (bounded.sic.code, bounded.sic.accession) == (6021, _ACCESSION)
    assert current == bounded
    assert sec.header_urls == [_URL]


@pytest.mark.parametrize(
    ("asked", "boundary"),
    [("JPM", _BOUNDARY), ("OTHER", _BOUNDARY), ("JPM", _BOUNDARY - timedelta(days=1))],
)
def test_without_a_matching_scope_the_sic_has_no_anchor_filing_and_nothing_is_requested(
    asked: str, boundary: datetime
) -> None:
    sec = _Sec()
    adapter = sec.adapter()
    assert adapter.resolve_as_filed_sic_at_anchor(asked, boundary).reason is SicUnavailableReason.NO_ANCHOR_FILING
    with adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY):
        scoped = adapter.resolve_as_filed_sic_at_anchor(asked, boundary)
    assert (scoped.reason is None) == (asked == "JPM" and boundary == _BOUNDARY)
    assert len(sec.header_urls) == (0 if scoped.reason is not None else 1)


def test_the_sic_of_a_scope_closed_again_is_no_longer_available() -> None:
    adapter = _Sec().adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY):
        pass
    assert adapter.resolve_as_filed_sic_at_anchor("JPM", None).reason is SicUnavailableReason.NO_ANCHOR_FILING


def test_a_header_fault_inside_the_scope_is_raised_as_the_classified_provider_error() -> None:
    fault = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id=_PROVIDER)
    adapter = _Sec(header=fault).adapter()
    with (
        adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY),
        pytest.raises(FinancialProviderError) as caught,
    ):
        adapter.resolve_as_filed_sic_at_anchor("JPM", None)
    assert caught.value.kind is ProviderFailureKind.UNREACHABLE


def test_the_industry_class_resolves_through_the_adapter_from_the_as_filed_code() -> None:
    adapter = _Sec().adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY):
        resolution = resolve_industry_class(adapter, ticker="jpm", as_of=_BOUNDARY)
    assert resolution == IndustryClassResolution(IndustryClass.FINANCIAL, None)


def test_the_industry_class_is_unknown_through_the_adapter_when_the_header_is_missing_or_no_scope_is_open() -> None:
    missing = FinancialProviderError("gone", kind=ProviderFailureKind.NO_DATA, provider_id=_PROVIDER)
    adapter = _Sec(header=missing).adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY):
        header_missing = resolve_industry_class(adapter, ticker="JPM", as_of=None)
    no_scope = resolve_industry_class(adapter, ticker="JPM", as_of=None)
    for outcome, reason in ((header_missing, "header_missing"), (no_scope, "no_anchor_filing")):
        assert isinstance(outcome, IndustryClassResolution)
        assert outcome.industry_class is None
        assert outcome.unknown is not None
        assert outcome.unknown.reason_code is ReasonCode.INDUSTRY_CLASS_UNKNOWN
        assert reason in outcome.unknown.reason


def test_a_header_fault_is_a_metric_inputs_failure_for_the_industry_class_input() -> None:
    fault = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id=_PROVIDER)
    adapter = _Sec(header=fault).adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=_PROVIDER, as_of=_BOUNDARY):
        outcome = resolve_industry_class(adapter, ticker="JPM", as_of=None)
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "industry_class"
    assert outcome.provider_failure == ProviderFailureRecord(
        ProviderFailureKind.UNREACHABLE, _PROVIDER, "industry_class"
    )
