# Slice D4 — Completion evidence

**Review disposition:** D4 reviewed and accepted by the project owner on 2026-09-18 (America/Toronto).
**Date:** 2026-09-18 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

D3 was accepted before this slice began. The project owner authorized D4
implementation directly, to be done in-session rather than handed to Cline.

## Delivered scope

- `src/workspace/fcf_growth_execution.py`: `execute_fcf_growth` (composes
  the profile and calls the existing `FCFEarningsGrowthAnalyzer` exactly as
  the `fcf-growth` command did) and `classify_fcf_growth_outcome` (the
  frozen native-status → `RunOutcome` mapping, based on the single
  `execution_status` field FCF results carry — simpler than Graham's
  two-tier assembly/result status, since FCF has no separate assembly
  stage). Preserves two exact existing quirks rather than "fixing" them:
  the CLI composes the FCF profile using the *same* production provider
  object for both the primary and Yahoo identity candidates (there is no
  separate Yahoo client in this command), and the CLI never reads back
  `result.instrument_profile` for rendering — it reuses the profile it
  composed before calling the analyzer. Both are preserved verbatim.
- `src/cli.py`: the `fcf-growth` command's inline profile composition and
  analyzer invocation is replaced with a call to `execute_fcf_growth`;
  presentation and exit-code selection are unchanged. `FCFEarningsGrowthAnalyzer`
  is no longer imported directly, and `compose_graham_profile` — now unused
  in `cli.py` since Number, Growth, and FCF have all moved to their own
  adapters — is no longer imported there either.
- `tests/test_cli_fcf_earnings_growth.py`, `tests/test_cli_financial_cache.py`:
  patch targets for the profile-composition helper updated to follow it to
  the new FCF adapter module (the multi-method-parametrized tests in the
  latter file already had per-adapter patches from D2/D3; this adds the
  third).
- `tests/workspace/test_fcf_growth_execution.py` (9 tests): focused,
  fake-dependency-only tests, including one that exercises the analyzer's
  real known-ETF short-circuit (not applicable status) end-to-end rather
  than mocking it away, and one confirming partial/optional metrics
  (forward evidence) survive capture unmodified.
- This completion evidence.

## Contract proof (§4, §6, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| Currency/provider/policy/as-of unchanged | `execute_fcf_growth` forwards `currency`, `provider_id`, `policy`, `as_of`, `use_cache`, and `effective_as_of` to the existing analyzer exactly as the CLI did; a dedicated test asserts every forwarded argument by identity/equality. |
| ETF semantics unchanged | A dedicated test supplies a real known-ETF profile (`fixture_known_etf_profile`) and runs the *real* analyzer (not mocked), confirming the existing `is_known_etf` short-circuit still yields `execution_status=not_applicable`, which `classify_fcf_growth_outcome` maps to `RunOutcome.NOT_APPLICABLE`. |
| Partial metric semantics unchanged | A dedicated test confirms `forward_evidence` (always `UNAVAILABLE` in this codebase's current provider composition) and `annual_observations` survive capture unmodified — nothing is stripped, filled in, or recomputed. |
| Exact capture/status mapping | `classify_fcf_growth_outcome` is tested against all five native `execution_status` values: OK → completed, not_applicable → not_applicable, input_unavailable → unavailable, invalid_input/provider_error → failed — the same frozen mapping shape as D2/D3, applied to FCF's single-status model. |
| Fake dependencies only | Every adapter test uses `FixtureAnnualFinancialFactsProvider`/`annual_series`, the existing `fixture_instrument_profile`/`fixture_known_etf_profile` helpers, and mocked/patched analyzer calls; a dedicated test patches `socket.socket.connect`/`socket.create_connection` to confirm no real network path is reachable. |
| Bounded CLI extraction | Only the profile-composition-then-analyzer-invocation seam moved out of the `fcf-growth` command body; option parsing, policy/currency validation, presentation, and exit-code selection remain in `src.cli` untouched. |

## Full managed gate

Ruff, Ruff format (379 files) and strict mypy (280 source/test files) passed
clean. The full pytest run: **2,927 passed** (9 new for this slice), combined
coverage **90%**; `fcf_growth_execution.py` reaches 100% line/branch coverage
on its own focused tests.

## Boundaries and review gate

No execution service, run persistence, `--save-run` CLI flag,
replay/reporting, or refresh code was introduced — those remain D5,
E-series, F-series and G-series. All four method adapters (Momentum,
Graham Number, Graham Growth, FCF) now exist; D5 (save service) is the
next slice. No financial calculation changed; FCF's math and CLI output are
identical to before this slice. Nothing was committed, pushed, or opened as
a PR.
