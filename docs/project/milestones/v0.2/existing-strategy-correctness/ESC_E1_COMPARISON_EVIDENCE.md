# ESC-E.1 — Side-by-side comparison evidence

Records how the first ESC-E slice compared the four existing analyses on `main` against ESC-D's accepted
revision, what it found, and what it could not reach.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
Scope and proposal: [ESC-E plan](ESC_E_RENEWAL_PLAN.md).

## 1. At a glance

- **Revisions:** baseline `7e2f8d2` (ESC-D's accepted revision, PR #42) against `main` at `e6b1f76`
  (IR.6 merged, PR #51).
- **Golden suite:** 19 of 19 cases pass on both. All 91 observed numerical and domain-outcome
  values match exactly. The only differences in the full native results are Momentum's run timestamps (X-09);
  the case definitions differ only by the removed Graham method constraints (X-13).
- **Live pairs:** 70 command pairs, each run on both revisions back to back.
  38 were byte-identical (14 of them the Momentum failures below), 19 were identical apart from timestamps and response ages,
  1 differed only as the register predicts (X-03), and 12 (every Graham JSON pair) differed
  in `analysis` as the register predicts (X-01) and in `schema_version` without any record (ESC-20). The
  14 Momentum pairs of this pass failed identically on both revisions, because Yahoo returned non-finite
  prices for the latest session (the condition ESC-D hit); Momentum's successful live pairs come from a
  first pass and from five added RY.TO pairs ([§4](#momentum), [§5](#5-first-pass-and-the-momentum-re-run)).
- **No unexplained difference** in any calculated value, status, reason, warning, source label or exit code.
- **One ledger entry:** [ESC-20](ESC_A_DEFECT_LEDGER.md#esc-20--graham-json-presentation-schema-version-changed-from-5-to-6-with-no-ir-record-and-two-user-documents-still-say-5).
- **Not reached:** `--save-run`, replay, watchlist refresh, the orchestrator path, Massive, invalid-input
  failures, and any cache state other than cold, hit and bypass ([§6](#6-limits)).

## 2. Method

- **Baseline worktree:** `E:\Source\iae-esc-baseline` at `7e2f8d2`, synchronized with `uv sync --frozen`;
  removed afterward.
- **Interpreter:** `7e2f8d2` cannot import on Python 3.12 or 3.13 (the defect IR.4 fixed), and `uv.lock` is
  unchanged between the revisions. Both revisions therefore ran on the baseline worktree's Python 3.14.7
  environment with pandas 3.0.5 and yfinance 1.6.0; only the imported `src` package and the working
  directory differed (`PYTHONPATH`). A first pass ran `main` on its own pinned Python 3.12.14 instead; its
  classifications agree with those reported here, apart from Momentum's success pairs
  ([§5](#5-first-pass-and-the-momentum-re-run)).
- **Isolation:** each revision had its own throwaway SQLite database
  (`sqlite:///.tmp/esc-e/baseline.sqlite3` and `.../main.sqlite3`), created with `ian db upgrade` before the
  first pair, so caches and stored versions never crossed over.
- **Pairing:** for each pair the baseline ran first and `main` second, within seconds. Both used the same
  environment (including the SEC identity setting) and `NO_COLOR=1`, `COLUMNS=200`, standard input
  redirected from nothing.
- **Flags:** each command's flags as they exist at that revision. Where the baseline lacks a flag (Momentum's
  `--as-of` and `--no-cache`) the baseline ran the equivalent its fresh database gives, or the run is
  recorded as `main`-only.
- **Normalization:** timestamps, UUIDs, quote response ages (`Quote response age: N seconds`,
  `retrieval_age_seconds`) and minute-resolution `Quote retrieved` times were masked before comparing.
  Nothing else was.
- **Classification:** every difference is expected (a register entry in
  [Appendix B](ESC_E_RENEWAL_PLAN.md#appendix-b-expected-difference-register) names it), live-data noise (a
  re-run shows the same revision varying by the same amount), or unexplained (a ledger entry).
- **Raw output:** `.tmp/esc-e/` in the repository (ignored by git): per-pair `.out`, `.err`, `.rc` and
  start and end times, the Golden reports and observed-value dumps, and the comparison scripts.

## 3. Golden suite (offline)

`ian evaluate --report` passed 19 of 19 on both revisions, but its report carries only pass or fail and
evidence text, so it cannot show a changed value. The comparison therefore dispatched every deterministic
case through the same fixture composition on each revision and dumped the complete native result
(`golden_observed.py`).

| Check | Result |
| :--- | :--- |
| Cases compared | 19 (FCF 5, Graham Number 6, Graham Growth 5, Momentum 3; the four SEC FPI cases are counted by analysis) |
| Observed numerical and domain-outcome values | 91 compared; all equal |
| Full native results | Equal except `metrics.timestamp` and the price inputs' `resolved_at` on the three Momentum cases (baseline: wall clock when computed; current: the run's injected `executed_at`) (X-09) |
| Tool arguments | Equal except Momentum's new `use_cache` field (X-05) |
| Case definitions | Equal except the removal of each Graham case's `graham_method_constraints` (X-13); suite version `h1-v3` to `h1-v4` |

## 4. Live pairs

Results by pair. "Identical" means byte-identical standard output, standard error and exit code.

| Pair | Exit (baseline to current) | Result |
| :--- | :--- | :--- |
| `esc17_graham-number_MSFT_asof2025-12-31_concise` | 1 to 1 | Identical |
| `esc17_graham-number_MSFT_asof2025-12-31_details` | 1 to 1 | Identical |
| `esc17_graham-number_MSFT_asof2025-12-31_diag` | 1 to 1 | Identical |
| `esc17_graham-number_MSFT_asof2025-12-31_json` | 1 to 1 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `fcf-growth_AAPL_concise` | 0 to 0 | Identical |
| `fcf-growth_AAPL_details` | 0 to 0 | Identical |
| `fcf-growth_AAPL_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_AAPL_json` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_KO_asof2024-06-30_concise` | 0 to 0 | Identical |
| `fcf-growth_KO_asof2024-06-30_details` | 0 to 0 | Identical |
| `fcf-growth_KO_asof2024-06-30_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_KO_asof2024-06-30_json` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_KO_concise` | 0 to 0 | Identical |
| `fcf-growth_KO_details` | 0 to 0 | Identical |
| `fcf-growth_KO_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_KO_json` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_KO_nocache_json` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_MSFT_concise` | 0 to 0 | Identical |
| `fcf-growth_MSFT_details` | 0 to 0 | Identical |
| `fcf-growth_MSFT_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_MSFT_json` | 0 to 0 | Identical apart from timestamps and ages |
| `fcf-growth_SPY_concise` | 0 to 0 | Identical |
| `fcf-growth_SPY_json` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_AAPL_concise` | 0 to 0 | Identical |
| `graham-growth_AAPL_details` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_AAPL_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_AAPL_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-growth_KO_asof2025-06-30_concise` | 0 to 0 | Identical |
| `graham-growth_KO_asof2025-06-30_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-growth_KO_concise` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_KO_details` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_KO_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_KO_fiscalyear_json` | 2 to 0 | Expected: X-03 (baseline exit 2, current accepts the basis) |
| `graham-growth_KO_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-growth_KO_nocache_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-growth_MSFT_concise` | 0 to 0 | Identical |
| `graham-growth_MSFT_details` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_MSFT_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-growth_MSFT_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-growth_SPY_concise` | 0 to 0 | Identical |
| `graham-growth_SPY_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-number_AAPL_concise` | 1 to 1 | Identical |
| `graham-number_AAPL_details` | 1 to 1 | Identical |
| `graham-number_AAPL_diag` | 1 to 1 | Identical |
| `graham-number_AAPL_json` | 1 to 1 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-number_KO_concise` | 0 to 0 | Identical |
| `graham-number_KO_details` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-number_KO_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `graham-number_KO_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-number_KO_nocache_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-number_MSFT_concise` | 1 to 1 | Identical |
| `graham-number_MSFT_details` | 1 to 1 | Identical |
| `graham-number_MSFT_diag` | 1 to 1 | Identical |
| `graham-number_MSFT_json` | 1 to 1 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `graham-number_SPY_concise` | 0 to 0 | Identical |
| `graham-number_SPY_json` | 0 to 0 | Expected: X-01 (`analysis` value); unexplained: ESC-20 (`schema_version` 5 to 6) |
| `momentum_AAPL_concise` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_AAPL_details` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_AAPL_diag` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_AAPL_json` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_KO_concise` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_KO_details` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_KO_diag` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_KO_json` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_MSFT_concise` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_MSFT_details` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_MSFT_diag` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_MSFT_json` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_SPY_concise` | 1 to 1 | Identical failure (upstream data-quality rejection) |
| `momentum_SPY_json` | 1 to 1 | Identical failure (upstream data-quality rejection) |

### Momentum

The reported pass ran from 00:02Z on 2026-10-01, after Yahoo began returning non-finite open, high, low and
close values for the 2026-09-30 row. Every US-ticker Momentum pair therefore failed identically on both
revisions with the sanitized `historical_quality` rejection (exit 1, same reason text, same affected
fields), which is the failure path ESC-D recorded. Momentum's successful live pairs come from two other
places:

- **First pass** (baseline on Python 3.14.7, `main` on 3.12.14, run 23:39Z to 23:55Z on 2026-09-30, before the
  bad row appeared): the 14 Momentum pairs for KO, AAPL, MSFT and SPY succeeded on both. Concise, details and
  diagnostics text were identical (apart from timestamps). The four JSON pairs differed only in `long_sma`,
  `sma_spread` and `sma_spread_percent` in the eighth digit ([§5](#5-first-pass-and-the-momentum-re-run)).
- **Added pairs** (matched interpreter, RY.TO, a Canadian listing whose latest row was valid): five pairs, all
  byte-identical or identical apart from timestamps, including both JSON runs.

**First pass (Momentum succeeded; mismatched interpreters)**

| Pair | Exit (baseline to current) | Result |
| :--- | :--- | :--- |
| `momentum_AAPL_concise` | 0 to 0 | Identical |
| `momentum_AAPL_details` | 0 to 0 | Identical |
| `momentum_AAPL_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `momentum_AAPL_json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit) |
| `momentum_KO_concise` | 0 to 0 | Identical |
| `momentum_KO_details` | 0 to 0 | Identical |
| `momentum_KO_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `momentum_KO_json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit) |
| `momentum_MSFT_concise` | 0 to 0 | Identical |
| `momentum_MSFT_details` | 0 to 0 | Identical |
| `momentum_MSFT_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `momentum_MSFT_json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit) |
| `momentum_SPY_concise` | 0 to 0 | Identical |
| `momentum_SPY_json` | 0 to 0 | Provider noise in `long_sma` and the two values derived from it (eighth digit) |

**Added pairs (RY.TO, matched interpreter)**

| Pair | Exit (baseline to current) | Result |
| :--- | :--- | :--- |
| `momentum_RY.TO_concise` | 0 to 0 | Identical |
| `momentum_RY.TO_details` | 0 to 0 | Identical |
| `momentum_RY.TO_diag` | 0 to 0 | Identical apart from timestamps and ages |
| `momentum_RY.TO_json` | 0 to 0 | Identical apart from timestamps and ages |
| `momentum_RY.TO_json_second` | 0 to 0 | Identical apart from timestamps and ages |

### Exit codes and outcomes the pairs exercised

- KO: Graham Number, Graham Growth and FCF succeed (exit 0) on both revisions, including Graham Number's KO
  success path. Momentum is covered in the Momentum subsection above.
- AAPL and MSFT: Graham Number fails with the same preferred-share-evidence reason on both revisions
  (exit 1), the guard ESC-17 documents. Graham Growth and FCF succeed.
- SPY: Graham Number and Graham Growth report "not applicable" for an ETF, FCF reports INDETERMINATE for an
  ETF, with identical text on both revisions (exit 0). Momentum for SPY is in the Momentum subsection.
- ESC-17's scenario (`graham-number MSFT --as-of 2025-12-31`): identical on both revisions in text, details
  and diagnostics (exit 1, EPS 11.71 USD, BVPS unavailable with the specific explanation); the JSON differs
  only in `analysis` and `schema_version`.
- FCF `--as-of 2024-06-30` (KO): identical on both revisions in all four modes.
- Graham Growth `--as-of 2025-06-30` (KO): identical on both revisions in concise; JSON differs only in
  `analysis` and `schema_version`.
- `--no-cache`: identical for FCF; the two Graham commands differ only as above.
- `graham-growth KO --eps-basis fiscal_year`: the baseline rejects the value (exit 2); `main` accepts it and
  returns a result (X-03).

## 5. First pass and the Momentum re-run

A first full pass ran the baseline on Python 3.14.7 and `main` on its own pinned Python 3.12.14, before the
interpreter was matched. It classified the same way as the reported pass, with one addition: four Momentum
JSON pairs differed in `long_sma`, `sma_spread` and `sma_spread_percent` in the eighth significant digit
(for example `long_sma` 78.96095844 against 78.96095810 for KO). Live data or the interpreter could explain
that, so the pairs were re-run before classifying them:

- A re-run of the four tickers on fresh databases matched exactly for KO and MSFT and differed again for
  AAPL and SPY, by a different amount from the first pass.
- Within one revision, two independent fetches differ by that amount: the baseline's KO `long_sma` was
  78.96095844 from one fetch and 78.96095810 from another, and `main` with `--no-cache` returned a value
  equal to the baseline's other fetch to the last digit.
- The rolling-mean arithmetic is not interpreter-dependent: a constructed float32 series gives the same
  200-day and 50-day means to the last digit on Python 3.12.14 and 3.14.7 with the same numpy 2.5.2 and
  pandas 3.0.5.
- The short SMA, the latest close and the RSI never differed. That is what a provider returning
  float32-rounded adjusted prices that vary slightly between fetches would produce.
- With the interpreter matched, the five RY.TO Momentum pairs were identical, JSON included.

Classification: provider noise, not a code difference. It limits independent arithmetic for Momentum from a
live fetch ([§6](#6-limits)). The first pass otherwise agrees with the reported one, so `main`'s output on
3.12 and on 3.14 is the same wherever the data is.

## 6. Limits

- **Momentum precision:** live Momentum arithmetic cannot be checked to better than about 1e-8 relative,
  because the provider's adjusted prices can vary slightly between fetches. ESC-D used a constructed fixture for
  Momentum's independent arithmetic for a related reason.
- **Momentum success path:** the matched-interpreter pass could not run it on US tickers (upstream data
  quality, above), so Momentum's live success comparison rests on the first pass (mismatched interpreters,
  provider float noise) and on RY.TO.
- **Graham Number success on one ticker:** only KO produced a Graham Number value live; AAPL and MSFT failed
  identically on both revisions because their preferred-share evidence is unavailable. The Number path is
  therefore compared on one successful issuer.
- **Not reached by any pair:** `--save-run`, replay, watchlist refresh and the orchestrator path (compared
  only through the Golden suite's dispatch); the Massive provider (no key configured); invalid-input
  failures (so X-02 is unobserved); expired, stale, future-stamped, legacy and corrupt cache entries; the
  ten-minute skew tolerance and the consolidated availability check (ESC-21); the Windows path guard.
- **Market movement:** pairs ran seconds apart. Quote values matched in every pair that includes a quote,
  so no price moved between a pair's two runs; response ages differed by seconds, as expected.
- **Dates:** the first pass ran 2026-09-30 from 23:39Z to 23:55Z; the reported pass and the added pairs ran
  from 00:02Z to about 00:30Z on 2026-10-01 (the evening of 2026-09-30 in the project owner's time zone).
- **Not a replacement for E.2 to E.5:** this slice compares behavior, not evidence. A passing comparison
  shows IR did not change what these commands print; it does not show the printed values are right.
