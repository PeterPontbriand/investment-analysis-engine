"""Opt-in isolation for tests that invoke the command line.

A module opts in with ``pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")``,
or the subset of the two it needs; a test that uses the isolated settings takes ``isolated_cli_settings`` as an
argument. Both fixtures are registered in ``tests/conftest.py``, so no module imports them.

``isolated_cli_settings`` points ``investment_analysis_engine.cli_support``'s,
``investment_analysis_engine.cli_workspace``'s and ``investment_analysis_engine.cli_run_support``'s database access at a
disposable, already-migrated SQLite file instead of the real local database at the default
``database_url``. Momentum/Graham CLI commands (via
``_production_historical_client``/``_production_financial_cache``) and the
watchlist/runs commands (via their own ``_workspace_database``) all call
``ensure_database_ready`` before doing any work; without this isolation,
tests that invoke those commands implicitly depend on the developer
machine's real local database already being upgraded to the current schema
head, which breaks after every migration until someone runs that upgrade by
hand.

Deliberately not extended to ``investment_analysis_engine.cli``'s own ``settings`` binding: that
name is shared for configuration well beyond database access (for example
SEC identity), and several already-accepted tests rely on
``patch.object(settings, "some_field", value)`` mutating the real shared
settings singleton `cli.py` reads. Rebinding `investment_analysis_engine.cli.settings` to a
different object here would silently defeat those patches. Tests exercising
the four direct commands' opt-in ``--save-run`` path isolate `investment_analysis_engine.cli`'s
run-storage database locally instead — see ``tests/test_cli_save_run.py``.
"""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from investment_analysis_engine.config import ProjectSettings
from tests._migrated_database import migrated_database_url


@pytest.fixture
def isolated_cli_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProjectSettings:
    """Migrate a disposable database to head and point CLI storage at it, returning the isolated settings.

    A test module that needs this isolation for every test lists the fixture in a ``pytestmark``; a test that uses
    the settings takes the fixture as an argument.
    """
    isolated = ProjectSettings(database_url=migrated_database_url(tmp_path))
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", isolated)
    monkeypatch.setattr("investment_analysis_engine.cli_workspace.settings", isolated)
    monkeypatch.setattr("investment_analysis_engine.cli_run_support.settings", isolated)
    return isolated


@pytest.fixture
def stub_yahoo_identity_metadata() -> Iterator[None]:
    """Stub the optional Yahoo identity and instrument-kind metadata lookups.

    Without it the CLI reaches ``YFinanceClient``'s live metadata fetch, which the suite-wide guard in
    ``tests/conftest.py`` rejects. A module opts in with a ``pytestmark``.
    """
    with (
        patch(
            "investment_analysis_engine.data.yfinance.client.YFinanceClient.resolve_security_identity",
            return_value=None,
        ),
        patch(
            "investment_analysis_engine.data.yfinance.client.YFinanceClient.resolve_instrument_kind", return_value=None
        ),
    ):
        yield
