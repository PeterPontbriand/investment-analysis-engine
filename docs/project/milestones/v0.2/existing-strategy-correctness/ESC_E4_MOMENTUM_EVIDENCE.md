# ESC-E.4 — Momentum evidence

Records the seven-dimension matrix for Momentum. The paths E.1 did not reach (`--save-run`, replay, refresh,
orchestrator) were verified once for all four analyses in
[E.2](ESC_E2_GRAHAM_NUMBER_EVIDENCE.md#2-cross-cutting-paths-all-four-analyses) and are cited here.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
Scope and proposal: [ESC-E plan](ESC_E_RENEWAL_PLAN.md#4-proposed-scope-for-e2-to-e5).

## 1. At a glance

- **Three new ledger entries, all low severity:** [ESC-22](ESC_A_DEFECT_LEDGER.md#esc-22--a-momentum---as-of-run-fails-when-a-bar-after-the-boundary-is-invalid)
  (an `--as-of` run fails if a later bar is invalid), [ESC-23](ESC_A_DEFECT_LEDGER.md#esc-23--a-live-momentum-run-does-not-check-bar-dates-against-the-execution-time)
  (a live run does not check bar dates against the execution time) and
  [ESC-24](ESC_A_DEFECT_LEDGER.md#esc-24--momentum---as-of-before-the-first-observation-reports-a-generic-error-not-the-cause)
  (a boundary before the first observation reports a generic error). ESC-24's proposed repair changes a public
  JSON field, so E.4 stopped there for the project owner's decision.
- **ESC-21, Momentum path:** Momentum does not use the shared freshness check, so the skew tolerance does not
  apply. Its boundary checks are a strict truncation to bars at or before `as_of` and a quality check on the
  fetched frame; four offline tests cover the truncation.
- **Calculations and formatting are unchanged from the baseline:** all 34 pairs match apart from provider noise
  and a live crypto price.
- **Environment:** Python 3.14.7 for the pairs (both revisions on the baseline's environment), 3.12.14 for the
  offline tests and gate. Live runs on 2026-10-01 from 01:55Z to 02:20Z, after Yahoo's non-finite 2026-09-30
  row had been corrected, against throwaway databases under `.tmp/esc-e/`, deleted afterward.

## 2. Momentum matrix

| Dimension | How it was verified | Narrowness and reason |
| :--- | :--- | :--- |
| Presentation | The 34 pairs ([table](#pairs)) compare concise, details, diagnostics and JSON for KO, AAPL, MSFT and SPY, with identical text. Momentum's presenter files are byte-identical to the baseline. The only JSON differences are provider float noise. The `--as-of` replay of a saved run equals the direct command in all four modes. | Comparison only, as approved: the presenter is unchanged. |
| Data lifecycle | Live: cold fetch, cache hit and `--no-cache` bypass (the baseline's fresh database is the equivalent of the cold path; a `--no-cache` run on `main` returned the same values as a cold baseline run, E.1 section 5). Offline: `tests/data/test_cached_client.py` (49 changed lines since the baseline, assertions added not weakened) covers hit, bypass, expired and stale entries, rejected and corrupt snapshots and provider failure during refresh; `tests/data/repositories/test_market_data.py` covers corrupt snapshots. The skew rule never applies here: the cache layer evaluates only cache residence age. A cache entry stamped in the future is reported as insufficient evidence and reused, not rejected (read from `_age_result`, which returns `INSUFFICIENT_EVIDENCE` for a future cache timestamp; no test pins it). | Full, as approved. |
| Time | The new `--as-of`, with no baseline to pair. Daily bars carry midnight UTC timestamps; `--as-of 2025-12-31` means the end of that day. `--as-of 2025-12-31T04:59:59+00:00` and `...05:00:00+00:00` and the date form all return the 2025-12-31 close (68.578), and `--as-of 2025-12-30T23:59:59+00:00` returns the 2025-12-30 close (68.735): bars at or before the boundary are kept, later ones dropped (tested offline to the second). `--as-of 2099-01-01` returns the latest bar; `--as-of 1990-01-01` fails (ESC-24). A naive or malformed `--as-of` is a usage error (exit 2). The documented limit that daily bars are filtered by their date, not by when the session's close was published, still holds and is carried forward. Review also produced ESC-22 and ESC-23. | Full, as approved. |
| Inputs and applicability | The invalid-input pairs below: zero and negative windows, short at or above long, zero RSI period, a long window longer than the history, an invalid, lowercase and missing ticker, the legacy `--ticker` option, a cryptocurrency, a Canadian listing and an ETF. Every pair matches the baseline, including the missing-ticker case (the configured default is now resolved in the CLI, not the analyzer, with the same result). | Narrow to the changed paths, as approved: the options and the ticker default. |
| Financial claims | The real analyzer on a constructed 300-bar series (seeded, closes rounded to four places), compared with an independent pure-Python oracle: 50-day SMA 112.33018800000002 against 112.33018799999999; 200-day SMA 106.149032 exact; RSI(14) simple-average (not Wilder) 85.37334356954496 exact; crossover 0 and trend BULLISH. All within 1e-9. The calculation body moved into `compute_momentum_metrics` unchanged. Live arithmetic cannot be checked closer than about 1e-8 because the provider's prices vary slightly between fetches (E.1). | One recomputation on a constructed fixture, as approved and as ESC-D did. |
| Composition | The cross-cutting table in E.2 covers Momentum (RY.TO live): `--save-run`, replay, refresh and orchestrator all match the direct command. Here a saved `--as-of 2025-12-31` run replays identically in all four modes. | Cited, as approved, plus the `--as-of` replay. |
| Public contracts | JSON `schema_version` 4 and every key identical to the baseline. New: `--as-of` and `--no-cache` options and their help text (X-05), and stored selections and runs at version 2 (X-08). The user guide (`MOMENTUM.md`) documents both options and the retroactive-adjustment note, and matches behavior except for ESC-22 and ESC-24. | Full, as approved. |

### Pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e4i_badticker` | `ian momentum ZZZZZZZ9` | 1 to 1 | Identical |
| `e4i_badticker_json` | `ian momentum ZZZZZZZ9 --json` | 1 to 1 | Identical |
| `e4i_cad` | `ian momentum RY.TO` | 0 to 0 | Identical |
| `e4i_crypto` | `ian momentum BTC-USD -s 5 -l 20` | 0 to 0 | Live price moved between the two runs (BTC-USD trades continuously) |
| `e4i_etf_small` | `ian momentum SPY -s 5 -l 20 --rsi-period 7` | 0 to 0 | Identical |
| `e4i_lower` | `ian momentum ko` | 0 to 0 | Identical |
| `e4i_noticker` | `ian momentum` | 1 to 1 | Identical |
| `e4i_opt_ticker` | `ian momentum --ticker KO` | 0 to 0 | Identical |
| `e4i_w_json_small` | `ian momentum -s 2 -l 3 --rsi-period 2 --json` | 1 to 1 | Identical |
| `e4i_w_large_long` | `ian momentum -s 50 -l 5000` | 1 to 1 | Identical |
| `e4i_w_long0` | `ian momentum -l 0` | 2 to 2 | Identical |
| `e4i_w_long_exact` | `ian momentum -s 50 -l 1000` | 1 to 1 | Identical |
| `e4i_w_neg` | `ian momentum -s -5` | 2 to 2 | Identical |
| `e4i_w_rsi0` | `ian momentum --rsi-period 0` | 2 to 2 | Identical |
| `e4i_w_short0` | `ian momentum -s 0` | 2 to 2 | Identical |
| `e4i_w_short_ge_long` | `ian momentum -s 50 -l 50` | 2 to 2 | Identical |
| `e4i_w_short_gt_long` | `ian momentum -s 60 -l 50` | 2 to 2 | Identical |
| `e4i_w_small` | `ian momentum -s 2 -l 3 --rsi-period 2` | 1 to 1 | Identical |
| `e4s_AAPL_concise` | `ian momentum AAPL` | 0 to 0 | Identical |
| `e4s_AAPL_details` | `ian momentum AAPL --details` | 0 to 0 | Identical |
| `e4s_AAPL_diag` | `ian momentum AAPL --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e4s_AAPL_json` | `ian momentum AAPL --json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit; see E.1 section 5) |
| `e4s_KO_concise` | `ian momentum KO` | 0 to 0 | Identical |
| `e4s_KO_details` | `ian momentum KO --details` | 0 to 0 | Identical |
| `e4s_KO_diag` | `ian momentum KO --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e4s_KO_json` | `ian momentum KO --json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit; see E.1 section 5) |
| `e4s_MSFT_concise` | `ian momentum MSFT` | 0 to 0 | Identical |
| `e4s_MSFT_details` | `ian momentum MSFT --details` | 0 to 0 | Identical |
| `e4s_MSFT_diag` | `ian momentum MSFT --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e4s_MSFT_json` | `ian momentum MSFT --json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit; see E.1 section 5) |
| `e4s_SPY_concise` | `ian momentum SPY` | 0 to 0 | Identical |
| `e4s_SPY_details` | `ian momentum SPY --details` | 0 to 0 | Identical |
| `e4s_SPY_diag` | `ian momentum SPY --diagnostics` | 0 to 0 | Identical apart from timestamps and ages |
| `e4s_SPY_json` | `ian momentum SPY --json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit; see E.1 section 5) |

## 3. Main-only runs (no baseline equivalent)

KO on 2026-10-01: `--as-of` at, before and after the bar (JSON, text, details, diagnostics); `--as-of`
2099-01-01, 1990-01-01, naive and malformed; `--no-cache --json`; `--as-of 2025-12-31 --save-run --json`
followed by `runs show` in four modes. Outputs are under `.tmp/esc-e/raw/e4-main-only/`.

## 4. Gate

`scripts/run-quality-gates.sh` on Python 3.12.14 and pandas 3.0.5, with the four new boundary tests: Ruff, format check
and `mypy --strict` clean over 311 source files; **3,423 tests passed, 91% coverage**. Artifacts:
`.tmp/quality-runs/20261001021629-585-8788/`.

## 5. Limits

- Live Momentum arithmetic is limited to about 1e-8 relative by provider noise.
- Earlier in the ESC-E window Yahoo returned non-finite prices for the latest session on US tickers
  (2026-09-30 to 2026-10-01 00:00Z to about 01:30Z); E.1's success-path evidence and E.4's pairs were taken
  when the data was valid. The failure path was exercised identically on both revisions during the bad
  window.
- Momentum on the Canadian and crypto tickers is covered by pairs, not by arithmetic checks.
