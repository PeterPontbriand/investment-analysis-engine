"""Offline tests of the ``about`` command: real throwaway Git repositories, no dependence on this repository's state."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from investment_analysis_engine import cli_about
from investment_analysis_engine.api.documents import installed_engine_version
from investment_analysis_engine.cli import app
from investment_analysis_engine.core import package_root
from investment_analysis_engine.reporting.documents.about import AboutDocument
from scripts.repository_root import REPOSITORY_ROOT

runner = CliRunner()
_GIT = ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com")


def _git(folder: Path, *arguments: str) -> str:
    completed = subprocess.run(  # noqa: S603
        [*_GIT, "-C", str(folder), *arguments], capture_output=True, text=True, check=True, timeout=60
    )
    return completed.stdout.strip()


def _checkout(folder: Path) -> str:
    """Create a repository with one commit at ``folder`` and return the commit."""
    folder.mkdir(parents=True)
    _git(folder, "init", "-q")
    (folder / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(folder, "add", "tracked.txt")
    _git(folder, "commit", "-q", "-m", "first")
    return _git(folder, "rev-parse", "HEAD")


def _run(
    monkeypatch: pytest.MonkeyPatch, folder: Path | None, *, json_output: bool = False
) -> tuple[str, dict[str, Any] | None]:
    monkeypatch.setattr(cli_about, "INSTALLATION_FOLDER", folder)
    result = runner.invoke(app, ["about", *(["--json"] if json_output else [])])
    assert result.exit_code == 0, result.output
    return result.stdout, json.loads(result.stdout) if json_output else None


def _text(folder: Path | None, commit: str, tail: str = "") -> str:
    lines = [f"Investment Analysis Engine {installed_engine_version()}"]
    if folder is None:
        lines += ["Installation folder: none (installed as a package)", "Commit: none"]
    else:
        lines += [f"Installation folder: {folder}", f"Commit: {commit}{tail}"]
    return "\n".join(lines) + "\n"


def _validate(value: object, schema: dict[str, Any], definitions: dict[str, Any]) -> None:
    """Check ``value`` against the subset of JSON Schema the generated documents use."""
    if "$ref" in schema:
        _validate(value, definitions[schema["$ref"].rsplit("/", 1)[1]], definitions)
    elif "anyOf" in schema:
        failures = 0
        for option in schema["anyOf"]:
            try:
                _validate(value, option, definitions)
            except AssertionError:
                failures += 1
        assert failures < len(schema["anyOf"]), f"{value!r} matches none of {schema['anyOf']}"
    elif "const" in schema:
        assert value == schema["const"]
    elif schema["type"] == "object":
        assert isinstance(value, dict)
        assert set(schema["required"]) <= set(value)
        assert schema["additionalProperties"] is False
        assert set(value) <= set(schema["properties"])
        for name, item in value.items():
            _validate(item, schema["properties"][name], definitions)
    else:
        types = {"string": str, "boolean": bool, "integer": int, "null": type(None)}
        assert type(value) is types[schema["type"]], f"{value!r} is not {schema['type']}"


def _assert_matches_schema(document: dict[str, Any]) -> None:
    schema = json.loads((REPOSITORY_ROOT / "schemas" / "about.schema.json").read_text(encoding="utf-8"))
    _validate(document, schema, schema.get("$defs", {}))
    assert AboutDocument.model_validate(document).model_dump(mode="json") == document


def test_a_clean_checkout_reports_its_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "engine"
    commit = _checkout(folder)

    text, _ = _run(monkeypatch, folder)
    _, document = _run(monkeypatch, folder, json_output=True)

    assert len(commit) == 40
    assert text == _text(folder, commit)
    assert document == {
        "schema_version": 1,
        "engine_version": installed_engine_version(),
        "installation_folder": str(folder),
        "commit": commit,
        "uncommitted_changes": False,
    }
    _assert_matches_schema(document)


def test_a_tracked_change_is_reported_as_uncommitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "engine"
    commit = _checkout(folder)
    (folder / "tracked.txt").write_text("two\n", encoding="utf-8")

    text, _ = _run(monkeypatch, folder)
    _, document = _run(monkeypatch, folder, json_output=True)

    assert text == _text(folder, commit, " (with uncommitted changes)")
    assert document is not None
    assert document["commit"] == commit
    assert document["uncommitted_changes"] is True
    _assert_matches_schema(document)


def test_an_untracked_file_is_reported_as_uncommitted_and_an_ignored_one_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "engine"
    commit = _checkout(folder)
    (folder / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    _git(folder, "add", ".gitignore")
    _git(folder, "commit", "-q", "-m", "ignore")
    commit = _git(folder, "rev-parse", "HEAD")
    (folder / "ignored.txt").write_text("x\n", encoding="utf-8")
    _, ignored_only = _run(monkeypatch, folder, json_output=True)
    (folder / "new.txt").write_text("x\n", encoding="utf-8")

    text, _ = _run(monkeypatch, folder)
    _, document = _run(monkeypatch, folder, json_output=True)

    assert ignored_only is not None
    assert ignored_only["uncommitted_changes"] is False
    assert text == _text(folder, commit, " (with uncommitted changes)")
    assert document is not None
    assert document["uncommitted_changes"] is True
    _assert_matches_schema(document)


def test_a_folder_that_is_not_a_checkout_has_no_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "engine"
    folder.mkdir()

    text, _ = _run(monkeypatch, folder)
    _, document = _run(monkeypatch, folder, json_output=True)

    assert text == _text(folder, "none (not a Git checkout)")
    assert document is not None
    assert (document["commit"], document["uncommitted_changes"]) == (None, None)
    assert document["installation_folder"] == str(folder)
    _assert_matches_schema(document)


def test_a_folder_inside_another_repository_is_not_a_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _checkout(tmp_path / "outer")
    folder = tmp_path / "outer" / "engine"
    folder.mkdir()

    text, _ = _run(monkeypatch, folder)
    _, document = _run(monkeypatch, folder, json_output=True)

    assert text == _text(folder, "none (not a Git checkout)")
    assert document is not None
    assert (document["commit"], document["uncommitted_changes"]) == (None, None)
    _assert_matches_schema(document)


def test_a_machine_without_git_reports_that_git_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "engine"
    _checkout(folder)

    def no_git(_folder: Path, _arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(cli_about, "run_git", no_git)
    text, _ = _run(monkeypatch, folder)
    _, document = _run(monkeypatch, folder, json_output=True)

    assert text == _text(folder, "none (Git is not installed)")
    assert document is not None
    assert (document["commit"], document["uncommitted_changes"]) == (None, None)
    _assert_matches_schema(document)


def test_run_git_without_a_git_executable_raises_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(FileNotFoundError):
        cli_about.run_git(tmp_path, ("status",))


def test_no_installation_folder_means_an_installed_package(monkeypatch: pytest.MonkeyPatch) -> None:
    text, _ = _run(monkeypatch, None)
    _, document = _run(monkeypatch, None, json_output=True)

    assert text == _text(None, "")
    assert document == {
        "schema_version": 1,
        "engine_version": installed_engine_version(),
        "installation_folder": None,
        "commit": None,
        "uncommitted_changes": None,
    }
    _assert_matches_schema(document)


def _completed(stdout: str, code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, "")


def test_a_failing_status_call_keeps_the_commit_and_leaves_the_status_unknown(tmp_path: Path) -> None:
    commit = "a" * 40
    document, git_missing = cli_about.build_about_document(
        folder=tmp_path,
        git=lambda _folder, arguments: (
            _completed(str(tmp_path))
            if arguments[1] == "--show-toplevel"
            else _completed(commit)
            if arguments[0] == "rev-parse"
            else _completed("", 128)
        ),
        version=lambda: "9.9.9",
    )

    assert (document.commit, document.uncommitted_changes, git_missing) == (commit, None, False)


def test_a_failing_head_call_leaves_no_commit(tmp_path: Path) -> None:
    document, _ = cli_about.build_about_document(
        folder=tmp_path,
        git=lambda _folder, arguments: (
            _completed(str(tmp_path)) if arguments[1] == "--show-toplevel" else _completed("", 128)
        ),
        version=lambda: "9.9.9",
    )

    assert (document.commit, document.uncommitted_changes) == (None, None)


def test_the_installation_folder_is_the_folder_holding_the_project_file(tmp_path: Path) -> None:
    with_project = tmp_path / "checkout"
    (with_project / "investment_analysis_engine" / "core").mkdir(parents=True)
    (with_project / "pyproject.toml").write_text("", encoding="utf-8")
    without_project = tmp_path / "site-packages"
    (without_project / "investment_analysis_engine" / "core").mkdir(parents=True)

    assert package_root.installation_folder_of(with_project / "investment_analysis_engine") == with_project
    assert package_root.installation_folder_of(without_project / "investment_analysis_engine") is None
    assert package_root.INSTALLATION_FOLDER == REPOSITORY_ROOT


def test_about_is_listed_in_the_application_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert "about" in result.stdout
