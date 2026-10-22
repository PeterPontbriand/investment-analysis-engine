"""Record the machine's socket state at the moment a test fails with ``WinError 10055``.

Windows reports 10055 when it lacks socket buffer space, and the cause of the intermittent failures has never been
captured: by the time a wrapper could look, the sockets present at the failure were gone. This module's
``pytest_runtest_makereport`` hook fires when a test's setup, call or teardown fails with an ``OSError`` whose
``winerror`` is 10055 anywhere in its ``__cause__``/``__context__`` chain. It records a snapshot at once and attaches
it to that test's report as a section titled ``socket snapshot``, so pytest prints it in the failure output and it
reaches the gate wrappers' ``gate-output.txt`` and CI logs. It attaches at most one snapshot per pytest session.

The hook never raises and never changes a test's outcome. On a system other than Windows it does nothing. When the
snapshot cannot be collected, the section says that and why. A test supplies its own collector through
``SNAPSHOT_COLLECTOR`` in ``config.stash``; the default collector runs local PowerShell, needing neither admin rights
nor a network call.
"""

from __future__ import annotations

import base64
import subprocess
import sys
from collections.abc import Callable

import pytest

SECTION_TITLE = "socket snapshot"
WSAENOBUFS = 10055
COLLECTION_TIMEOUT_SECONDS = 30

SnapshotCollector = Callable[[], str]

SNAPSHOT_COLLECTOR = pytest.StashKey[SnapshotCollector]()
_SNAPSHOT_TAKEN = pytest.StashKey[bool]()

# Each line is one labelled item. A failing item reports that it is unavailable and why, and the others still run.
_POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$connections = $null
$connectionsError = 'no connection list'
try { $connections = @(Get-NetTCPConnection) } catch { $connectionsError = $_.Exception.Message }
function Report([string]$label, [scriptblock]$body) {
    try { Write-Output ('{0}: {1}' -f $label, (& $body)) }
    catch { Write-Output ('{0}: unavailable ({1})' -f $label, $_.Exception.Message) }
}
Report 'tcp connections by state' {
    if ($null -eq $connections) { throw $connectionsError }
    $states = ($connections | Group-Object State | Sort-Object Count -Descending |
        ForEach-Object { '{0}={1}' -f $_.Name, $_.Count }) -join ', '
    '{0} total; {1}' -f $connections.Count, $states
}
Report 'top tcp owners' {
    if ($null -eq $connections) { throw $connectionsError }
    ($connections | Group-Object OwningProcess | Sort-Object Count -Descending | Select-Object -First 10 |
        ForEach-Object {
            $owner = Get-Process -Id ([int]$_.Name) -ErrorAction SilentlyContinue
            $name = if ($owner) { $owner.ProcessName } else { 'unknown' }
            '{0}(pid {1})={2}' -f $name, $_.Name, $_.Count
        }) -join ', '
}
Report 'dynamic tcp port range' {
    $output = netsh int ipv4 show dynamicport tcp
    if ($LASTEXITCODE -ne 0) { throw ('netsh exit code {0}' -f $LASTEXITCODE) }
    $numbers = @($output | ForEach-Object { if ($_ -match ':\s*(\d+)\s*$') { [int]$Matches[1] } })
    if ($numbers.Count -lt 2) { throw 'netsh output not recognised' }
    'start {0}, {1} ports' -f $numbers[0], $numbers[1]
}
Report 'non-paged pool bytes' { (Get-CimInstance Win32_PerfRawData_PerfOS_Memory).PoolNonpagedBytes }
Report 'available memory bytes' { (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory * 1KB }
$python = @(Get-Process -Name 'python*' -ErrorAction SilentlyContinue)
Report 'python processes' { $python.Count }
Report 'python handles total' { [int64]($python | Measure-Object -Property HandleCount -Sum).Sum }
"""


def collect_socket_snapshot() -> str:
    """Return the labelled snapshot lines, collected with local PowerShell.

    Raises:
        OSError: PowerShell could not be started.
        subprocess.SubprocessError: PowerShell timed out or exited with a failure.
    """
    encoded = base64.b64encode(_POWERSHELL_SCRIPT.encode("utf-16-le")).decode("ascii")
    completed = subprocess.run(  # noqa: S603 - fixed argument list, no untrusted input
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],  # noqa: S607
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=COLLECTION_TIMEOUT_SECONDS,
        check=True,
    )
    return completed.stdout.strip()


def _platform_is_windows() -> bool:
    return sys.platform == "win32"


def _is_buffer_exhaustion(error: BaseException | None) -> bool:
    """Return whether ``error`` or anything in its cause/context chain is an ``OSError`` with ``winerror`` 10055."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, OSError) and getattr(error, "winerror", None) == WSAENOBUFS:
            return True
        error = error.__cause__ or error.__context__
    return False


def _snapshot_text(collector: SnapshotCollector) -> str:
    try:
        return collector()
    except Exception as error:  # noqa: BLE001 - whatever stops collection is reported in the section, never raised
        return f"snapshot not collected: {type(error).__name__}: {error}"


def _wrapped_exception(call: pytest.CallInfo[object]) -> BaseException | None:
    excinfo = call.excinfo
    return None if excinfo is None else excinfo.value


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]) -> object:
    """Attach one ``socket snapshot`` section to the first report whose failure carries ``WinError 10055``."""
    report = yield
    try:
        stash = item.config.stash
        collector = stash.get(SNAPSHOT_COLLECTOR, None)
        if collector is None and _platform_is_windows():
            collector = collect_socket_snapshot
        if (
            collector is not None
            and not stash.get(_SNAPSHOT_TAKEN, False)
            and isinstance(report, pytest.TestReport)
            and report.failed
            and _is_buffer_exhaustion(_wrapped_exception(call))
        ):
            stash[_SNAPSHOT_TAKEN] = True
            report.sections.append((SECTION_TITLE, _snapshot_text(collector)))
    except Exception:  # noqa: BLE001, S110 - the hook must never raise or change a result
        pass
    return report
