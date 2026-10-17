# PKG.3 — Self-contained package: slice plan

## At a glance

- **What this does:** the package stops reading anything through the repository. The migrations, the runtime agent rules,
  the shipped strategy settings and the Golden fixtures move into the package; settings, the database and logs use
  per-user folders; `ian` runs from a wheel installed outside the repository.
- **What it is not:** a change of any formula, classification, report or schema. The deterministic Golden report and the
  generated schemas stay byte-for-byte the same apart from run identity fields.
- **Rules it follows:** nothing stored is migrated (no compatibility code); every test run is pointed at a temporary
  folder before the package is imported; the full managed quality gate on the final commit.
- **Parent:** [PKG plan, PKG.3](PKG_RENAME_PLAN.md#pkg3--self-contained-package); decisions are recorded in its
  Appendix A.8.

## Sequence and status

| Commit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 1 | This plan | Complete | 2026-10-16 |
| 2 | Package root and repository root (D12) | Complete | 2026-10-17 |
| 3 | Files move into the package (D7, D9, D10, D11) | Complete | 2026-10-17 |
| 4 | Per-user folders, platformdirs, isolation, no default ticker (D1 to D6, D8, D13, D14, D17) | Complete | 2026-10-17 |
| 5 | Live checks read the per-user `.env` (D19) | Complete | 2026-10-17 |
| 6 | Installed-package proof and CI step (D20) | Complete | 2026-10-17 |
| 7 | Documents | Complete | 2026-10-17 |

## Decisions

| | Decision |
| :--- | :--- |
| D1 | `platformdirs>=4.11` is added as a dependency; `package-data` lists the non-Python files in the wheel. |
| D2 | Per-user folders, below. Resolving a folder never creates it. |
| D3 | Override order, below. |
| D4 | `IAN_CONFIG_DIR` is read from the process environment only; the `.env` file cannot set it. `IAN_BASE_DIR` and `base_dir` are removed. |
| D5 | Folder variables and a file path in `IAN_DATABASE_URL` must be absolute; `--database-url` resolves a relative path against the current folder. |
| D6 | `.env` is loaded only from the settings folder, with an explicit path. |
| D7 | Shipped strategy defaults are `settings.toml` beside the strategy's `settings.py`; a user file overrides per key. |
| D8 | The default ticker is removed: `ian momentum` requires a ticker like the other direct commands. |
| D9 | Migrations live in `investment_analysis_engine/data/repositories/migration_scripts/`; `alembic.ini` stays at the root for developers. |
| D10 | `RUNTIME_AGENTS.md` moves into `orchestrator/`; a missing file raises. |
| D11 | Golden fixtures move to `evaluation/fixtures/sec_edgar/step_2_5a_d0/`, named by one constant. |
| D12 | `core/package_root.py` holds `PACKAGE_ROOT`; `scripts/repository_root.py` holds `REPOSITORY_ROOT` for tests and scripts, and no other file derives it. |
| D13 | No folder is created when the settings module loads; logging creates the log folder. |
| D14 | `ollama_base_url` defaults to `http://localhost:11434`. |
| D17 | Tests run against a session temporary folder set before any import; the session stops if a resolved folder lies outside it. |
| D19 | The live-check scripts read `SEC_USER_AGENT` from the per-user `.env` when it is not set. |
| D20 | `scripts/check_installed_package.py`, run as a module, proves the wheel works outside the repository. |

## Folders (D2)

Application folder `investment-analysis-engine`, no author folder.

| | Settings folder | Data folder (database) | Log folder |
| :--- | :--- | :--- | :--- |
| Windows | `%APPDATA%\investment-analysis-engine` | `%LOCALAPPDATA%\investment-analysis-engine` | `%LOCALAPPDATA%\investment-analysis-engine\Logs` |
| macOS | `~/Library/Application Support/investment-analysis-engine` | same | `~/Library/Logs/investment-analysis-engine` |
| Linux | `$XDG_CONFIG_HOME/investment-analysis-engine` | `$XDG_DATA_HOME/investment-analysis-engine` | `$XDG_STATE_HOME/investment-analysis-engine/log` |

Inside them: `<settings>/.env`, `<settings>/strategies/<alias>.toml`, `<data>/investment-analysis-engine.sqlite3`,
`<logs>/app.log`, `<logs>/trajectories/`.

## Override order (D3)

Highest first.

| Setting | Order |
| :--- | :--- |
| Settings folder | `IAN_CONFIG_DIR`, then the per-user folder |
| Data folder | `IAN_DATA_DIR`, then the per-user folder |
| Log folder | `IAN_LOG_DIR`, then the per-user folder |
| Telemetry folder | `IAN_TELEMETRY_LOG_DIR`, then the log folder in use |
| Database | `--database-url` (`ian db` commands), then `IAN_DATABASE_URL`, then `<data>/investment-analysis-engine.sqlite3` |
| Every `IAN_*` setting | process environment, then `<settings>/.env`, then the code default |
| Strategy settings, per key | `<settings>/strategies/<alias>.toml`, then the shipped default |

## Proof (D20)

`uv run python -m scripts.check_installed_package` builds the wheel into a temporary folder outside the repository, checks its contents,
installs it into a new environment and runs the installed `ian` with every `IAN_*` variable removed and the three folder
variables pointing into the temporary folder. It checks the import location, `--help`, `ian db upgrade` and `ian db status`,
a deterministic evaluation report equal to the checkout's, the runtime rules in the system prompt, the missing-ticker
message of `ian momentum`, a valid and an invalid user strategy settings file, and that the repository's `git status` is
unchanged. With `--real-user-folders` it sets no folder variables and checks the database lands in the per-user data
folder; only CI passes it, on every leg of the matrix, after the test step.

## Isolation (D17)

`tests/conftest.py` removes every `IAN_*` variable, creates one session folder, points the three folder variables into it
and sets `IAN_PROVIDER_CHECK=false`, all before any import that can load the package. At session start it checks that the
resolved settings, data, log and telemetry folders and the database path lie inside the session folder and otherwise stops
the session. The folder is removed at session end. Issue #148 stays open for the invisible opt-in.

## Acceptance

- `ian` runs from an installed wheel outside the repository (D20 passes).
- Nothing in `investment_analysis_engine/` names the repository.
- The Golden report and `uv run python -m scripts.generate_schemas --check` are unchanged; `--help` differs only where it described the
  default ticker or the settings location.
- The complete managed quality gate passes, including the 3.14 pass.
