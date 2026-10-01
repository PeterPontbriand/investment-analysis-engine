# ESC-E.3 — Graham Growth evidence

Records the seven-dimension matrix for Graham Growth. The paths E.1 did not reach (`--save-run`, replay,
refresh, orchestrator) were verified once for all four analyses in
[E.2](ESC_E2_GRAHAM_NUMBER_EVIDENCE.md#2-cross-cutting-paths-all-four-analyses) and are cited here, not
repeated.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
Scope and proposal: [ESC-E plan](ESC_E_RENEWAL_PLAN.md#4-proposed-scope-for-e2-to-e5).

## 1. At a glance

- **No new ledger entry.** Every difference from the baseline is in the expected-difference register (X-01,
  X-02, X-03) or is ESC-20.
- **Graham Growth shares Graham Number's changed resolver, clock and presenter code**, so the evidence that
  covers that code in E.2 covers it here, and E.3 adds what is Growth's own: the growth and AAA-yield
  assumptions, the newly reachable `fiscal_year` EPS basis, and the zero, negative and non-finite assumption
  semantics.
- **Environment:** as E.2. Live runs on 2026-10-01 between 00:55Z and 01:35Z, against throwaway databases
  under `.tmp/esc-e/`, deleted afterward.

## 2. Graham Growth matrix

| Dimension | How it was verified | Narrowness and reason |
| :--- | :--- | :--- |
| Presentation | E.1's 18 Graham Growth pairs compared all four modes on KO, AAPL, MSFT, SPY and two historical and cache-bypass cases. The presenter differential from E.2 includes Growth's own cases (the baseline's `test_graham_nonpositive_growth_presentation.py` and the Growth cases in `test_graham_presenter.py` and `test_security_identity_presenters.py`): they pass against `main`'s presenters except for the `schema_version` pins (ESC-20). Growth's text and JSON failure reasons were already consistent with each other (ESC-D.3); the 43 pairs below keep that true on `main`. | As approved: comparison plus differential. |
| Data lifecycle | Growth uses the same resolver base as Number. The E.2 lifecycle test map applies, and the 48 ESC-21 cases run against `GrahamGrowthInputResolver` too. Growth-specific offline tests: `test_c2d_growth_value_success`, `test_c2d_growth_value_aaa_yield_override`, `test_c2d_growth_value_no_cache_historical_as_of_propagation`, `test_c2d_growth_value_missing_growth` and `test_c2d_growth_value_non_finite_growth`. Live: cold, hit and bypass (E.1: KO, AAPL, MSFT and `--no-cache`), and the expired-quote re-fetch (E.2 refresh). | Full, as approved. |
| Time | KO's 10-K was accepted 2026-02-20T14:46:32Z. Pairs one second before, exactly at and one second after: identical text on both revisions, and the current-price comparison is correctly unavailable for a historical request. For the new `fiscal_year` basis on `main` (no baseline to pair): one second before the filing the single fiscal year is FY2024 (EPS 2.46, growth value 52.89); at the filing it is FY2025 (EPS 3.04, 65.36). Both equal `EPS × 21.5` at `g = 6.5`. | Full, as approved. |
| Inputs and applicability | 32 pairs ([table](#inputs-pairs)) covering growth of zero, negative, huge negative (a negative valuation P/E), huge positive, NaN and infinite; AAA yield of zero, negative, NaN and high; zero, negative and NaN EPS; zero and NaN price; every `--eps-basis` value including the new `fiscal_year`; Massive; a bogus provider; invalid, lowercase and missing tickers; invalid and naive `--as-of`; a Canadian listing, an ETF and a cryptocurrency. Missing growth or yield is a usage error (exit 2) on both. | Full, as approved. |
| Financial claims | Recomputed from the unrounded retained inputs, independently of the calculator, with `growth value = EPS × (8.5 + 2g) × 4.4 / y` (`FINANCE_MATH.md`): KO default `2.6566666666666667 × 21.5 = 57.11833333333333` (matches the live JSON exactly); `g = 0` gives 22.58, `g = −3` gives 6.64, `g = 500` gives 2,679.25, `y = 20` gives 12.57, EPS 0 gives 0.00, EPS −1 gives −21.50, all matching the output; `g = −50` makes the valuation P/E `8.5 − 100 = −91.5`, which both revisions reject with exit 1; the `fiscal_year` values above match. Margin of safety `(57.11833333333333 − 86.08) / 57.11833333333333 × 100 = −50.70467742406116` matches the orchestrator and direct output. | Nine recomputations, more than the one the plan asked for, because the assumption semantics are Growth's own risk. |
| Composition | The cross-cutting table in E.2 covers Growth: `--save-run`, replay, refresh and orchestrator. | Cited, as approved. |
| Public contracts | JSON keys and exit codes equal the baseline except as the register and ESC-20 record. The guide's examples (`--expected-growth 5 --aaa-yield 4.5`, with `--eps 3.25` and with `--current-price 75`) behave identically on both revisions. The guide's EPS-basis table (SEC EDGAR accepts `three_year_average` and `fiscal_year`, defaults to `three_year_average`) matches `main` and the `--help` text. | Full, as approved. |

### Inputs pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e3in_gg_asof_bad` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of not-a-date` | 2 to 2 | Identical |
| `e3in_gg_asof_naive` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2025-12-31T12:00:00` | 2 to 2 | Identical |
| `e3in_gg_badticker` | `ian graham-growth ZZZZZZZ9 -g 6.5 -y 4.4` | 1 to 1 | Identical |
| `e3in_gg_basis_3y` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis three_year_average` | 0 to 0 | Identical apart from timestamps and ages |
| `e3in_gg_basis_bogus` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis bogus` | 2 to 2 | Expected: X-03 (the rejection message names the accepted values) |
| `e3in_gg_basis_fy` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis fiscal_year` | 2 to 0 | Expected: X-03 (the baseline rejects `--eps-basis fiscal_year`; the current accepts it) |
| `e3in_gg_basis_fy_json` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis fiscal_year --json` | 2 to 0 | Expected: X-03 (the baseline rejects `--eps-basis fiscal_year`; the current accepts it) |
| `e3in_gg_basis_ttm` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis ttm` | 2 to 2 | Expected: X-03 (the rejection message names the accepted values) |
| `e3in_gg_cad` | `ian graham-growth RY.TO -g 6.5 -y 4.4` | 1 to 1 | Identical |
| `e3in_gg_crypto` | `ian graham-growth BTC-USD -g 6.5 -y 4.4` | 1 to 1 | Identical |
| `e3in_gg_eps0` | `ian graham-growth KO -g 6.5 -y 4.4 --eps 0` | 0 to 0 | Identical apart from timestamps and ages |
| `e3in_gg_epsnan` | `ian graham-growth KO -g 6.5 -y 4.4 --eps nan` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e3in_gg_epsneg` | `ian graham-growth KO -g 6.5 -y 4.4 --eps -1` | 0 to 0 | Identical apart from timestamps and ages |
| `e3in_gg_etf_override` | `ian graham-growth SPY -g 6.5 -y 4.4 --eps 3` | 0 to 0 | Identical |
| `e3in_gg_g0` | `ian graham-growth KO -g 0 -y 4.4` | 0 to 0 | Identical |
| `e3in_gg_ghuge_neg` | `ian graham-growth KO -g -50 -y 4.4` | 1 to 1 | Identical |
| `e3in_gg_ghuge_pos` | `ian graham-growth KO -g 500 -y 4.4` | 0 to 0 | Identical apart from timestamps and ages |
| `e3in_gg_ginf` | `ian graham-growth KO -g inf -y 4.4` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e3in_gg_gnan` | `ian graham-growth KO -g nan -y 4.4` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e3in_gg_gneg` | `ian graham-growth KO -g -3 -y 4.4` | 0 to 0 | Identical apart from timestamps and ages |
| `e3in_gg_massive` | `ian graham-growth KO -g 6.5 -y 4.4 --data-provider massive` | 1 to 1 | Identical |
| `e3in_gg_nogrowth` | `ian graham-growth KO -y 4.4` | 2 to 2 | Identical |
| `e3in_gg_noticker` | `ian graham-growth -g 6.5 -y 4.4` | 2 to 2 | Identical |
| `e3in_gg_noyield` | `ian graham-growth KO -g 6.5` | 2 to 2 | Identical |
| `e3in_gg_price0` | `ian graham-growth KO -g 6.5 -y 4.4 --current-price 0` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e3in_gg_price75` | `ian graham-growth KO -g 6.5 -y 4.4 --current-price 75` | 0 to 0 | Identical |
| `e3in_gg_price75_json` | `ian graham-growth KO -g 6.5 -y 4.4 --current-price 75 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e3in_gg_provider_bogus` | `ian graham-growth KO -g 6.5 -y 4.4 --data-provider bogus` | 1 to 1 | Identical |
| `e3in_gg_y0` | `ian graham-growth KO -g 6.5 -y 0` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e3in_gg_yhigh` | `ian graham-growth KO -g 6.5 -y 20` | 0 to 0 | Identical apart from timestamps and ages |
| `e3in_gg_ynan` | `ian graham-growth KO -g 6.5 -y nan` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e3in_gg_yneg` | `ian graham-growth KO -g 6.5 -y -1` | 1 to 1 | Expected: X-02 (invalid-input wording) |

### Time pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e3time_gg_KO_after_concise` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2026-02-20T14:46:33+00:00` | 0 to 0 | Identical |
| `e3time_gg_KO_after_json` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2026-02-20T14:46:33+00:00 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e3time_gg_KO_before_concise` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2026-02-20T14:46:31+00:00` | 0 to 0 | Identical |
| `e3time_gg_KO_before_json` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2026-02-20T14:46:31+00:00 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e3time_gg_KO_exact_concise` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2026-02-20T14:46:32+00:00` | 0 to 0 | Identical |
| `e3time_gg_KO_exact_json` | `ian graham-growth KO -g 6.5 -y 4.4 --as-of 2026-02-20T14:46:32+00:00 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e3time_gg_KO_fy_before_json` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis fiscal_year --as-of 2026-02-20T14:46:31+00:00 --json` | 2 to 0 | Expected: X-03 (the baseline rejects `--eps-basis fiscal_year`; the current accepts it) |
| `e3time_gg_KO_fy_exact_json` | `ian graham-growth KO -g 6.5 -y 4.4 --eps-basis fiscal_year --as-of 2026-02-20T14:46:32+00:00 --json` | 2 to 0 | Expected: X-03 (the baseline rejects `--eps-basis fiscal_year`; the current accepts it) |

### Documented-example pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e3doc_gg_5_45` | `ian graham-growth KO --expected-growth 5 --aaa-yield 4.5` | 0 to 0 | Identical apart from timestamps and ages |
| `e3doc_gg_5_45_eps` | `ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --eps 3.25` | 0 to 0 | Identical apart from timestamps and ages |
| `e3doc_gg_5_45_price` | `ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --current-price 75` | 0 to 0 | Identical |

## 3. Gate

No code or test changed in E.3 apart from broadening the E.2 skew tests to run against both Graham
resolvers (48 cases). `scripts/run-quality-gates.sh` on Python 3.12.14 and pandas 3.0.5: Ruff, format check and `mypy --strict` clean
over 310 source files; **3,419 tests passed, 91% coverage**. Artifacts: `.tmp/quality-runs/20261001010658-1685-2964/`.

## 4. Limits

- Graham Growth produced values live for KO, AAPL, MSFT and SPY; the Massive path stops at its
  configuration error because no key is configured.
- `--eps-basis fiscal_year` has no baseline behavior to compare against, so it is verified by arithmetic
  and against the guide, not by a pair.
