"""Run the workspace and database commands against a disposable database and capture their output.

Shared by ``tests/test_workspace_command_output.py`` and the regeneration entry point::

    uv run python -m tests._workspace_command_output [DIRECTORY]

The scenario runs, in order, every success path of the ``watchlist``, ``runs``, ``refresh`` and ``db`` commands in
text and, where the command offers it, ``--json``: one step per invocation, recording the exit code and both
standard streams. Streams go through ``normalize_cli_output`` (as ``docs/project/README.md`` requires for CLI
assertions) and then a mask for the values that differ between any two runs: UUIDs, ISO timestamps and the
temporary database path. Nothing else is altered, so a changed key, sentence or exit code shows in the stored files.

Regeneration with no argument rewrites ``tests/expected_output/workspace_commands/`` so an intended output change is a
reviewed diff. With a directory argument it writes there instead, which is how the output of two revisions is compared.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from alembic.config import Config
from typer.testing import CliRunner

from alembic import command
from src.cli import app
from src.config import ProjectSettings
from src.data.market_data import HistoricalMarketData
from tests._cli_helpers import normalize_cli_output
from tests._direct_command_output import _FixtureYahoo

EXPECTED_DIRECTORY = Path(__file__).resolve().parent / "expected_output" / "workspace_commands"
_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_DATABASE_SUFFIX = re.compile(r"<database>(?:[\\/]+[\w.\-]+)+")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")

# Offset-preserving mask for the steps that pin timestamp spelling: only the digits are replaced, so ``Z`` and
# ``+00:00`` stay visible. The wall-clock digits are the only part that differs between runs, so the output is
# deterministic.
_TIMESTAMP_DIGITS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?=Z|[+-]\d{2}:\d{2})")

_FAILING_TICKER = "BAD"

_MOMENTUM = ["--analysis", "momentum", "--short-window", "2", "--long-window", "3", "--rsi-period", "3", "--no-cache"]
_GRAHAM_GROWTH = ["--analysis", "graham-growth", "--expected-growth", "5", "--aaa-yield", "4.5"]

# Each step is one command line, run in order; later steps depend on the state earlier ones leave.
_STEPS: tuple[tuple[str, list[str]], ...] = (
    ("db-status-ready", ["db", "status"]),
    ("db-status-ready-json", ["db", "status", "--json"]),
    ("db-upgrade-ready", ["db", "upgrade"]),
    ("db-upgrade-ready-json", ["db", "upgrade", "--json"]),
    ("watchlist-list-empty", ["watchlist", "list"]),
    ("watchlist-create-empty", ["watchlist", "create", "Core"]),
    ("watchlist-create-seeded", ["watchlist", "create", "Seeded", "AAPL", "MSFT", *_MOMENTUM]),
    ("watchlist-add-selection-graham-number", ["watchlist", "add-selection", "Core", "KO", "-a", "graham-number"]),
    ("watchlist-add-selection-graham-growth", ["watchlist", "add-selection", "Core", "KO", *_GRAHAM_GROWTH]),
    ("watchlist-add-selection-fcf-growth", ["watchlist", "add-selection", "Core", "MSFT", "-a", "fcf-growth"]),
    ("watchlist-add-selection-momentum", ["watchlist", "add-selection", "Core", "AAPL", *_MOMENTUM]),
    ("watchlist-list", ["watchlist", "list"]),
    ("watchlist-show", ["watchlist", "show", "Core"]),
    ("watchlist-show-by-method", ["watchlist", "show", "Core", "--group-by", "method"]),
    ("watchlist-show-json", ["watchlist", "show", "Core", "--json"]),
    ("watchlist-remove-entry", ["watchlist", "remove-entry", "Core", "1"]),
    ("watchlist-remove-ticker", ["watchlist", "remove-ticker", "Core", "KO"]),
    ("watchlist-remove-method", ["watchlist", "remove-method", "Core", "-a", "fcf-growth"]),
    ("watchlist-rename", ["watchlist", "rename", "Core", "Core Holdings"]),
    ("watchlist-rename-json", ["watchlist", "rename", "Core Holdings", "Core Renamed", "--json"]),
    ("refresh-no-save", ["refresh", "Seeded", "--workers", "1", "--no-save"]),
    ("refresh-no-save-json", ["refresh", "Seeded", "--workers", "1", "--no-save", "--json"]),
    ("refresh", ["refresh", "Seeded", "--workers", "1"]),
    ("refresh-json", ["refresh", "Seeded", "--workers", "1", "--json"]),
    ("runs-list", ["runs", "list"]),
    ("runs-list-json", ["runs", "list", "--json"]),
    ("runs-list-filtered", ["runs", "list", "--ticker", "AAPL", "--analysis", "momentum", "--status", "completed"]),
    ("runs-list-empty", ["runs", "list", "--ticker", "NONE"]),
    ("runs-show", ["runs", "show", "<run>"]),
    ("runs-show-details", ["runs", "show", "<run>", "--details"]),
    ("runs-show-diagnostics", ["runs", "show", "<run>", "--diagnostics"]),
    ("runs-show-json", ["runs", "show", "<run>", "--json"]),
    ("watchlist-delete-missing-ok", ["watchlist", "delete", "Nowhere", "--yes", "--missing-ok"]),
    ("watchlist-delete-missing-ok-json", ["watchlist", "delete", "Nowhere", "--yes", "--missing-ok", "--json"]),
    ("watchlist-delete", ["watchlist", "delete", "Core Renamed", "--yes"]),
    ("watchlist-delete-json", ["watchlist", "delete", "Seeded", "--yes", "--json"]),
    ("db-status-missing-json", ["db", "status", "--database-url", "<new>", "--json"]),
    ("db-upgrade-new", ["db", "upgrade", "--database-url", "<new>"]),
    ("db-upgrade-new-json", ["db", "upgrade", "--database-url", "<new2>", "--json"]),
    ("db-status-new", ["db", "status", "--database-url", "<new>"]),
    # Steps below pin what the masked steps above cannot: the spelling of each timestamp (the offset is kept in the
    # stored text), a watchlist with no entries (so a null `updated_at`), and a refresh in which one job raises.
    ("watchlist-create-single-entry", ["watchlist", "create", "Fresh", "AAPL", *_MOMENTUM]),
    ("watchlist-create-empty-second", ["watchlist", "create", "Vacant"]),
    ("watchlist-show-json-timestamps", ["watchlist", "show", "Fresh", "--json"]),
    ("watchlist-show-json-empty", ["watchlist", "show", "Vacant", "--json"]),
    ("watchlist-create-failing", ["watchlist", "create", "Failing", "AAPL", _FAILING_TICKER, *_MOMENTUM]),
    ("refresh-failed-job-json", ["refresh", "Failing", "--workers", "1", "--json"]),
    ("refresh-failed-job", ["refresh", "Failing", "--workers", "1"]),
    ("runs-list-json-timestamps", ["runs", "list", "--ticker", "AAPL", "--limit", "1", "--json"]),
    ("watchlist-rename-json-timestamps", ["watchlist", "rename", "Fresh", "Fresh Renamed", "--json"]),
    ("watchlist-delete-json-timestamps", ["watchlist", "delete", "Fresh Renamed", "--yes", "--json"]),
)

# Steps whose stored text keeps each timestamp's offset suffix.
_OFFSET_STEPS = frozenset(name for name, _arguments in _STEPS if name.endswith("-timestamps"))


@dataclass(frozen=True)
class Step:
    """One command invocation: its name, exit code and masked standard streams."""

    name: str
    exit_code: int
    stdout: str
    stderr: str

    def text(self) -> str:
        """Return the stored form of the step."""
        return f"exit {self.exit_code}\n--- stdout\n{self.stdout}\n--- stderr\n{self.stderr}\n"


class _FixtureYahooFailingFor(_FixtureYahoo):
    """The fixture client, except that fetching the one failing ticker raises before any data is returned."""

    def fetch_historical_data(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool = True
    ) -> HistoricalMarketData:
        if ticker == _FAILING_TICKER:
            raise RuntimeError("fixture provider failure")
        return super().fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)


def scenario_root(directory: Path) -> Path:
    """Return ``directory`` in the one spelling the commands print, resolved once before any command runs.

    The commands report the database path they resolved, so the temporary directory must already be in that form:
    Windows temp folders are created under an 8.3 short name (``RUNNER~1``) that resolves to the long name, and macOS
    temp folders are under ``/var``, a link to ``/private/var``. Masking the unresolved spelling leaves the other
    spelling, or a leftover prefix such as ``/private``, in the output.
    """
    return directory.resolve()


def _mask(text: str, paths: list[Path], *, keep_offset: bool = False) -> str:
    """Normalize CLI styling, then replace the values that differ between runs.

    With ``keep_offset`` a timestamp's digits are replaced and its ``Z`` or ``+00:00`` suffix is kept.
    """
    text = normalize_cli_output(text)
    for path in paths:
        for spelling in (str(path), path.as_posix(), json.dumps(str(path))[1:-1], json.dumps(path.as_posix())[1:-1]):
            text = text.replace(spelling, "<database>")
    text = _DATABASE_SUFFIX.sub("<database>", text)
    pattern = _TIMESTAMP_DIGITS if keep_offset else _TIMESTAMP
    return pattern.sub("<time>", _UUID.sub("<uuid>", text))


def _migrated_settings(path: Path) -> ProjectSettings:
    url = f"sqlite:///{path.as_posix()}"
    config = Config(str(_REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    return ProjectSettings(database_url=url)


def run_scenario() -> list[Step]:
    """Run every step against a fresh migrated database and fixture providers; no network call is made."""
    steps: list[Step] = []
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        root = scenario_root(Path(directory))
        settings = _migrated_settings(root / "workspace.sqlite3")
        for module in ("src.cli_support", "src.cli_workspace", "src.cli_database"):
            stack.enter_context(patch(f"{module}.settings", settings))
        stack.enter_context(patch("src.strategies.momentum.cli.YFinanceClient", _FixtureYahooFailingFor))
        stack.enter_context(
            patch("src.data.yfinance.client.YFinanceClient.resolve_security_identity", return_value=None)
        )
        stack.enter_context(patch("src.data.yfinance.client.YFinanceClient.resolve_instrument_kind", return_value=None))
        runner = CliRunner()
        substitutions = {
            "<new>": f"sqlite:///{(root / 'new' / 'one.sqlite3').as_posix()}",
            "<new2>": f"sqlite:///{(root / 'new' / 'two.sqlite3').as_posix()}",
        }
        paths = [root]
        run_id = ""
        for name, arguments in _STEPS:
            resolved = [substitutions.get(item, run_id if item == "<run>" else item) for item in arguments]
            result = runner.invoke(app, resolved)
            if name == "runs-list-json":
                run_id = json.loads(result.stdout)[0]["analysis_run_id"]
            keep = name in _OFFSET_STEPS
            steps.append(
                Step(
                    name,
                    result.exit_code,
                    _mask(result.stdout, paths, keep_offset=keep),
                    _mask(result.stderr, paths, keep_offset=keep),
                )
            )
    return steps


def cases() -> Iterator[str]:
    """Yield the name of every step, which is the stem of its stored file."""
    for name, _arguments in _STEPS:
        yield name


def expected_path(name: str) -> Path:
    """Return the stored expected-output file of one step."""
    return EXPECTED_DIRECTORY / f"{name}.txt"


def write_steps(steps: list[Step], directory: Path) -> None:
    """Write one file per step into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    for step in steps:
        (directory / f"{step.name}.txt").write_bytes(step.text().encode("utf-8"))


if __name__ == "__main__":
    write_steps(run_scenario(), Path(sys.argv[1]) if len(sys.argv) > 1 else EXPECTED_DIRECTORY)
