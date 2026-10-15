# LAY.7 — Strategy settings files

## At a glance

- **What:** one convention for a strategy's editable defaults: a TOML file per strategy, a typed settings model in
  the strategy's package declared by its descriptor, one generic loader, and composition roots that pass the typed
  settings in.
- **Why now:** the four existing strategies are the examples every Step 3.5 strategy copies. Momentum and Graham
  Growth read their files in two different ways, untyped, and Momentum reads its file from inside the strategy.
- **Not:** no formula, classification, command output, `--help` default, published schema, golden result or stored
  value changes. One deliberate exception: the Momentum tool schema in the local-model prompt ([§3.6](#36-who-reads-the-file-and-how-values-reach-the-strategy)).
- **Rules:** strategies never read settings files; evaluation never reads user-editable files; a settings model has
  no defaults; unknown keys are errors.
- Replaces LAY design decision 6
  ([LAY plan A.12](LAY_CONTRACT_AND_SLICE_PLAN.md#a12-lay7-strategy-settings-files-replace-design-decision-6-2026-10-14)).

## 1. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| LAY.7a | [This plan](#lay7a--plan) | Complete | 2026-10-14 |
| LAY.7b | [Strategy settings for Momentum and Graham Growth](#lay7b--momentum-and-graham-growth) | Complete | 2026-10-14 |

## 2. The slices

### LAY.7a — Plan

- **Problem:** no convention says where a strategy's editable defaults live or how they reach it.
- **Decision:** the convention in §3, applied as in §4.
- **Scope:** this plan; the LAY.7 row, section and A.12 in the parent plan; one SWC.7 scope bullet. No file under
  `src/`, `config/` or `tests/`.
- **Branch:** `docs/lay-7a-strategy-settings-plan`.
- **Detail:** this document.

### LAY.7b — Momentum and Graham Growth

- **Problem:** Momentum's analyzer, selection and tool read its settings file from inside the strategy, at import;
  Graham Growth's file is read by the command line on every call; neither is typed or validated.
- **Decision:** apply §3 to both strategies, as listed in §4.
- **Scope:** the `config` package (loader), `StrategyDescriptor` (`settings_type`), both strategies' packages
  (`settings.py`, config, selection, tool, CLI), `src/cli_composition.py`, `src/cli_support.py`,
  `src/cli_workspace.py`, Momentum and Graham Growth evaluation composition, the four settings files, their tests,
  the pinned prompt hash, ARCHITECTURE, AGENTS.md §9, `docs/user/INSTALLATION.md` and both strategy guides.
- **Branch:** `refactor/lay-7b-strategy-settings`, from `main` after LAY.7a.
- **Detail:** §3 and §4 of this document.

## 3. The convention

### 3.1 One file per strategy

- Path: `config/strategies/<alias>.toml`, where `<alias>` is the descriptor's `alias` (`momentum`,
  `graham-growth`).
- Flat keys, one per setting, each preceded by a one-line comment saying what it is.
- A strategy with nothing to configure has no file.
- Adding a strategy adds a file; it never edits a shared one.

### 3.2 What goes in a settings file

| In the strategy's settings file | Stays in code |
| :--- | :--- |
| Any value a user may reasonably tune without changing what the method is: window lengths, look-back periods, the history start date, Graham Growth's configured constants | Values that define the method (for example Graham's 22.5) and data-eligibility rules, under the existing rules for documented constants |

### 3.3 A typed settings model

- Each strategy with a file declares `<Strategy>Settings` in `src/strategies/<package>/settings.py`.
- A frozen pydantic model that forbids extra keys, with strict types.
- **No defaults:** the shipped file is the single source of every value.
- Each field's docstring documents its key; validators enforce the invariants (for example short window < long
  window, positive base P/E).

### 3.4 The descriptor declares it

`StrategyDescriptor` gains `settings_type: type[BaseModel] | None`; `None` means the strategy has no file.

### 3.5 One loader, in `config`

- `config` gains one generic function that reads `config/strategies/<alias>.toml` and validates it into a given
  model. It knows no strategy, so `config` stays a base-layer package.
- Loaded once per process and cached.
- A missing file, an unknown key, a missing key or an invalid value stops the program at startup (including
  `--help`) with exit code 2 and one message naming the file and the key and stating what is wrong, never repeating
  the value, as the engine-settings startup error does.

### 3.6 Who reads the file, and how values reach the strategy

Strategies never read settings. Composition roots load the typed settings and pass them in:

| Entry point | How the settings arrive |
| :--- | :--- |
| Direct command | `cli_composition` loads them; the command's option defaults, and so `--help`, show the configured values |
| Workspace selection (`watchlist add`, …) | the configured values are materialized into the selection when it is created; a later edit to the file never changes a saved entry, and replay never reads settings |
| Calculation constants | passed to the analyzer when it is built (as Graham Growth's policy is today) |
| Local-model tool | the handler receives the settings in its dependencies; a tool argument with a configured default is optional (`None` means "use the configured value", and its field description says so), and the handler fills it |

The tool rule changes the Momentum entry of the model prompt once: its window and RSI arguments become optional. The
pinned prompt hash is updated in LAY.7b. The other three tool schemas do not change.

### 3.7 Evaluation

Golden composition never reads a settings file. It passes fixed Golden settings, as Graham Growth's evaluation
already does, so editing a settings file cannot change Golden results or the model prompt.

### 3.8 Checks

A conformance test verifies, for every descriptor: a declared `settings_type` has a file that validates; every file
in `config/strategies/` belongs to a descriptor with a `settings_type`; every settings model is frozen, forbids extra
keys and has no field with a default.

## 4. Momentum and Graham Growth under the convention

| | `config/strategies/momentum.toml` | `config/strategies/graham-growth.toml` |
| :--- | :--- | :--- |
| Keys | `short_window = 50`, `long_window = 200`, `rsi_period = 14`, `history_start_date = "2021-01-01"` | `base_pe = 8.5`, `growth_multiplier = 2.0`, `baseline_aaa_yield = 4.4` |
| Model | `MomentumSettings` | `GrahamGrowthSettings`, which builds the existing `GrahamGrowthCalculationPolicy` |
| Replaces | `config/momentum_config/momentum_analysis_settings.toml` and `data_start_date` in `config/general_analysis_settings.toml` | `config/graham_value_config/graham_value_analysis_settings.toml` |

Removed in LAY.7b:
- `ProjectSettings.get_momentum_analysis` and `get_graham_value_analysis`;
- the `ConfigKeys` entries for the removed keys;
- `MomentumConfig`'s default factories and its fixed `rsi_period` default (its fields become required);
- `MomentumSelection.from_settings`;
- `cli_composition.growth_assumptions`;
- `cli_support._default_history_start_date`;
- the dead Momentum keys (`medium_window`, `crossSignals`, `thresholds`, `performance_metrics`);
- the two emptied `config/` subfolders.

`general_analysis_settings.toml` keeps `default_ticker`, which is not a strategy setting. Graham Number and Free Cash
Flow & Earnings Growth have nothing to configure today and get no file.

## 5. Scope limits

- No formula, classification, threshold or data-rule change; every value keeps its current number.
- No environment-variable override for strategy settings.
- No settings file for Graham Number or Free Cash Flow & Earnings Growth.
- Only the Momentum tool schema in the model prompt changes; no other observable output changes.

## 6. Acceptance criteria

- No file under `src/strategies/` imports `src.config`; the `strategies` row of ARCHITECTURE §13 drops `config`.
- Command output, `--help` text, published schemas (`scripts/generate_schemas.py --check`), golden results and
  stored values are unchanged.
- The pinned prompt hash changes only through the Momentum tool schema, and the test's comment records why.
- The §3.8 conformance test passes, and fails when a file is missing, has an unknown key or a model gains a default.
- Each settings error (missing file, unknown key, missing key, invalid value) has a test of its exit code and
  message.
- ARCHITECTURE describes the convention in durable terms; AGENTS.md §9 states that a strategy's editable defaults
  live in its settings file and that strategies never read settings; `docs/user/INSTALLATION.md` §2 gains a
  "Strategy settings files" subsection; the Momentum and Graham Growth guides name their file and keys.

## 7. Background: how settings are read today

| | Momentum | Graham Growth |
| :--- | :--- | :--- |
| File | `config/momentum_config/momentum_analysis_settings.toml` | `config/graham_value_config/graham_value_analysis_settings.toml` |
| Accessor | `settings.get_momentum_analysis()`, an untyped dict | `settings.get_graham_value_analysis()`, an untyped dict |
| Who reads it | the strategy itself: `MomentumConfig` default factories, `MomentumSelection.from_settings` (tests only), and `MomentumConfig()` at import in the tool, the Momentum CLI and `cli_workspace.py` | `cli_composition.growth_assumptions()`, on every call |
| Validation | `int(...)` on two keys; the other keys are read by nothing | `GrahamGrowthCalculationPolicy.__post_init__` |
| Evaluation | depends on the file (windows) and on `general_analysis_settings.toml` (start date) | fixed Golden constants |
| Values outside any file | `rsi_period = 14` in code | none |

Because the tool's defaults are read from the file at import, editing Momentum's file today breaks the pinned prompt
hash.

## Appendix A — Decision records

### A.1 Decisions of 2026-10-14

Approved by the project owner.

1. Design decision 6 (a `MomentumDefaults` built from `settings.get_momentum_analysis()`) is replaced by the
   convention in §3. Two alternatives were rejected: decision 6 as written, which treats Momentum differently from
   Graham Growth and still changes the model prompt; and removing Momentum's file in favour of code constants. Both
   TOML configurations are kept: any reason to remove one would be a reason to remove strategy configuration
   altogether, and editable defaults must stay editable in a file.
2. The local-model tool: arguments with configured defaults become optional and the handler fills them; the Momentum
   tool schema in the prompt changes once and the pinned hash is updated. Not chosen: a per-process subclass of the
   arguments model carrying the configured defaults, which would keep the prompt identical but create classes at
   run time.
3. Momentum's `rsi_period` and history start date move into `momentum.toml`.
4. Process: this plan first (LAY.7a), then one implementation slice covering both Momentum and Graham Growth
   (LAY.7b), so the mechanism is proven generic by two users.

### A.2 LAY.7b implementation decisions (2026-10-14)

Approved by the project owner.

1. Loader: `load_strategy_settings(alias, model, directory)` in `src/config/strategy_settings.py`, cached per process on `(alias, model, directory)`, clearable for tests, raising `StrategySettingsError` (a `ValueError` in `src/core/settings_error.py`); production passes `config/strategies`.
2. Messages: missing file, unreadable TOML and validation failure each give one message naming `config/strategies/<alias>.toml`; a validation message names the key and the rule, never the value, and a whole-model rule names no key.
3. Startup: `load_all_strategy_settings()` in `src/cli_composition.py` loads every declared file once, before any command is defined; `src/main.py` prints the message to stderr and exits with code 2, with no traceback and no log entry.
4. Accessors: `momentum_settings()` and `graham_growth_settings()` in `src/cli_composition.py`; the Momentum option defaults come from `momentum_settings()`, and `--help` is unchanged.
5. Descriptor: `StrategyDescriptor.settings_type` (`MomentumSettings`, `GrahamGrowthSettings`, `None` for the other two), added to the conformance script's field table.
6. `MomentumSettings`: frozen, no extra keys, no defaults, window order checked; `MomentumConfig` and `MomentumSelection.rsi_period` lose their defaults; `MomentumSelection.from_settings` and `cli_support._default_history_start_date` are deleted, and composition passes `history_start_date` as the analyzer's start date.
7. Momentum tool: `short_window`, `long_window` and `rsi_period` become optional ("Omit to use the configured value."), the handler fills them from `MomentumToolDependencies.settings`, and the pinned prompt hash is updated.
8. `GrahamGrowthSettings`: frozen, no extra keys, no defaults, one validator per constant, `to_policy()` returns the existing policy; `growth_assumptions()` is deleted and its three callers use `graham_growth_settings().to_policy()`.
9. Golden: `GOLDEN_MOMENTUM_SETTINGS` in `src/evaluation/fixtures/market_data.py` is passed by Momentum's evaluation composition; nothing under evaluation calls the loader.
10. Files: `config/strategies/momentum.toml` and `graham-growth.toml` are added; the two old strategy files and folders, `data_start_date`, `ProjectSettings.get_momentum_analysis` and `get_graham_value_analysis`, and the unused `ConfigKeys` entries are deleted.
11. Tests: the settings patches become explicit settings objects; new tests cover the loader, the cache, the startup exit, the §3.8 conformance check, the tool handler and `to_policy()`.
12. Documentation: ARCHITECTURE §6 and §13, AGENTS.md §9, INSTALLATION §2 and the two strategy guides.

Second exception to "no published schema changes": the published watchlist schemas (`schemas/watchlist.schema.json`, and `schemas/watchlist-delete.schema.json`, which embeds the same Momentum selection) make `rsi_period` required and drop its default of 14, a consequence of decision 6. The first exception is the Momentum tool schema (decision 7).
