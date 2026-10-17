"""Prove that ``ian`` runs from a wheel installed outside the repository.

The script builds the wheel into a new temporary folder, checks what the wheel holds, installs it into a fresh
environment there and runs the installed ``ian`` with the temporary folder as the current folder. It checks, in order:

* the wheel contains every file ``package-data`` lists and exactly one top-level package;
* ``import investment_analysis_engine`` resolves inside the new environment;
* ``ian --help`` succeeds, and ``ian db upgrade`` and ``ian db status`` succeed with the database in the data folder;
* ``ian evaluate --mode deterministic`` writes the same report as the repository checkout;
* the system prompt built by the installed package contains the runtime rules;
* ``ian momentum`` without a ticker gives the message ``ian graham-number`` gives, for its own name;
* a user ``strategies/momentum.toml`` with one valid key is accepted, and one with an invalid value is refused with a
  message naming that file;
* ``git status --porcelain`` of the repository is the same before and after.

Every ``PYTHONPATH`` and ``IAN_*`` variable is removed first. By default ``IAN_CONFIG_DIR``, ``IAN_DATA_DIR`` and
``IAN_LOG_DIR`` point into the temporary folder. With ``--real-user-folders`` no folder variable is set for the runs and
the script checks that the database lands in the platform's per-user data folder; only CI passes it. Standard library
only; it changes nothing in the repository.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_NAME = "investment_analysis_engine"
RUN_IDENTITY_KEYS = frozenset({"executed_at", "run_id", "trajectory_id"})
VALID_USER_SETTINGS = "rsi_period = 21\n"
INVALID_USER_SETTINGS = "rsi_period = -1\n"
STEP_TIMEOUT_SECONDS = 900
# The two lines uv itself prints because it builds with byte-compiling off; they say nothing about the project.
UV_BUILD_NOTICES = frozenset(
    {
        "warning: build_py: byte-compiling is disabled, skipping.",
        "warning: install_lib: byte-compiling is disabled, skipping.",
    }
)


@dataclass
class Results:
    """The outcome of each named check, in the order it ran."""

    outcomes: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, passed: bool, detail: str = "") -> bool:
        """Record and print one check; return whether it passed."""
        self.outcomes.append((name, passed, detail))
        print(f"{'PASS' if passed else 'FAIL'}  {name}" + (f": {detail}" if detail and not passed else ""), flush=True)
        return passed

    @property
    def failed(self) -> list[str]:
        """Return the names of the checks that failed."""
        return [name for name, passed, _ in self.outcomes if not passed]


def run(
    command: Sequence[str | Path], *, cwd: Path, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``command`` without a shell, capturing text output; a command that cannot start or times out fails."""
    try:
        return subprocess.run(  # noqa: S603
            [str(part) for part in command],
            cwd=cwd,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STEP_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess([str(part) for part in command], 127, "", f"{type(error).__name__}: {error}")


def tail(completed: subprocess.CompletedProcess[str]) -> str:
    """Return the last lines of a command's output, for a failure detail."""
    text = (completed.stderr or completed.stdout).strip()
    return " | ".join(text.splitlines()[-4:]) or f"exit code {completed.returncode}"


def repository_root() -> Path:
    """Return the top folder of the repository this script is run from."""
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git is required to find the repository.")
    completed = subprocess.run(  # noqa: S603
        [git, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False, timeout=60
    )
    if completed.returncode != 0:
        raise SystemExit("Run this script inside the repository.")
    return Path(completed.stdout.strip()).resolve()


def git_status(repository: Path) -> str:
    """Return ``git status --porcelain`` for the repository."""
    git = shutil.which("git") or "git"
    return run([git, "status", "--porcelain"], cwd=repository).stdout


def expected_package_data(repository: Path) -> list[str]:
    """Return every file, relative to the repository, that ``package-data`` in ``pyproject.toml`` names."""
    with (repository / "pyproject.toml").open("rb") as handle:
        patterns: list[str] = tomllib.load(handle)["tool"]["setuptools"]["package-data"][PACKAGE_NAME]
    package = repository / PACKAGE_NAME
    return sorted(
        path.relative_to(repository).as_posix()
        for pattern in patterns
        for path in package.glob(pattern)
        if path.is_file()
    )


def clean_environment(base: Mapping[str, str]) -> dict[str, str]:
    """Return ``base`` without ``PYTHONPATH``, an active virtual environment or any ``IAN_*`` variable."""
    removed = {"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"}
    environment = {
        name: value
        for name, value in base.items()
        if name.upper() not in removed and not name.upper().startswith("IAN_")
    }
    environment["PYTHONUTF8"] = "1"
    return environment


def comparable(report: object) -> object:
    """Return a Golden report without the fields that identify one run."""
    if isinstance(report, dict):
        return {key: comparable(value) for key, value in report.items() if key not in RUN_IDENTITY_KEYS}
    if isinstance(report, list):
        return [comparable(item) for item in report]
    return report


def check_wheel(results: Results, repository: Path, wheel: Path) -> None:
    """Check the wheel's package-data files and that it holds exactly one top-level package."""
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    expected = expected_package_data(repository)
    missing = [name for name in expected if name not in names]
    results.record("wheel holds every package-data file", bool(expected) and not missing, f"missing {missing[:3]}")
    top_level = {name.split("/", 1)[0] for name in names if not name.split("/", 1)[0].endswith(".dist-info")}
    results.record(
        "wheel holds exactly one top-level package", top_level == {PACKAGE_NAME}, f"top-level names {sorted(top_level)}"
    )
    data_patterns = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"][
        "package-data"
    ][PACKAGE_NAME]
    unexpected = [
        name
        for name in names
        if name.startswith(f"{PACKAGE_NAME}/")
        and not name.endswith((".py", "/"))
        and not any(fnmatch.fnmatch(name, f"{PACKAGE_NAME}/{pattern}") for pattern in data_patterns)
    ]
    results.record("wheel holds no data file beyond package-data", not unexpected, f"found {unexpected[:3]}")


def build_wheel(results: Results, repository: Path, destination: Path) -> Path | None:
    """Build the wheel into ``destination``; a warning in the build output fails the check."""
    uv = shutil.which("uv")
    if uv is None:
        results.record("uv is available", False, "uv was not found on the path")
        return None
    completed = run(
        [uv, "build", "--wheel", "--out-dir", destination], cwd=repository, env=clean_environment(os.environ)
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    wheels = sorted(destination.glob("*.whl"))
    built = completed.returncode == 0 and len(wheels) == 1
    results.record("uv build --wheel succeeds", built, tail(completed))
    warned = [
        line for line in output.splitlines() if "warning" in line.lower() and line.strip() not in UV_BUILD_NOTICES
    ]
    results.record("uv build prints no warning", not warned, " | ".join(warned[:3]))
    return wheels[0] if built else None


def install_wheel(results: Results, wheel: Path, work: Path) -> Path | None:
    """Create a fresh environment of the running Python version, install the wheel and return its interpreter."""
    uv = shutil.which("uv") or "uv"
    environment = work / "venv"
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    created = run([uv, "venv", environment, "--python", version], cwd=work, env=clean_environment(os.environ))
    if not results.record("fresh environment is created", created.returncode == 0, tail(created)):
        return None
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    installed = run([uv, "pip", "install", "--python", python, wheel], cwd=work, env=clean_environment(os.environ))
    if not results.record("wheel installs into the fresh environment", installed.returncode == 0, tail(installed)):
        return None
    return python


def installed_ian(python: Path) -> Path:
    """Return the ``ian`` executable that sits beside ``python``."""
    return python.parent / ("ian.exe" if sys.platform == "win32" else "ian")


def run_installed_checks(  # noqa: PLR0913
    results: Results,
    repository: Path,
    work: Path,
    python: Path,
    environment: Mapping[str, str],
    *,
    data_folder: Callable[[], Path],
) -> None:
    """Run the installed ``ian`` and the installed package through the checks in the module docstring."""
    ian = installed_ian(python)
    where = run([python, "-c", f"import {PACKAGE_NAME}; print({PACKAGE_NAME}.__file__)"], cwd=work, env=environment)
    location = Path(where.stdout.strip()).resolve() if where.returncode == 0 and where.stdout.strip() else None
    environment_root = python.parent.parent.resolve()
    results.record(
        "import resolves inside the new environment",
        location is not None and location.is_relative_to(environment_root),
        f"{location} is not inside {environment_root}" if location else tail(where),
    )

    helped = run([ian, "--help"], cwd=work, env=environment)
    results.record("ian --help succeeds", helped.returncode == 0, tail(helped))

    upgraded = run([ian, "db", "upgrade"], cwd=work, env=environment)
    results.record("ian db upgrade succeeds", upgraded.returncode == 0, tail(upgraded))
    status = run([ian, "db", "status", "--json"], cwd=work, env=environment)
    database: Path | None
    try:
        database = Path(json.loads(status.stdout)["database_path"]).resolve()
    except (ValueError, KeyError, OSError):
        database = None
    results.record("ian db status succeeds", status.returncode == 0, tail(status))
    expected_folder = data_folder().resolve()
    results.record(
        "the database lies in the data folder",
        database is not None and database.parent == expected_folder and database.is_file(),
        f"database {database}, data folder {expected_folder}",
    )

    installed_report, checkout_report = work / "installed-report.json", work / "checkout-report.json"
    evaluated = run(
        [ian, "evaluate", "--mode", "deterministic", "--report", installed_report], cwd=work, env=environment
    )
    uv = shutil.which("uv") or "uv"
    reference = run(
        [uv, "run", "--no-sync", "ian", "evaluate", "--mode", "deterministic", "--report", checkout_report],
        cwd=repository,
        env=environment,
    )
    same = False
    if evaluated.returncode == 0 and reference.returncode == 0:
        same = comparable(json.loads(installed_report.read_text(encoding="utf-8"))) == comparable(
            json.loads(checkout_report.read_text(encoding="utf-8"))
        )
    results.record(
        "the evaluation report equals the repository checkout's",
        same,
        tail(evaluated) if evaluated.returncode else tail(reference) if reference.returncode else "reports differ",
    )

    prompt = run(
        [
            python,
            "-c",
            "from investment_analysis_engine.orchestrator.prompts import SystemPromptBuilder; "
            "p = SystemPromptBuilder().build(); "
            "print('# RUNTIME AGENT RULES' in p and 'Runtime Guardrails' in p)",
        ],
        cwd=work,
        env=environment,
    )
    results.record("the system prompt contains the runtime rules", prompt.stdout.strip() == "True", tail(prompt))

    momentum = run([ian, "momentum"], cwd=work, env=environment)
    graham = run([ian, "graham-number"], cwd=work, env=environment)
    results.record(
        "ian momentum without a ticker gives the message ian graham-number gives",
        momentum.returncode == graham.returncode == 1
        and bool(momentum.stderr.strip())
        and momentum.stderr.strip() == graham.stderr.strip().replace("graham-number", "momentum"),
        f"{momentum.stderr.strip()!r} against {graham.stderr.strip()!r}",
    )


def run_user_settings_checks(results: Results, work: Path, python: Path, base: Mapping[str, str]) -> None:
    """Check a user strategy settings file with one valid key, then with an invalid value, in a folder of its own."""
    config = work / "user-settings"
    environment = {
        **base,
        "IAN_CONFIG_DIR": str(config),
        "IAN_DATA_DIR": str(work / "user-settings-state" / "data"),
        "IAN_LOG_DIR": str(work / "user-settings-state" / "logs"),
    }
    ian = installed_ian(python)
    user_file = config / "strategies" / "momentum.toml"
    user_file.parent.mkdir(parents=True)

    user_file.write_text(VALID_USER_SETTINGS, encoding="utf-8")
    accepted = run([ian, "--help"], cwd=work, env=environment)
    applied = run(
        [
            python,
            "-c",
            "from investment_analysis_engine.cli_composition import momentum_settings as m; print(m().rsi_period)",
        ],
        cwd=work,
        env=environment,
    )
    results.record(
        "a user strategy file with one valid key is accepted and applied",
        accepted.returncode == 0 and applied.stdout.strip() == "21",
        f"{tail(accepted)} / {tail(applied)}",
    )

    user_file.write_text(INVALID_USER_SETTINGS, encoding="utf-8")
    refused = run([ian, "--help"], cwd=work, env=environment)
    results.record(
        "a user strategy file with an invalid value is refused naming that file",
        refused.returncode == 2 and str(user_file.resolve()) in refused.stderr,
        tail(refused),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run every check and return 0 when all pass."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument(
        "--real-user-folders",
        action="store_true",
        help="set no folder variable for the runs and check the database lands in the per-user data folder (CI only)",
    )
    arguments = parser.parse_args(argv)

    repository = repository_root()
    status_before = git_status(repository)
    results = Results()
    work = Path(tempfile.mkdtemp(prefix="ian-installed-")).resolve()
    try:
        if work.is_relative_to(repository):
            raise SystemExit("The temporary folder must be outside the repository.")
        wheel = build_wheel(results, repository, work / "dist")
        if wheel is not None:
            check_wheel(results, repository, wheel)
            python = install_wheel(results, wheel, work)
            if python is not None:
                base = clean_environment(os.environ)
                if arguments.real_user_folders:
                    environment = base

                    def data_folder() -> Path:
                        found = run(
                            [
                                python,
                                "-c",
                                "from investment_analysis_engine.config.user_folders import user_data_folder; "
                                "print(user_data_folder())",
                            ],
                            cwd=work,
                            env=environment,
                        )
                        return Path(found.stdout.strip())
                else:
                    folders = {name: work / "state" / name.lower() for name in ("config", "data", "logs")}
                    environment = {
                        **base,
                        "IAN_CONFIG_DIR": str(folders["config"]),
                        "IAN_DATA_DIR": str(folders["data"]),
                        "IAN_LOG_DIR": str(folders["logs"]),
                    }

                    def data_folder() -> Path:
                        return folders["data"]

                run_installed_checks(results, repository, work, python, environment, data_folder=data_folder)
                run_user_settings_checks(results, work, python, base)
        results.record("git status --porcelain is the same before and after", git_status(repository) == status_before)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if results.failed:
        print(f"{len(results.failed)} of {len(results.outcomes)} checks failed.", file=sys.stderr)
        return 1
    print(f"All {len(results.outcomes)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
