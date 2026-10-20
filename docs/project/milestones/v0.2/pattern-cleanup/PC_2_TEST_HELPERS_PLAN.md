# PC.2 — Test Helpers: Slice Plan

Makes CLI test isolation an explicit opt-in
([#148](https://github.com/PeterPontbriand/investment-analysis-engine/issues/148)) and replaces the repeated Alembic
setup of the tests with one migrated-database helper
([#145](https://github.com/PeterPontbriand/investment-analysis-engine/issues/145), item 3 of
[#156](https://github.com/PeterPontbriand/investment-analysis-engine/issues/156)).

Parent plan: [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#pc2--test-helpers).

## 1. At a glance

- **What this slice does:** replaces two test patterns a new strategy's tests would copy. CLI test isolation stops
  depending on an import that looks unused, and every test that needs a database at the latest revision gets it from
  one helper that migrates a template once per test process and copies it.
- **What it is not:** a production change. No file under `investment_analysis_engine/`, `scripts/` or `alembic.ini`
  changes, and no test expectation or snapshot changes. It does not cover the other items of #156.
- **Rules it follows:** a consolidation package under `AGENTS.md` §0. The complete managed gate, with the extra
  interpreter, runs on the final commit. Each guard is proved to bite on a deliberate breakage that is then reverted.
- **Decisions:** all approved by the project owner on 2026-10-20 ([A.1](#a1-approved-decisions-2026-10-20)).

## 2. Sequence and status

| Unit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| Slice plan | [This document](#3-the-work-units) and the parent-plan updates | Complete | 2026-10-20 |
| #148 | [CLI test isolation is an opt-in](#148--cli-test-isolation-is-an-opt-in) | Next | |
| #145 | [One migrated-database helper](#145--one-migrated-database-helper) | Planned | |
| Completion | [Plan rows and the final gate](#completion) | Planned | |

## 3. The work units

### #148 — CLI test isolation is an opt-in

- **Problem:** two autouse fixtures in `tests/_cli_helpers.py` isolate the CLI tests from the real database and from
  live Yahoo lookups. A module activates them by importing their names with `# noqa: F401`; nothing in the module uses
  the names, so a tidy-up that removes the "unused" import silently runs the module against the database. A second
  fixture, `isolated_cli_settings`, is a bridge to the first.
- **Decision:** the fixtures become non-autouse and are registered in `tests/conftest.py` like the network guards. A
  module opts in with `pytestmark = pytest.mark.usefixtures(...)`. The two database fixtures become one,
  `isolated_cli_settings`, which isolates the database and returns the isolated `ProjectSettings`.
- **Scope:** the fixture module, `tests/conftest.py`, the 15 modules below, the local copies below, two guard tests and
  the telemetry item.
- **Branch:** `refactor/pc-2-test-helpers`
- **Detail:** the sections below.

#### The fixtures

| Fixture | Where | What it does |
| :--- | :--- | :--- |
| `isolated_cli_settings` | `tests/_cli_isolation.py`, registered in `tests/conftest.py` | Migrates a disposable database (through `migrated_database_url`), patches `settings` in `investment_analysis_engine.cli_support`, `cli_workspace` and `cli_run_support`, and returns the isolated `ProjectSettings`. It does not patch `investment_analysis_engine.cli.settings`, for the reason its docstring keeps: that name is shared well beyond database access, and accepted tests patch fields of the real settings object that `cli.py` reads |
| `stub_yahoo_identity_metadata` | the same module | Stubs the Yahoo identity and instrument-kind lookups |

`isolated_cli_database` no longer exists. `tests/_cli_helpers.py` keeps `normalize_cli_output` and `carry_profile`.

#### The 15 modules

| Module | Needs | Requests the settings | Opt-in |
| :--- | :--- | :--- | :--- |
| `tests/reporting/test_failure_envelope.py` | both | no | `pytestmark` with both names |
| `tests/test_cli.py` | `isolated_cli_settings` | no | `pytestmark` with `isolated_cli_settings` |
| `tests/test_cli_database_readiness.py` | `stub_yahoo_identity_metadata` | no | `pytestmark` with the stub |
| `tests/test_cli_failure_envelope.py` | both | yes (2 tests) | `pytestmark` with both names |
| `tests/test_cli_graham_nonpositive_growth.py` | both | no | `pytestmark` with both names |
| `tests/test_cli_provider_check.py` | both | yes | `pytestmark` with both names |
| `tests/test_cli_refresh.py` | both | yes | `pytestmark` with both names |
| `tests/test_cli_save_run.py` | `isolated_cli_settings` | no | `pytestmark`; its local fixture requests `isolated_cli_settings` so it runs after it ([local copies](#local-copies)) |
| `tests/test_cli_workspace.py` | `isolated_cli_settings` | yes | `pytestmark` with `isolated_cli_settings` |
| `tests/test_command_validation_failures.py` | both | yes (2 tests) | `pytestmark` with both names |
| `tests/test_existing_strategy_failure_output.py` | `stub_yahoo_identity_metadata` | no | `pytestmark` with the stub |
| `tests/test_failure_messages.py` | both | yes | `pytestmark` with both names |
| `tests/test_graham_growth_default_policy.py` | `isolated_cli_settings` | no | `pytestmark` with `isolated_cli_settings` |
| `tests/test_provider_check_element.py` | both | yes | `pytestmark` with both names |
| `tests/test_workspace_integration.py` | both | no | `pytestmark` with both names |

Every `# noqa: F401` import of these fixtures is removed. A test that takes `isolated_cli_settings` as an argument
keeps doing so.

#### Local copies

| Copy | Decision | Reason |
| :--- | :--- | :--- |
| `tests/test_cli_save_run.py`, `isolated_save_run_database` | stays | Keeps every other field of the real settings and patches `cli_run_support` and `cli_support` with that object. It requests `isolated_cli_settings`, so the fixtures run in a fixed order and its patches are the ones in effect. Its migration uses `migrated_database_url` |
| `tests/test_save_run_every_direct_command.py` | stays | Not a fixture: a function that creates one database per strategy alias and patches `cli_run_support` and `cli_support` with real-settings fields kept. Its migration uses `migrated_database_url` |
| `tests/_strategy_document_output.py`, `_migrated` | stays | A function over a temporary folder outside any test fixture, with real-settings fields kept; patches `cli_workspace` and `cli_support`. Its migration uses `migrated_database_url` |
| `tests/_workspace_command_output.py`, `_migrated_settings` | stays | A function over a temporary folder outside any test fixture; also patches `cli_database`. Its migration uses `migrated_database_url` |
| `tests/test_cli_financial_cache.py`, `configured_database` | stays | Parametrised "ready" and "missing"; the "missing" case is an unmigrated database, which the shared fixture never produces. Patches only `cli_support`. The "ready" case uses `migrated_database_url` |
| `tests/test_cli_historical_cache.py`, `configured_settings` | stays | The same "ready" and "missing" parametrisation. The "ready" case uses `migrated_database_url` |
| `tests/test_failure_messages.py`, `_migrated` | stays | Called inside a test after its fixtures with real-settings fields kept; its migration uses `migrated_database_url` |
| `tests/test_cli_workspace.py`, `test_workspace_commands_report_a_sanitized_readiness_error` | stays | Patches `cli_workspace` with an old-revision database on purpose |

No copy does exactly what `isolated_cli_settings` does, so none is replaced by the fixture itself. The search for
others (`cli_support.settings`, `cli_workspace.settings`, `cli_run_support.settings` patched in a test) found only the
modules above and `tests/test_cli_database_readiness.py`, which patches a database that the test builds to fail.

#### Guard tests

| Test | Where | What it asserts |
| :--- | :--- | :--- |
| `test_no_test_module_imports_a_fixture_defined_in_a_helper_module` | `tests/test_helper_conventions.py` | An AST scan: no `test_*.py` module imports a fixture defined in a `tests/_*.py` module. Conftest files, including the inner conftest text in `tests/test_live_selection.py`, are exempt |
| `fail_if_session_database_exists` (autouse fixture) | `tests/conftest.py` | After each test, fails that test if a database file exists at the session's own `database_url` path. The message names the rule: a test that writes to a database isolates it |
| `test_session_database_path_is_the_one_the_guard_checks` | `tests/test_session_isolation.py` | The path the fixture checks is the file the default `database_url` names, inside the session data folder |

#### Telemetry file

A full run leaves one file in the session folder, `logs/trajectories/<uuid>.jsonl`. The slice identifies the test that
writes it and, if one line isolates it, fixes it; otherwise it files an issue at that time naming the test. The result
is reported with the slice.

### #145 — one migrated-database helper

- **Problem:** about thirty test files repeat the same Alembic lines: build a `Config` from `alembic.ini`, point it at a
  temporary database and upgrade to head. Each upgrade takes real time, and the suite pays it for every test.
- **Decision:** a helper module, `tests/_migrated_database.py`, migrates one template database to head once per test
  process and copies the file for each caller. A shared fixture yields a `SQLiteDatabase` over a copy.
- **Scope:** the helper, its registration in `tests/conftest.py`, the 39 sites below, the helper's own test and a guard
  test. No production code.
- **Branch:** `refactor/pc-2-test-helpers`
- **Detail:** the sections below.

#### The helper

| Name | Purpose |
| :--- | :--- |
| `migrated_database_url(folder: Path) -> str` | Copies the template into `folder` and returns the URL of the copy. A second call for the same folder fails: a caller that needs two databases uses two folders |
| `migrated_database` (fixture) | Yields a `SQLiteDatabase` over a copy in the test's `tmp_path` and closes it |
| `alembic_config(database_url: str) -> Config` | The one place that names `alembic.ini`; for the tests whose subject is migration |
| `upgrade_to_head(config: Config) -> None` | The one place that upgrades to head; builds the template and serves the tests whose subject is migration |
| `ALEMBIC_INI` | The path of `alembic.ini`, for the one test that copies the file |

The template is created inside the session folder, through `alembic.ini` as before, on the first use in a process. Every
connection to it is closed and the write-ahead log is checkpointed and removed before the first copy; the helper
raises if a log file remains. A copy is therefore a complete file.

#### The 39 sites

`git grep -n "alembic.ini" -- tests` on `main` (`af46091`) lists 39 lines in 31 files.

| Site | Class | Reason |
| :--- | :--- | :--- |
| `tests/_cli_helpers.py:69` | helper | `isolated_cli_settings` is built on `migrated_database_url` |
| `tests/_strategy_document_output.py:355` | helper | `_migrated` calls `migrated_database_url`; the copy of real-settings fields stays |
| `tests/_workspace_command_output.py:174` | helper | `_migrated_settings` calls `migrated_database_url` on a folder |
| `tests/analysis/fcf_earnings_growth/test_fcf_availability_and_cache_eligibility.py:70` | helper | `database` fixture becomes `migrated_database` |
| `tests/analysis/momentum/test_momentum_as_of_fetch.py:93` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/repositories/test_instrument_profiles.py:30` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/repositories/test_instrument_profiles.py:136` | helper | reopen test calls `migrated_database_url` |
| `tests/data/repositories/test_market_data.py:121` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/repositories/test_migrations.py:25` | keeps its own (migration test) | `migration_config` is the file's own config helper; the file tests migration and `alembic.ini` |
| `tests/data/repositories/test_migrations.py:147` | keeps its own (migration test) | upgrades to head to test the migration scripts and `alembic.ini` |
| `tests/data/repositories/test_persistence_smoke.py:41` | keeps its own (migration test) | upgrades a fresh file twice, then downgrades to base and upgrades again: the subject is the migration round trip. Uses `alembic_config` and `upgrade_to_head` |
| `tests/data/repositories/test_readiness_concurrency.py:46` | keeps its own (migration test) | child process upgrades a fresh file with the migration step patched to pause: the subject is concurrent migration. Uses `alembic_config` and `upgrade_to_head` |
| `tests/data/repositories/test_readiness_concurrency.py:78` | keeps its own (migration test) | the same test's waiting child process. Uses `alembic_config` and `upgrade_to_head` |
| `tests/data/repositories/test_resolved_input_cache.py:183` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/repositories/test_schema.py:53` | keeps its own (migration test) | `config_for` serves `test_failed_initial_revision_rolls_back_all_tables`, whose subject is a failing upgrade of a fresh file; it uses `alembic_config` and `upgrade_to_head`. The `database` fixture that also used it becomes `migrated_database` |
| `tests/data/repositories/test_series_cache.py:60` | helper | the SQLite case of `cache_factory` calls `migrated_database_url` |
| `tests/data/test_cached_client.py:158` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/test_instrument_profile_cache.py:81` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/test_instrument_profile_failure_kinds.py:238` | helper | `database` fixture becomes `migrated_database` |
| `tests/data/test_quote_freshness.py:225` | helper | calls `migrated_database_url`; no longer depends on the working folder |
| `tests/reporting/test_analysis_run_instrument_profile_snapshot.py:121` | helper | `database` fixture becomes `migrated_database` |
| `tests/scripts/test_new_strategy_end_to_end.py:40` | keeps its own (migration test) | copies `alembic.ini` into the generated repository copy; no upgrade. Names the file through `ALEMBIC_INI` |
| `tests/telemetry/test_quality_telemetry.py:53` | helper | calls `migrated_database_url`; no longer depends on the working folder |
| `tests/telemetry/test_sqlite_sink.py:100` | helper | `database` fixture becomes `migrated_database` |
| `tests/test_cli_financial_cache.py:58` | helper | the "ready" case calls `migrated_database_url`; the "missing" case stays an unmigrated file |
| `tests/test_cli_historical_cache.py:36` | helper | the "ready" case calls `migrated_database_url`; the "missing" case stays an unmigrated file |
| `tests/test_cli_save_run.py:60` | helper | `isolated_save_run_database` calls `migrated_database_url` |
| `tests/test_cli_workspace.py:722` | keeps its own (migration test) | upgrades to `0001_persistence`, an older revision, on purpose. Uses `alembic_config` |
| `tests/test_failure_messages.py:300` | helper | `_migrated` calls `migrated_database_url` |
| `tests/test_save_run_every_direct_command.py:37` | helper | calls `migrated_database_url` |
| `tests/workspace/repositories/test_analysis_runs.py:58` | helper | `database` fixture becomes `migrated_database` |
| `tests/workspace/repositories/test_analysis_runs.py:75` | helper | reopen test calls `migrated_database_url` |
| `tests/workspace/repositories/test_analysis_runs.py:101` | helper | reopen test calls `migrated_database_url` |
| `tests/workspace/repositories/test_analysis_runs.py:256` | helper | no-network test calls `migrated_database_url` |
| `tests/workspace/repositories/test_watchlist_repository.py:49` | helper | `database` fixture becomes `migrated_database` |
| `tests/workspace/repositories/test_watchlist_repository.py:297` | helper | reopen test calls `migrated_database_url` |
| `tests/workspace/repositories/test_watchlist_repository.py:334` | helper | no-network test calls `migrated_database_url` |
| `tests/workspace/test_execution.py:321` | helper | reopen test calls `migrated_database_url` |
| `tests/workspace/test_refresh.py:818` | helper | calls `migrated_database_url` |

Totals: 31 sites use the helper and 8 keep their own Alembic calls.

#### Migration tests

Tests whose subject is migration keep their own Alembic calls, through `alembic_config` and `upgrade_to_head` so that
the file name and the head upgrade are written in one place: `tests/data/repositories/test_migrations.py` (exempt from
the guard, because it also tests `alembic.ini`), every upgrade to a revision other than head, and the tests listed above
as "keeps its own". The guard below then covers every other file under `tests/`.

#### Guard tests

| Test | Where | What it asserts |
| :--- | :--- | :--- |
| `test_a_copied_database_is_at_head_and_ready` | `tests/test_migrated_database.py` | A copy is at head and passes `ensure_database_ready`, the check the CLI uses, with outcome `READY` and no upgrade |
| `test_two_copies_are_independent_files` | `tests/test_migrated_database.py` | Writing to one copy leaves the template and the other copy unchanged |
| `test_a_second_copy_into_the_same_folder_is_refused` | `tests/test_migrated_database.py` | The helper never overwrites a database |
| `test_no_test_names_alembic_ini_or_upgrades_to_head_outside_the_migration_helper` | `tests/test_helper_conventions.py` | An AST scan: no string constant `"alembic.ini"` and no `upgrade(..., "head")` call anywhere under `tests/` outside `tests/_migrated_database.py`, `tests/data/repositories/test_migrations.py` and the scan's own file |

### Completion

- In [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status), PC.2 is Complete with its date
  and PC.3 is Next.
- The complete managed gate runs on the final commit, with the extra interpreter.

## 4. Scope limits

- No file under `investment_analysis_engine/`, `scripts/` or `alembic.ini` changes.
- No test expectation or snapshot changes.
- The work stops for the project owner when: a change needs production code; a test seems to need its own upgrade to
  head for a reason other than testing migration; the session-database guard fails on a test that neither an opt-in nor
  the helper isolates; a test's observed behaviour changes after a copied template replaces its own migration; or the
  generator end-to-end test exceeds its 2-minute budget on either Python version.

## 5. Acceptance criteria

- No test module imports an isolation fixture; every module that needs one opts in with `pytestmark`.
- `isolated_cli_database` does not exist.
- No file under `tests/` outside the migration helper and `test_migrations.py` names `alembic.ini` or upgrades to head.
- The three guards fail on their deliberate breakages (proved and reverted, and reported with the slice).
- The complete managed gate passes; its times before and after are posted on #156.

## 6. Background: origin of this slice

PC removes patterns that Step 3.5 strategies would copy. The tests of a new strategy would copy the invisible
isolation import and the Alembic lines of whichever test they were modelled on. See
[PC §6](PC_CONTRACT_AND_SLICE_PLAN.md#6-background-origin-of-this-work-package).

## Appendix A: Decision records

### A.1 Approved decisions (2026-10-20)

Decisions of the project owner, 2026-10-20.

- **#148:** the CLI isolation fixtures are non-autouse, defined in a helper module, registered in `tests/conftest.py`,
  and opted into with `pytestmark`. The two database fixtures become one, `isolated_cli_settings`. It also patches
  `cli_run_support`. Local copies of the same isolation use it where they do exactly the same thing. An import guard
  and a session-database guard are added. The leftover telemetry file is fixed if one line does it, otherwise filed.
- **#145:** `migrated_database_url` and `migrated_database` in a helper module, registered in `tests/conftest.py`; one
  template migrated per process, closed, and copied; a test that a copy is at head and ready; every test upgrade to
  head uses the helper; migration tests keep their own Alembic calls; a guard scan under `tests/`.
- **Commits:** the slice plan, then #148, then #145, then the completion commit.
