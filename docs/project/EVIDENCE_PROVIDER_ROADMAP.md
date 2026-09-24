# Evidence Provider Roadmap — Candidate Backlog

**This document is a non-authoritative candidate backlog, not a plan.** The
[Master Plan](MASTER_PLAN.md) and the active
[milestone implementation plan](milestones/v0.2/IMPLEMENTATION_PLAN.md#sequence-and-status) own
scope, sequencing, and status for this project. Every candidate strategy, platform feature, or
cleanup item listed below needs its own specification and explicit approval before any
implementation begins — inclusion here is not that approval. Where an item below has already
been scoped and sequenced as a real work package (for example [IR](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)
or [PKG](milestones/v0.2/PKG_RENAME_PLAN.md)), that work package's own document is authoritative
and this backlog defers to it rather than duplicating its scope.

The project's role, as already established by its existing design: a point-in-time evidence and
filter provider — a defensible pass, fail, or unknown about an instrument on a stated date, with
the reason and the sources behind it — not a trading-signal or order-generation system. The ideas
below build on three existing strengths: typed outcomes that can say "unavailable" and explain
why, point-in-time discipline, and provenance on every input. Each section is a candidate list to
annotate, reorder, or strike, not a commitment.

## Current baseline

The [durable instrument-profile work](milestones/v0.2/p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md)
(P2-Profiles, PR #39) established the current-identity half of identifier resolution; the
historical half, including survivorship, remains open. The
[existing-analysis renewal](milestones/v0.2/existing-strategy-correctness/ESC_D_FINAL_ACCEPTANCE.md)
(ESC-D, PR #42) re-verified the four existing analyses' typed-failure contract end to end on the
current revision, which the composable-screen ideas below would depend on.

| Area | Delivered | Still open |
| --- | --- | --- |
| Security identity | [`SecurityIdentity`](../../src/data/security_identity.py) with issuer identifier (SEC CIK, resolved from SEC's `company_tickers.json`), listing venue, instrument identifier, and name, from SEC and yfinance providers | Identity is current only — the type's own docstring states that `resolved_at` does not establish that the same identity applied at a historical `as_of`. No ticker history, delisted companies, or FIGI/CUSIP mapping |
| Instrument kind | Reviewed, fail-closed mapping of yfinance types to equity, ETF, or cryptocurrency; unreviewed providers and values deliberately stay unclassified | Mappings for other providers; finer kinds (REIT, bank, ADR, closed-end fund) that strategy applicability needs |
| Security unit | Fail-closed check that the quoted security matches the filing's per-share unit; ADR recognized, no conversion performed | ADR ratio and currency conversion; per-share adjustment across splits (see corporate-actions ledger below) |
| Profile cache | Durable instrument-profile cache with TTL-based freshness evaluation | Point-in-time profile history rather than latest snapshot |
| Typed failures | ESC-D's renewal found and fixed one real gap (Graham Number's JSON failure reason was less specific than its text-mode equivalent for the same blocker) and corrected one initial finding that further investigation showed was never actually reachable in production (a `DataQualityError` branch believed to affect Momentum's error message turned out to be dead code before and after the change that prompted the investigation — see the [defect ledger](milestones/v0.2/existing-strategy-correctness/ESC_A_DEFECT_LEDGER.md)) | Published JSON Schemas so consumers can rely on reason codes contractually (see [IR](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md) item 7) |

A repository-wide dead code audit ([R3](milestones/v0.2/R3_DEAD_CODE_AUDIT_PLAN.md)) is next in
sequence, followed by [integration readiness (IR)](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)
and the [`src` package rename (PKG)](milestones/v0.2/PKG_RENAME_PLAN.md) — both scoped
independently of this backlog but addressing the same "library-readiness" observations it
originally raised (see "Suggested priorities" below) — all three before
[Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status)'s
five new analyzers land. Step 3.5 (plan accepted) covers Piotroski F-Score, Altman Z-Score,
Beneish M-Score, EV/EBITDA and FCF yield, and the Greenblatt Magic Formula ranking. [Step 4.1](MASTER_PLAN.md#milestone-v03-analytics-expansion--canadian-localization)
lists price-to-cash-flow/price-to-free-cash-flow screens as committed scope, with cash-conversion
quality, ROIC, point-in-time estimate revisions, growth-adjusted cash-flow valuation, and leverage
and earnings stability named as candidates subject to separate approval; Step 4.2 covers further
technical indicators; Step 4.3 covers aggregation, drawdown, and volatility, with cross-sectional
ranking named as a possibility for later product-policy work. The strategy table below marks each
candidate against these owners; the plans stay authoritative for sequencing.

## Cross-cutting platform features

These raise the value of every strategy, current and future. The first two are the largest
differentiators.

- **Three-valued composable screens.** Combine strategy outputs into rules ("Graham passes AND
  interest coverage > 5 AND liquidity OK") where an unavailable input stays unavailable instead of
  becoming a false fail. `MetricResult` (`src/core/metric_result.py`) already distinguishes `ok`,
  `unavailable`, and `not_applicable` outcomes rather than silently defaulting to zero or a false
  boolean — most screeners do not make this distinction, and it is the foundation this idea would
  build on, though a genuinely composable screen-combination layer does not exist yet. Step 4.3
  already requires an explicit missing-data policy for any composite screen; three-valued logic
  could be that policy.
- **Historical identity and survivorship.** Extend the current identity work into history: CIK as
  the primary key, dated ticker changes, delisted companies, and FIGI mapping via the free
  OpenFIGI service. Screens without delisted companies are biased toward survivors.
- **Bitemporal facts and restatement evidence.** Record when each value was learned, not only when
  it became available, so "what was known on date X" and "what is true now" are both answerable.
  Restatements (10-K/A amendments, revised XBRL facts) become evidence in their own right.
- **Change attribution between two dates.** Explain why a result changed between as-of A and B:
  new filing, price move, restatement, or policy change. Monitoring systems, advisors, and agents
  all ask "why did this flip?"
- **Validity windows and expected-evidence calendars.** Attach a "stale after" hint to each result,
  derived from the next expected event, such as a 10-Q due date from filer status and fiscal
  calendar.
- **Reproducibility receipts.** Hash inputs, config, code version, and provider responses so a
  stored result can be re-verified later, for audit and client-facing use.
- **Corporate-actions ledger.** Splits, reverse splits, spinoffs, and special dividends with
  provenance, applied when adjusting per-share facts. Completes the security-unit work referenced
  above.
- **Multi-provider reconciliation.** When EDGAR, Yahoo, and Massive disagree, report the
  disagreement as evidence under a tolerance policy rather than silently choosing one.
- **Sensitivity and breakeven solving.** Deterministic sensitivity grids and inverse solves for
  formula strategies, such as the growth rate at which Graham Growth equals the current price.
- **Data-license tags in provenance.** Mark each fact's redistribution status (SEC public domain
  vs. Yahoo-via-yfinance) so downstream products can filter to what they may show clients.
- **Standard delivery surfaces — decided, deferred.** An MCP server over the existing dispatcher,
  an HTTP API with an OpenAPI spec, and Parquet/Arrow export for cross-sectional batches (published
  JSON Schemas are already [IR](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)
  item 7, not part of this candidate). The project owner confirmed this becomes its own scoped
  work package rather than folding into an existing one, explicitly not scheduled until after
  [Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status) —
  see [the deferred-item record](milestones/v0.2/DEFERRED_STANDARD_DELIVERY_SURFACES.md).
- **Published conformance suite.** Release Golden Suite fixtures as test vectors so other
  implementations can prove they compute the same results.

Library-readiness cleanup (renaming the top-level `src` package, injecting the clock into
`run_analysis`, moving import-time configuration reads into explicit construction, typing the
analyzer result instead of returning `Any`, and the `pyproject.toml` license correction) is not
listed as a candidate here: it is already scoped and sequenced as two work packages,
[IR](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md) and
[PKG](milestones/v0.2/PKG_RENAME_PLAN.md), sequenced after R3 and before Step 3.5. Those documents
are authoritative for this scope; see "Suggested priorities" below for why that sequencing was
chosen.

## New analysis strategies

Thirty-two candidates across eight families; most filing-based ones would reuse the existing fact
resolver. "Existing plan" names the Master Plan step that already owns a candidate, precisely —
where a step names a candidate only as a subject to separate approval rather than committed scope,
or where the candidate would merely fall under a step's general subject without being separately
named there, that distinction is stated rather than implied. "New" marks roadmap-only ideas. "Data
on hand" means the current providers (SEC EDGAR, yfinance, Massive) can plausibly supply the
inputs.

| Family | Strategy | Evidence it produces | Existing plan | Data on hand |
| --- | --- | --- | --- | --- |
| Graham extensions | Defensive Investor criteria | Seven pass/fail/unknown tests: size, current ratio, earnings stability, dividend record, growth, P/E and P/B caps | New | Yes |
| Graham extensions | Enterprising Investor criteria | Graham's looser multi-part screen, same component structure | New | Yes |
| Graham extensions | Net current asset value (net-nets) | Liquidation-floor test from balance-sheet facts | New | Yes |
| Graham extensions | Earnings Power Value | No-growth valuation, a counterweight to Graham Growth | New | Yes |
| Accounting quality and distress | Piotroski F-Score | Nine binary signals, each with status and reason | [Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#21-piotroski-f-score-srcanalysisstrategypiotroskipy) | Yes |
| Accounting quality and distress | Altman Z-Score and Z'' | Distress zone for manufacturers and non-manufacturers | [Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#22-altman-z-score-srcanalysisstrategyaltman_zpy) covers only the classic 1968 five-factor model for non-financial public firms; the Z'' variant (non-manufacturers/private firms) is not in that scope — confirmed by direct inspection, not left open | Yes |
| Accounting quality and distress | Ohlson O-Score | Bankruptcy-probability evidence | New | Yes |
| Accounting quality and distress | Beneish M-Score | Earnings-manipulation likelihood | [Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#23-beneish-m-score-srcanalysisstrategybeneish_mpy) | Yes |
| Accounting quality and distress | Sloan accruals ratio and cash conversion | Earnings quality relative to cash | Step 4.1 names cash-conversion quality as a candidate subject to separate approval; the Sloan accruals ratio specifically is not named there — New for that part | Yes |
| Accounting quality and distress | Dilution and stock-comp-adjusted FCF | Share-count creep; FCF after stock-based compensation | New | Yes |
| Accounting quality and distress | ROIC and gross profitability | Capital efficiency and quality | Step 4.1 names ROIC (and incremental-ROIC/reinvestment opportunity) as a candidate subject to separate approval; gross profitability specifically is not named there — New for that part | Yes |
| Accounting quality and distress | Kind-specific metrics | FFO/AFFO for REITs; efficiency ratio, capital ratios, NIM for banks | New — confirmed to require extending `InstrumentKind` (`src/data/instrument_profile.py`) beyond its current equity/ETF/cryptocurrency set; deliberately not planned further until after Step 3.5 | Partial |
| Market-implied and relative valuation | Reverse DCF | Growth rate the current price implies, by deterministic root-finding | New (Step 4.1 requires a separate DCF specification before any DCF-based method) | Yes |
| Market-implied and relative valuation | Point-in-time EV multiples | EV/EBIT, EV/EBITDA, earnings yield with as-of share count and net debt | [Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#24-unlevered-valuation-multiples-srcanalysisstrategyvaluation_multiplespy) covers EV/EBITDA and FCF yield; EV/EBIT and earnings yield specifically are not named there | Yes |
| Market-implied and relative valuation | Greenblatt Magic Formula | Earnings yield plus return on capital, combined rank | [Step 3.5](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#25-greenblatt-magic-formula-ranking-srcanalysisstrategymagic_formulapy) | Yes |
| Market-implied and relative valuation | Shareholder yield and dividend safety | Dividends + net buybacks + debt paydown; payout coverage by FCF | New | Yes |
| Market-implied and relative valuation | Peer-relative percentiles | Rank within point-in-time peer group, with coverage counts | Step 4.3 names cross-sectional ranking only as a possibility for later product-policy work, not committed scope | Partial |
| Price and market structure | Liquidity and capacity | Average daily dollar volume, Amihud illiquidity, spread proxies | New | Yes |
| Price and market structure | Risk profile | Realized volatility, maximum drawdown, Ulcer index, downside deviation, beta | Step 4.3 names maximum drawdown and volatility as committed examples of its basic risk measures; Ulcer index, downside deviation, and beta specifically are not named there | Yes |
| Price and market structure | Momentum variants | 12-minus-1-month momentum, 52-week-high proximity, time-series momentum, trend with hysteresis | Step 4.2 is the general "additional technical indicators" step (its own named examples are RSI/EMA/MACD); these specific variants are not separately named and would need their own specification under 4.2's "only when explicitly selected and specified" gate | Yes |
| Price and market structure | Abnormal events | Price gaps and volume spikes vs. the stock's own history | New | Yes |
| Filing behavior and ownership | Filing red flags | Late-filing notices, 8-K Item 4.01 auditor changes, Item 5.02 departures, going-concern language, amendment frequency | New | Yes |
| Filing behavior and ownership | Insider activity (Form 4) | Net insider buying, cluster buys, purchases vs. option exercises | New | Yes |
| Filing behavior and ownership | Large holders (13D/13G, 13F) | Activist stakes; institutional changes with the 45-day 13F lag encoded | New | Partial |
| Filing behavior and ownership | Buybacks executed vs. authorized | Whether announced programs happen | New | Partial |
| Macro and rates | ALFRED point-in-time macro | Yield-curve regime, real rates, equity risk premium from dated data vintages | New | No |
| Portfolio and account | Look-through aggregation | Holdings-weighted evidence with coverage, for portfolios and ETFs | New | Partial |
| Portfolio and account | Concentration and drift | Concentration measures, issuer and sector caps, drift from targets | New | Yes |
| Portfolio and account | Tax-rule windows | US wash-sale and Canadian superficial-loss window detection from trade dates | New | Yes |
| Portfolio and account | Suitability checks | Holdings tested against a stated risk profile, every judgment traceable | New | Yes |
| Portfolio and account | ETF-specific evidence | Expense ratio, tracking difference, premium or discount to NAV | New | Partial |
| Verification for agents | Fact-supply strategies for external claim verification | Additional simple, narrowly-scoped fact strategies — not a claim-verification engine itself — that an external system could combine to confirm, contradict, or flag a claim as unverifiable | New — claim verification itself does not fit this project's heterogeneous-strategy model (Core Design Principle #8) and may never be built directly in this project; only supporting fact-supply strategies for an external consumer are in scope (project owner decision), and even those are not planned further right now | Yes |

This is deliberately narrower than a claim-verification engine: this project's role would remain
supplying additional deterministic facts (extending Core Design Principle #1's rule that the LLM
never performs the arithmetic), not judging whether an external claim is true. Confirming,
contradicting, or flagging a claim as unverifiable is the external consumer's job, done by
combining this project's typed facts with whatever else it needs.

## Who would consume this

Each segment below maps to features and strategies above; the fit is strongest where a defensible,
traceable judgment matters more than speed. This table is illustrative, not a commitment to any
named integration.

| Consumer | What they need most |
| --- | --- |
| Wealth and advisory platforms | Suitability checks, portfolio look-through, change attribution |
| Credit and lending | Altman and Ohlson scores, coverage ratios, filing red flags |
| Compliance and audit | Reproducibility receipts, restatement history, filing red flags |
| Screeners and fintech apps | Three-valued composable screens, license-aware data, liquidity gates |
| Research and investor relations | Peer-relative percentiles, point-in-time EV multiples |
| Tax and accounting tools | Wash-sale and superficial-loss windows, corporate-actions ledger |
| Agent frameworks | MCP tools, fact-supply strategies for external claim verification, typed unavailable outcomes with reason codes |
| Education | Progressive-disclosure explanations, conformance fixtures as worked examples |

## Suggested priorities

These are proposals; the implementation plan owns actual sequencing. The one exception is the
library-readiness item below, which is not a proposal — it reflects work already scoped and
sequenced as [R3](milestones/v0.2/R3_DEAD_CODE_AUDIT_PLAN.md),
[IR](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md), and
[PKG](milestones/v0.2/PKG_RENAME_PLAN.md).

1. **Library-readiness cleanup, already decided and sequenced.** New code in this project is
   agent-written, and agents replicate the patterns they find; fixing the patterns before Step 3.5
   adds five more analyzers keeps review effort bounded. This runs as R3 (dead code), then IR
   (analyzer contract, Momentum purity, JSON schemas, license), then PKG (the `src` rename), all
   before Step 3.5. IR's own contract additionally calls for validating the new typed analyzer
   contract against Piotroski — Step 3.5's first analyzer — once it exists, rather than treating
   the contract as settled from the four existing analyzers alone.
2. **Step 3.5 quantitative screens.** As already planned: Piotroski, Altman, Beneish, EV/EBITDA and
   FCF yield, Magic Formula.
3. **Three-valued composable screens.** Proposed as the missing-data policy Step 4.3 requires;
   multiplies the value of every strategy.
4. **Graham Defensive and Enterprising criteria, and NCAV.** New, and almost entirely reuse the
   Graham fact resolution.
5. **Reverse DCF.** High explanatory value per line of code; needs its own DCF specification under
   Step 4.1.
6. **Liquidity evidence.** A cheap gate nearly every consumer would need.
7. **EDGAR filing-behavior flags.** Distinctive, and built on a client this project already has.
8. **Historical identity and survivorship.** Builds directly on the existing identity work.
9. **Change attribution and ALFRED macro.** Both reinforce the point-in-time story.

Deferred until a provider question is settled: consensus estimates, full 13F parsing, and ETF
holdings, which lack free, redistributable sources.

## Terms without a glossary entry

The following terms appear above without a corresponding entry in
[the glossary](../user/GLOSSARY.md). Listed for awareness only — no new glossary entries are added
by this document.

Piotroski F-Score, Altman Z-Score, Z'' (Altman Z-double-prime), Ohlson O-Score, Beneish M-Score,
Sloan accruals ratio, ROIC (Return on Invested Capital), Greenblatt Magic Formula, Reverse DCF,
EV/EBIT, EV/EBITDA, FCF Yield (as a market-implied multiple, distinct from the existing FCF Yield
glossary entry's own scope), shareholder yield, Amihud illiquidity, Ulcer index, downside
deviation, beta, 52-week-high, FIGI (Financial Instrument Global Identifier), CUSIP, XBRL
(eXtensible Business Reporting Language), 8-K, 10-K/A, 13D, 13G, 13F, wash-sale rule, superficial-loss
rule, ALFRED (Archival Federal Reserve Economic Data), MCP (Model Context Protocol), OpenAPI,
Parquet, Arrow, FFO (Funds From Operations), AFFO (Adjusted Funds From Operations), NIM (Net
Interest Margin).

## Resolved considerations

Three questions raised during this document's drafting were resolved by the project owner
(2026-09-23), rather than left open:

- **Standard delivery surfaces** becomes its own scoped work package, not folded into IR/PKG, and
  is explicitly not scheduled until after Step 3.5. Recorded at
  [`DEFERRED_STANDARD_DELIVERY_SURFACES.md`](milestones/v0.2/DEFERRED_STANDARD_DELIVERY_SURFACES.md).
- **Kind-specific metrics** does imply extending `InstrumentKind` beyond its current
  equity/ETF/cryptocurrency set — confirmed, not merely suspected — but this is deliberately not
  planned further until after Step 3.5.
- **Claim verification** itself does not fit this project's heterogeneous-strategy model and may
  never be built directly here. What the project should keep in view instead is its own capacity
  to supply facts an external claim-verification system would consume — most likely through
  additional simple, narrowly-scoped fact-providing strategies, not a verification engine of its
  own — reflected above as "Fact-supply strategies for external claim verification." Also not
  planned further right now.
