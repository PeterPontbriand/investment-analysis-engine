# Slice B1 — Completion evidence

**Review disposition:** accepted on 2026-09-13 (America/Toronto). This record is the Slice B1 acceptance basis; B2 may proceed under its own handoff and review gate per contract §9.

## Revisions and scope

Verified branch: `feat/step-3.4-local-research-workspace`. Readiness closeout
is an ancestor of the tested HEAD. Companion evidence in this planning
directory: [Phase 2A](PHASE_2A_REPAIR_EVIDENCE.md), [Phase 2B](PHASE_2B_EVIDENCE.md),
[Phase 2C](PHASE_2C_EVIDENCE.md), and this final record; Phase 1's 149-test
baseline was reported by Cline, not rerun retrospectively in Phase 3.

Phase 3 required no source/test changes beyond `src/workspace/__init__.py`,
`src/workspace/requests.py` and `tests/workspace/test_requests.py`. Unrelated
uncommitted Step 3.5 planning and PIOTROSKI documents remained untouched. No
dependency files, existing analyzers/calculators, CLI, migrations,
repositories or settings were changed.

## Interfaces and design decisions

Four explicit frozen selection variants use canonical method discriminators and
fixed integer configuration version 1:

| Selection | Analysis / method |
| :--- | :--- |
| `MomentumSelection` | `momentum` / `sma_crossover` |
| `GrahamNumberSelection` | `graham` / `graham_number` |
| `GrahamGrowthSelection` | `graham` / `graham_growth_value` |
| `FCFGrowthSelection` | `fcf_earnings_growth` / `reported_fcf_eps_cagr` |

`AnalysisSelection` is a discriminated union, not a registry.
`AnalysisRequest` binds a normalized nonempty ticker to a selection; temporal
and cache options stay in the selection. Momentum accepts no requested as_of.

Momentum and Graham snapshots store immutable scalar configuration values rather
than retaining a mutable caller-owned analyzer config. Their conversion methods
return existing analyzer config types. The private Graham base shares only
equivalent provider/override validation; Number and Growth keep different fields.
FCF uses a separate frozen `FCFPolicySnapshot`, native enums and conversion to
a fresh `FCFEarningsGrowthPolicy` dataclass.

`default_selections()` materializes fresh Momentum, Number and historical FCF
defaults in that order. Growth always requires explicit growth and AAA yield
percentages. Finite zero/negative financial inputs retain execution semantics;
nonfinite values are rejected. Effective Growth calculation-policy capture
remains execution evidence, as specified by the handoff.

`parse_selection(alias, config_json)` accepts only the four exact aliases and
their method-specific JSON bodies. It rejects malformed/non-object documents,
duplicate keys at every depth, nonfinite constants/overflow, unknown fields and
identity/version overrides. It resolves omitted defaults once and performs no
file I/O. Explicit configuration and serialized snapshots replay without
settings rereads. Supported provider choices follow current CLI composition.

## Acceptance criteria and tests

All named tests below are in `tests/workspace/test_requests.py`.
The [Phase 2C checklist](PHASE_2C_EVIDENCE.md#b1-checklist-audit) provides the
expanded mapping.

| B1 requirement | Verification |
| :--- | :--- |
| Canonical identifiers, all aliases, fixed version | `test_parser_aliases_and_canonical_identifiers`; `test_union_rejects_bad_identifiers_and_versions`; `test_union_rejects_version_type_coercion` |
| Default order, no automatic Growth, independent snapshots | `test_default_selections_order_freshness_and_settings_snapshot`; `test_settings_mutation_and_converted_config_cannot_change_snapshot` |
| Normalized venue-suffixed and nonempty tickers | `test_all_request_variants_round_trip_without_settings`; `test_request_rejects_empty_ticker` |
| Explicit Growth assumptions and method independence | `test_growth_requires_each_explicit_assumption`; `test_growth_rejects_number_and_calculation_policy_fields`; `test_growth_conversion_preserves_assumptions` |
| Provider compatibility and Number book-value requirement | `test_graham_rejects_incompatible_provider_combinations`; `test_growth_rejects_incompatible_options`; `test_parser_materializes_omitted_defaults_and_preserves_explicit_fields` |
| Native FCF policy/defaults, currency, aware time and cache | `test_fcf_defaults_match_existing_policy`; `test_fcf_native_enum_strings_round_trip`; `test_fcf_normalizes_currency_provider_and_preserves_time`; `test_fcf_rejects_invalid_request_options` |
| Invalid JSON, duplicates, nested extras, nonfinite numbers | `test_parser_rejects_malformed_or_nonobject_json`; `test_parser_rejects_duplicate_keys_at_every_depth`; `test_parser_enforces_method_and_nested_field_allowlists`; `test_parser_rejects_nonfinite_json_anywhere` |
| Pure deterministic configuration replay/conversion | `test_explicit_config_round_trips_without_settings_or_external_activity` guards file, socket, SQLite, environment-read and settings entry points during the operation |
| Preservation of existing method behavior | Existing Momentum analyzer, Graham config/BVPS semantics, Growth defaults and FCF model regressions pass in focused checks and the full suite |

## Verification results

Focused results and exact commands are retained in the phase evidence:

- Phase 2A pre-repair baseline: 109 passed; repaired full gate: 2,400 passed.
- Phase 2B baseline: 197 passed; final focused suite: 275 passed.
- Phase 2C baseline: 289 passed; final focused suite: **423 passed**, including
  all **274 workspace tests**; focused lint, formatting and strict typing passed.

Phase 3 ran the authoritative wrapper from the repository root:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

The wrapper uses `uv run --no-sync`, unique repository-local temporary/cache
directories, strict mypy over `src tests`, and the full pytest suite with
coverage. Approved elevated execution was used for interpreter access, following
the earlier sandbox access failure; no dependencies were synchronized.

| Final full gate | Result |
| :--- | :--- |
| Ruff check | Passed |
| Ruff format check | 338 files already formatted |
| `mypy --strict src tests` | Passed, 251 files |
| Full pytest | **2,612 passed in 92.80s** |
| Overall combined coverage | **90%**, above the 85% requirement |
| Workspace combined coverage | **99%**; requests.py covers 214 of 215 statements |

Environment: Windows, Python 3.14.7, pytest 9.1.1. Other Python versions were
not separately exercised in this run.

Full output: `.tmp/b1-phase3-quality.txt`.
Isolated artifacts and HTML coverage:
`.tmp/quality-runs/20260913175805271-33784-0a978d0ccfe543da9072c4a1f55d4185/`.
The implementation diff passes whitespace checks. Only this evidence document
was added after the successful gate.

## Limitations and stop

B1 supplies request contracts only. Watchlist/run envelopes, persistence,
result codecs, execution adapters, refresh and CLI file I/O remain later slices.
No live provider or LLM validation is claimed or required by this deterministic
request boundary. The guarded replay test covers operations after module imports.
No public analyzer behavior was removed or financial calculations changed.

No unresolved B1 implementation or verification failures were found in Phase 3.
No commit, push or PR was performed. Stop for explicit B1 acceptance before B2.
