"""The ``health`` command: run the shared provider shape checks and print one line per provider.

The command composes the two production adapters from settings and hands them to the check bodies in
``src.data.provider_checks``, which the live test suite also uses; it carries no probe logic of its own. It is
text only and reports a condition; it never retries, repairs or switches provider.
"""

from __future__ import annotations

from typing import Annotated

import typer

from src.cli_composition import build_sec_production_provider
from src.cli_support import AnalysisConfigurationError
from src.config import settings
from src.data.http_json import fetch_json
from src.data.provider_checks import (
    PROVIDER_CHECKS,
    ProviderCheckEntry,
    ProviderCheckResult,
    ProviderClients,
    SecTransport,
    SecUnavailable,
)
from src.data.yfinance import YFinanceClient


def build_provider_clients() -> ProviderClients:
    """Compose the production adapters; a missing SEC identity becomes an unavailable SEC check, not a skipped one."""
    sec: SecTransport | SecUnavailable
    try:
        build_sec_production_provider()
    except AnalysisConfigurationError as exc:
        sec = SecUnavailable(str(exc))
    else:
        sec = SecTransport(fetch_json, (settings.sec_user_agent or "").strip())
    return ProviderClients(yahoo=YFinanceClient(), sec=sec)


def format_result(result: ProviderCheckResult) -> str:
    """Render one check as ``<provider>: <verdict> (probe: <description>, <elapsed> s)`` plus any failure detail."""
    verdict = "ok" if result.passed else "failed"
    line = f"{result.provider_id}: {verdict} (probe: {result.probe}, {result.elapsed_seconds:.2f} s)"
    return line if result.detail is None else f"{line} - {result.detail}"


def _select(provider: str | None) -> tuple[ProviderCheckEntry, ...]:
    if provider is None:
        return PROVIDER_CHECKS
    wanted = provider.strip().lower()
    selected = tuple(entry for entry in PROVIDER_CHECKS if entry.provider_id == wanted)
    if not selected:
        valid = ", ".join(entry.provider_id for entry in PROVIDER_CHECKS)
        raise typer.BadParameter(
            f"Unknown provider {provider!r}; valid providers are: {valid}.", param_hint="--provider"
        )
    return selected


def health(
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Check one provider (yfinance or sec_edgar) instead of all of them"),
    ] = None,
) -> None:
    """Check that Yahoo and SEC EDGAR still answer in the shape the adapters read."""
    entries = _select(provider)
    clients = build_provider_clients()
    all_passed = True
    for entry in entries:
        result = entry.run(clients)
        all_passed = all_passed and result.passed
        typer.echo(format_result(result))
    if not all_passed:
        raise typer.Exit(code=1)


def register(app: typer.Typer) -> None:
    """Register the ``health`` command on the root Typer app."""
    app.command(name="health")(health)
