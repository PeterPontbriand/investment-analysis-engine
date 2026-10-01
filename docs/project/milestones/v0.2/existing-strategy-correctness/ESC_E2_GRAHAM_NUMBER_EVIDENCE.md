# ESC-E.2 — Cross-cutting paths and Graham Number evidence

Records what E.2 verified: first, once for all four analyses, the paths E.1 did not reach (`--save-run`,
replay, watchlist refresh, the orchestrator); then the seven-dimension matrix for Graham Number.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
Scope and proposal: [ESC-E plan](ESC_E_RENEWAL_PLAN.md#4-proposed-scope-for-e2-to-e5).

## 1. At a glance

- **Cross-cutting paths (all four analyses):** every replay, refresh and orchestrator result matches the
  direct command's output. The only differences are two documented, expected ones: the durable
  instrument-profile cache adds a diagnostic event on `--save-run` and refresh paths, and a refresh that
  starts more than five minutes after another run re-fetches the quote because the quote's reuse limit is
  300 seconds.
- **Graham Number:** no new ledger entry. Presentation, Data lifecycle, Time, Inputs and applicability,
  Financial claims, Composition and Public contracts were verified at the scope the plan approved
  ([§3](#3-graham-number-matrix)).
- **ESC-21, Graham resolver path:** 24 new offline scenarios, run against both Graham resolvers (48 test cases), confirm the contract: a live run accepts a provider
  fact or quote stamped up to ten minutes after `executed_at` and rejects one beyond it, from the provider
  and from a cache hit; an `--as-of` run rejects a fact available one second after the boundary.
- **Environment:** `main` at the E.2 commit on Python 3.12.14 (the project's pinned interpreter); baseline
  `7e2f8d2` on its Python 3.14.7 environment where a baseline comparison was needed. Live runs on
  2026-10-01 from 00:30Z to 00:50Z (the evening of 2026-09-30 in the project owner's time zone), against
  throwaway databases under `.tmp/esc-e/`, deleted afterward.

## 2. Cross-cutting paths, all four analyses

Run once, on `main`, against one throwaway database. Tickers: KO for Graham Number, Graham Growth
(`-g 6.5 -y 4.4`) and FCF/Earnings Growth; RY.TO for Momentum. Momentum on KO was not usable: see the note
below the table.

| Path | What was compared | Result |
| :--- | :--- | :--- |
| `--save-run` | the saved command's text and JSON against the direct command's | Same values, labels and exit codes. The saved run's JSON and diagnostics carry one extra event, "Reused the durable instrument profile", because `--save-run` resolves the profile through the durable cache (ESC-D §6 documents this). Source labels read "SEC EDGAR (saved input)" where an earlier direct run had read "derived from SEC EDGAR", because the saved run hit the cache the earlier run had filled. |
| Replay (`runs show`) | a saved run replayed in concise, details, diagnostics and JSON against the direct command run afterward on a warm cache | Graham Number and Momentum identical in all four modes. Graham Growth and FCF identical in concise and details; diagnostics and JSON differ only by the profile-cache event above. |
| Watchlist `refresh` | a four-entry watchlist refreshed, each run replayed, against the warm direct command | All four completed. Concise and details identical for all four. Graham Number, Growth and FCF diagnostics and JSON differ by the profile-cache event, and for the two Graham commands by the quote: the refresh ran more than 300 seconds after the direct run, so its quote was re-fetched ("cache entry failed temporal eligibility", then "requested from provider") instead of reused. Momentum identical. |
| Orchestrator | the four production tool handlers, registered on the production dispatcher with real providers, against the direct commands' JSON | Graham Number 21.14186862097603 with margin −307.15417138953944; Graham Growth 57.11833333333333 with margin −50.70467742406116; FCF screen `fail` with execution status `ok`; Momentum short SMA 289.3730847167969, long SMA 255.8555802154541, price 279.94000244140625, RSI 41.051122355315165. Every value equals the direct command's. |

**Momentum on a US ticker.** `momentum KO --as-of 2025-12-31` failed with the same upstream rejection every
US-ticker Momentum run had at that hour (non-finite prices in the 2026-09-30 row). It fails even though the
boundary is months earlier, because the resolver's data-quality check runs on the whole fetched frame and the
bad row is after the boundary. That is a behavior E.4 examines under Time; it is not recorded as a finding
here because nothing about it is wrong yet: failing closed on a bad row is the safe direction.

## 3. Graham Number matrix

| Dimension | How it was verified | Narrowness and reason |
| :--- | :--- | :--- |
| Presentation | E.1's 19 Graham Number pairs (KO, AAPL, MSFT, SPY and ESC-17's scenario) compared all four modes. Added a differential over every presenter branch: the baseline's own six presenter test files (82 tests, which cover unavailable, not applicable, overrides, warnings, failure reasons, quote timing and identity) were run unmodified against `main`'s presenters, with only a name shim for the module split and one call adapted for the analyzer signature. 79 pass; the 3 failures are exactly the assertions that pin `schema_version` to 5 (ESC-20). The test diff itself was audited: every changed expected string is X-01, X-02, X-03 or ESC-20. | As approved: comparison plus differential, not a hand-check of each branch live. |
| Data lifecycle | Live: cold fetch, cache hit, `--no-cache` bypass (E.1) and an expired quote re-fetched on refresh (above). Offline, each state names a passing test: cold `test_cache_miss_falls_through_to_provider`; hit `test_valid_cache_hit_wins_over_provider`; bypass `test_use_cache_false_skips_cache`; expired and stale `test_stale_ttl_entry_falls_through` and `tests/data/test_quote_freshness.py`; future `test_current_cache_future_available_at_falls_through` and the new skew tests; legacy `test_schema_version_mismatch_falls_through` and `test_legacy_yahoo_timestamp_is_not_market_observation`; corrupt `test_corrupt_storage_raises` and `test_series_read_rejects_corruption_without_partial_results`; provider failure during refresh `test_expired_quote_refresh_failure_never_returns_stale_value` and `test_c2c_provider_error_never_caches`. The assertion diff of those test files since the baseline adds checks and weakens none. | Full, as approved. |
| Time | Live pairs at the SEC filing boundary for KO's 10-K, accepted 2026-02-20T14:46:32Z: one second before, exactly at, and one second after, plus the day before. Before: EPS 2.37 (older fiscal years). At and after: EPS 2.66. Baseline and current identical in text; JSON differs only as in the register. So the boundary is inclusive and look-ahead is excluded on both revisions. ESC-21's `--as-of` half: a fact available one second after the boundary is rejected, exactly at it accepted, from the provider and from the cache. | Full, as approved. |
| Inputs and applicability | 26 pairs ([table](#inputs-pairs)): zero, negative, NaN and infinite EPS; zero and negative BVPS; zero and NaN price; every `--eps-basis` value; Massive with and without BVPS; a bogus provider; an invalid, lowercase and missing ticker; invalid, naive and future `--as-of`; a Canadian listing, an ETF with overrides and a cryptocurrency. | Full, as approved. |
| Financial claims | Recomputed from the unrounded retained inputs of the live KO JSON, independently of the calculator: EPS `(2.47 + 2.46 + 3.04) / 3 = 2.6566666666666667`; BVPS `32,169,000,000 / (7,040,000,000 − 2,738,000,000) = 7.47768479776848`; `sqrt(22.5 × EPS × BVPS) = 21.14186862097603`; margin `(21.14186862097603 − 86.08000183105469) / 21.14186862097603 × 100 = −307.15417138953944`. All four match the output exactly and `FINANCE_MATH.md`. The calculation module is unchanged except a method tag. | One recomputation, as approved. |
| Composition | The cross-cutting table above, plus the Golden suite (E.1) and `tests/analysis/test_base_analyzer_conformance.py` in the gate. | Full, as approved. |
| Public contracts | JSON keys and exit codes identical to the baseline except as the register and ESC-20 record. The documented examples in `GRAHAM_NUMBER.md` (`--eps 3.25 --bvps 8.10`, `--current-price 75`) behave identically on both revisions; the Massive example now fails on a missing key, not a usage error, as the guide's provider table says (X-04). `USAGE.md` and `SMOKE_TESTING.md` were corrected to schema 6 under ESC-20. | Full, as approved. |

### Inputs pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e2in_gn_asof_bad` | `ian graham-number KO --as-of not-a-date` | 2 to 2 | Identical |
| `e2in_gn_asof_future` | `ian graham-number KO --as-of 2099-01-01` | 0 to 0 | Identical |
| `e2in_gn_asof_naive` | `ian graham-number KO --as-of 2025-12-31T12:00:00` | 2 to 2 | Identical |
| `e2in_gn_badticker` | `ian graham-number ZZZZZZZ9` | 1 to 1 | Identical |
| `e2in_gn_badticker_json` | `ian graham-number ZZZZZZZ9 --json` | 1 to 1 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e2in_gn_basis_bogus` | `ian graham-number KO --eps-basis bogus` | 2 to 2 | Identical |
| `e2in_gn_basis_fy` | `ian graham-number KO --eps-basis fiscal_year` | 2 to 2 | Identical |
| `e2in_gn_basis_ttm` | `ian graham-number KO --eps-basis ttm` | 2 to 2 | Expected: X-03 (the rejection message names the accepted values) |
| `e2in_gn_bvps0` | `ian graham-number KO --bvps 0` | 0 to 0 | Identical |
| `e2in_gn_bvpsneg` | `ian graham-number KO --bvps -3` | 0 to 0 | Identical |
| `e2in_gn_cad` | `ian graham-number RY.TO` | 1 to 1 | Identical |
| `e2in_gn_crypto` | `ian graham-number BTC-USD` | 1 to 1 | Identical |
| `e2in_gn_eps0` | `ian graham-number KO --eps 0` | 0 to 0 | Identical |
| `e2in_gn_epsbvps_ok` | `ian graham-number KO --eps 3 --bvps 10 --current-price 50` | 1 to 1 | Identical |
| `e2in_gn_epsbvps_ok_json` | `ian graham-number KO --eps 3 --bvps 10 --current-price 50 --json` | 1 to 1 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e2in_gn_epsinf` | `ian graham-number KO --eps inf` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e2in_gn_epsnan` | `ian graham-number KO --eps nan` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e2in_gn_epsneg` | `ian graham-number KO --eps -1.5` | 0 to 0 | Identical |
| `e2in_gn_etf_override` | `ian graham-number SPY --eps 3 --bvps 10` | 0 to 0 | Identical |
| `e2in_gn_lowercase` | `ian graham-number ko` | 0 to 0 | Identical apart from timestamps and ages |
| `e2in_gn_massive_bvps` | `ian graham-number KO --data-provider massive --bvps 10` | 2 to 1 | Expected: X-04 (Massive now defaults to `ttm`, so the baseline's `--eps-basis` rejection is gone) |
| `e2in_gn_massive_nobvps` | `ian graham-number KO --data-provider massive` | 2 to 2 | Expected: X-04 (Massive now defaults to `ttm`, so the baseline's `--eps-basis` rejection is gone) |
| `e2in_gn_noticker` | `ian graham-number` | 2 to 2 | Identical |
| `e2in_gn_price0` | `ian graham-number KO --current-price 0` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e2in_gn_pricenan` | `ian graham-number KO --current-price nan` | 1 to 1 | Expected: X-02 (invalid-input wording) |
| `e2in_gn_provider_bogus` | `ian graham-number KO --data-provider bogus` | 1 to 1 | Identical |

### Time pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e2time_gn_KO_after_concise` | `ian graham-number KO --as-of 2026-02-20T14:46:33+00:00` | 0 to 0 | Identical |
| `e2time_gn_KO_after_json` | `ian graham-number KO --as-of 2026-02-20T14:46:33+00:00 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e2time_gn_KO_before_concise` | `ian graham-number KO --as-of 2026-02-20T14:46:31+00:00` | 0 to 0 | Identical |
| `e2time_gn_KO_before_json` | `ian graham-number KO --as-of 2026-02-20T14:46:31+00:00 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e2time_gn_KO_day_before_json` | `ian graham-number KO --as-of 2026-02-19 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `e2time_gn_KO_exact_concise` | `ian graham-number KO --as-of 2026-02-20T14:46:32+00:00` | 0 to 0 | Identical |
| `e2time_gn_KO_exact_json` | `ian graham-number KO --as-of 2026-02-20T14:46:32+00:00 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |

### Documented-example pairs

| Pair | Command | Exit (baseline to current) | Result |
| :--- | :--- | :--- | :--- |
| `e2doc_gn_eps_bvps` | `ian graham-number KO --eps 3.25 --bvps 8.10` | 0 to 0 | Identical |
| `e2doc_gn_price75` | `ian graham-number KO --current-price 75` | 0 to 0 | Identical |
| `e2doc_gn_price75_json` | `ian graham-number KO --current-price 75 --json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |

## 4. ESC-21 for the Graham resolver path

`tests/analysis/graham_value/test_clock_skew_tolerance.py` (24 scenarios, each run against both
`GrahamNumberInputResolver` and `GrahamGrowthInputResolver`, which share one fact-resolution path; offline, no
network, every OS) drives the shared input resolver with a frozen clock:

- a live provider fact with `available_at` at 0, 9:59 and exactly ten minutes after `executed_at` is accepted;
  at ten minutes and one second, and at one hour, it is rejected as `input_unavailable`;
- a live cache hit whose stored `available_at` is five or ten minutes ahead is used; at ten minutes and one
  second it falls through to the provider;
- a live quote whose retrieval time or observation time is five or ten minutes ahead is accepted with status
  `recent_retrieval`, from the provider and from a cache hit; at ten minutes and one second it is rejected,
  and a stored quote falls through to the provider;
- an `--as-of` fact available exactly at the boundary is accepted and one second after it rejected; an
  `--as-of` cache entry tolerates no skew at all: one second ahead falls through, five minutes ahead falls
  through.

All 48 cases pass on the unmodified code, so the behavior matches the contract in ESC-21. Pre-existing coverage
is narrower: `tests/data/test_quality.py` and `tests/data/test_quote_freshness.py` test the shared check and
the quote check directly, and neither drives the resolver or a cache hit.

## 5. Gate

`scripts/run-quality-gates.sh` on Python 3.12.14 and pandas 3.0.5, after the new tests were added: link check,
Ruff, format check and `mypy --strict` clean over 310 source files; **3,395 tests passed, 91% coverage**.
Artifacts: `.tmp/quality-runs/20261001005033-1249-1120/`. E.3 later broadened the skew tests to run against both
Graham resolvers (3,419 tests).

## 6. Limits

- Graham Number produced a value live only for KO; AAPL and MSFT fail on both revisions on preferred-share
  evidence (the ESC-17 guard).
- The Massive provider was not exercised beyond its configuration error: no key is configured.
- The profile-cache event and the quote re-fetch are expected product behavior, not differences between
  revisions; they are listed so a reader does not take them for findings.
