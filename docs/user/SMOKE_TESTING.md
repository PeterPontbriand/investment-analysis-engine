# Smoke Testing Commands

Execute this short set of commands as a smoke test after deploying or updating Financial Data Agents. Run the commands from the repository root. They exercise representative CLI parsing, live provider access, deterministic calculations, progressive-disclosure output, and machine-readable output without attempting exhaustive coverage.

## Prerequisites

- Complete the normal installation and configuration steps.
- Allow outbound access required by Yahoo Finance, SEC EDGAR, and—when tested—Massive.
- Configure the SEC EDGAR application identity described in the installation guidance.
- Set `MASSIVE_API_KEY` before running the optional Massive command.

Provider data changes over time, so exact values are not prescribed. For each command, confirm that output is well-formed, identifies the requested ticker and method, contains no traceback or `NaN`/infinity, and either produces a typed result or explains classified unavailability clearly.

## Commands

1. Confirm that the CLI starts and lists its commands:

   ```powershell
   uv run financial-agents --help
   ```

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

5. Validate Momentum's machine-readable output on a highly traded ETF:

   ```powershell
   uv run financial-agents momentum SPY --json
   ```

6. Run the default SEC-backed Graham Number path, including optional quote comparison:

   ```powershell
   uv run financial-agents graham KO
   ```

7. Inspect the Graham Number's resolved inputs and derivation provenance:

   ```powershell
   uv run financial-agents graham AAPL --details
   ```

8. Exercise a historical Graham boundary and its resolver diagnostics:

   ```powershell
   uv run financial-agents graham MSFT --as-of 2025-12-31 --diagnostics
   ```

9. Run the separate forecast-dependent Graham Growth Value method with explicit assumptions:

   ```powershell
   uv run financial-agents graham KO --method growth --expected-growth 5 --aaa-yield 4.5 --details
   ```

10. If Massive access is configured, exercise the deliberately supported Massive Graham Number route—TTM EPS plus an explicit BVPS override and Massive quote:

    ```powershell
    uv run financial-agents graham AAPL --data-provider massive --eps-basis ttm --bvps 4.50 --details
    ```

11. Run the default historical Free Cash Flow & Earnings Growth screen:

    ```powershell
    uv run financial-agents fcf-growth AAPL
    ```

12. Exercise a strict horizon, FCF-per-share classification, and detailed annual evidence:

    ```powershell
    uv run financial-agents fcf-growth MSFT --growth-years 3 --classification-basis fcf-per-share --details
    ```

## Review checklist

- Help and option parsing complete without a traceback.
- Investor-facing output uses readable statuses, warnings, and limitations.
- Detail and diagnostic views retain provider, period, freshness, and resolution evidence.
- JSON output parses as JSON and uses `null`, never non-standard numeric sentinels.
- Historical requests do not use information published after the requested boundary.
- Optional quote failure does not discard an otherwise valid Graham calculation.
- Any unavailable result gives a classified reason rather than silently substituting zero.

Do not treat a changed market value, screening classification, or unavailable optional quote as a deployment failure by itself. Investigate malformed output, unclassified exceptions, unsupported-option errors for the commands above, missing provenance, or unexplained provider failures.
