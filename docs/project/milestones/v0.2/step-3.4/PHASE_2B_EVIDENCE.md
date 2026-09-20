# B1 Phase 2B evidence

Starting point: the approved Phase 2A checkpoint on
`feat/step-3.4-local-research-workspace`.

## Delivered

- `GrahamGrowthSelection` requires explicit finite growth and AAA yield values,
  preserves finite zero/negative execution semantics, and rejects book-value or
  calculation-policy fields. Conversion returns the existing
  `GrahamGrowthConfig`; no assumptions or calculation policy are inferred.
- Graham selections reuse only their equivalent scalar fields and provider
  validation in a private base. Number retains its own book-value requirement.
- `FCFGrowthSelection` retains a distinct frozen `FCFPolicySnapshot` using
  native policy enums and defaults. Extra policy fields are rejected. Conversion
  returns a fresh `FCFEarningsGrowthPolicy`; currency follows CLI normalization,
  and the provider is restricted to the currently composed SEC EDGAR capability.
- `AnalysisSelection` is a four-variant discriminated union using canonical
  method IDs. `AnalysisRequest` binds the selection to a normalized nonempty
  ticker without duplicating temporal/cache options at the request root.
- `default_selections()` creates fresh Momentum, Number and historical FCF
  selections in that order. Growth is excluded; settings changes affect only
  subsequently constructed defaults.

Implementation and exports are confined to `src/workspace/requests.py` and
`src/workspace/__init__.py`; tests extend `tests/workspace/test_requests.py`.

## Verification

Pre-edit baseline: **197 passed in 2.00s**, including all Phase 2A workspace
tests, Graham configuration tests, FCF model tests and Growth default-policy tests.
Baseline artifacts:
`.tmp/quality-runs/phase2b-baseline-9bef21ff936048f9845e7052cbf04681/`.

Final focused commands, from the repository root:

```text
uv run --no-sync ruff check --no-cache src/workspace tests/workspace
uv run --no-sync ruff format --check src/workspace tests/workspace
uv run --no-sync mypy --strict --cache-dir <run>/mypy src/workspace tests/workspace
uv run --no-sync pytest -o addopts= -p no:cacheprovider --basetemp <run>/pytest tests/workspace/test_requests.py tests/analysis/graham_value/test_analyzer_config.py tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_models.py tests/test_graham_growth_default_policy.py -q
```

Here `<run>` is the actual isolated directory:
`E:/Source/financial-data-agents/.tmp/quality-runs/phase2b-final-52aaedca481f45bc90bad7f7836bd37f`.
TEMP, TMP and UV_CACHE_DIR were also isolated beneath this directory.
Existing interpreter access required approved elevated execution; no dependency
synchronization was performed.

All focused checks passed: lint, formatting, strict typing (3 files),
and **275 tests in 1.96s**, including all **140 workspace tests**.
Tests cover required Growth assumptions and compatibility, nonfinite rejection,
every native FCF enum combination, nested policy validation, fresh defaults,
mutation isolation, ticker normalization, identifier/version rejection, and
four-variant JSON reconstruction with settings access forbidden.
The final implementation diff also passes whitespace checks.

## Stop state

Phase 2B is ready for review. The alias/config parser and remaining boundary
audit belong to Phase 2C. The full managed gate remains deferred to Phase 3,
as directed by the handoff; this is not a B1 acceptance claim.
No commits, pushes, PRs, provider calls, dependency changes or later-phase work.
Unrelated Step 3.5 and PIOTROSKI documentation remains untouched.
