"""Shared setup for the API tests: an in-process client, a fixed token and port, and one stored run per strategy."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from functools import cache

from starlette.testclient import TestClient

from investment_analysis_engine.api.app import create_app
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun
from scripts.strategy_conformance import stored_runs

TOKEN = "test-token-0123456789"
PORT = 8123
HOST = f"127.0.0.1:{PORT}"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@contextmanager
def client_for(
    settings: ProjectSettings, *, origins: Sequence[str] = (), raise_server_exceptions: bool = True
) -> Iterator[TestClient]:
    """Yield an in-process client of the API built over ``settings``, closed on exit."""
    app = create_app(
        context=ApplicationContext(settings=settings), token=TOKEN, port=PORT, allowed_origins=tuple(origins)
    )
    with TestClient(app, base_url=f"http://{HOST}", raise_server_exceptions=raise_server_exceptions) as client:
        yield client


@cache
def runs_by_alias() -> dict[str, AnalysisRun]:
    """Return one stored run per declared strategy, executed from its golden fixture."""
    runs: dict[str, AnalysisRun] = {}
    for entry in stored_runs(STRATEGIES):
        assert isinstance(entry.run, AnalysisRun)
        runs[entry.descriptor.alias] = entry.run
    return runs


def store(settings: ProjectSettings, *runs: AnalysisRun) -> None:
    """Insert ``runs`` into the database ``settings`` selects."""
    database = SQLiteDatabase(settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        for run in runs:
            repository.insert(run)
    finally:
        database.close()
