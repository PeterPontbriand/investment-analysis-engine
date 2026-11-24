"""Report a failed run on ``main`` in one ``main-red`` GitHub issue.

The workflow passes the job results as JSON in ``JOB_RESULTS`` (``toJSON(needs)``), plus ``RUN_URL``, ``COMMIT_SHA`` and
``COMMIT_TITLE``. When every job result is ``success`` or ``skipped`` nothing happens; otherwise the script opens one
issue labelled ``main-red``, or comments on the open one, through the ``gh`` command. ``--dry-run`` prints the plan and
runs no command. Standard library only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass

LABEL = "main-red"
LABEL_COLOR = "B60205"
LABEL_DESCRIPTION = "A run on main failed or found a flaky test"
ISSUE_TITLE = "main is red"
PASSING_RESULTS = frozenset({"success", "skipped"})
SHORT_SHA_LENGTH = 7


@dataclass(frozen=True)
class MainReport:
    """What to do about a run on ``main``: nothing, open an issue, or comment on the open one."""

    action: str
    issue: int | None
    title: str
    body: str


def plan_main_report(
    jobs: Mapping[str, str],
    run_url: str,
    commit_sha: str,
    commit_title: str,
    open_issue: int | None,
) -> MainReport:
    """Decide the report for a run whose jobs finished with the given results."""
    failed = sorted(name for name, result in jobs.items() if result not in PASSING_RESULTS)
    if not failed:
        return MainReport(action="none", issue=None, title="", body="")
    lines = [
        f"Commit: `{commit_sha[:SHORT_SHA_LENGTH]}` {commit_title}",
        f"Run: {run_url}",
        "",
        "Failed jobs:",
        *(f"- `{name}`: {jobs[name]}" for name in failed),
    ]
    body = "\n".join(lines)
    if open_issue is None:
        return MainReport(action="create", issue=None, title=ISSUE_TITLE, body=body)
    return MainReport(action="comment", issue=open_issue, title=ISSUE_TITLE, body=body)


def _gh(arguments: list[str]) -> str:
    """Run one ``gh`` command without a shell and return its standard output."""
    completed = subprocess.run(["gh", *arguments], check=True, capture_output=True, text=True)
    return completed.stdout


def _open_issue() -> int | None:
    """Return the number of the open ``main-red`` issue, or ``None``."""
    listed = json.loads(_gh(["issue", "list", "--label", LABEL, "--state", "open", "--json", "number"]))
    if not listed:
        return None
    return int(listed[0]["number"])


def main() -> int:
    """Read the run from the environment and report it."""
    needs = json.loads(os.environ["JOB_RESULTS"])
    jobs = {name: str(entry["result"]) for name, entry in needs.items()}
    run_url = os.environ["RUN_URL"]
    commit_sha = os.environ["COMMIT_SHA"]
    commit_title = os.environ["COMMIT_TITLE"]
    dry_run = "--dry-run" in sys.argv[1:]
    if dry_run:
        report = plan_main_report(jobs, run_url, commit_sha, commit_title, None)
        sys.stdout.write(f"action={report.action}\ntitle={report.title}\n{report.body}\n")
        return 0
    if all(result in PASSING_RESULTS for result in jobs.values()):
        sys.stdout.write("action=none\n")
        return 0
    _gh(["label", "create", LABEL, "--color", LABEL_COLOR, "--description", LABEL_DESCRIPTION, "--force"])
    report = plan_main_report(jobs, run_url, commit_sha, commit_title, _open_issue())
    if report.action == "create":
        _gh(["issue", "create", "--label", LABEL, "--title", report.title, "--body", report.body])
    elif report.action == "comment" and report.issue is not None:
        _gh(["issue", "comment", str(report.issue), "--body", report.body])
    sys.stdout.write(f"action={report.action}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
