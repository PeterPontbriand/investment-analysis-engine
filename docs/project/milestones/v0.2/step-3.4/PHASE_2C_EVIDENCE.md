# B1 Phase 2C evidence

Starting point: the approved Phase 2B checkpoint on
`feat/step-3.4-local-research-workspace`.

## Delivered

`parse_selection(alias, config_json)` accepts the four exact CLI aliases,
unwraps Momentum/Graham configuration objects, and validates FCF's distinct
policy/options body. It returns existing immutable selection variants.
Configuration identifiers and versions cannot be supplied even when their
values match the chosen method. Missing defaults are resolved once; explicit
null required fields/configuration objects are rejected.

JSON decoding rejects duplicate keys at every depth (including escaped-equivalent
keys), malformed/non-object documents, nonfinite constants and exponent overflow.
Unknown root and nested fields remain errors. Parsing performs no file I/O,
provider construction, financial calculation or result-evidence decoding.

The boundary audit also tightened version validation: boolean, float and string
lookalikes are rejected before the fixed integer version literal is checked.
Implementation/export changes remain in `src/workspace/requests.py` and
`src/workspace/__init__.py`; tests remain in `tests/workspace/test_requests.py`.

## B1 checklist audit

| Requirement | Focused proof in test_requests.py |
| :--- | :--- |
| Four exact aliases and canonical analysis/method/version identities | `test_parser_aliases_and_canonical_identifiers`, `test_parser_rejects_nonexact_aliases` |
| Default order, Growth exclusion, resolved defaults, independent snapshots | `test_default_selections_order_freshness_and_settings_snapshot`, `test_parser_materializes_omitted_defaults_and_preserves_explicit_fields` |
| Venue-suffixed normalization and nonempty ticker | `test_all_request_variants_round_trip_without_settings`, `test_request_rejects_empty_ticker` |
| Growth assumptions, financial semantics and provider compatibility | `test_growth_requires_each_explicit_assumption`, `test_growth_conversion_preserves_assumptions`, `test_growth_rejects_incompatible_options`, existing Number compatibility tests |
| FCF native enums, currency, aware time, cache and policy isolation | `test_fcf_native_enum_strings_round_trip`, `test_fcf_normalizes_currency_provider_and_preserves_time`, `test_fcf_rejects_invalid_request_options`, `test_fcf_policy_copies_input_and_converts_independently` |
| Malformed JSON, duplicate keys and nonfinite numbers | `test_parser_rejects_malformed_or_nonobject_json`, `test_parser_rejects_duplicate_keys_at_every_depth`, `test_parser_rejects_nonfinite_json_anywhere` |
| Unknown/foreign/nested fields and explicit null handling | `test_parser_rejects_top_level_foreign_fields`, `test_parser_requires_config_object_when_present`, `test_parser_enforces_method_and_nested_field_allowlists` |
| Discriminator/version rejection | `test_union_rejects_bad_identifiers_and_versions`, `test_union_rejects_version_type_coercion`, `test_parser_rejects_even_matching_identity_fields_in_config` |
| Deterministic config round trips without external/mutable-state access | `test_explicit_config_round_trips_without_settings_or_external_activity` guards settings, file, socket, SQLite and environment-read entry points during parsing/conversion |

## Verification

Pre-edit baseline: **289 passed in 2.20s**.
Artifacts: `.tmp/quality-runs/phase2c-baseline-905d85108ef2489fab8e87f65f35b94f/`.

Final focused checks all passed:

- `uv run --no-sync ruff check --no-cache src/workspace tests/workspace`
- `uv run --no-sync ruff format --check src/workspace tests/workspace`
- `uv run --no-sync mypy --strict --cache-dir <run>/mypy src/workspace tests/workspace`
  — 3 files.
- `uv run --no-sync pytest -o addopts= -p no:cacheprovider --basetemp <run>/pytest --cov=src.workspace --cov-report=term-missing tests/workspace/test_requests.py tests/analysis/momentum/test_momentum_analyzer.py tests/analysis/graham_value/test_analyzer_config.py tests/analysis/graham_value/test_bvps_basis_semantics.py tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_models.py tests/test_graham_growth_default_policy.py -q`
  — **423 passed in 2.68s**, including **274 workspace tests**.

Here `<run>` is
`E:/Source/financial-data-agents/.tmp/quality-runs/phase2c-final-a2ba47f52a2949da8f58d2c9a0ecfe62`.
TEMP, TMP, UV cache and coverage data were isolated beneath this directory.
Verification used approved elevated access to the existing interpreter without
dependency synchronization. Workspace combined coverage is **99%** (216 of 217
statements covered); this focused run does not establish overall repository coverage.
The final implementation diff passes whitespace checks.

Phase 2C is ready for review. Phase 3's full managed gate and final B1 acceptance
evidence remain pending. No commit, push, PR or later-phase work was performed.
Unrelated Step 3.5/PIOTROSKI edits remain untouched.
