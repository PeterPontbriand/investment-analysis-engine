# IR.8 — Windows Path Anchoring Guard

Revision 1 was approved for implementation on 2026-09-29.

Parent: [IR contract and slice plan](IR_CONTRACT_AND_SLICE_PLAN.md).

## 1. At a glance

- **What IR.8 is:** on Windows, every filesystem path the project accepts must be either relative
  or fully qualified. A path that is only partly anchored is rejected with a message that names
  the setting and suggests the path the user probably meant. Examples are `/e/Source/x` (a root
  but no drive, which is how Git Bash writes paths) and `E:data` (a drive but no root).
- **Why:** today such a path is accepted without complaint. Windows resolves it against the root
  of the current drive, so SQLite or the log handlers create folders like `E:\e\Source\…` outside
  the project. This has already happened in smoke tests.
- **What it is not:** no change on Linux or macOS; no automatic conversion of Git Bash paths; no
  change to how relative or fully qualified paths resolve today, apart from the log-directory
  alignment in [3.1](#31-guard-in-the-settings-loader); no change to how startup errors are
  presented.
- **Rules it follows:** `AGENTS.md` §0, §7 (full managed gate on every commit) and line 58 (no
  AI/tool attribution). It is one gated slice that stops for review once, at the end.
- **Branch:** `fix/ir8-windows-path-guard` off `main`, merged to `main` on its own once accepted,
  following IR.4's precedent. It shares no code with IR.2–IR.6.

## 2. Sequence and status

| Commit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 1 | [Guard in the settings loader](#31-guard-in-the-settings-loader) | Complete | 2026-09-29 |
| 2 | [Reasons reach the user on every CLI surface](#32-reasons-reach-the-user-on-every-cli-surface) | Complete | 2026-09-29 |
| 3 | [User documentation and agent guidance](#33-user-documentation-and-agent-guidance) | Complete | 2026-09-30 |

## 3. The commits

### 3.1 Guard in the settings loader

- **Problem:** `ProjectSettings` joins configured paths to `base_dir` with `pathlib`. On Windows,
  `base_dir / "/e/Source/x"` keeps `base_dir`'s drive and discards the rest, which gives
  `E:\e\Source\x`. `log_dir` and `telemetry_log_dir` are used as given, so the same input lands
  under the current drive's root, and a relative value resolves against the terminal's current
  folder instead of the project.
- **Decision:** add a new helper,
  `require_anchored_path(value: str, *, name: str, windows: bool) -> None` in
  `src/utils/paths.py`, which raises `ValueError` for a partly anchored path. It is built on
  `PureWindowsPath`, so the rule is testable on every OS. `ProjectSettings`' existing model
  validator calls it with `windows=sys.platform == "win32"` on the *raw* values of `base_dir`,
  `data_dir`, `log_dir`, `telemetry_log_dir` and `database_url`'s database path, before any
  resolution. `log_dir` and `telemetry_log_dir` also start resolving relative values against
  `base_dir`, which is how `data_dir` and `database_url` already behave.
- **Scope:** `src/utils/paths.py` (new), `src/config.py`, `tests/utils/test_paths.py` (new),
  `tests/test_config.py`.
- **Branch:** `fix/ir8-windows-path-guard`.
- **Detail:** [A.1](#a1-commit-1-guard-in-the-settings-loader).

### 3.2 Reasons reach the user on every CLI surface

- **Problem:** `database check` and `database upgrade --database-url` replace every validation
  failure with "Select a valid local SQLite database URL.", so the guard's explanation would
  never be shown there. `evaluate --report` accepts a path and creates its parent folders without
  any check.
- **Decision:** the `database` commands keep that sentence and append the validator's reason.
  `evaluate --report` applies the same helper and reports a failure as `typer.BadParameter`.
- **Scope:** `src/cli_database.py`, `src/cli.py` (`evaluate` only), and their tests.
- **Branch:** `fix/ir8-windows-path-guard`.
- **Detail:** [A.2](#a2-commit-2-reasons-reach-the-user-on-every-cli-surface).

### 3.3 User documentation and agent guidance

- **Problem:** `DATABASE.md`'s only Bash example is a Linux path (`sqlite:////srv/…`). A Git Bash
  user on Windows who adapts it writes `sqlite:////e/…`, which is exactly the path this guard
  now rejects.
- **Decision:** separate the Linux/macOS and Git Bash examples, and add one sentence to
  `AGENTS.md` §10 for agents working in Git Bash.
- **Scope:** `docs/user/DATABASE.md`, `AGENTS.md`.
- **Branch:** `fix/ir8-windows-path-guard`.
- **Detail:** [A.3](#a3-commit-3-user-documentation-and-agent-guidance).

## 4. Out of scope

- How an invalid setting is reported at startup. Importing `src.config` raises today, and the
  guard's message will appear in that traceback. Structured error output has its own record:
  [DEFERRED_STRUCTURED_ERROR_REPORTING.md](../DEFERRED_STRUCTURED_ERROR_REPORTING.md).
- Converting Git Bash paths automatically ([B.1](#b1-decisions), item 1).
- Any change on Linux or macOS, where `/e/Source` is a valid absolute path.
- Registering IR.8 in the IR contract's sequence table. The contract is maintained on
  `feat/ir-integration-readiness`, so the row is added there when `main` is merged back in.

## 5. Acceptance criteria

- **Rejected on Windows, with a readable reason:** `/e/Source/x`, `\e\Source\x` and `E:data`, in
  each of the five settings and in `evaluate --report`. Nothing is created on disk.
- **Accepted and unchanged:** relative paths, drive-qualified paths (`E:/Source/x`, `E:\Source\x`),
  UNC paths, `:memory:` and the empty database, on every OS; any path on Linux and macOS.
- **Log directories:** a relative `log_dir` or `telemetry_log_dir` resolves under `base_dir`; the
  defaults are unchanged.
- **Reason shown:** `database check --database-url sqlite:////e/x.sqlite3` on Windows prints the
  existing sentence followed by the guard's reason.
- **Tests run everywhere:** the helper's tests run on all three CI operating systems via
  `windows=True/False`. At least one end-to-end `ProjectSettings` test runs unmocked on Windows
  (`skipif` elsewhere).
- **Quality gate:** the full managed gate after every commit, ≥85% coverage.

**Acceptance note (2026-09-30).** All three commits passed the full managed gate; final state 3311
tests, 91% line coverage. Live check on Windows 11 with Git Bash, using only Windows-form or relative
paths:

- `ian db status --database-url sqlite:////e/ir8-probe/x.sqlite3` is rejected as a usage error that
  shows the existing sentence, the guard's reason and the suggestion `E:/ir8-probe/x.sqlite3`.
- With `database_url` set to that value in the environment, `ian db status` fails on import with the
  guard's one-line message inside the startup traceback, as [Out of scope](#4-out-of-scope) says.
- `ian db status --database-url sqlite:///.tmp/ir8-probe/x.sqlite3` and `ian db upgrade` against the same
  relative URL work and create the database under the project folder.
- `E:\e`, `E:\c` and `E:\ir8-probe` do not exist afterward. The throwaway `.tmp/ir8-probe` was deleted.

## 6. Background

On 2026-09-29, two unwanted folder trees were found at the root of `E:`, next to the repository:
`E:\e\Source\investment-analysis-engine\.tmp\esc-d2-evidence\` (22–23 September) and
`E:\c\Users\…\Temp\claude\…\scratchpad\ir25-smoke-normal\` (28 September). Each held a smoke-test
SQLite database. Both came from a Git Bash–style path (`/e/…`, `/c/…`) placed in `database_url`
during agent smoke tests; `ProjectSettings` accepted it and SQLite created the folders. IR.2.6's
live smoke hit the same trap again. A contributor using Git Bash, the shell `AGENTS.md` §10
recommends as the alternative to PowerShell, would hit it too.

---

## Appendix A: Implementation detail

### A.1 Commit 1: guard in the settings loader

The rule, applied to `PureWindowsPath(value)` when `windows` is true:

| `drive` | `root` | Example | Result |
| :--- | :--- | :--- | :--- |
| empty | empty | `data/x.sqlite3` | accepted (relative) |
| set | set | `E:/Source/x`, `\\server\share\x` | accepted (fully qualified, including UNC) |
| empty | set | `/e/Source/x`, `\e\Source\x` | rejected |
| set | empty | `E:data` | rejected |

When `windows` is false, the helper returns without checking.

Message shape (one line; the suggestion appears only when the first segment is a single ASCII
letter):

```text
database_url path '/e/Source/x.sqlite3' has a root but no drive letter, so Windows would place it under the current drive's root. Use a full path such as 'E:/Source/x.sqlite3' or a path relative to the project folder; in Git Bash, 'cygpath -m <path>' prints the Windows form.
```

The drive-but-no-root case reads "…has a drive letter but no root, so Windows would resolve it
against that drive's current folder…".

- The validator checks raw values before the existing `base_dir` / `data_dir` / database
  resolution. For `base_dir`, `data_dir`, `log_dir` and `telemetry_log_dir`, it checks only
  values in `model_fields_set`; defaults are always fully qualified.
- `log_dir` and `telemetry_log_dir`: a relative value set by the user resolves as
  `(self.base_dir / value).resolve()`, the same way `data_dir` does. The defaults
  (`base_dir / "logs"`, the module-relative telemetry path) are not changed.
- Tests: `tests/utils/test_paths.py` covers each row of the table in both `windows` modes, plus
  the suggestion text. `tests/test_config.py` gains validator-level rejection tests for each
  setting, using `windows=True` through a module-level seam
  (`src.config._IS_WINDOWS`, monkeypatched). It also gains relative log-directory resolution
  tests and one unmocked `skipif(sys.platform != "win32")` test.

### A.2 Commit 2: reasons reach the user on every CLI surface

- `src/cli_database.py` `_run`: the `BadParameter` message becomes
  `"Select a valid local SQLite database URL: <reason>"`. `<reason>` is the first validation
  error's message with pydantic's "Value error, " prefix removed, or `str(exc)` for a plain
  `ValueError`. This also exposes the existing reasons (wrong driver, credentials, `file:` URIs);
  update tests that assert the old exact text.
- `src/cli.py` `evaluate`: call `require_anchored_path(str(report_path), name="--report",
  windows=sys.platform == "win32")` before any work, converting `ValueError` to
  `typer.BadParameter`. Relative `--report` paths keep resolving against the current folder, as
  command-line paths conventionally do.
- Tests: `tests/test_cli_database.py` (reason appended, for the guard and one existing reason);
  `evaluate --report` rejection with the report file and its folders not created.

### A.3 Commit 3: user documentation and agent guidance

- `docs/user/DATABASE.md` "Choose the database location": retitle the Bash example "Linux or
  macOS"; add a "Git Bash on Windows" example using
  `export database_url="sqlite:///E:/FinancialData/investment-analysis-engine.sqlite3"`; add one
  sentence saying that on Windows a path with a root but no drive letter (such as `/e/…`) is
  rejected, and that `cygpath -m` converts it. Use no planning labels.
- `AGENTS.md` §10, first list, after "Prefer portable path handling": in Git Bash, give settings
  and CLI options Windows-form (`E:/…`) or relative paths. For throwaway smoke databases, prefer
  a relative URL such as `sqlite:///.tmp/<name>/x.sqlite3`, which resolves under the project
  folder.

---

## Appendix B: Decision records

### B.1 Decisions

1. **Reject, don't convert.** Rewriting `/e/Source` to `E:/Source` would be right for Git Bash
   input, but `/tmp/x` or `/data/x` have no single correct Windows meaning. A guess that puts data
   somewhere unexpected is the failure this guard exists to prevent. The message carries the
   suggested form instead.
2. **The rule lives in the settings loader, not in `SQLiteDatabase`.** Every database surface
   (the application, `database check/upgrade --database-url`, Alembic `-x database_url`) already
   builds a `ProjectSettings`, so one check covers all of them, and the log directories come for
   free.
3. **Relative log directories now follow `base_dir`.** This closes the one remaining case where a
   path setting's meaning depends on the terminal's current folder. It is in scope because the
   guard's goal is that no configured path lands somewhere unexpected; it changes behavior only
   for users who set a relative `log_dir` or `telemetry_log_dir`.
4. **Existing `database` error reasons become visible too.** Hiding the reason was a
   contributor-hostile default for every failure, not just this one. The existing sentence is
   kept as the message's first part.

### B.2 Found during implementation

1. **The plan says `database check`; the command is `ian db status`.** The hidden `db` group has
   `status` and `upgrade`; there is no `check`. Every reference in this plan and its tests means
   `db status`.
2. **`evaluate` needs its own Windows seam.** A.2 passes `sys.platform == "win32"` inline, which cannot be
   exercised on Linux or macOS. `src/cli.py` gains a module constant `_IS_WINDOWS`, the same seam
   `src/config.py` uses, and the tests monkeypatch it.
3. **Messages show forward slashes.** Path-valued settings and `--report` reach the guard as
   `Path` objects, so the original spelling is gone. They are passed as `as_posix()`, which is the form
   the message's suggestion uses; the database URL path is passed exactly as typed.

