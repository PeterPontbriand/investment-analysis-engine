# Smoke Testing Commands

Execute this short set of commands as a smoke test after deploying or updating Financial Data Agents. Run the commands from the repository root. They exercise representative CLI parsing, live provider access, deterministic calculations, progressive-disclosure output, and machine-readable output without attempting exhaustive coverage.

## Prerequisites

- Complete the normal installation and configuration steps, including
  [database schema preparation](DATABASE.md). The database guide also describes
  the separate offline persistence test.
- Allow outbound access required by Yahoo Finance, SEC EDGAR, and—when tested—Massive.
- Configure the SEC EDGAR application identity described in the installation guidance.
- Set `MASSIVE_API_KEY` before running the optional Massive command.

Provider data changes over time, so exact values are not prescribed. For each command, confirm that output is well-formed, identifies the requested ticker and method, contains no traceback or `NaN`/infinity, and either produces a typed result or explains classified unavailability clearly.

## Commands

1. Confirm that the CLI starts and lists its commands:

   ```powershell
   uv run financial-agents --help
   ```

   Expect the analysis commands, `evaluate`, and `--help`. Shell-setup options such as `--show-completion` and `--install-completion` must not appear; help must not emit shell scripts.

2. Run the default Momentum analysis over a liquid U.S. equity:

   ```powershell
   uv run financial-agents momentum AAPL
   ```

3. Exercise custom SMA and RSI periods with detailed market-data context:

   ```powershell
   uv run financial-agents momentum MSFT --short-window 10 --long-window 30 --rsi-period 14 --details
   ```

4. Inspect Momentum diagnostics for a defensive consumer company:

   ```powershell
   uv run financial-agents momentum KO --diagnostics
   ```

   Confirm that resolver/provider or cache events are present without duplicated messages. The price is an adjusted historical Close with an observation date, not a live quote. A zero crossover means no transition between two valid SMA pairs; insufficient transition history must have an unavailable reason.

5. Immediately repeat the same Momentum request in JSON to inspect cache provenance:

   ```powershell
   uv run financial-agents momentum KO --json
   ```

   With historical caching enabled and the preceding snapshot still eligible, expect `data_resolution.source_kind` to be `cache`, with the original retrieval time retained and cache evidence in `diagnostics`. Expect the top-level `schema_version` to be 4; `data_resolution.cache_schema_version` remains 1. Cache reuse must not relabel the snapshot as freshly retrieved provider data.

6. Inspect the default SEC-backed Graham Number calculation, quote comparison and detailed lineage:

   ```powershell
   uv run financial-agents graham-number KO --details
   ```

   Check quote retrieval separately from market observation time; Yahoo's missing exchange timestamp must be stated honestly. Expect a compact explanation of EPS, book value, the formula and material assumptions. Inferred preferred-share zero must be qualified as not explicitly reported; repeated share components should appear once. BVPS must consistently use its supported fiscal-year-end basis. Filing venue must be identified as historical evidence. Raw provider fields, context IDs and recursive notes belong in diagnostics/JSON. With compatible inputs, expect a numeric price relationship; unexplained unavailability requires investigation.

7. Immediately repeat Graham Number in JSON to check quote reuse and typed evidence:

   ```powershell
   uv run financial-agents graham-number KO --json
   ```

   Expect top-level schema version 5 and `price_comparison.quote_freshness` with original retrieval time, response age and the configured maximum (300 seconds by default). An eligible cache hit retains its retrieval time; an expired or unverifiable quote must refresh or explain unavailability, never silently fall back to stale data. A missing market timestamp remains `null`. If legacy-input evidence prevents comparison, rerun command 6 with `--no-cache`; continuing unavailability requires its own supported explanation, not automatic acceptance of the refresh hint.

8. Exercise a historical Graham boundary and its resolver diagnostics:

   ```powershell
   uv run financial-agents graham-number MSFT --as-of 2025-12-31 --diagnostics
   ```

   An unavailable Graham Number must identify the unresolved financial input in the opening, before diagnostics. If preferred-share evidence cannot be established, explain why BVPS cannot be derived and state that missing preferred-share data is not assumed to be zero. Direct common shares plus absent preferred-share concepts do not satisfy the supported SEC zero-preferred inference rules. Distinguish a price that was not requested after required-input failure from an attempted quote retrieval that failed. No price comparison is performed without a calculated Graham Number; current-only quote adapters also cannot supply a historical quote. Retain resolver evidence in diagnostics, and do not use information published after the requested boundary.

9. Run the separate forecast-dependent Graham Growth Value method with explicit assumptions:

   ```powershell
   uv run financial-agents graham-growth KO --expected-growth 5 --aaa-yield 4.5 --details
   ```

10. If Massive access is configured, exercise the deliberately supported Massive Graham Number route—TTM EPS plus an explicit BVPS override and Massive quote:

    ```powershell
    uv run financial-agents graham-number AAPL --data-provider massive --eps-basis ttm --bvps 4.50 --details
    ```

11. Run the default historical Free Cash Flow & Earnings Growth screen:

    ```powershell
    uv run financial-agents fcf-growth AAPL
    ```

12. Exercise a strict horizon, FCF-per-share classification, and detailed annual evidence:

    ```powershell
    uv run financial-agents fcf-growth MSFT --growth-years 3 --classification-basis fcf-per-share --details
    ```

    Confirm that the explanation refers to FCF **per diluted share** and agrees with that measure's growth. Expect a compact annual table with currency, share counts and formulas. Detailed source/cache origin and derivation notes remain available in diagnostics/JSON. Unsupported optional consensus or market-cap metrics should carry reasons rather than substituted zeroes. A calculated `FAIL` is a valid screen result, not an execution error.

## Review checklist

- Help and option parsing complete without a traceback.
- Investor-facing output uses readable statuses, warnings, and limitations.
- Successful text reports begin with the instrument name/ticker and analysis heading. Routine cache rejection or refresh must not print an internal quality warning before that heading; diagnostic evidence remains available in `--diagnostics` and JSON.
- Detail and diagnostic views retain provider, period, freshness, and resolution evidence.
- JSON output parses as JSON and uses `null`, never non-standard numeric sentinels. If a runtime failure occurs during either JSON command, stdout must still contain a versioned failure document with `result: null` and a reason; `$LASTEXITCODE` must be nonzero. Historical numeric-quality failures should identify affected fields/dates without dumping raw payloads or secrets. Do not manufacture a live provider failure merely to complete this smoke test.
- Historical requests do not use information published after the requested boundary.
- Optional quote failure does not discard an otherwise valid Graham calculation.
- Any unavailable result gives a classified reason rather than silently substituting zero.

Do not treat a changed market value, screening classification, or unavailable optional quote as a deployment failure by itself. Investigate malformed output, unclassified exceptions, unsupported-option errors for the commands above, missing provenance, or unexplained provider failures.

This remains twelve primary commands, including the optional Massive route. Exact quote-expiry boundaries, stale-refresh failures, first-valid-SMA transitions, invalid preloaded frames and historical execution-clock selection belong to deterministic regression tests; live smoke data cannot reliably force those cases.
