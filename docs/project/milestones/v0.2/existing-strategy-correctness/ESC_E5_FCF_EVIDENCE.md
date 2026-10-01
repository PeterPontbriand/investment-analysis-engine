# ESC-E.5 — FCF/Earnings Growth evidence

Records the seven-dimension matrix for FCF/Earnings Growth. The paths E.1 did not reach (`--save-run`, replay,
refresh, orchestrator) were verified once for all four analyses in
[E.2](ESC_E2_GRAHAM_NUMBER_EVIDENCE.md#2-cross-cutting-paths-all-four-analyses) and are cited here, not
repeated.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
Scope and proposal: [ESC-E plan](ESC_E_RENEWAL_PLAN.md#4-proposed-scope-for-e2-to-e5).

## 1. At a glance

- **No new ledger entry.** All 59 pairs matched the baseline: 28 identical and 31 identical apart from timestamps, ages and identifiers, with no difference in any value, label or exit code, so nothing needed an entry in the expected-difference register.
- **What changed for FCF since the baseline:** the analyzer is now a `BaseAnalyzer` and takes a configuration and
  an `AnalysisContext`; the resolver's clock is the run's `executed_at` instead of the historical boundary; the
  provider call carries `effective_as_of`; and every resolution event is stamped with the run's clock instead of
  a wall-clock read. The calculation module and the presenter are byte-identical to the baseline.
- **One observation, not a finding:** FCF compares a fact's `available_at` with the run's boundary exactly, on a
  live run as well as an `--as-of` run, so it tolerates none of the ten-minute clock skew that the Graham
  resolvers accept (ESC-21). Annual facts carry the filing's acceptance time, which is months old, so no real
  run is affected, and the stricter rule is the safe direction. Pinned by offline tests.
- **Environment:** as E.4: Python 3.14.7 for the pairs (both revisions on the baseline's environment), 3.12.14 for
  the offline tests and gate. Live runs on 2026-10-01 from 11:03Z to 11:16Z, against throwaway databases under
  `.tmp/esc-e/`, deleted afterward.

## 2. FCF/Earnings Growth matrix

| Dimension | How it was verified | Narrowness and reason |
| :--- | :--- | :--- |
| Presentation | E.1's 19 FCF pairs, plus the 59 pairs below, compare concise, details, diagnostics and JSON. The presenter (`src/reporting/fcf_earnings_growth.py`), its provenance helper and the calculation module are byte-identical to the baseline (`git diff 7e2f8d2 HEAD` lists none of them). The only presentation file that changed on the path is the shared failure-document builder (`presentation.py`, 6 lines: the failure schema stays 5 for FCF). | Comparison only, as approved: the presenter is unchanged. |
| Data lifecycle | Live: cold fetch, cache hit and `--no-cache` bypass for the live key, and the same three for an `--as-of` key ([pairs](#lifecycle-pairs)); the `--diagnostics` pairs show each field's source, "Complete annual field series resolved from cache" on a hit and from the provider on a miss. Offline, each state names a passing test: complete cache avoids the provider `test_complete_cache_avoids_provider_and_partial_cache_refreshes_field`; partial `test_partial_cached_series_causes_complete_field_refresh`; stale `test_stale_cache_refreshes_all_fields`; incompatible, with and without provider failure `test_incompatible_cached_series_refreshes_complete_field_without_stale_fallback`; live key shared across runs `test_live_runs_share_a_cache_key_regardless_of_executed_at`; live and `--as-of` keys distinct `test_as_of_boundary_does_not_reuse_a_live_runs_cache_entry`. New in E.5, `tests/analysis/fcf_earnings_growth/test_fcf_availability_and_cache_eligibility.py` (26 cases, each run against the in-memory and the SQLite series cache) covers the path through `financial_cache_eligible`: an `--as-of` series is reused only while every entry was available by the boundary (exactly at it reused, one second after refreshed), a live series is reused only while every entry was available by `executed_at` (the shared check ignores `available_at` on a live key, the resolver's own per-fact check does not), a series cached after the run's clock is still eligible, and a live and an `--as-of` run never share a series. | Full, as approved. |
| Time | KO's 10-K was accepted 2026-02-20T14:46:32Z. Pairs one second before, exactly at and one second after, and the day before ([pairs](#time-pairs)). Before the filing the latest fiscal year is FY2024 (FCF CAGR -10.85%, EPS CAGR 3.51%); at the filing and one second after it is FY2025 (-9.38% and 11.17%); the day before matches "before". Text and JSON are identical on both revisions, so the boundary is inclusive and look-ahead is excluded on both. Offline: a restated EPS available exactly at the boundary is admitted and one second after, ten minutes after and a day after is excluded, for a live run (boundary `executed_at`) and an `--as-of` run alike (20 cases). | Full, as approved. |
| Inputs and applicability | 25 pairs ([table](#inputs-pairs)): every `--growth-years` value including zero and six, invalid `--classification-basis` and `--forward-policy`, `--currency` in a different currency, lowercase and malformed, an invalid, lowercase and missing ticker, `--data-provider massive` and a bogus provider, naive, malformed, future and pre-history `--as-of`, an ETF, a cryptocurrency, a Canadian listing and a foreign filer. | Narrow to the changed paths, as approved: the options, the ticker default and the boundary. |
| Financial claims | Two recomputations from the retained annual inputs, independent of the calculator (`FINANCE_MATH.md`): free cash flow `operating cash flow - capital expenditures` per year, then `CAGR = ((last / first)^(1 / years) - 1) x 100`. Failing outcome, KO (FY2020 to FY2025): free cash flow 8,667 and 5,296 million, CAGR -9.381715561220638% against the reported -9.381715561220638 (difference 0), EPS CAGR 11.17422496891589 (difference 0), so total-FCF growth is not positive and the screen is FAIL with `fcf_not_growing`, as reported. Passing outcome, MSFT (FY2021 to FY2026): FCF CAGR 3.604273274160441 and EPS CAGR 17.396112163192925, both equal to the reported values, both positive, so PASS, as reported. All six annual free cash flow values per company equal the reported ones exactly. The same recomputation on the baseline revision's output gives the same numbers. | Two recomputations, as approved: one failing and one passing outcome. |
| Composition | The cross-cutting table in E.2 covers FCF (KO): `--save-run`, replay, refresh and orchestrator, with the same values as the direct command (the orchestrator returned screen `fail` with execution status `ok`). | Cited, as approved. |
| Public contracts | JSON `schema_version` 5 and every key identical to the baseline. The documented examples in `FCF_EARNINGS_GROWTH.md` and `USAGE.md` (`--growth-years 5`, both classification bases, the three forward policies, `--as-of 2025-12-31`, the smoke-test command) behave identically on both revisions ([pairs](#documented-example-pairs)). The guide describes the effective analysis time as controlling input eligibility and says a later resolver clock cannot admit later filings into an earlier boundary; the offline boundary tests confirm both. | Full, as approved. |

### Documented-example pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e5doc_AAPL_concise` | `ian fcf-growth AAPL` | 0 to 0 | Identical |
| `e5doc_MSFT_asof_concise` | `ian fcf-growth MSFT --as-of 2025-12-31` | 0 to 0 | Identical |
| `e5doc_MSFT_asof_details` | `ian fcf-growth MSFT --as-of 2025-12-31 --details` | 0 to 0 | Identical |
| `e5doc_MSFT_asof_diag` | `ian fcf-growth MSFT --as-of 2025-12-31 --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_asof_json` | `ian fcf-growth MSFT --as-of 2025-12-31 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_fwd_confirm_concise` | `ian fcf-growth MSFT --forward-policy confirmation` | 0 to 0 | Identical |
| `e5doc_MSFT_fwd_confirm_json` | `ian fcf-growth MSFT --forward-policy confirmation --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_fwd_display_json` | `ian fcf-growth MSFT --forward-policy display-only --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_fwd_hard_concise` | `ian fcf-growth MSFT --forward-policy hard-gate` | 0 to 0 | Identical |
| `e5doc_MSFT_fwd_hard_json` | `ian fcf-growth MSFT --forward-policy hard-gate --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_g5_concise` | `ian fcf-growth MSFT --growth-years 5` | 0 to 0 | Identical |
| `e5doc_MSFT_g5_json` | `ian fcf-growth MSFT --growth-years 5 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_pershare_concise` | `ian fcf-growth MSFT --classification-basis fcf-per-share` | 0 to 0 | Identical |
| `e5doc_MSFT_pershare_details` | `ian fcf-growth MSFT --classification-basis fcf-per-share --details` | 0 to 0 | Identical |
| `e5doc_MSFT_pershare_json` | `ian fcf-growth MSFT --classification-basis fcf-per-share --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5doc_MSFT_smoke_details` | `ian fcf-growth MSFT --growth-years 3 --classification-basis fcf-per-share --details` | 0 to 0 | Identical |
| `e5doc_MSFT_total_details` | `ian fcf-growth MSFT --classification-basis total-fcf --details` | 0 to 0 | Identical |
| `e5doc_MSFT_total_json` | `ian fcf-growth MSFT --classification-basis total-fcf --json` | 0 to 0 | Identical apart from timestamps and ages |

### Inputs pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e5in_BTC_json` | `ian fcf-growth BTC-USD --json` | 1 to 1 | Identical apart from timestamps and ages |
| `e5in_MSFT_asof_1990` | `ian fcf-growth MSFT --as-of 1990-01-01 --json` | 1 to 1 | Identical apart from timestamps and ages |
| `e5in_MSFT_asof_1990_concise` | `ian fcf-growth MSFT --as-of 1990-01-01` | 1 to 1 | Identical |
| `e5in_MSFT_asof_bad` | `ian fcf-growth MSFT --as-of notadate` | 2 to 2 | Identical |
| `e5in_MSFT_asof_future` | `ian fcf-growth MSFT --as-of 2099-01-01 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5in_MSFT_asof_naive` | `ian fcf-growth MSFT --as-of 2025-12-31T00:00:00` | 2 to 2 | Identical |
| `e5in_MSFT_basis_bad` | `ian fcf-growth MSFT --classification-basis bogus` | 2 to 2 | Identical |
| `e5in_MSFT_cur_bad` | `ian fcf-growth MSFT --currency US` | 2 to 2 | Identical |
| `e5in_MSFT_cur_eur_concise` | `ian fcf-growth MSFT --currency EUR` | 1 to 1 | Identical |
| `e5in_MSFT_cur_eur_json` | `ian fcf-growth MSFT --currency EUR --json` | 1 to 1 | Identical apart from timestamps and ages |
| `e5in_MSFT_cur_lower` | `ian fcf-growth MSFT --currency usd --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5in_MSFT_fwd_bad` | `ian fcf-growth MSFT --forward-policy bogus` | 2 to 2 | Identical |
| `e5in_MSFT_g0` | `ian fcf-growth MSFT --growth-years 0` | 2 to 2 | Identical |
| `e5in_MSFT_g3_json` | `ian fcf-growth MSFT --growth-years 3 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5in_MSFT_g4_json` | `ian fcf-growth MSFT --growth-years 4 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5in_MSFT_g6` | `ian fcf-growth MSFT --growth-years 6` | 2 to 2 | Identical |
| `e5in_MSFT_provider_bogus` | `ian fcf-growth MSFT --data-provider bogus` | 1 to 1 | Identical |
| `e5in_MSFT_provider_massive` | `ian fcf-growth MSFT --data-provider massive` | 1 to 1 | Identical |
| `e5in_RYTO_concise` | `ian fcf-growth RY.TO` | 1 to 1 | Identical |
| `e5in_RYTO_json` | `ian fcf-growth RY.TO --json` | 1 to 1 | Identical apart from timestamps and ages |
| `e5in_SPY_details` | `ian fcf-growth SPY --details` | 0 to 0 | Identical |
| `e5in_TSM_json` | `ian fcf-growth TSM --json` | 1 to 1 | Identical apart from timestamps and ages |
| `e5in_ticker_invalid` | `ian fcf-growth 1NVALID!` | 1 to 1 | Identical |
| `e5in_ticker_lower` | `ian fcf-growth msft --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5in_ticker_missing` | `ian fcf-growth` | 2 to 2 | Identical |

### Time pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e5time_KO_after_concise` | `ian fcf-growth KO --as-of 2026-02-20T14:46:33+00:00` | 0 to 0 | Identical |
| `e5time_KO_after_json` | `ian fcf-growth KO --as-of 2026-02-20T14:46:33+00:00 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5time_KO_before_concise` | `ian fcf-growth KO --as-of 2026-02-20T14:46:31+00:00` | 0 to 0 | Identical |
| `e5time_KO_before_json` | `ian fcf-growth KO --as-of 2026-02-20T14:46:31+00:00 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5time_KO_daybefore_diag` | `ian fcf-growth KO --as-of 2026-02-19 --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e5time_KO_daybefore_json` | `ian fcf-growth KO --as-of 2026-02-19 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5time_KO_exact_concise` | `ian fcf-growth KO --as-of 2026-02-20T14:46:32+00:00` | 0 to 0 | Identical |
| `e5time_KO_exact_json` | `ian fcf-growth KO --as-of 2026-02-20T14:46:32+00:00 --json` | 0 to 0 | Identical apart from timestamps and ages |

### Lifecycle pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e5life_KO_asof_cold_json` | `ian fcf-growth KO --as-of 2025-06-30 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_asof_hit_diag` | `ian fcf-growth KO --as-of 2025-06-30 --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_asof_hit_json` | `ian fcf-growth KO --as-of 2025-06-30 --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_bypass_diag` | `ian fcf-growth KO --no-cache --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_bypass_json` | `ian fcf-growth KO --no-cache --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_cold_json` | `ian fcf-growth KO --json` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_hit_diag` | `ian fcf-growth KO --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e5life_KO_hit_json` | `ian fcf-growth KO --json` | 0 to 0 | Identical apart from timestamps and ages |

## 3. Gate

`scripts/run-quality-gates.sh` on Python 3.12.14 and pandas 3.0.5 with the 26 new E.5 tests: Ruff, format check, `mypy --strict` (313 source files) and the doc-link check clean; **3,477 tests passed, 91% coverage**. Artifacts: `.tmp/quality-runs/20261001110502-2029-16196/`. No source file changed in E.5.

## 4. Limits

- FCF produced values live for KO, AAPL and MSFT; the foreign-filer and Canadian pairs are comparisons of the
  refusal or unavailable outcome, not arithmetic checks.
- The forward-consensus policies depend on an approved consensus provider that is not configured; they are
  compared as the unavailable outcome both revisions return.
- Live arithmetic is limited to the retained inputs: the SEC figures are filing facts and do not vary between
  fetches.
