"""The first line after a provider failure: what one test request to the implicated provider found.

Every operation that reports a provider failure calls :func:`provider_check_findings` once. The text lines and the
``provider_check`` element of the JSON documents are both built from those findings, so the wording, the order and the
rules live here once and no other path calls the probe. The probe is built by the caller and reaches an operation
through the application context. The check can add lines or an element; it can never replace or hide the failure, and an
error inside it reports ``not_checked``.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from investment_analysis_engine.core.provider_check_element import ProviderCheckItem, ProviderCheckVerdict
from investment_analysis_engine.core.provider_failure_element import ProviderFailure
from investment_analysis_engine.core.provider_failure_kind import PROVIDER_KIND_PRECEDENCE
from investment_analysis_engine.data.provider_probe import ProbeFinding, ProbeVerdict
from investment_analysis_engine.reporting.presentation import PresentationMode, provider_display_name

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
    """What an operation needs from the probe: the finding for one provider."""

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        """Return the finding for *provider_id*; ``requested`` is false when the caller turned the check off."""
        ...


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
        finding: object = probe.check(provider_id, requested=requested)
    except Exception:
        logger.warning("The provider check of %s failed.", provider_id, exc_info=True)
        return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED)
    if not isinstance(finding, ProbeFinding):
        logger.warning("The provider check of %s returned an unexpected value.", provider_id)
        return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED)
    return finding


@dataclass(frozen=True)
class ProviderCheckFindings:
    """What the provider check found for each implicated provider, in the order of their most severe failed kind."""

    findings: tuple[ProbeFinding, ...] = ()

    def lines(self) -> tuple[str, ...]:
        """Return the text lines, one per provider; none when no provider is implicated."""
        lines: list[str] = []
        for finding in self.findings:
            provider = provider_display_name(finding.provider_id)
            if finding.verdict is not ProbeVerdict.NOT_CHECKED:
                template = _FINDING_LINES[finding.verdict]
            elif finding.switched_off:
                template = _SWITCHED_OFF_LINE
            else:
                template = _COULD_NOT_CHECK_LINE
            lines.append(template.format(provider=provider))
        return tuple(lines)

    def element(self) -> tuple[ProviderCheckItem, ...] | None:
        """Return the ``provider_check`` element: one entry per provider, or null when none is implicated."""
        if not self.findings:
            return None
        return tuple(
            ProviderCheckItem(provider_id=finding.provider_id, verdict=ProviderCheckVerdict(finding.verdict.value))
            for finding in self.findings
        )


@dataclass(frozen=True)
class ProviderCheckChoice:
    """The probe a caller was given and whether this invocation asked for the check."""

    probe: ProviderCheck | None
    requested: bool


def provider_check_findings(
    failures: Iterable[ProviderFailure | None], choice: ProviderCheckChoice | None
) -> ProviderCheckFindings:
    """Run the check once for the implicated providers and return what it found; none when none is named.

    A failure that names no provider (``None``) is not implicated in anything. Providers come in the order of their
    most severe failed kind. Without a probe there is nothing to say and no finding is returned. An operation calls
    this once and builds both its text lines and its document element from the result.
    """
    if choice is None or choice.probe is None:
        return ProviderCheckFindings()
    return ProviderCheckFindings(
        tuple(
            _finding_of(choice.probe, provider_id, requested=choice.requested)
            for provider_id in _implicated_providers(failures)
        )
    )


def with_provider_check(output: str, findings: ProviderCheckFindings, mode: PresentationMode) -> str:
    """Return *output* preceded by the provider check lines, for a command that prints its failure as one block.

    ``--json`` output is returned unchanged: the document carries the findings as its ``provider_check`` element.
    """
    if mode is PresentationMode.JSON:
        return output
    return "\n".join((*findings.lines(), output))


__all__ = [
    "ProviderCheck",
    "ProviderCheckChoice",
    "ProviderCheckFindings",
    "provider_check_findings",
    "with_provider_check",
]
