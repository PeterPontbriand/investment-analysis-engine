"""Reading what an annual filing's cover registers for a ticker.

The cover of an annual report lists each security registered under Section 12(b) with its title, trading symbol and
exchange. The SEC renders that cover as the first report of the filing (``R1.htm``), a few tens of kilobytes beside a
primary document of several megabytes, and each row of the report names its XBRL concept, so a filer's own row labels
never matter. When the first report is not the cover, the filing's ``FilingSummary.xml`` names it. Only the row group
of the requested ticker is classified; the other securities of the cover do not affect the outcome.

The title vocabulary is an explicit list of title forms, each backed by a captured cover
(``docs/project/milestones/v0.2/step-3.5/STEP_3_5_2_LISTING_EVIDENCE.md``). A title outside it is neither affirmed nor
mistaken for a share: it is reported as ``other``. A cover that cannot be read, that names another form or another
registrant, or that lists the ticker under two different titles, is refused rather than guessed at. The one
exception is a ticker shared by one share and debt titles of an explicit form, which is the share's.

A ticker the anchor cover does not list may have been renamed since. ``read_renamed_listing`` affirms that only when
the anchor cover registers exactly one share and no depositary share, and the registrant's latest annual cover
registers the requested ticker as its only share: the one share line is then renamed, not replaced.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from html.parser import HTMLParser
from typing import Protocol, runtime_checkable

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.filing_document import read_bounded

COVER_REPORT_NAME = "R1.htm"
SUMMARY_NAME = "FilingSummary.xml"
_REPORT_NAME = re.compile(r"R[0-9]{1,4}\.htm")
_COVER_URL_PATTERN = re.compile(
    r"https://www\.sec\.gov/Archives/edgar/data/(?P<cik>[0-9]+)/(?P<folder>[0-9]{18})/R[0-9]{1,4}\.htm"
)
_SUMMARY_URL_PATTERN = re.compile(
    r"https://www\.sec\.gov/Archives/edgar/data/(?P<cik>[0-9]+)/(?P<folder>[0-9]{18})/FilingSummary\.xml"
)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_MEMBER_ROW = re.compile(r"showAR\(\s*this,\s*'defref_[^']*=")
_MEMBER = "(member)"
_CONCEPT = re.compile(r"showAR\(\s*this,\s*'defref_(?P<prefix>[A-Za-z0-9-]+)_(?P<name>[A-Za-z0-9]+)'")

_DOCUMENT_TYPE = "DocumentType"
_CIK = "EntityCentralIndexKey"
_TITLE_CONCEPTS = frozenset({"Security12bTitle", "Security12gTitle"})
_SEPARATORS = str.maketrans({".": "-", "/": "-"})
_SYMBOL = "TradingSymbol"
_EXCHANGE = "SecurityExchangeName"
_NO_SYMBOL = "NoTradingSymbolFlag"


@dataclass(frozen=True)
class CoverReaderPolicy:
    """Limit a cover read to one rendered report.

    The largest cover captured, a combined filing of eight registrants, is about 136 KB; the limit is 512 KiB. The
    largest ``FilingSummary.xml`` captured is about 87 KB (Disney); its limit is also 512 KiB.
    """

    timeout_seconds: float = 20.0
    max_cover_bytes: int = 512 * 1024
    max_summary_bytes: int = 512 * 1024

    def __post_init__(self) -> None:
        """Reject unbounded or invalid transport settings."""
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Cover timeout must be finite and positive.")
        if self.max_cover_bytes <= 0 or self.max_summary_bytes <= 0:
            raise ValueError("Cover size limits must be positive.")


def _filing_url(cik: str, accession: str, name: str) -> str:
    if not re.fullmatch(r"[0-9]{1,10}", cik) or int(cik) == 0:
        raise ValueError("Invalid filing CIK.")
    if not _ACCESSION.fullmatch(accession):
        raise ValueError("Invalid filing accession.")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{name}"


def cover_url(cik: str, accession: str, report: str = COVER_REPORT_NAME) -> str:
    """Construct the URL of a filing's rendered cover solely from validated filing identifiers and a report name."""
    if not _REPORT_NAME.fullmatch(report):
        raise ValueError("Invalid report name.")
    return _filing_url(cik, accession, report)


def summary_url(cik: str, accession: str) -> str:
    """Construct the URL of a filing's ``FilingSummary.xml`` solely from validated filing identifiers."""
    return _filing_url(cik, accession, SUMMARY_NAME)


class CoverFetcher(Protocol):
    """Inject a cover transport without a live dependency in tests."""

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        policy: CoverReaderPolicy,
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        """Return the bounded UTF-8 text of one rendered cover.

        ``not_found`` is the kind of an HTTP 404 and ``provider_id`` names the provider the request serves.
        """
        ...


def fetch_cover(
    url: str,
    *,
    headers: Mapping[str, str],
    policy: CoverReaderPolicy,
    not_found: ProviderFailureKind,
    provider_id: str,
) -> str:
    """Read one rendered report or ``FilingSummary.xml``: no redirect, no retry, bounded, UTF-8.

    The transport rules are those of a filing document. The read does not consult ``FilingReaderPolicy.max_documents``:
    a cover is not a filing document.

    Raises:
        ValueError: The URL or the declared identity is not acceptable; a defect of the caller.
        FinancialProviderError: A transport fault, a 404, a cover over the size limit or one that is not UTF-8,
            carrying the kind of the failure and *provider_id*.
    """
    summary = _SUMMARY_URL_PATTERN.fullmatch(url) is not None
    return read_bounded(
        url,
        pattern=_SUMMARY_URL_PATTERN if summary else _COVER_URL_PATTERN,
        noun="cover summary" if summary else "cover",
        accept="application/xml" if summary else "text/html",
        headers=headers,
        timeout_seconds=policy.timeout_seconds,
        max_bytes=policy.max_summary_bytes if summary else policy.max_cover_bytes,
        not_found=not_found,
        provider_id=provider_id,
    )


class SecurityKind(StrEnum):
    """What the cover says a registered security is."""

    SHARE = "share"
    DEPOSITARY_SHARE = "depositary_share"
    UNIT = "unit"
    WARRANT = "warrant"
    PREFERRED = "preferred"
    OTHER = "other"
    NOT_LISTED = "not_listed"


class CoverUnavailableReason(StrEnum):
    """Why no cover could be read for an anchor filing."""

    PROVIDER_UNSUPPORTED = "provider_unsupported"
    NO_ANALYSIS_SCOPE = "no_analysis_scope"
    SUBJECT_MISMATCH = "subject_mismatch"
    NO_ANCHOR_FILING = "no_anchor_filing"
    FORM_UNAVAILABLE = "form_unavailable"
    ACCEPTANCE_UNAVAILABLE = "acceptance_unavailable"
    ACCEPTED_AFTER_BOUNDARY = "accepted_after_boundary"
    COVER_MISSING = "cover_missing"
    COVER_UNREADABLE = "cover_unreadable"
    NO_REGISTRATION_TABLE = "no_registration_table"
    FORM_MISMATCH = "form_mismatch"
    CIK_MISMATCH = "cik_mismatch"
    AMBIGUOUS_LISTING = "ambiguous_listing"


@dataclass(frozen=True)
class CoverListingRequest:
    """Request the registered security of one ticker from the cover of the active analysis scope's anchor filing."""

    ticker: str
    provider_id: str

    def __post_init__(self) -> None:
        """Normalize the ticker and the provider identifier."""
        ticker = " ".join(self.ticker.split()).upper()
        provider_id = " ".join(self.provider_id.split())
        if not ticker or not provider_id:
            raise ValueError("A cover listing request requires a ticker and a provider.")
        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "provider_id", provider_id)


@dataclass(frozen=True)
class ListingRename:
    """The two covers that show one share line renamed: the anchor's and the registrant's latest, symbols as filed."""

    anchor_accession: str
    anchor_form: str
    anchor_symbol: str
    latest_accession: str
    latest_form: str
    latest_symbol: str

    def __post_init__(self) -> None:
        """Require dashed accessions and the symbols and forms of both covers."""
        for accession in (self.anchor_accession, self.latest_accession):
            if not _ACCESSION.fullmatch(accession):
                raise ValueError("A listing rename requires dashed accession numbers.")
        if not all(
            item.strip() for item in (self.anchor_form, self.anchor_symbol, self.latest_form, self.latest_symbol)
        ):
            raise ValueError("A listing rename requires the forms and symbols of both covers.")


@dataclass(frozen=True)
class ListingEvidence:
    """What the anchor filing's cover registers for the requested ticker, with the filing it was read from.

    Attributes:
        ticker: The requested ticker, upper-case.
        kind: What the registered security is; ``NOT_LISTED`` when no row of the issuer's cover lists the ticker.
        title: The registered title as filed, with its whitespace collapsed; ``None`` only when not listed.
        cik: The issuer's ten-digit CIK.
        accession: The dashed accession of the filing read.
        form: The form of the filing read.
        accepted_at: When the SEC accepted the filing, in UTC.
        source_url: The URL the cover was read from.
        retrieved_at: When the cover was read.
        rename: Set only when the ticker is not on the anchor cover but is the renamed one share line of the
            registrant's latest annual cover; then ``accession``, ``form``, ``title``, ``accepted_at`` and
            ``source_url`` describe that latest cover, and the rename names the anchor cover too.
    """

    ticker: str
    kind: SecurityKind
    title: str | None
    cik: str
    accession: str
    form: str
    accepted_at: datetime
    source_url: str
    retrieved_at: datetime
    rename: ListingRename | None = None

    def __post_init__(self) -> None:
        """Require a title exactly when the ticker is listed, and well-formed filing identifiers."""
        if self.rename is not None and self.kind is not SecurityKind.SHARE:
            raise ValueError("A renamed listing is a share.")
        if (self.kind is SecurityKind.NOT_LISTED) != (self.title is None):
            raise ValueError("Listing evidence carries a title exactly when the ticker is listed.")
        if self.title is not None and not self.title.strip():
            raise ValueError("A registered title must be non-empty.")
        if not re.fullmatch(r"[0-9]{10}", self.cik):
            raise ValueError("Listing evidence requires a ten-digit CIK.")
        if not _ACCESSION.fullmatch(self.accession):
            raise ValueError("Listing evidence requires a dashed accession number.")
        if not self.ticker.strip() or not self.form.strip() or not self.source_url:
            raise ValueError("Listing evidence requires its ticker, form and source URL.")
        for stamp in (self.accepted_at, self.retrieved_at):
            if stamp.utcoffset() is None:
                raise ValueError("Listing evidence timestamps must be timezone-aware.")


@dataclass(frozen=True)
class ListingResolution:
    """Either the listing evidence or the reason no cover could be read, never both and never neither."""

    evidence: ListingEvidence | None = None
    reason: CoverUnavailableReason | None = None

    def __post_init__(self) -> None:
        """Require exactly one of the evidence and the reason."""
        if (self.evidence is None) == (self.reason is None):
            raise ValueError("A listing resolution holds exactly one of the evidence and the reason.")


@runtime_checkable
class CoverListingProvider(Protocol):
    """Optional capability: read the registered security of a ticker from the active scope's anchor cover."""

    def resolve_cover_listing(self, request: CoverListingRequest) -> ListingResolution:
        """Return the listing evidence or the reason no cover could be read; a transport fault raises."""
        ...


# --- the title vocabulary ------------------------------------------------------------------------------------------

# Each designation is a registered title of a share of the issuer on a captured cover (see the evidence record).
_SHARE_DESIGNATIONS = (
    "common stock",
    "common shares",
    "class a common stock",
    "class b common stock",
    "class a ordinary shares",
    "class c capital stock",
    "ordinary shares",
)
# An amount is a decimal ("$0.01", "$.01") or a mixed fraction ("$1-2/3").
_PAR = r"\$(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+|[0-9]+-[0-9]+/[0-9]+)"
# Each clause is a form on a captured cover; a designation alone is also a title ("Ordinary Shares").
_PAR_CLAUSES = (
    rf", {_PAR} par value",
    rf", par value {_PAR} per share",
    rf", {_PAR} par value per share",
    rf", par value {_PAR}",
    rf" {_PAR} par value",
    ", without par value",
    r" \(no par value\)",
    rf" \({_PAR} par value\)",
    rf" \(par value {_PAR} per share\)",
    r", par value [0-9]+-[0-9]+/[0-9]+ cents per share",
    r", par value chf [0-9]+(?:\.[0-9]+)? per share",
    r" \(\u20ac[0-9]+(?:\.[0-9]+)? nominal value per share\)",
)
_SHARE_TITLE = re.compile(
    "(?:" + "|".join(re.escape(item) for item in _SHARE_DESIGNATIONS) + ")(?:" + "|".join(_PAR_CLAUSES) + ")?"
)
_DEPOSITARY_PREFIXES = ("depositary shares", "american depositary shares", "dep shs")
_UNIT_PREFIXES = ("units",)
_WARRANT_PREFIXES = ("warrants",)
_PREFERRED_SUFFIXES = ("preferred stock",)
_PREFERRED_SERIES = re.compile(r".*preferred stock, series [a-z]+")
# A debt title of an explicit form: "3.125% Notes due 2028" (Microsoft lists its notes under the symbol of its stock).
_DEBT_TITLE = re.compile(r"[0-9]+(?:\.[0-9]+)?% notes due [0-9]{4}")


def classify_title(title: str) -> SecurityKind:
    """Return what a registered title is, by the explicit vocabulary; a title outside it is ``OTHER``."""
    normalized = " ".join(title.split()).lower()
    if normalized.startswith(_DEPOSITARY_PREFIXES):
        return SecurityKind.DEPOSITARY_SHARE
    if normalized.startswith(_UNIT_PREFIXES):
        return SecurityKind.UNIT
    if normalized.startswith(_WARRANT_PREFIXES):
        return SecurityKind.WARRANT
    if normalized.endswith(_PREFERRED_SUFFIXES) or _PREFERRED_SERIES.fullmatch(normalized):
        return SecurityKind.PREFERRED
    if _SHARE_TITLE.fullmatch(normalized):
        return SecurityKind.SHARE
    return SecurityKind.OTHER


def _is_debt_title(title: str) -> bool:
    """Return whether a title is a debt title of an explicit form on a captured cover."""
    return _DEBT_TITLE.fullmatch(" ".join(title.split()).lower()) is not None


# --- the rendered cover --------------------------------------------------------------------------------------------


class _CoverError(ValueError):
    """A cover whose rows cannot be read without guessing."""


@dataclass
class _Registered:
    """One registered security: a title and the symbol and exchange rows that follow it."""

    title: str
    cik: str | None
    symbol: str | None = None
    exchange: str | None = None
    no_symbol: str | None = None


@dataclass
class _Cover:
    """The facts of a cover the listing check reads."""

    document_types: set[str] = field(default_factory=set)
    ciks: list[str] = field(default_factory=list)
    registered: list[_Registered] = field(default_factory=list)


class _ReportParser(HTMLParser):
    """Collect the rows of the first top-level ``report`` table as (concept, value cells)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str | None, list[str]]] = []
        self.found = False
        self._depth = 0
        self._active = False
        self._finished = False
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None
        self._concept: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "table":
            self._depth += 1
            if self._depth == 1 and not self._finished and "report" in values.get("class", "").split():
                self._active = self.found = True
        elif not self._active or self._depth != 1:
            return
        elif tag == "tr":
            self._cells, self._concept = [], None
        elif tag in ("td", "th") and self._cells is not None:
            self._cell = []
        elif tag == "a" and self._cells is not None and not self._cells and self._cell is not None:
            onclick = values.get("onclick", "")
            match = _CONCEPT.search(onclick)
            if match is not None and match.group("prefix") == "dei":
                self._concept = match.group("name")
            elif _MEMBER_ROW.search(onclick) is not None:
                self._concept = _MEMBER
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._depth == 1 and self._active:
                self._active, self._finished = False, True
            self._depth = max(self._depth - 1, 0)
        elif not self._active or self._depth != 1:
            return
        elif tag in ("td", "th") and self._cell is not None and self._cells is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            self.rows.append((self._concept, self._cells[1:]))
            self._cells = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _symbol_key(symbol: str) -> str:
    """Return a trading symbol as compared: trimmed, upper-cased, with ``.``, ``-`` and ``/`` the same separator."""
    return symbol.strip().upper().translate(_SEPARATORS)


def _row_value(cells: list[str]) -> str | None:
    """Return the one value a row holds across its period columns, or ``None`` when it holds none."""
    values = {cell for cell in cells if cell}
    if len(values) > 1:
        raise _CoverError("A cover row holds different values in different columns.")
    return next(iter(values), None)


def _normalized_cik(value: str) -> str:
    if not value.isdigit() or int(value) == 0:
        raise _CoverError("A cover registrant key is not a CIK.")
    return value.zfill(10)


def _read_cover(markup: str) -> _Cover:
    """Parse the rows of a rendered cover into its document type, registrant keys and registered securities."""
    parser = _ReportParser()
    parser.feed(markup)
    parser.close()
    if not parser.found:
        raise _CoverError("The page holds no report table.")
    cover = _Cover()
    # A security starts at its title. A symbol, exchange or no-symbol row belongs to the nearest title above it in the
    # same block, a block being the rows between two member headers; one that precedes every title of its block
    # belongs to the first title of the block. The exchange row of a block with no title is the registrant's own and
    # belongs to no security; a symbol row with no title is unreadable.
    current: _Registered | None = None
    loose: list[tuple[str, str]] = []
    for concept, cells in parser.rows:
        if concept is None:
            continue
        if concept == _MEMBER:
            _refuse_untitled_symbol(loose)
            loose, current = [], None
            continue
        value = _row_value(cells)
        if concept == _DOCUMENT_TYPE and value is not None:
            cover.document_types.add(value.upper())
        elif concept == _CIK and value is not None:
            cover.ciks.append(_normalized_cik(value))
        elif concept in _TITLE_CONCEPTS and value is not None:
            first = current is None
            current = _Registered(value, cover.ciks[-1] if cover.ciks else None)
            cover.registered.append(current)
            if first:
                for pending_concept, pending_value in loose:
                    _attach(current, pending_concept, pending_value)
                loose = []
        elif concept in (_SYMBOL, _EXCHANGE, _NO_SYMBOL) and value is not None:
            if current is None:
                loose.append((concept, value))
            else:
                _attach(current, concept, value)
    _refuse_untitled_symbol(loose)
    return cover


def _refuse_untitled_symbol(loose: list[tuple[str, str]]) -> None:
    if any(concept == _SYMBOL for concept, _ in loose):
        raise _CoverError("A symbol row belongs to no registered title.")


def _attach(security: _Registered, concept: str, value: str) -> None:
    attribute = {_SYMBOL: "symbol", _EXCHANGE: "exchange", _NO_SYMBOL: "no_symbol"}[concept]
    if getattr(security, attribute) not in (None, value):
        raise _CoverError("A registered title has two different symbols or exchanges.")
    setattr(security, attribute, value)


def _own_securities(  # noqa: PLR0911
    markup: str, *, form: str, issuer: str
) -> list[_Registered] | CoverUnavailableReason:
    """Return the securities a cover registers for the issuer, or the reason the cover cannot be used."""
    try:
        cover = _read_cover(markup)
    except _CoverError:
        return CoverUnavailableReason.COVER_UNREADABLE
    if not cover.document_types or not cover.ciks:
        return CoverUnavailableReason.COVER_UNREADABLE
    if cover.document_types != {form.strip().upper()}:
        return CoverUnavailableReason.FORM_MISMATCH
    if issuer not in cover.ciks:
        return CoverUnavailableReason.CIK_MISMATCH
    if not cover.registered:
        return CoverUnavailableReason.NO_REGISTRATION_TABLE
    if len(set(cover.ciks)) > 1 and any(item.cik is None for item in cover.registered):
        return CoverUnavailableReason.COVER_UNREADABLE
    # A cover with one registrant key belongs to it; a combined cover's securities belong to the nearest key above.
    return [item for item in cover.registered if len(set(cover.ciks)) == 1 or item.cik == issuer]


def _share_lines(securities: list[_Registered]) -> list[_Registered]:
    """Return the distinct share lines of the securities; one title and symbol listed twice is one line."""
    lines: dict[tuple[str, str], _Registered] = {}
    for item in securities:
        if classify_title(item.title) is SecurityKind.SHARE:
            lines.setdefault((" ".join(item.title.split()), _symbol_key(item.symbol or "")), item)
    return list(lines.values())


def read_renamed_listing(  # noqa: PLR0911, PLR0913
    anchor_markup: str,
    latest_markup: str,
    *,
    ticker: str,
    cik: str,
    anchor_accession: str,
    anchor_form: str,
    latest_accession: str,
    latest_form: str,
    latest_accepted_at: datetime,
    latest_source_url: str,
    retrieved_at: datetime,
) -> ListingEvidence | None:
    """Return the evidence that *ticker* is the renamed one share line of the issuer, or ``None``.

    The ticker is affirmed only when both hold: the anchor cover registers exactly one share line under this CIK, with a
    symbol, and no depositary share; and the issuer's latest annual cover registers *ticker* as its only share line.
    Every other case, including a cover that cannot be read, gives ``None`` and leaves the caller's outcome as it was.
    The evidence describes the latest cover and records both accessions, forms and symbols as filed.
    """
    issuer = cik.zfill(10)
    anchor = _own_securities(anchor_markup, form=anchor_form, issuer=issuer)
    latest = _own_securities(latest_markup, form=latest_form, issuer=issuer)
    if isinstance(anchor, CoverUnavailableReason) or isinstance(latest, CoverUnavailableReason):
        return None
    if any(classify_title(item.title) is SecurityKind.DEPOSITARY_SHARE for item in anchor):
        return None
    anchor_lines, latest_lines = _share_lines(anchor), _share_lines(latest)
    if len(anchor_lines) != 1 or len(latest_lines) != 1:
        return None
    before, after = anchor_lines[0], latest_lines[0]
    wanted = ticker.strip().upper()
    if not before.symbol or not after.symbol or _symbol_key(after.symbol) != _symbol_key(wanted):
        return None
    if _symbol_key(before.symbol) == _symbol_key(wanted) or after.exchange is None:
        return None
    return ListingEvidence(
        ticker=wanted,
        kind=SecurityKind.SHARE,
        title=" ".join(after.title.split()),
        cik=issuer,
        accession=latest_accession,
        form=latest_form.strip().upper(),
        accepted_at=latest_accepted_at,
        source_url=latest_source_url,
        retrieved_at=retrieved_at,
        rename=ListingRename(
            anchor_accession=anchor_accession,
            anchor_form=anchor_form.strip().upper(),
            anchor_symbol=before.symbol.strip(),
            latest_accession=latest_accession,
            latest_form=latest_form.strip().upper(),
            latest_symbol=after.symbol.strip(),
        ),
    )


def read_cover_listing(  # noqa: PLR0911, PLR0913
    markup: str,
    *,
    ticker: str,
    cik: str,
    accession: str,
    form: str,
    accepted_at: datetime,
    boundary: datetime,
    source_url: str,
    retrieved_at: datetime,
) -> ListingResolution:
    """Return what the cover registers for *ticker*, or the reason it cannot be established.

    Args:
        markup: The text of the rendered cover (``R1.htm``).
        ticker: The requested ticker; only a row whose trading symbol equals it, with ``.``, ``-`` and ``/`` read as the
            same separator, is classified.
        cik: The issuer's CIK; a cover that does not name it is refused.
        accession: The anchor filing's accession.
        form: The anchor filing's form as the submissions data gives it; the cover must name the same one.
        accepted_at: When the SEC accepted the filing, timezone-aware.
        boundary: The timezone-aware analysis boundary; a filing accepted after it is refused.
        source_url: The URL the cover was read from.
        retrieved_at: When the cover was read.
    """
    if accepted_at > boundary:
        return ListingResolution(reason=CoverUnavailableReason.ACCEPTED_AFTER_BOUNDARY)
    issuer = cik.zfill(10)
    own = _own_securities(markup, form=form, issuer=issuer)
    if isinstance(own, CoverUnavailableReason):
        return ListingResolution(reason=own)
    wanted = ticker.strip().upper()
    wanted_key = _symbol_key(wanted)
    matches = [item for item in own if _symbol_key(item.symbol or "") == wanted_key]
    if any(item.exchange is None for item in matches):
        return ListingResolution(reason=CoverUnavailableReason.COVER_UNREADABLE)
    titles = {" ".join(item.title.split()) for item in matches}
    if len(titles) > 1:
        # A symbol shared by one share and debt titles of explicit forms is the share's; any other mix is refused.
        shares = [item for item in titles if classify_title(item) is SecurityKind.SHARE]
        if len(shares) != 1 or not all(_is_debt_title(item) for item in titles if item != shares[0]):
            return ListingResolution(reason=CoverUnavailableReason.AMBIGUOUS_LISTING)
        titles = set(shares)
    title = titles.pop() if titles else None
    return ListingResolution(
        evidence=ListingEvidence(
            ticker=wanted,
            kind=SecurityKind.NOT_LISTED if title is None else classify_title(title),
            title=title,
            cik=issuer,
            accession=accession,
            form=form.strip().upper(),
            accepted_at=accepted_at,
            source_url=source_url,
            retrieved_at=retrieved_at,
        )
    )


def looks_like_cover(markup: str) -> bool:
    """Return whether a rendered report is a cover: its table has a document type row and a registrant key row."""
    parser = _ReportParser()
    parser.feed(markup)
    parser.close()
    concepts = {concept for concept, cells in parser.rows if concept is not None and _row_value(cells) is not None}
    return parser.found and _DOCUMENT_TYPE in concepts and _CIK in concepts


_SUMMARY_COVER_NAMES = frozenset({"cover", "cover page"})


class _SummaryParser(HTMLParser):
    """Collect the reports of a ``FilingSummary.xml`` as (file name, short name, menu category)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.reports: list[dict[str, str]] = []
        self._tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs  # the summary's values are element text
        if tag == "report":
            self.reports.append({})
        self._tag = tag if tag in ("htmlfilename", "shortname", "menucategory") else None

    def handle_endtag(self, tag: str) -> None:
        if tag == self._tag:
            self._tag = None

    def handle_data(self, data: str) -> None:
        if self._tag is not None and self.reports:
            report = self.reports[-1]
            report[self._tag] = report.get(self._tag, "") + data


def cover_report_from_summary(summary: str) -> str | None:
    """Return the file name of the one report a ``FilingSummary.xml`` marks as the cover, or ``None``.

    A report is marked as the cover when its menu category is ``Cover`` and its short name is "Cover" or "Cover Page"
    (any case). The category alone marks two reports on the captured summaries, the cover and the audit information.
    No such report, or more than one, or a file name that is not ``R<n>.htm``, gives ``None``.
    """
    parser = _SummaryParser()
    parser.feed(summary)
    parser.close()
    marked = [
        report.get("htmlfilename", "").strip()
        for report in parser.reports
        if report.get("menucategory", "").strip().lower() == "cover"
        and " ".join(report.get("shortname", "").split()).lower() in _SUMMARY_COVER_NAMES
    ]
    if len(marked) != 1 or _REPORT_NAME.fullmatch(marked[0]) is None:
        return None
    return marked[0]


def fetch_anchor_cover(  # noqa: PLR0913
    cik: str,
    accession: str,
    *,
    fetcher: CoverFetcher,
    headers: Mapping[str, str],
    policy: CoverReaderPolicy,
    not_found: ProviderFailureKind,
    provider_id: str,
) -> tuple[str, str]:
    """Return the text and URL of an anchor filing's cover: ``R1.htm``, or the report its summary marks as the cover.

    The first read is always ``R1.htm``. Only when that page is not a cover is ``FilingSummary.xml`` read once; if it
    marks exactly one other report as the cover, that report is read. A summary that is missing or marks no cover or
    more than one leaves the first page, which the reader refuses as unreadable.

    Raises:
        ValueError: The identifiers or the declared identity are not acceptable; a defect of the caller.
        FinancialProviderError: A transport fault, or a 404 of the first page or of the marked report, carrying
            *not_found* for the 404.
    """
    first_url = cover_url(cik, accession)

    def read(url: str) -> str:
        return fetcher(url, headers=headers, policy=policy, not_found=not_found, provider_id=provider_id)

    first = read(first_url)
    if looks_like_cover(first):
        return first, first_url
    try:
        summary = read(summary_url(cik, accession))
    except FinancialProviderError as exc:
        if exc.kind is not not_found:
            raise
        return first, first_url
    report = cover_report_from_summary(summary)
    if report is None or report == COVER_REPORT_NAME:
        return first, first_url
    url = cover_url(cik, accession, report)
    return read(url), url
