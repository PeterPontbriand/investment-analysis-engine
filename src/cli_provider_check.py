"""The first line after a provider failure: what one test request to the implicated provider found.

Every command that reports a provider failure in a text mode (``momentum``, ``graham-number``, ``graham-growth``,
``fcf-growth`` and ``refresh``) calls :func:`provider_check_lines`, so the wording and the rules live here once. The
probe itself is built at the composition root (``src.cli``) and reaches a command through the Typer context. The
check can add lines; it can never replace or hide the failure, and an error inside it reports ``not_checked``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import typer

from src.core.provider_failure_element import ProviderFailure
from src.core.provider_failure_kind import PROVIDER_KIND_PRECEDENCE
from src.data.provider_probe import ProbeFinding, ProbeVerdict
from src.reporting.presentation import PresentationMode, provider_display_name

logger = logging.getLogger(__name__)

_FINDING_LINES = {
    ProbeVerdict.UNREACHABLE: "{provider} is not answering: a test request also failed.",
    ProbeVerdict.RATE_LIMITED: "{provider} is limiting requests: a test request was also refused.",
    ProbeVerdict.UNEXPECTED_RESPONSE: "{provider} answered a test request in a form this application does not read.",
    ProbeVerdict.NO_DATA: "{provider} returned no data for a known test ticker. It may be limiting requests.",
    ProbeVerdict.HEALTHY: "{provider} answered a test request normally. The failure may be specific to this request.",
}
_SWITCHED_OFF_LINE = "{provider} was not checked (the provider check is turned off)."
_COULD_NOT_CHECK_LINE = "{provider} could not be checked."


@runtime_checkable
class ProviderCheck(Protocol):
    """What a command needs from the probe: the finding for one provider."""

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        """Return the finding for *provider_id*; ``requested`` is false under ``--no-provider-check``."""
        ...


@dataclass(frozen=True)
class ProviderCheckChoice:
    """The probe a command was given and whether this invocation asked for the check."""

    probe: ProviderCheck | None
    requested: bool


def provider_check_choice(context: typer.Context, *, no_provider_check: bool) -> ProviderCheckChoice:
    """Read the probe the composition root put on the Typer context and pair it with the command's option."""
    probe = context.obj if isinstance(context.obj, ProviderCheck) else None
    return ProviderCheckChoice(probe=probe, requested=not no_provider_check)


def _implicated_providers(failures: Iterable[ProviderFailure | None]) -> tuple[str, ...]:
    """Return each implicated provider once, ordered by its most severe failed kind and then by first appearance."""
    severity: dict[str, int] = {}
    appearance: dict[str, int] = {}
    for failure in failures:
        if failure is None:
            continue
        for item in failure.inputs:
            rank = PROVIDER_KIND_PRECEDENCE.index(item.kind)
            severity[item.provider_id] = min(rank, severity.get(item.provider_id, rank))
            appearance.setdefault(item.provider_id, len(appearance))
    return tuple(sorted(severity, key=lambda provider_id: (severity[provider_id], appearance[provider_id])))


def _finding_of(probe: ProviderCheck, provider_id: str, *, requested: bool) -> ProbeFinding:
    """Ask the probe, failing open: any error or unexpected answer is a provider that could not be checked."""
    try:
        finding = probe.check(provider_id, requested=requested)
    except Exception:
        logger.warning("The provider check of %s failed.", provider_id, exc_info=True)
        return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED)
    if not isinstance(finding, ProbeFinding):
        logger.warning("The provider check of %s returned an unexpected value.", provider_id)
        return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED)
    return finding


def provider_check_lines(
    failures: Iterable[ProviderFailure | None], choice: ProviderCheckChoice | None
) -> tuple[str, ...]:
    """Return the lines to print before the failure text: one per implicated provider, none when none is named.

    A failure that names no provider (``None``) is not implicated in anything and adds no line. Providers come in
    the order of their most severe failed kind. Without a probe there is nothing to say and no line is returned.
    """
    if choice is None or choice.probe is None:
        return ()
    lines: list[str] = []
    for provider_id in _implicated_providers(failures):
        finding = _finding_of(choice.probe, provider_id, requested=choice.requested)
        provider = provider_display_name(provider_id)
        if finding.verdict is not ProbeVerdict.NOT_CHECKED:
            template = _FINDING_LINES[finding.verdict]
        elif finding.switched_off:
            template = _SWITCHED_OFF_LINE
        else:
            template = _COULD_NOT_CHECK_LINE
        lines.append(template.format(provider=provider))
    return tuple(lines)


def with_provider_check(
    output: str, failure: ProviderFailure | None, choice: ProviderCheckChoice | None, mode: PresentationMode
) -> str:
    """Return *output* preceded by the provider check lines, for a command that prints its failure as one block.

    ``--json`` output is returned unchanged: the check adds nothing to a document.
    """
    if mode is PresentationMode.JSON:
        return output
    return "\n".join((*provider_check_lines((failure,), choice), output))


def echo_provider_check(
    failures: Iterable[ProviderFailure | None], choice: ProviderCheckChoice | None, *, err: bool
) -> None:
    """Write the provider check lines to the stream the failure text that follows them uses."""
    for line in provider_check_lines(failures, choice):
        typer.echo(line, err=err)
