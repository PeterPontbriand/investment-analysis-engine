"""The ``health`` command: run the shared provider shape checks and print one line per provider.

The command composes the two production adapters from settings and hands them to the check bodies in
``src.data.provider_checks``, which the live test suite also uses; it carries no probe logic of its own. It prints
one line per provider, or with ``--json`` one typed document, and reports a condition; it never retries, repairs or
switches provider.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version
from typing import Annotated

import typer

from src.cli_composition import build_sec_production_provider
from src.cli_support import parameter_failures
from src.config import settings
from src.core.operator_errors import AnalysisConfigurationError, InvalidParameterError
from src.data.http_json import fetch_json
from src.data.provider_checks import (
    PROVIDER_CHECKS,
    ConnectionStep,
    ProviderCheckEntry,
    ProviderCheckResult,
    ProviderClients,
    SecTransport,
    SecUnavailable,
)
from src.data.yfinance import YFinanceClient
from src.reporting.documents.health import ProviderHealthDocument, ProviderHealthEntry, ProviderLibrary


def build_provider_clients() -> ProviderClients:
    """Compose the production adapters; a missing SEC identity becomes an unavailable SEC check, not a skipped one."""
    sec: SecTransport | SecUnavailable
    try:
        build_sec_production_provider()
    except AnalysisConfigurationError as exc:
        sec = SecUnavailable(str(exc))
    else:
        sec = SecTransport(fetch_json, (settings.sec_user_agent or "").strip())
    return ProviderClients(
        yahoo=YFinanceClient(),
        sec=sec,
        connection=ConnectionStep(),
    )


def format_result(result: ProviderCheckResult) -> str:
    """Render one check as ``<provider>: <verdict> (probe: <description>, <elapsed> s)`` plus any failure detail.

    The verdict is the check's outcome with underscores read as spaces: ``ok``, ``unreachable``,
    ``rate limited``, ``unexpected response``, ``no data``, ``not configured`` or ``failed``.
    """
    verdict = result.verdict.value.replace("_", " ")
    line = f"{result.provider_id}: {verdict} (probe: {result.probe}, {result.elapsed_seconds:.2f} s)"
    return line if result.detail is None else f"{line} - {result.detail}"


def _library_of(provider_id: str, library_version: Callable[[str], str]) -> ProviderLibrary | None:
    """Return a provider's library and installed version, or ``None`` when it has none or is not installed."""
    entry = next((candidate for candidate in PROVIDER_CHECKS if candidate.provider_id == provider_id), None)
    if entry is None or entry.library is None:
        return None
    try:
        return ProviderLibrary(name=entry.library, version=library_version(entry.library))
    except PackageNotFoundError:
        return None


def health_document(
    results: Sequence[ProviderCheckResult], *, library_version: Callable[[str], str] = installed_version
) -> ProviderHealthDocument:
    """Build the typed ``--json`` document from the check results, in the order given.

    ``library_version`` reads a library's installed version from the package metadata.
    """
    return ProviderHealthDocument(
        providers=tuple(
            ProviderHealthEntry(
                provider_id=result.provider_id,
                verdict=result.verdict.value,
                probe=result.probe,
                elapsed_seconds=round(result.elapsed_seconds, 2),
                detail=result.detail,
                library=_library_of(result.provider_id, library_version),
            )
            for result in results
        )
    )


def _select(provider: str | None) -> tuple[ProviderCheckEntry, ...]:
    if provider is None:
        return PROVIDER_CHECKS
    wanted = provider.strip().lower()
    selected = tuple(entry for entry in PROVIDER_CHECKS if entry.provider_id == wanted)
    if not selected:
        valid = ", ".join(entry.provider_id for entry in PROVIDER_CHECKS)
        raise InvalidParameterError(
            f"Unknown --provider {provider!r}; valid providers are: {valid}.", parameters=("--provider",)
        )
    return selected


def health(
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Check one provider (yfinance or sec_edgar) instead of all of them"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Write one JSON document to standard output instead of one line per provider"),
    ] = False,
) -> None:
    """Check that Yahoo and SEC EDGAR still answer in the shape the adapters read."""
    with parameter_failures(json_output=json_output):
        entries = _select(provider)
    clients = build_provider_clients()
    results: list[ProviderCheckResult] = []
    for entry in entries:
        result = entry.run(clients)
        results.append(result)
        if not json_output:
            typer.echo(format_result(result))
    if json_output:
        typer.echo(health_document(results).model_dump_json())
    if not all(result.passed for result in results):
        raise typer.Exit(code=1)


def register(app: typer.Typer) -> None:
    """Register the ``health`` command on the root Typer app."""
    app.command(name="health")(health)
