"""Investor-facing presentation for SMA momentum analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.analysis.strategy.momentum.momentum_analyzer import MomentumConfig, MomentumMetrics
from src.core.metric_result import MetricResult
from src.data.financial.resolution_trace import ResolutionTrace
from src.data.instrument_profile import InstrumentProfile, instrument_kind_evidence_payload, profile_identity_resolution
from src.data.market_data import HistoricalDataResolution, MarketDataContext
from src.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentityResolution,
    security_display_label,
    security_identity_payload,
)
from src.reporting.presentation import (
    PresentationMode,
    ResolutionDiagnostic,
    diagnostic_payload,
    format_datetime,
    format_money,
    format_number,
    json_document,
    provider_display_name,
)

_SCHEMA_VERSION = 4
_LIMITATION = (
    "SMA momentum describes recent price trend; it is not a valuation, "
    "fundamental-quality conclusion, or investment recommendation."
)


@dataclass(frozen=True)
class MomentumPresentation:
    """Presentation context for one Momentum analysis."""

    metrics: MomentumMetrics
    config: MomentumConfig
    market_data: MarketDataContext | None = None
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[ResolutionDiagnostic, ...] = ()
    identity_resolution: SecurityIdentityResolution | None = None
    instrument_profile: InstrumentProfile | None = None
    resolution_trace: ResolutionTrace = ResolutionTrace()
    data_resolution: HistoricalDataResolution | None = None

    def __post_init__(self) -> None:
        """Project composed identity evidence when no legacy resolution was supplied."""
        if self.identity_resolution is None and self.instrument_profile is not None:
            object.__setattr__(self, "identity_resolution", profile_identity_resolution(self.instrument_profile))


def render_momentum(
    presentation: MomentumPresentation,
    mode: PresentationMode = PresentationMode.CONCISE,
) -> str:
    """Render Momentum using the same progressive-disclosure grammar as Graham."""
    if mode is PresentationMode.JSON:
        return json_document(_payload(presentation))

    lines = _concise_lines(presentation)
    if mode is PresentationMode.DETAILS:
        lines.extend(_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_diagnostic_lines(presentation))
    return "\n".join(lines)


def _concise_lines(p: MomentumPresentation) -> list[str]:
    metrics = p.metrics
    currency = _currency(p)
    short_label = _sma_label(p.config.short_window, p.market_data)
    long_label = _sma_label(p.config.long_window, p.market_data)
    spread = _sma_spread(metrics)
    spread_percent = _sma_spread_percent(metrics)

    lines = [
        f"{security_display_label(metrics.ticker, p.identity_resolution)} — Momentum",
        f"Status: {metrics.status.display_name(locale='en')}",
        f"Price used ({_close_label(p.market_data)}): {format_money(metrics.current_price, currency)}",
        f"{short_label}: {_optional_money(metrics.short_sma_val, currency)}",
        f"{long_label}: {_optional_money(metrics.long_sma_val, currency)}",
        f"RSI ({p.config.rsi_period} observations): {_metric_result_text(metrics.rsi_14)}",
    ]

    if spread is not None:
        spread_text = format_money(spread, currency)
        if spread_percent is not None:
            spread_text = f"{spread_text} ({format_number(spread_percent)}%)"
        lines.append(f"SMA spread: {spread_text}")

    lines.append(f"Signal: {_trend_interpretation(metrics, p.config, p.market_data)}")

    crossover = _crossover_interpretation(metrics.crossover_signal)
    if crossover is not None:
        lines.append(f"Latest crossover: {crossover}")
    elif metrics.crossover_result is not None and metrics.crossover_result.reason:
        lines.append(f"Latest crossover: unavailable — {metrics.crossover_result.reason}")

    lines.append(f"Data: {_data_summary(p.market_data)}")
    lines.extend(f"Warning: {warning}" for warning in _warnings(p))
    lines.append(f"Limitation: {_LIMITATION}")
    return lines


def _technical_detail_lines(p: MomentumPresentation) -> list[str]:
    context = p.market_data
    interval = context.observation_interval if context is not None else None
    observation_count = context.observation_count if context is not None else None
    provider = context.provider_id if context is not None else None
    data_as_of = context.data_as_of if context is not None else None
    currency = context.currency if context is not None else None

    return [
        "",
        "Details",
        "-------",
        "Method: simple moving-average crossover",
        f"Configured windows: {p.config.short_window} / {p.config.long_window} {_window_basis(context)}",
        f"Configured RSI period: {p.config.rsi_period} observations",
        f"Price basis: {_price_basis_detail(context)}",
        f"Analysis timestamp: {format_datetime(p.metrics.timestamp)}",
        f"Data provider: {provider_display_name(provider)}",
        f"Data interval: {_interval_detail(interval)}",
        f"Latest data observation: {data_as_of.isoformat() if data_as_of is not None else 'unavailable'}",
        f"Observations returned: {observation_count if observation_count is not None else 'unavailable'}",
        f"Currency: {currency or 'unavailable'}",
        f"Retrieval source: {p.data_resolution.source_kind.value if p.data_resolution else 'not retained'}",
        "Originally retrieved: "
        f"{format_datetime(p.data_resolution.retrieved_at) if p.data_resolution else 'not retained'}",
        "Historical timing: daily labels are not verified exchange-close timestamps; "
        "adjusted-price vintages are not retained.",
        *_identity_detail_lines(p.identity_resolution),
        *_kind_detail_lines(p.instrument_profile),
    ]


def _detail_lines(p: MomentumPresentation) -> list[str]:
    context = p.market_data
    lines = [
        "",
        "Calculation and evidence",
        "------------------------",
        "Method: simple moving-average crossover",
        f"Configured windows: {p.config.short_window} / {p.config.long_window} {_window_basis(context)}",
        "Each SMA is the arithmetic mean of closing prices over its observation window.",
        "A crossover requires two consecutive valid SMA pairs; an existing trend alone is not a new crossover.",
        f"RSI uses simple average gains and losses over {p.config.rsi_period} price changes (not Wilder smoothing).",
        "RSI is 50 for a flat window, 100 for gains only and 0 for losses only.",
        f"Price basis: {_price_basis_detail(context)}",
        f"Data provider: {provider_display_name(context.provider_id if context else None)}",
        f"Data interval: {_interval_detail(context.observation_interval if context else None)}",
        f"Currency: {context.currency if context and context.currency else 'unavailable'}",
        "Latest data observation: "
        f"{context.data_as_of.isoformat() if context and context.data_as_of else 'unavailable'}",
        f"Observations returned: {context.observation_count if context else 'unavailable'}",
        "Daily dates do not establish exchange-close timestamps or historical adjustment availability.",
        "Full retrieval, cache and provider evidence: --diagnostics or --json.",
    ]
    if p.instrument_profile and p.instrument_profile.kind_evidence:
        lines.append(_kind_detail_lines(p.instrument_profile)[0])
    return lines


def _resolution_diagnostics(p: MomentumPresentation) -> tuple[ResolutionDiagnostic, ...]:
    items = (
        *(
            ResolutionDiagnostic(item.field_name, item.stage.value, item.outcome.value, item.message)
            for item in p.resolution_trace.events
        ),
        *p.diagnostics,
    )
    return tuple(dict.fromkeys(items))


def _diagnostic_lines(p: MomentumPresentation) -> list[str]:
    metrics = p.metrics
    context = p.market_data
    lines = [
        *_technical_detail_lines(p),
        "",
        "Diagnostics",
        "-----------",
        f"Raw crossover signal: {_optional_metric(metrics.crossover_signal, decimals=0)}",
        f"Trend relationship: {_trend_relationship(metrics) or 'unavailable'}",
        f"Market-data context: {_diagnostic_market_data(context)}",
    ]
    for item in _resolution_diagnostics(p):
        lines.append(f"{item.field_name}: {item.stage} -> {item.outcome} — {item.message}")
    if p.instrument_profile is not None:
        lines.extend(
            f"{item.capability.value}: {item.provider_id}/{item.status.value} — {item.message}"
            for item in p.instrument_profile.diagnostics
        )
    elif p.identity_resolution is not None:
        lines.append(
            f"security_identity: provider -> {p.identity_resolution.status.value} — {p.identity_resolution.message}"
        )
    return lines


def _identity_detail_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
    """Describe the retained current identity snapshot without historical implication."""
    if resolution is None or resolution.identity is None:
        return ["Security identity: unavailable"]
    identity = resolution.identity
    return [
        f"Instrument name: {identity.instrument_name or 'unavailable'}",
        f"Current listing venue: {identity.listing_venue or 'not supplied by selected identity provider'}",
        f"Identity provider: {provider_display_name(identity.provider_id)}",
        f"Identity resolved: {format_datetime(identity.resolved_at)} (current descriptive metadata)",
    ]


def _kind_detail_lines(profile: InstrumentProfile | None) -> list[str]:
    """Describe current provider-backed instrument classification."""
    if profile is None or profile.kind_evidence is None:
        return ["Instrument kind: unavailable"]
    evidence = profile.kind_evidence
    return [
        f"Instrument kind: {evidence.kind.value if evidence.kind is not None else 'unreviewed'}",
        f"Kind provider value: {evidence.provider_value}",
        f"Kind provider: {provider_display_name(evidence.provider_id)}",
        f"Kind resolved: {format_datetime(evidence.resolved_at)} (current classification metadata)",
    ]


def _trend_interpretation(
    metrics: MomentumMetrics,
    config: MomentumConfig,
    context: MarketDataContext | None,
) -> str:
    short_label = _window_label(config.short_window, context)
    long_label = _window_label(config.long_window, context)
    relationship = _trend_relationship(metrics)
    if relationship == "short_above_long":
        return f"{short_label} SMA is above the {long_label} SMA, indicating bullish price momentum"
    if relationship == "short_below_long":
        return f"{short_label} SMA is below the {long_label} SMA, indicating bearish price momentum"
    if relationship == "short_equal_long":
        return (
            f"{short_label} SMA is equal to the {long_label} SMA; "
            "under the configured rule, the trend is classified as bearish"
        )
    return _unclassified_interpretation(config, context)


def _crossover_interpretation(signal: float | None) -> str | None:
    if signal is None:
        return None
    if signal > 0:
        return "bullish crossover detected on the latest observation"
    if signal < 0:
        return "bearish crossover detected on the latest observation"
    return None


def _warnings(p: MomentumPresentation) -> list[str]:
    warnings = list(p.warnings)
    metrics = p.metrics
    if metrics.short_sma_val is None or metrics.long_sma_val is None:
        context = p.market_data
        count = context.observation_count if context is not None else None
        if count is not None and count < p.config.long_window:
            requirements: list[str] = []
            if count < p.config.short_window:
                requirements.append(f"{p.config.short_window} required for the short SMA")
            requirements.append(f"{p.config.long_window} required for the long SMA")
            warnings.append(
                f"Insufficient history for the configured SMA windows: {count} observations available; "
                f"{' and '.join(requirements)}."
            )
        else:
            warnings.append(
                "The configured SMA windows could not be computed from the returned price history; "
                "trend status is unknown."
            )
    return warnings


def _unclassified_interpretation(config: MomentumConfig, context: MarketDataContext | None) -> str:
    count = context.observation_count if context is not None else None
    if count is not None and count < config.long_window:
        return "insufficient history for the configured moving averages; trend is unclassified"
    return "the configured moving averages are unavailable from the returned history; trend is unclassified"


def _data_summary(context: MarketDataContext | None) -> str:
    if context is None:
        return "provider unavailable · interval unavailable · observation date unavailable"

    provider = provider_display_name(context.provider_id) if context.provider_id else "provider unavailable"
    interval = _interval_summary(context.observation_interval)
    if context.data_as_of is None:
        freshness = "observation date unavailable"
    else:
        freshness = f"through {context.data_as_of.isoformat()}"
    return f"{provider} · {interval} · {freshness}"


def _diagnostic_market_data(context: MarketDataContext | None) -> str:
    if context is None:
        return "unavailable"
    return (
        f"provider={context.provider_id or 'unavailable'}, "
        f"interval={context.observation_interval or 'unavailable'}, "
        f"observations={context.observation_count if context.observation_count is not None else 'unavailable'}, "
        f"latest={context.data_as_of.isoformat() if context.data_as_of is not None else 'unavailable'}, "
        f"currency={context.currency or 'unavailable'}, "
        f"adjustment={context.price_adjustment or 'unavailable'}"
    )


def _window_basis(context: MarketDataContext | None) -> str:
    if context is not None and context.observation_interval == "1d":
        return "daily observations"
    return "observations"


def _window_label(window: int, context: MarketDataContext | None) -> str:
    if context is not None and context.observation_interval == "1d":
        return f"{window}-day"
    return f"{window}-observation"


def _sma_label(window: int, context: MarketDataContext | None) -> str:
    return f"{_window_label(window, context)} SMA"


def _interval_summary(interval: str | None) -> str:
    if interval == "1d":
        return "daily"
    return interval or "interval unavailable"


def _interval_detail(interval: str | None) -> str:
    if interval == "1d":
        return "1d (daily)"
    return interval or "unavailable"


def _close_label(context: MarketDataContext | None) -> str:
    if context is not None and context.price_adjustment == "adjusted":
        return "adjusted Close"
    return "Close"


def _price_basis_detail(context: MarketDataContext | None) -> str:
    if context is not None and context.price_adjustment == "adjusted":
        return "latest adjusted historical Close value"
    return "latest historical Close value"


def _json_price_basis(context: MarketDataContext | None) -> str:
    if context is not None and context.price_adjustment == "adjusted":
        return "latest_adjusted_historical_close"
    return "latest_historical_close"


def _currency(p: MomentumPresentation) -> str | None:
    return p.market_data.currency if p.market_data is not None else None


def _optional_money(value: float | None, currency: str | None) -> str:
    return "unavailable" if value is None else format_money(value, currency)


def _optional_metric(value: float | None, *, decimals: int) -> str:
    """Format an optional Momentum metric without exposing non-finite sentinels."""
    return "unavailable" if value is None else format_number(value, decimals=decimals)


def _metric_result_text(result: MetricResult) -> str:
    """Render a standard metric result without leaking machine reason codes."""
    return "unavailable" if result.value is None else format_number(result.value)


def _sma_spread(metrics: MomentumMetrics) -> float | None:
    if metrics.short_sma_val is None or metrics.long_sma_val is None:
        return None
    return metrics.short_sma_val - metrics.long_sma_val


def _sma_spread_percent(metrics: MomentumMetrics) -> float | None:
    spread = _sma_spread(metrics)
    long_sma = metrics.long_sma_val
    if spread is None or long_sma is None or long_sma == 0.0:
        return None
    return (spread / long_sma) * 100.0


def _trend_relationship(metrics: MomentumMetrics) -> str | None:
    if metrics.short_sma_val is None or metrics.long_sma_val is None:
        return None
    if metrics.short_sma_val > metrics.long_sma_val:
        return "short_above_long"
    if metrics.short_sma_val < metrics.long_sma_val:
        return "short_below_long"
    return "short_equal_long"


def _crossover_state(signal: float | None) -> str | None:
    if signal is None:
        return None
    if signal > 0:
        return "bullish_crossover"
    if signal < 0:
        return "bearish_crossover"
    return "no_new_crossover"


def _payload(p: MomentumPresentation) -> dict[str, Any]:
    metrics = p.metrics
    context = p.market_data
    data_as_of = context.data_as_of if context is not None else None
    spread = _sma_spread(metrics)
    spread_percent = _sma_spread_percent(metrics)

    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis": "momentum",
        "ticker": metrics.ticker.upper(),
        "security_identity": security_identity_payload(metrics.ticker, p.identity_resolution),
        "instrument_kind": instrument_kind_evidence_payload(
            p.instrument_profile.kind_evidence if p.instrument_profile is not None else None
        ),
        "method": "sma_crossover",
        "as_of": data_as_of.isoformat() if data_as_of is not None else None,
        "analysis_timestamp": metrics.timestamp.isoformat(),
        "status": metrics.status.value,
        "result": {
            "current_price": metrics.current_price,
            "price_basis": _json_price_basis(context),
            "short_sma": metrics.short_sma_val,
            "long_sma": metrics.long_sma_val,
            "sma_spread": spread,
            "sma_spread_percent": spread_percent,
            "trend_relationship": _trend_relationship(metrics),
            "crossover_signal": metrics.crossover_signal,
            "crossover_result": asdict(metrics.crossover_result) if metrics.crossover_result is not None else None,
            "crossover_state": _crossover_state(metrics.crossover_signal),
            "rsi": {
                "status": metrics.rsi_14.status.value,
                "value": metrics.rsi_14.value,
                "reason_code": metrics.rsi_14.reason_code.value if metrics.rsi_14.reason_code else None,
                "reason": metrics.rsi_14.reason,
            },
        },
        "parameters": {
            "short_window": p.config.short_window,
            "long_window": p.config.long_window,
            "rsi_period": p.config.rsi_period,
        },
        "source": {
            "provider": context.provider_id if context is not None else None,
            "data_as_of": data_as_of.isoformat() if data_as_of is not None else None,
            "interval": context.observation_interval if context is not None else None,
            "observation_count": context.observation_count if context is not None else None,
            "currency": context.currency if context is not None else None,
            "price_adjustment": context.price_adjustment if context is not None else None,
        },
        "warnings": _warnings(p),
        "data_resolution": None
        if p.data_resolution is None
        else {
            "source_kind": p.data_resolution.source_kind.value,
            "retrieved_at": p.data_resolution.retrieved_at.isoformat() if p.data_resolution.retrieved_at else None,
            "cached_at": p.data_resolution.cached_at.isoformat() if p.data_resolution.cached_at else None,
            "resolved_at": p.data_resolution.resolved_at.isoformat(),
            "cache_schema_version": p.data_resolution.cache_schema_version,
        },
        "limitations": [_LIMITATION],
        "diagnostics": [
            *[diagnostic_payload(item) for item in _resolution_diagnostics(p)],
            *(
                [
                    {
                        "field_name": item.capability.value,
                        "stage": "provider",
                        "outcome": item.status.value,
                        "message": item.message,
                        "provider_id": item.provider_id,
                    }
                    for item in p.instrument_profile.diagnostics
                ]
                if p.instrument_profile is not None
                else []
            ),
            *(
                [
                    {
                        "field_name": "security_identity",
                        "stage": "provider",
                        "outcome": p.identity_resolution.status.value,
                        "message": p.identity_resolution.message,
                    }
                ]
                if p.instrument_profile is None
                and p.identity_resolution is not None
                and p.identity_resolution.status is not IdentityResolutionStatus.RESOLVED
                else []
            ),
        ],
    }
