"""The provider probe: verdicts, one request per provider per process, and failing open. No real service is called."""

import threading
from collections.abc import Callable, Iterator
from typing import cast
from unittest.mock import patch

import pytest

from src.core.provider_failure_kind import ProviderFailureKind
from src.data import provider_probe
from src.data.provider_checks import (
    PROVIDER_CHECKS,
    CheckVerdict,
    ProviderCheckEntry,
    ProviderCheckResult,
    ProviderClients,
)
from src.data.provider_probe import ProbeVerdict, ProviderProbe

_YAHOO = "yfinance"


def _no_clients() -> ProviderClients:
    """Stand in for the provider clients; the fake check bodies never use them."""
    return cast(ProviderClients, object())


def _join_probe_threads() -> None:
    """Wait for every probe worker thread to end, so none outlives the test that started it."""
    for thread in threading.enumerate():
        if thread.name == "provider-probe":
            thread.join(timeout=5)
    assert not [t for t in threading.enumerate() if t.name == "provider-probe"]


@pytest.fixture(autouse=True)
def _no_probe_thread_outlives_a_test() -> Iterator[None]:
    yield
    _join_probe_threads()


def _result(provider_id: str, verdict: CheckVerdict) -> ProviderCheckResult:
    kind = (
        None
        if verdict in (CheckVerdict.OK, CheckVerdict.NOT_CONFIGURED, CheckVerdict.FAILED)
        else ProviderFailureKind(verdict.value)
    )
    passed = verdict is CheckVerdict.OK
    return ProviderCheckResult(
        provider_id,
        "a test probe",
        passed,
        0.01,
        None if passed else "detail",
        kind,
        not_configured=verdict is CheckVerdict.NOT_CONFIGURED,
    )


class _Runner:
    """A check body that returns a chosen value and records how it was called."""

    def __init__(self, outcome: Callable[[], object]) -> None:
        self._outcome = outcome
        self.timeouts: list[float | None] = []

    def __call__(self, clients: ProviderClients, *, timeout_seconds: float | None = None) -> ProviderCheckResult:
        del clients
        self.timeouts.append(timeout_seconds)
        return self._outcome()  # type: ignore[return-value]

    @property
    def calls(self) -> int:
        return len(self.timeouts)


def _probe(
    runner: _Runner, *, enabled: bool = True, timeout_seconds: float = 10.0, provider_id: str = _YAHOO
) -> ProviderProbe:
    return ProviderProbe(
        enabled=enabled,
        timeout_seconds=timeout_seconds,
        clients=_no_clients,
        checks=(ProviderCheckEntry(provider_id=provider_id, probe="a test probe", run=runner),),
    )


@pytest.mark.parametrize(
    ("check", "verdict"),
    [
        (CheckVerdict.OK, ProbeVerdict.HEALTHY),
        (CheckVerdict.UNREACHABLE, ProbeVerdict.UNREACHABLE),
        (CheckVerdict.RATE_LIMITED, ProbeVerdict.RATE_LIMITED),
        (CheckVerdict.UNEXPECTED_RESPONSE, ProbeVerdict.UNEXPECTED_RESPONSE),
        (CheckVerdict.NO_DATA, ProbeVerdict.NO_DATA),
        (CheckVerdict.NOT_CONFIGURED, ProbeVerdict.NOT_CHECKED),
        (CheckVerdict.FAILED, ProbeVerdict.NOT_CHECKED),
    ],
    ids=lambda value: value.value,
)
def test_each_health_outcome_maps_to_its_verdict(check: CheckVerdict, verdict: ProbeVerdict) -> None:
    runner = _Runner(lambda: _result(_YAHOO, check))

    finding = _probe(runner).check(_YAHOO)

    assert finding.verdict is verdict
    assert finding.provider_id == _YAHOO
    assert finding.switched_off is False


def test_the_time_limit_is_passed_to_the_check_body() -> None:
    runner = _Runner(lambda: _result(_YAHOO, CheckVerdict.OK))

    _probe(runner, timeout_seconds=7.5).check(_YAHOO)

    assert runner.timeouts == [7.5]


def test_a_provider_is_checked_once_per_process_and_the_finding_is_reused() -> None:
    runner = _Runner(lambda: _result(_YAHOO, CheckVerdict.UNREACHABLE))
    probe = _probe(runner)

    findings = [probe.check(_YAHOO) for _ in range(5)]

    assert runner.calls == 1
    assert {finding.verdict for finding in findings} == {ProbeVerdict.UNREACHABLE}


def test_concurrent_callers_share_one_request() -> None:
    release = threading.Event()

    def outcome() -> ProviderCheckResult:
        release.wait(timeout=5)
        return _result(_YAHOO, CheckVerdict.OK)

    runner = _Runner(outcome)
    probe = _probe(runner)
    findings: list[ProbeVerdict] = []
    threads = [threading.Thread(target=lambda: findings.append(probe.check(_YAHOO).verdict)) for _ in range(4)]
    for thread in threads:
        thread.start()
    release.set()
    for thread in threads:
        thread.join(timeout=5)

    assert runner.calls == 1
    assert findings == [ProbeVerdict.HEALTHY] * 4


def test_a_failed_finding_is_not_retried() -> None:
    runner = _Runner(lambda: _result(_YAHOO, CheckVerdict.FAILED))
    probe = _probe(runner)

    probe.check(_YAHOO)
    probe.check(_YAHOO)

    assert runner.calls == 1


def test_a_switched_off_setting_makes_no_request() -> None:
    runner = _Runner(lambda: _result(_YAHOO, CheckVerdict.OK))

    finding = _probe(runner, enabled=False).check(_YAHOO)

    assert (finding.verdict, finding.switched_off) == (ProbeVerdict.NOT_CHECKED, True)
    assert runner.calls == 0


def test_a_declined_request_makes_no_request() -> None:
    runner = _Runner(lambda: _result(_YAHOO, CheckVerdict.OK))

    finding = _probe(runner).check(_YAHOO, requested=False)

    assert (finding.verdict, finding.switched_off) == (ProbeVerdict.NOT_CHECKED, True)
    assert runner.calls == 0


def test_a_provider_with_no_check_is_not_checked_and_makes_no_request() -> None:
    runner = _Runner(lambda: _result(_YAHOO, CheckVerdict.OK))

    finding = _probe(runner).check("fixture")

    assert (finding.verdict, finding.switched_off) == (ProbeVerdict.NOT_CHECKED, False)
    assert runner.calls == 0


def test_only_the_implicated_provider_is_checked() -> None:
    yahoo = _Runner(lambda: _result(_YAHOO, CheckVerdict.OK))
    sec = _Runner(lambda: _result("sec_edgar", CheckVerdict.NO_DATA))
    probe = ProviderProbe(
        enabled=True,
        timeout_seconds=10,
        clients=_no_clients,
        checks=(
            ProviderCheckEntry(provider_id=_YAHOO, probe="y", run=yahoo),
            ProviderCheckEntry(provider_id="sec_edgar", probe="s", run=sec),
        ),
    )

    assert probe.check("sec_edgar").verdict is ProbeVerdict.NO_DATA
    assert (yahoo.calls, sec.calls) == (0, 1)


def test_a_check_that_raises_is_not_checked_and_does_not_raise() -> None:
    def outcome() -> ProviderCheckResult:
        raise RuntimeError("defect inside the check")

    finding = _probe(_Runner(outcome)).check(_YAHOO)

    assert finding.verdict is ProbeVerdict.NOT_CHECKED
    assert finding.switched_off is False


def test_a_clients_factory_that_raises_is_not_checked() -> None:
    def clients() -> ProviderClients:
        raise RuntimeError("cannot compose")

    probe = ProviderProbe(
        enabled=True,
        timeout_seconds=10,
        clients=clients,
        checks=(
            ProviderCheckEntry(provider_id=_YAHOO, probe="y", run=_Runner(lambda: _result(_YAHOO, CheckVerdict.OK))),
        ),
    )

    assert probe.check(_YAHOO).verdict is ProbeVerdict.NOT_CHECKED


@pytest.mark.parametrize("returned", [None, "healthy", 3, object()], ids=["none", "text", "number", "object"])
def test_an_unexpected_return_value_is_not_checked(returned: object) -> None:
    finding = _probe(_Runner(lambda: returned)).check(_YAHOO)

    assert finding.verdict is ProbeVerdict.NOT_CHECKED


def test_a_check_that_hangs_past_the_limit_is_not_checked() -> None:
    release = threading.Event()

    def outcome() -> ProviderCheckResult:
        release.wait(timeout=10)
        return _result(_YAHOO, CheckVerdict.OK)

    try:
        with patch.object(provider_probe, "_BODY_GRACE_SECONDS", 0.05):
            finding = _probe(_Runner(outcome), timeout_seconds=0.05).check(_YAHOO)
    finally:
        release.set()
        _join_probe_threads()

    assert finding.verdict is ProbeVerdict.NOT_CHECKED


def test_an_explicit_time_limit_replaces_the_default_in_each_declared_spec() -> None:
    """The shared bodies take the limit from their spec, so a 10-second limit changes no body."""
    seen: dict[str, list[float]] = {_YAHOO: [], "sec_edgar": []}

    def fake_yahoo(_client: object, *, spec: object, connection: object) -> ProviderCheckResult:
        del connection
        seen[_YAHOO].append(spec.timeout_seconds)  # type: ignore[attr-defined]
        return _result(_YAHOO, CheckVerdict.OK)

    def fake_sec(_transport: object, *, spec: object) -> ProviderCheckResult:
        seen["sec_edgar"].append(spec.timeout_seconds)  # type: ignore[attr-defined]
        return _result("sec_edgar", CheckVerdict.OK)

    class _Clients:
        yahoo = connection = sec = object()

    with (
        patch("src.data.provider_checks.check_yfinance", fake_yahoo),
        patch("src.data.provider_checks.check_sec_edgar", fake_sec),
    ):
        for entry in PROVIDER_CHECKS:
            entry.run(_Clients(), timeout_seconds=10.0)  # type: ignore[arg-type]
            entry.run(_Clients())  # type: ignore[arg-type]

    assert seen == {_YAHOO: [10.0, 20.0], "sec_edgar": [10.0, 20.0]}
