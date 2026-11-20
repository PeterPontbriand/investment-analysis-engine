"""The pure helpers of the installed-package proof; the proof itself builds a wheel and runs in CI."""

from __future__ import annotations

import json

from scripts.check_installed_package import (
    PACKAGE_NAME,
    UV_BUILD_NOTICES,
    build_warnings,
    bundle_difference,
    clean_environment,
    comparable,
    expected_package_data,
)
from scripts.repository_root import REPOSITORY_ROOT


def test_the_environment_loses_pythonpath_and_every_engine_variable_in_any_case() -> None:
    cleaned = clean_environment(
        {
            "PYTHONPATH": "x",
            "IAN_DATA_DIR": "a",
            "ian_log_dir": "b",
            "VIRTUAL_ENV": "v",
            "SEC_USER_AGENT": "u",
            "PATH": "p",
        }
    )

    assert cleaned == {"SEC_USER_AGENT": "u", "PATH": "p", "PYTHONUTF8": "1"}


def test_reports_are_compared_without_the_fields_that_identify_a_run() -> None:
    first = {"run_id": "1", "cases": [{"trajectory_id": "a", "value": 2}], "executed_at": "t1"}
    second = {"run_id": "2", "cases": [{"trajectory_id": "b", "value": 2}], "executed_at": "t2"}

    assert comparable(first) == comparable(second) == {"cases": [{"value": 2}]}
    assert comparable(first) != comparable({"cases": [{"value": 3}]})


def test_the_expected_package_data_lists_the_files_the_project_file_names() -> None:
    expected = expected_package_data(REPOSITORY_ROOT)

    assert f"{PACKAGE_NAME}/orchestrator/RUNTIME_AGENTS.md" in expected
    assert f"{PACKAGE_NAME}/strategies/momentum/settings.toml" in expected
    assert f"{PACKAGE_NAME}/strategies/graham_growth/settings.toml" in expected
    assert f"{PACKAGE_NAME}/evaluation/fixtures/sec_edgar/step_2_5a_d0/SHA256SUMS" in expected
    assert f"{PACKAGE_NAME}/data/repositories/migration_scripts/env.py" in expected
    assert any(name.endswith("versions/0001_persistence.py") for name in expected)


def test_every_settings_file_shipped_in_the_package_matches_a_package_data_pattern() -> None:
    expected = set(expected_package_data(REPOSITORY_ROOT))
    shipped = {
        path.relative_to(REPOSITORY_ROOT).as_posix() for path in (REPOSITORY_ROOT / PACKAGE_NAME).rglob("settings.toml")
    }

    assert f"{PACKAGE_NAME}/data/sec_edgar/settings.toml" in expected
    assert shipped <= expected


def test_the_help_bundle_is_listed_in_package_data() -> None:
    assert f"{PACKAGE_NAME}/help/help_bundle.en.json" in expected_package_data(REPOSITORY_ROOT)


def test_an_installed_bundle_is_compared_with_the_repositorys_as_a_whole() -> None:
    repository_file = REPOSITORY_ROOT / PACKAGE_NAME / "help" / "help_bundle.en.json"
    installed = repository_file.read_text(encoding="utf-8")

    assert bundle_difference(installed, repository_file) is None

    changed = json.loads(installed)
    changed["terms"][next(iter(changed["terms"]))]["body"] += " changed"
    assert bundle_difference(json.dumps(changed, ensure_ascii=False), repository_file) == (
        "the installed bundle differs from the repository's in terms"
    )

    first = next(iter(changed["documents"]))
    smaller = json.loads(installed)
    smaller["documents"][first]["sections"].pop()
    assert bundle_difference(json.dumps(smaller, ensure_ascii=False), repository_file) == (
        "the installed bundle differs from the repository's in documents"
    )

    assert "did not print a bundle as JSON" in str(bundle_difference("Traceback", repository_file))


def test_a_copied_file_whose_name_contains_warning_is_not_a_build_warning() -> None:
    output = "copying investment_analysis_engine/core/entry_warnings.py -> build/lib/investment_analysis_engine/core"

    assert build_warnings(output) == []


def test_a_warning_line_and_a_python_warning_category_are_build_warnings() -> None:
    plain = "warning: something"
    category = "/tmp/build/x.py:1: SetuptoolsDeprecationWarning: something"
    output = "\n".join(["copying a.py -> b", plain, "WARNING: Shouty", category, "done"])

    assert build_warnings(output) == [plain, "WARNING: Shouty", category]


def test_the_two_notices_uv_prints_itself_are_not_build_warnings() -> None:
    assert len(UV_BUILD_NOTICES) == 2
    output = "\n".join(f"  {notice}" for notice in sorted(UV_BUILD_NOTICES))

    assert build_warnings(output) == []
