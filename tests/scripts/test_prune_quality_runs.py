"""Tests for pruning old gate run directories and cleaning a finished run's directory."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from scripts.prune_quality_runs import (
    KEEP_COUNT,
    KEPT_FILE_NAME,
    MIN_AGE_SECONDS,
    clean_finished_run,
    is_run_directory_name,
    main,
    prune_old_runs,
)

NOW = 1_800_000_000.0
OLD = NOW - 3 * MIN_AGE_SECONDS


def powershell_name(index: int) -> str:
    return f"20260101120000{index:03d}-4242-{index:032x}"


def shell_name(index: int) -> str:
    return f"{20260101120000 + index}-4242-{index}"


def make_run(root: Path, name: str, modified: float, *, with_output: bool = True) -> Path:
    """Create a run directory whose own and gate-output.txt modification times are ``modified``."""
    run = root / name
    (run / "pytest").mkdir(parents=True)
    (run / "pytest" / "file.txt").write_text("x", encoding="utf-8")
    if with_output:
        (run / KEPT_FILE_NAME).write_text("log", encoding="utf-8")
        os.utime(run / KEPT_FILE_NAME, (modified, modified))
    os.utime(run, (modified, modified))
    return run


def remaining(root: Path) -> set[str]:
    return {entry.name for entry in root.iterdir()}


def test_both_wrapper_name_formats_are_recognized_and_others_are_not() -> None:
    assert is_run_directory_name(powershell_name(1))
    assert is_run_directory_name(shell_name(1))
    assert not is_run_directory_name("r2-a-collection-20260101120000000-4242-1")
    assert not is_run_directory_name(powershell_name(1) + "-extra")
    assert not is_run_directory_name("")


def test_directories_beyond_the_keep_count_are_deleted_oldest_first(tmp_path: Path) -> None:
    names = [powershell_name(index) for index in range(KEEP_COUNT + 3)]
    for index, name in enumerate(names):
        make_run(tmp_path, name, OLD + index)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW)

    assert len(result.removed) == 4
    assert result.failures == []
    assert remaining(tmp_path) == {*names[4:], own.name}


def test_at_or_under_the_keep_count_nothing_is_deleted(tmp_path: Path) -> None:
    for index in range(KEEP_COUNT - 1):
        make_run(tmp_path, shell_name(index), OLD + index)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW)

    assert result.removed == []
    assert len(remaining(tmp_path)) == KEEP_COUNT


def test_a_young_directory_is_never_deleted_even_beyond_the_keep_count(tmp_path: Path) -> None:
    young = [make_run(tmp_path, powershell_name(index), NOW - 3600 - index) for index in range(KEEP_COUNT + 5)]
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW)

    assert result.removed == []
    assert all(run.exists() for run in young)


def test_a_directory_just_over_the_minimum_age_is_deletable(tmp_path: Path) -> None:
    just_old = make_run(tmp_path, powershell_name(1), NOW - MIN_AGE_SECONDS - 1)
    just_young = make_run(tmp_path, powershell_name(2), NOW - MIN_AGE_SECONDS + 60)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW, keep_count=1)

    assert result.removed == [just_old]
    assert just_young.exists()


def test_unrecognized_names_and_files_are_never_deleted_or_counted(tmp_path: Path) -> None:
    hand_made = make_run(tmp_path, "r2-a-collection-20260101120000000-4242-1", OLD - 10)
    stray_file = tmp_path / "notes.txt"
    stray_file.write_text("keep", encoding="utf-8")
    os.utime(stray_file, (OLD - 10, OLD - 10))
    gate = [make_run(tmp_path, shell_name(index), OLD + index) for index in range(KEEP_COUNT - 1)]
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW)

    assert result.removed == []
    assert hand_made.exists()
    assert stray_file.exists()
    assert all(run.exists() for run in gate)


def test_order_comes_from_modification_time_not_name(tmp_path: Path) -> None:
    newest_by_name_oldest_by_time = make_run(tmp_path, powershell_name(999), OLD)
    oldest_by_name_newest_by_time = make_run(tmp_path, powershell_name(1), OLD + 100)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW, keep_count=2)

    assert result.removed == [newest_by_name_oldest_by_time]
    assert oldest_by_name_newest_by_time.exists()


def test_activity_is_the_later_of_the_directory_and_its_output_file(tmp_path: Path) -> None:
    stale_directory_fresh_output = make_run(tmp_path, powershell_name(1), OLD)
    os.utime(stale_directory_fresh_output / KEPT_FILE_NAME, (OLD + 500, OLD + 500))
    plain = make_run(tmp_path, powershell_name(2), OLD + 100)
    no_output = make_run(tmp_path, powershell_name(3), OLD + 50, with_output=False)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    result = prune_old_runs(tmp_path, own, now=NOW, keep_count=3)

    assert result.removed == [no_output]
    assert stale_directory_fresh_output.exists()
    assert plain.exists()


def test_the_runs_own_directory_is_never_deleted_and_counts_as_kept(tmp_path: Path) -> None:
    own = make_run(tmp_path, powershell_name(1), OLD)
    other = make_run(tmp_path, powershell_name(2), OLD + 10)

    result = prune_old_runs(tmp_path, own, now=NOW, keep_count=1)

    assert result.removed == []
    assert own.exists()
    assert other.exists()


def test_a_missing_runs_root_is_a_warning_not_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = prune_old_runs(tmp_path / "absent", tmp_path / powershell_name(1), now=NOW)

    assert result.removed == []
    assert len(result.failures) == 1
    assert "absent" in capsys.readouterr().err


def test_clean_finished_run_keeps_only_the_output_file(tmp_path: Path) -> None:
    run = make_run(tmp_path, powershell_name(1), NOW)
    (run / "htmlcov").mkdir()
    (run / "htmlcov" / "index.html").write_text("x", encoding="utf-8")
    (run / ".coverage").write_text("x", encoding="utf-8")
    (run / "step-output.txt").write_text("x", encoding="utf-8")

    result = clean_finished_run(run)

    assert result.failures == []
    assert {path.name for path in result.removed} == {"pytest", "htmlcov", ".coverage", "step-output.txt"}
    assert remaining(run) == {KEPT_FILE_NAME}
    assert (run / KEPT_FILE_NAME).read_text(encoding="utf-8") == "log"


def test_clean_finished_run_removes_read_only_files(tmp_path: Path) -> None:
    run = make_run(tmp_path, shell_name(1), NOW)
    locked = run / "pytest" / "file.txt"
    locked.chmod(0o444)

    result = clean_finished_run(run)

    assert result.failures == []
    assert remaining(run) == {KEPT_FILE_NAME}


def test_clean_finished_run_refuses_a_folder_that_is_not_a_run_directory(tmp_path: Path) -> None:
    other = tmp_path / "not-a-run"
    other.mkdir()
    (other / "precious.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="not a gate run directory"):
        clean_finished_run(other)

    assert (other / "precious.txt").exists()


def test_a_deletion_failure_is_reported_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    old = make_run(tmp_path, powershell_name(1), OLD)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    def locked(*_args: object, **_kwargs: object) -> None:
        raise OSError("in use")

    monkeypatch.setattr(shutil, "rmtree", locked)

    result = prune_old_runs(tmp_path, own, now=NOW, keep_count=1)

    assert result.removed == []
    assert len(result.failures) == 1
    assert old.exists()
    assert f"could not delete {old}" in capsys.readouterr().err


def test_a_deletion_that_leaves_the_path_in_place_is_reported_and_not_counted_as_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    old = make_run(tmp_path, powershell_name(1), OLD)
    own = make_run(tmp_path, powershell_name(900), NOW - 1)

    def does_nothing(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(shutil, "rmtree", does_nothing)

    result = prune_old_runs(tmp_path, own, now=NOW, keep_count=1)

    assert result.removed == []
    assert len(result.failures) == 1
    assert old.exists()
    assert f"could not delete {old}" in capsys.readouterr().err


def test_a_locked_file_inside_a_run_is_reported_and_the_rest_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run = make_run(tmp_path, powershell_name(1), NOW)
    (run / "stuck.txt").write_text("x", encoding="utf-8")
    real_unlink = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name == "stuck.txt":
            raise PermissionError("locked")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)

    result = clean_finished_run(run)

    assert len(result.failures) == 1
    assert "stuck.txt" in capsys.readouterr().err
    assert remaining(run) == {KEPT_FILE_NAME, "stuck.txt"}


def test_main_prune_and_clean_exit_zero_and_a_bad_clean_target_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    own = make_run(tmp_path, powershell_name(1), NOW)

    assert main(["prune", str(tmp_path), str(own)]) == 0
    assert "Removed 0 old run directories" in capsys.readouterr().out
    assert main(["clean", str(own)]) == 0
    assert "kept gate-output.txt" in capsys.readouterr().out
    assert remaining(own) == {KEPT_FILE_NAME}
    assert main(["clean", str(tmp_path)]) == 2
