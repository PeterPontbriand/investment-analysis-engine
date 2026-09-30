"""Shared test helpers for CLI-invoking tests.

CLI error messages rendered through Typer + Rich may contain ANSI escape
sequences (colour, bold, underline) and Rich box/border-drawing characters
(straight and rounded) depending on the terminal environment.  ``normalize_cli_output``
strips both so that tests can assert on the semantic text without coupling
to terminal-styling details.

``isolated_cli_database`` points ``src.cli_support``'s and
``src.cli_workspace``'s database access at a disposable, already-migrated
SQLite file instead of the real local database at the default
``database_url``. Momentum/Graham CLI commands (via
``_production_historical_client``/``_production_financial_cache``) and the
watchlist/runs commands (via their own ``_workspace_database``) all call
``ensure_database_ready`` before doing any work; without this isolation,
tests that invoke those commands implicitly depend on the developer
machine's real local database already being upgraded to the current schema
head, which breaks after every migration until someone runs that upgrade by
hand.

Deliberately not extended to ``src.cli``'s own ``settings`` binding: that
name is shared for configuration well beyond database access (for example
SEC identity), and several already-accepted tests rely on
``patch.object(settings, "some_field", value)`` mutating the real shared
settings singleton `cli.py` reads. Rebinding `src.cli.settings` to a
different object here would silently defeat those patches. Tests exercising
the four direct commands' opt-in ``--save-run`` path isolate `src.cli`'s
run-storage database locally instead — see ``tests/test_cli_save_run.py``.
"""

import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alembic.config import Config

from alembic import command
from src.config import ProjectSettings

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def normalize_cli_output(output: str) -> str:
    """Strip ANSI terminal-control sequences and normalize Rich box/border layout.

    This makes substring assertions robust across local execution, Windows
    terminals, and headless CI runners where Typer/Rich may or may not emit
    styling codes.  Handles both straight (│┌┐└┘) and rounded (╭╮╰╯)
    border-drawing characters.
    """
    text = _ANSI_ESCAPE_RE.sub("", output)
    for ch in "─│┌┐└┘╭╮╰╯":
        text = text.replace(ch, " ")
    return " ".join(text.split())


@pytest.fixture(autouse=True)
def isolated_cli_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrate a disposable database to head and point CLI storage at it.

    Importing this fixture's name into a test module activates it for every
    test in that module, matching pytest's usual cross-module fixture sharing.
    """
    url = f"sqlite:///{(tmp_path / 'cli.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    isolated = ProjectSettings(database_url=url)
    monkeypatch.setattr("src.cli_support.settings", isolated)
    monkeypatch.setattr("src.cli_workspace.settings", isolated)


def carry_profile(mock_run: MagicMock) -> None:
    """Make a mocked ``MomentumAnalyzer.run_analysis`` return its canned run carrying the caller's profile.

    The real analyzer embeds ``context.instrument_profile`` in the run it returns, and the
    ``momentum`` presenters read it from there; a bare canned run would not carry it.
    """
    canned = mock_run.return_value
    mock_run.side_effect = lambda **kwargs: replace(canned, instrument_profile=kwargs["context"].instrument_profile)
