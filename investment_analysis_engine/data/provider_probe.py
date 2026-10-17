"""The automatic provider check: one bounded test request to a provider that has just failed.

:class:`ProviderProbe` runs the shared check body of one provider (the body ``ian health`` and the live test suite
also use) under a time limit and turns its outcome into one of six verdicts. It is built once, at the composition
root, and passed in; nothing below the root imports it. It runs at most once per provider per process and keeps the
finding, so a refresh over many tickers probes once and reuses it. It never retries, repairs, or reads or writes a
cache, and it never raises: whatever goes wrong inside the check, the caller gets a ``not_checked`` finding and the
failure it was explaining is untouched.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from investment_analysis_engine.data.provider_checks import (
    PROVIDER_CHECKS,
    CheckVerdict,
    ProviderCheckEntry,
    ProviderCheckResult,
    ProviderClients,
)

logger = logging.getLogger(__name__)

# The check body enforces its own whole-check deadline. This is the extra time the probe waits for the body to
# return before it stops waiting, so a body that fails to honour its limit still cannot hold a command.
_BODY_GRACE_SECONDS = 2.0


class ProbeVerdict(StrEnum):
    """What a test request found: five provider conditions, or that nothing was checked."""

    HEALTHY = "healthy"
    UNREACHABLE = "unreachable"
    RATE_LIMITED = "rate_limited"
    UNEXPECTED_RESPONSE = "unexpected_response"
    NO_DATA = "no_data"
    NOT_CHECKED = "not_checked"


_VERDICT_OF_CHECK: Mapping[CheckVerdict, ProbeVerdict] = {
    CheckVerdict.OK: ProbeVerdict.HEALTHY,
    CheckVerdict.UNREACHABLE: ProbeVerdict.UNREACHABLE,
    CheckVerdict.RATE_LIMITED: ProbeVerdict.RATE_LIMITED,
    CheckVerdict.UNEXPECTED_RESPONSE: ProbeVerdict.UNEXPECTED_RESPONSE,
    CheckVerdict.NO_DATA: ProbeVerdict.NO_DATA,
    CheckVerdict.NOT_CONFIGURED: ProbeVerdict.NOT_CHECKED,
    CheckVerdict.FAILED: ProbeVerdict.NOT_CHECKED,
}


@dataclass(frozen=True)
class ProbeFinding:
    """The verdict for one provider; ``switched_off`` is true only for a ``not_checked`` the user turned off."""

    provider_id: str
    verdict: ProbeVerdict
    switched_off: bool = False


class ProviderProbe:
    """Runs the shared check of an implicated provider at most once per process and remembers what it found."""

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_seconds: float,
        clients: Callable[[], ProviderClients],
        checks: Sequence[ProviderCheckEntry] = PROVIDER_CHECKS,
    ) -> None:
        """Hold the setting, the time limit, the composition of the provider clients and the checks.

        Args:
            enabled: The ``PROVIDER_CHECK`` setting; when false no provider is ever contacted.
            timeout_seconds: The time limit for one provider's whole test request.
            clients: Builds the provider adapters when a check first runs, so a command that never fails builds
                nothing.
            checks: The providers that have a check, by identity.
        """
        self._enabled = enabled
        self._timeout_seconds = timeout_seconds
        self._clients = clients
        self._entries = {entry.provider_id: entry for entry in checks}
        self._findings: dict[str, ProbeFinding] = {}
        self._lock = threading.Lock()

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        """Return the finding for *provider_id*; ``requested`` is false when the command was given the opt-out.

        A switched-off check and a provider with no check make no request. Otherwise the first call runs the
        check and every later call in this process returns that finding.
        """
        if not (self._enabled and requested):
            return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED, switched_off=True)
        entry = self._entries.get(provider_id)
        if entry is None:
            return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED)
        with self._lock:
            finding = self._findings.get(provider_id)
            if finding is None:
                finding = self._run(entry)
                self._findings[provider_id] = finding
            return finding

    def _run(self, entry: ProviderCheckEntry) -> ProbeFinding:
        """Run one check in a daemon thread and stop waiting at the limit; never raises."""
        outcome: list[object] = []

        def work() -> None:
            try:
                outcome.append(entry.run(self._clients(), timeout_seconds=self._timeout_seconds))
            except Exception:
                logger.warning("The provider check of %s could not be run.", entry.provider_id, exc_info=True)

        worker = threading.Thread(target=work, name="provider-probe", daemon=True)
        worker.start()
        worker.join(self._timeout_seconds + _BODY_GRACE_SECONDS)
        not_checked = ProbeFinding(entry.provider_id, ProbeVerdict.NOT_CHECKED)
        if worker.is_alive() or not outcome:
            return not_checked
        result = outcome[0]
        if not isinstance(result, ProviderCheckResult):
            logger.warning("The provider check of %s returned an unexpected value.", entry.provider_id)
            return not_checked
        return ProbeFinding(entry.provider_id, _VERDICT_OF_CHECK[result.verdict])


__all__ = ["ProbeFinding", "ProbeVerdict", "ProviderProbe"]
