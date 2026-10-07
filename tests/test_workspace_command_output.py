"""Compare the output of every workspace and database command with stored expected output.

``tests/_workspace_command_output.py`` runs each success path of the ``watchlist``, ``runs``, ``refresh`` and
``db`` commands, in text and ``--json``, against a disposable database and fixture providers; no network, provider or
model call is made. Output goes through ``normalize_cli_output`` and a mask for UUIDs, timestamps and the database
path, and the exit code is stored with it. The stored files differ from the output of ``main`` only in the six
``--json`` files listed in the SWC design (H.27), so this is the check that a later change alters no success output
beyond the changes it lists. The steps whose names end in ``-timestamps`` keep each timestamp's offset suffix, so
they pin the spelling (``Z`` or ``+00:00``) that the masked steps hide; the failed-job refresh and the watchlist edge
cases were captured from ``main`` before any document builder changed.

To change the expected output deliberately, regenerate the files and review the diff::

    uv run python -m tests._workspace_command_output
"""

from __future__ import annotations

import pytest

from tests._workspace_command_output import EXPECTED_DIRECTORY, Step, cases, expected_path, run_scenario


@pytest.fixture(scope="module")
def steps() -> dict[str, Step]:
    """Run the whole scenario once; its steps depend on one another."""
    return {step.name: step for step in run_scenario()}


@pytest.mark.parametrize("name", list(cases()))
def test_workspace_command_output_matches_the_stored_output(steps: dict[str, Step], name: str) -> None:
    """Each command prints exactly the stored text and exits as stored."""
    assert steps[name].text().encode("utf-8") == expected_path(name).read_bytes()


def test_every_stored_file_belongs_to_a_step() -> None:
    """A removed or renamed step must not leave a stale expected file behind."""
    assert {path.stem for path in EXPECTED_DIRECTORY.glob("*.txt")} == set(cases())


def test_the_scenario_is_deterministic() -> None:
    """Two runs give identical output, so a difference from the stored files is a real change."""
    assert [step.text() for step in run_scenario()] == [step.text() for step in run_scenario()]


def test_the_scenario_covers_every_workspace_and_database_command(steps: dict[str, Step]) -> None:
    """Every command word appears in a step, so a new command without a step is noticed."""
    import typer.main  # noqa: PLC0415

    from src.cli import app  # noqa: PLC0415 - imported late to keep module import free of the application

    tree = typer.main.get_command(app)
    covered = {name.split("-")[0] for name in steps}
    groups = {"watchlist", "runs", "db"}
    for group in groups:
        subcommands = set(getattr(tree, "commands")[group].commands)  # noqa: B009
        stored = " ".join(name for name in steps if name.startswith(group))
        for subcommand in subcommands:
            assert subcommand in stored, f"no step runs {group} {subcommand}"
    assert "refresh" in covered
