"""Narrow Inline XBRL evidence for domestic single-common-class securities.

This parser verifies existing inputs; it does not supply or calculate financial
facts. Unsupported markup or class relationships fail closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from src.data.financial.provenance import ResolvedInput, SourceKind

MAPPING_ID = "sec_domestic_single_common_class_v1"
_COMMON = re.compile(r"common stock(?:, \$[0-9]+(?:\.[0-9]+)? par value|, par value \$[0-9]+(?:\.[0-9]+)? per share)?")
_DEBT = re.compile(r"[0-9]+(?:\.[0-9]+)?% notes due [0-9]{4}")
_VOID = frozenset(
    {"meta", "link", "br", "hr", "img", "input", "wbr", "area", "base", "col", "embed", "param", "source", "track"}
)
_NUMERIC = frozenset(
    {
        "EarningsPerShareDiluted",
        "StockholdersEquity",
        "CommonStockSharesOutstanding",
        "PreferredStockSharesOutstanding",
        "CommonStockSharesIssued",
        "TreasuryStockCommonShares",
        "CommonStockValue",
    }
)


class UnitMappingError(ValueError):
    """An unsupported or inconsistent evidence shape, never an inferred ratio."""


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    namespaces: dict[str, str]
    parts: list[str | _Node] = field(default_factory=list)

    def text(self) -> str:
        return "".join(part if isinstance(part, str) else part.text() for part in self.parts)

    def descendants(self) -> list[_Node]:
        return [child for part in self.parts if isinstance(part, _Node) for child in [part, *part.descendants()]]

    def name(self, value: str | None = None) -> tuple[str, str]:
        prefix, separator, local = (value or self.tag).partition(":")
        return (self.namespaces.get(prefix, ""), local) if separator else (self.namespaces.get("", ""), prefix)


class _DocumentParser(HTMLParser):
    """Capture contexts and facts without evaluating external resources."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        namespaces = dict(self.stack[-1].namespaces)
        namespaces.update(
            {key.partition(":")[2]: value for key, value in attributes.items() if key.startswith("xmlns:")}
        )
        if "xmlns" in attributes:
            namespaces[""] = attributes["xmlns"]
        node = _Node(tag, attributes, namespaces)
        self.stack[-1].parts.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if len(self.stack) > 1 and self.stack[-1].tag == tag:
            self.stack.pop()
        elif tag not in _VOID:
            raise UnitMappingError("Unbalanced filing markup.")

    def handle_data(self, data: str) -> None:
        self.stack[-1].parts.append(data)


def _family(uri: str, family: str) -> bool:
    patterns = {
        "dei": r"https?://xbrl\.sec\.gov/dei/[0-9]{4}",
        "us-gaap": r"https?://fasb\.org/us-gaap/[0-9]{4}",
        "ix": r"http://www\.xbrl\.org/(?:2008|2013)/inlineXBRL",
    }
    return re.fullmatch(patterns[family], uri) is not None


def _is(node: _Node, uri: str, local: str) -> bool:
    return node.name() == (uri, local)


def _single_text(nodes: list[_Node], uri: str, local: str) -> str:
    values = {node.text().strip() for node in nodes if _is(node, uri, local)}
    if len(values) != 1:
        raise UnitMappingError("Missing or ambiguous context field.")
    return values.pop()


@dataclass(frozen=True)
class _Context:
    cik: str
    start: str | None
    end: str
    dimensions: tuple[tuple[str, str], ...]


def _context(node: _Node) -> _Context:
    nodes = node.descendants()
    uri = "http://www.xbrl.org/2003/instance"
    cik = _single_text(nodes, uri, "identifier")
    if not cik.isdigit():
        raise UnitMappingError("Invalid context issuer.")
    instants = [item for item in nodes if _is(item, uri, "instant")]
    start = None if instants else _single_text(nodes, uri, "startdate")
    end = _single_text(nodes, uri, "instant" if instants else "enddate")
    dimensions = []
    for item in nodes:
        if item.name()[0] == "http://xbrl.org/2006/xbrldi":
            if item.name()[1] != "explicitmember":
                dimensions.append(("unsupported", "typed"))
                continue
            axis_uri, axis = item.name(item.attrs.get("dimension", ""))
            if axis == "StatementClassOfStockAxis" and not _family(axis_uri, "us-gaap"):
                raise UnitMappingError("Unknown share-class axis namespace.")
            member_uri, member = item.name(item.text().strip())
            if not member_uri or not member:
                raise UnitMappingError("Unknown class member namespace.")
            dimensions.append((f"{axis_uri}:{axis}", f"{member_uri}:{member}"))
    return _Context(cik.zfill(10), start, end, tuple(sorted(dimensions)))


def _fact_text(node: _Node) -> str:
    if "continuedat" in node.attrs or any(
        node.name(key) == ("http://www.w3.org/2001/XMLSchema-instance", "nil") for key in node.attrs
    ):
        raise UnitMappingError("Unsupported continued or nil fact.")
    for child in node.descendants():
        if _family(child.name()[0], "ix") and child.name()[1] in ("exclude", "continuation"):
            raise UnitMappingError("Unsupported fact text transformation.")
    return " ".join(node.text().split())


def _number(node: _Node) -> Decimal:
    text = _fact_text(node)
    transformation = node.attrs.get("format")
    if transformation:
        uri, local = node.name(transformation)
        if not re.fullmatch(r"http://www\.xbrl\.org/inlineXBRL/transformation/[0-9-]+", uri):
            raise UnitMappingError("Unknown numeric transformation namespace.")
        if local not in ("num-dot-decimal", "numdotdecimal"):
            raise UnitMappingError("Unsupported numeric transformation.")
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", text):
            raise UnitMappingError("Malformed decimal value.")
        text = text.replace(",", "")
    elif not re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text):
        raise UnitMappingError("Unsupported decimal syntax.")
    try:
        scale = int(node.attrs.get("scale", "0"))
        if not -20 <= scale <= 20 or node.attrs.get("sign", "") not in ("", "-"):
            raise UnitMappingError("Unsupported scale or sign.")
        value = Decimal(text) * (Decimal(10) ** scale)
        if node.attrs.get("sign") == "-":
            value = -value
        if not value.is_finite():
            raise UnitMappingError("Nonfinite filing value.")
        return value
    except (InvalidOperation, ValueError) as exc:
        raise UnitMappingError("Invalid filing numeric evidence.") from exc


@dataclass(frozen=True)
class ParsedUnitDocument:
    """Validated single-class evidence with original numeric fact contexts."""

    class_title: str
    class_contexts: tuple[str, ...]
    contexts: dict[str, _Context]
    facts: tuple[_Node, ...]
    units: dict[str, tuple[str, ...]]
    listing_venue: str | None = None

    def verify(self, value: ResolvedInput) -> tuple[str, ...]:
        """Match a resolved source leaf to an entity-wide filing fact."""
        concept = (value.provider_field or "").removeprefix("us-gaap:")
        matches: list[tuple[str, Decimal]] = []
        for fact in self.facts:
            if fact.name(fact.attrs["name"])[1] != concept:
                continue
            context_id = fact.attrs.get("contextref", "")
            context = self.contexts.get(context_id)
            if context is None:
                raise UnitMappingError("Missing financial context.")
            if context.dimensions:
                # Disaggregated equity/investee disclosures are not candidates
                # for an entity-wide source fact. The document-level share-class
                # check still rejects class-specific financial evidence.
                continue
            end = value.observation_period_end
            start = value.observation_period_start
            if end is None or context.end != end.date().isoformat():
                continue
            if context.start != (start.date().isoformat() if start is not None else None):
                continue
            expected_units: tuple[str, ...] = ("shares",) if value.units == "shares" else (value.currency or "",)
            if value.units == "currency_per_share":
                expected_units = (value.currency or "", "shares")
            if self.units.get(fact.attrs.get("unitref", "")) != expected_units:
                raise UnitMappingError("Financial units differ.")
            matches.append((context_id, _number(fact)))
        if not matches or {number for _, number in matches} != {Decimal(str(value.value))}:
            raise UnitMappingError("Financial source value is absent or contradictory.")
        return tuple(sorted({context_id for context_id, _ in matches}))


def parse_unit_document(markup: str, *, cik: str, ticker: str) -> ParsedUnitDocument:  # noqa: PLR0912, PLR0915
    """Affirm only an explicitly registered single ordinary common-stock class."""
    parser = _DocumentParser()
    parser.feed(markup)
    parser.close()
    if len(parser.stack) != 1:
        raise UnitMappingError("Truncated filing markup.")
    nodes = parser.root.descendants()
    contexts: dict[str, _Context] = {}
    units: dict[str, tuple[str, ...]] = {}
    uri = "http://www.xbrl.org/2003/instance"
    for node in nodes:
        if _is(node, uri, "context"):
            identifier = node.attrs.get("id", "")
            if not identifier or identifier in contexts:
                raise UnitMappingError("Duplicate or missing context ID.")
            contexts[identifier] = _context(node)
        if _is(node, uri, "unit"):
            identifier = node.attrs.get("id", "")
            if not identifier or identifier in units:
                raise UnitMappingError("Duplicate or missing unit ID.")
            measures = []
            descendants = node.descendants()
            dividers = [item for item in descendants if _is(item, uri, "divide")]
            if dividers:
                numerator = [item for item in descendants if _is(item, uri, "unitnumerator")]
                denominator = [item for item in descendants if _is(item, uri, "unitdenominator")]
                if len(dividers) != 1 or len(numerator) != 1 or len(denominator) != 1:
                    raise UnitMappingError("Malformed divided unit.")
                if any(
                    len([item for item in part.descendants() if _is(item, uri, "measure")]) != 1
                    for part in (numerator[0], denominator[0])
                ):
                    raise UnitMappingError("Unsupported compound unit.")
                descendants = [*numerator[0].descendants(), *denominator[0].descendants()]
            for item in descendants:
                if _is(item, uri, "measure"):
                    measure_uri, measure = item.name(item.text().strip())
                    measures.append(
                        measure
                        if (
                            (measure_uri == uri and measure == "shares")
                            or measure_uri == "http://www.xbrl.org/2003/iso4217"
                        )
                        else "unsupported"
                    )
            units[identifier] = tuple(measures)
    # Only relevant financial/class contexts are checked; segment disclosures elsewhere are not evidence.
    titles: dict[str, dict[str, str]] = {}
    financial = []
    for node in nodes:
        if not _family(node.name()[0], "ix") or "name" not in node.attrs:
            continue
        namespace, concept = node.name(node.attrs["name"])
        if _family(namespace, "us-gaap") and concept in _NUMERIC:
            financial.append(node)
        if _family(namespace, "dei") and concept in (
            "Security12bTitle",
            "Security12gTitle",
            "TradingSymbol",
            "SecurityExchangeName",
        ):
            context_id = node.attrs.get("contextref", "")
            fields = titles.setdefault(context_id, {})
            text = _fact_text(node)
            if concept in fields and fields[concept] != text:
                raise UnitMappingError("Conflicting registration facts.")
            fields[concept] = text
    common: list[tuple[str, str, _Context]] = []
    for context_id, fields in titles.items():
        registered = {
            fields[key].lower()
            for key in ("Security12bTitle", "Security12gTitle")
            if key in fields and fields[key].lower() not in ("none", "")
        }
        if len(registered) > 1:
            raise UnitMappingError("Conflicting registered class titles.")
        title = fields.get("Security12bTitle", fields.get("Security12gTitle", ""))
        normalized = title.lower()
        if normalized in ("none", "") and "Security12gTitle" in fields:
            continue
        context = contexts.get(context_id)
        if context is None or context.cik != cik.zfill(10):
            raise UnitMappingError("Registration issuer is unavailable or mismatched.")
        if _DEBT.fullmatch(normalized):
            continue
        if not _COMMON.fullmatch(normalized):
            raise UnitMappingError("Unsupported registered class.")
        if any(not axis.endswith(":StatementClassOfStockAxis") for axis, _ in context.dimensions):
            raise UnitMappingError("Unsupported common class dimension.")
        if fields.get("TradingSymbol") != ticker or not fields.get("SecurityExchangeName"):
            raise UnitMappingError("Common stock symbol or exchange is unverified.")
        common.append((context_id, normalized, context))
    if (
        not common
        or len({(title, context.dimensions, context.start, context.end) for _, title, context in common}) != 1
    ):
        raise UnitMappingError("Single common class is not established.")
    for fact in financial:
        context = contexts.get(fact.attrs.get("contextref", ""))
        if context is None or context.cik != cik.zfill(10):
            raise UnitMappingError("Ambiguous financial share context.")
        if any(axis.endswith(":StatementClassOfStockAxis") for axis, _ in context.dimensions):
            raise UnitMappingError("Class-specific financial input.")
    if not any(
        fact.name(fact.attrs["name"])[1]
        in ("CommonStockValue", "CommonStockSharesIssued", "CommonStockSharesOutstanding")
        and not contexts[fact.attrs.get("contextref", "")].dimensions
        and _number(fact) > 0
        for fact in financial
    ):
        raise UnitMappingError("Positive common-stock evidence is missing.")
    return ParsedUnitDocument(
        common[0][1],
        tuple(sorted(item[0] for item in common)),
        contexts,
        tuple(financial),
        units,
        "; ".join(sorted({titles[item[0]]["SecurityExchangeName"] for item in common})),
    )


def source_leaves(inputs: tuple[ResolvedInput, ...]) -> tuple[ResolvedInput, ...]:
    """Recover original source leaves, including cached adapter derivations."""
    leaves: list[ResolvedInput] = []
    for value in inputs:
        if value.source_kind is SourceKind.OVERRIDE:
            continue
        if value.lineage is not None:
            leaves.extend(source_leaves(value.lineage.components))
        else:
            leaves.append(value)
    return tuple(leaves)


def source_accession(value: ResolvedInput) -> str:
    """Require a source accession, rather than silently replacing old cache evidence."""
    accession = (value.provider_fact_id or "").partition(":")[0]
    if value.provider_id != "sec_edgar" or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
        raise UnitMappingError("Missing original SEC source lineage; refresh with --no-cache.")
    if not (value.provider_field or "").startswith("us-gaap:"):
        raise UnitMappingError("Unsupported source concept.")
    return accession
