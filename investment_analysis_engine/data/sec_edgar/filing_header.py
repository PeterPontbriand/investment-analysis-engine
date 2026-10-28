"""Reading the as-filed SIC code from the SEC header of an annual filing.

The header of a filing (``<accession>.hdr.sgml``) records the ``ASSIGNED-SIC`` the SEC had assigned to each registrant
on the filing date, so it is the point-in-time industry code. The ``sic`` field of the EDGAR submissions data is the
issuer's code today and is never a substitute. A combined filing has one ``<FILER>`` block per registrant, and only the
block whose ``<CIK>`` is the issuer's is read.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

_SEC_EASTERN = ZoneInfo("America/New_York")
_TAG_LINE = re.compile(r"^<(?P<tag>/?[A-Z0-9-]+)>(?P<value>.*)$")
_CODE = re.compile(r"[0-9]{4}")
_ACCEPTANCE = re.compile(r"[0-9]{14}")
_FILING_DATE = re.compile(r"[0-9]{8}")
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")


class SicUnavailableReason(StrEnum):
    """Why an as-filed SIC code could not be established for an anchor filing.

    ``NO_ANCHOR_FILING`` says SEC EDGAR has no CIK for the ticker. ``ACCEPTED_AFTER_BOUNDARY`` says the anchor filing,
    or every annual filing of the registrant, was accepted after the boundary.
    """

    NO_ANCHOR_FILING = "no_anchor_filing"
    HEADER_MISSING = "header_missing"
    HEADER_INCOMPLETE = "header_incomplete"
    NO_FILER_BLOCK = "no_filer_block"
    AMBIGUOUS_FILER_BLOCK = "ambiguous_filer_block"
    CODE_MISSING = "code_missing"
    CODE_MALFORMED = "code_malformed"
    ACCESSION_MISMATCH = "accession_mismatch"
    FILING_DATE_UNAVAILABLE = "filing_date_unavailable"
    FILING_DATE_MISMATCH = "filing_date_mismatch"
    ACCEPTED_AFTER_BOUNDARY = "accepted_after_boundary"


@dataclass(frozen=True)
class AsFiledSic:
    """The SIC code a filing's header assigns to the issuer, with the filing evidence it came from."""

    code: int
    cik: str
    accession: str
    filing_date: date
    accepted_at: datetime
    source_url: str
    retrieved_at: datetime

    def __post_init__(self) -> None:
        """Reject a code outside four digits and timestamps without a timezone."""
        if not 1 <= self.code <= 9999:
            raise ValueError("An as-filed SIC code has four digits and is not 0000.")
        if not re.fullmatch(r"[0-9]{10}", self.cik):
            raise ValueError("The as-filed SIC evidence requires a ten-digit CIK.")
        if not _ACCESSION.fullmatch(self.accession):
            raise ValueError("The as-filed SIC evidence requires a dashed accession number.")
        for stamp in (self.accepted_at, self.retrieved_at):
            if stamp.utcoffset() is None:
                raise ValueError("As-filed SIC timestamps must be timezone-aware.")
        if not self.source_url:
            raise ValueError("The as-filed SIC evidence requires its source URL.")


@dataclass(frozen=True)
class AsFiledSicResolution:
    """Either the as-filed SIC evidence or the reason it is unavailable, never both and never neither."""

    sic: AsFiledSic | None = None
    reason: SicUnavailableReason | None = None

    def __post_init__(self) -> None:
        """Require exactly one of the evidence and the reason."""
        if (self.sic is None) == (self.reason is None):
            raise ValueError("An as-filed SIC resolution holds exactly one of the evidence and the reason.")


@dataclass(frozen=True)
class _FilerBlock:
    """The two lines of one ``<FILER>`` block the reader uses."""

    cik: str | None
    code: str | None


def _read_header(text: str) -> tuple[dict[str, str], list[_FilerBlock]]:
    """Split a header into its three top-level fields and its ``<FILER>`` blocks, ignoring every other line."""
    top: dict[str, str] = {}
    filers: list[_FilerBlock] = []
    block: dict[str, str] | None = None
    for raw in text.splitlines():
        match = _TAG_LINE.match(raw.strip())
        if match is None:
            continue
        tag, value = match.group("tag"), match.group("value").strip()
        if tag == "FILER":
            block = {}
        elif tag == "/FILER":
            if block is not None:
                filers.append(_FilerBlock(block.get("CIK"), block.get("ASSIGNED-SIC")))
            block = None
        elif block is not None:
            block.setdefault(tag, value)
        elif tag in ("ACCEPTANCE-DATETIME", "ACCESSION-NUMBER", "FILING-DATE"):
            top.setdefault(tag, value)
    return top, filers


def parse_filing_header(  # noqa: PLR0911, PLR0913
    text: str,
    *,
    cik: str,
    accession: str,
    filing_date: date | None,
    boundary: datetime,
    source_url: str,
    retrieved_at: datetime,
) -> AsFiledSicResolution:
    """Return the issuer's as-filed SIC code from a filing header, or the reason it cannot be established.

    Args:
        text: The text of ``<accession>.hdr.sgml``.
        cik: The issuer's CIK; only the ``<FILER>`` block with this ``<CIK>`` is read.
        accession: The anchor filing's accession; the header must name the same one.
        filing_date: The filing date the submissions data gives the accession, or ``None`` when it gives none.
        boundary: The timezone-aware analysis boundary; a filing accepted after it is rejected.
        source_url: The URL the header was read from.
        retrieved_at: When the header was read.
    """
    top, filers = _read_header(text)
    header_accession = top.get("ACCESSION-NUMBER")
    header_date = top.get("FILING-DATE")
    header_accepted = top.get("ACCEPTANCE-DATETIME")
    if (
        header_accession is None
        or header_date is None
        or header_accepted is None
        or not _FILING_DATE.fullmatch(header_date)
        or not _ACCEPTANCE.fullmatch(header_accepted)
    ):
        return AsFiledSicResolution(reason=SicUnavailableReason.HEADER_INCOMPLETE)
    if header_accession != accession:
        return AsFiledSicResolution(reason=SicUnavailableReason.ACCESSION_MISMATCH)
    if filing_date is None:
        return AsFiledSicResolution(reason=SicUnavailableReason.FILING_DATE_UNAVAILABLE)
    try:
        parsed_date = datetime.strptime(header_date, "%Y%m%d").date()
        accepted_at = datetime.strptime(header_accepted, "%Y%m%d%H%M%S").replace(tzinfo=_SEC_EASTERN).astimezone(UTC)
    except ValueError:
        return AsFiledSicResolution(reason=SicUnavailableReason.HEADER_INCOMPLETE)
    if parsed_date != filing_date:
        return AsFiledSicResolution(reason=SicUnavailableReason.FILING_DATE_MISMATCH)
    own = [item for item in filers if item.cik is not None and item.cik.isdigit() and int(item.cik) == int(cik)]
    if not own:
        return AsFiledSicResolution(reason=SicUnavailableReason.NO_FILER_BLOCK)
    codes = {item.code for item in own}
    if len(codes) != 1:
        return AsFiledSicResolution(reason=SicUnavailableReason.AMBIGUOUS_FILER_BLOCK)
    code = codes.pop()
    if code is None or not code:
        return AsFiledSicResolution(reason=SicUnavailableReason.CODE_MISSING)
    if _CODE.fullmatch(code) is None or int(code) == 0:
        return AsFiledSicResolution(reason=SicUnavailableReason.CODE_MALFORMED)
    if accepted_at > boundary:
        return AsFiledSicResolution(reason=SicUnavailableReason.ACCEPTED_AFTER_BOUNDARY)
    return AsFiledSicResolution(
        sic=AsFiledSic(
            code=int(code),
            cik=cik.zfill(10),
            accession=accession,
            filing_date=parsed_date,
            accepted_at=accepted_at,
            source_url=source_url,
            retrieved_at=retrieved_at,
        )
    )
