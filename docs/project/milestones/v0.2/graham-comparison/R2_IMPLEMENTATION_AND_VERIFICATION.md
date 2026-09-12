# Graham Comparison Repair — R2 implementation and verification

**Acceptance update:** The verified Graham repair is checkpointed in `e8f4a95` on the renamed `fix/existing-strategy-correctness` branch. Its final acceptance is reopened and incorporated into ESC-C of the [expanded four-analysis audit](../existing-strategy-correctness/EXISTING_STRATEGY_CORRECTNESS_PLAN.md). Preserve the following evidence as history, not approval of the expanded scope or permission to resume readiness.

**Status:** Implementation and deterministic verification complete on 2026-09-10;
paused for R2/R3 stakeholder review. Final acceptance has not been granted.

## Authorization and branch

R1 was accepted and R2 explicitly authorized. The user subsequently approved
typed source lineage for derived common shares and the inferred zero-preferred
guard. After the concurrent S0–S6 distribution amendment was surfaced, the user
instructed continuation toward final review. Intermediate slice approvals are
not claimed; the repair plan records that execution clarification.

Work is on `fix/graham-price-comparison`, with HEAD `fba79c5` plus the working
tree changes. That shared-checkout commit already includes the README audit
correction and part of the production repair. Review the combined branch and
working-tree changes, not only the unstaged diff. This completion made no commit,
push, or PR. Database-readiness implementation remains separate and unauthorized.

## Implemented contract

- The SEC adapter completes missing unit evidence after financial resolution,
  within its existing request scope. It verifies original source accessions and
  the current eligible annual filing, matching issuer, registered common class,
  ticker, source values, periods, and units. The reviewed single-common-class
  inference supplies 1:1 evidence only for supported current domestic US-GAAP
  filings. Caller-supplied evidence and no-profile programmatic behavior remain
  supported.
- The filing reader limits each document to 8 MiB with a 20-second timeout and
  at most four documents per request. URL construction is restricted to SEC
  archive identifiers. Redirects and automatic retries are disabled. The pure
  parser resolves namespaces, joins registration facts by context, distinguishes
  supported debt registrations, handles nested/scaled numeric evidence, and
  rejects ambiguous or unsupported evidence.
- Existing adapter derivations retain typed source lineage through the existing
  resolved-input cache representation. Raw issued/treasury share sources have
  their own type: zero treasury shares remain valid, while shares outstanding
  retain their positive-value requirement. The zero-preferred guard retains its
  existing assumptions and source anchors; no new financial formula is introduced.
- Shared comparison evaluation returns status, reason, and percentage. The old
  nullable percentage helper delegates to it. Both Graham services and CLI
  paths propagate the result, including unavailable calculations. Evidence-only
  failures preserve independently valid financial results.
- Concise output explains unavailable comparisons. Details and diagnostics
  expose sanitized unit/provider/mapping/accession/context evidence. Graham JSON
  is version 4, retains the legacy percentage, and adds `price_comparison`.
  Legacy manually constructed presentations may leave the new object null.
- The Graham guide, usage guide, financial math reference, and architecture
  describe these boundaries. The original reproduction now runs positive
  production-composition regressions; its pre-repair form remains in Git history.

## Deterministic evidence

| Requirement | Verification |
| :--- | :--- |
| Production composition | `tests/test_graham_comparison_composition.py`: real SEC adapter, production facade, resolver, profile completion, both Graham services, and CLI renderers with synthetic fetchers; no prebuilt affirmative profile or mocked comparison. |
| Output/cache parity | Both methods × concise/details/diagnostics/JSON × normal-cache/bypass; two invocations per case; original accession retained; percentage checked against unrounded result and legacy field. Details/diagnostics assert evidence visibility. |
| Filing validation | `tests/data/test_sec_security_unit.py`: ordinary common stock with a separate note registration; exact source values, nested/scaled numerics, conflicting duplicates, malformed IDs, wrong units, namespaces, missing/continued/nil/excluded facts, class/symbol/issuer conflicts, ADR/preferred/unknown registrations, and unsupported scales/transforms. |
| Acquisition boundaries | Legacy missing lineage, historical request, missing primary document, unsupported quote provider, mismatched symbol, transport failure, four original documents accepted once each, and overflow rejected before document reads. Reader tests verify request timeout, declared agent, bounded read, URL restrictions, and disabled redirects using a fake opener. |
| Comparison preservation | New stable-reason/precedence tests plus existing security-unit, shared-helper, method-analyzer, quote/override, nonpositive Growth, orchestration, and Golden tests. The ADR fixture preserves a valid Number and reports unsupported evidence. |
| Existing derivation behavior | Existing zero-treasury regression caught a lineage modelling error during development; the corrected separate raw-share type passes without weakening outstanding-share validation. |

Original managed gate, 2026-09-10 UTC (superseded by the follow-up below):

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

- Ruff check: passed; format check: 302 files clean.
- Strict mypy: passed for 234 source/test files.
- Pytest: **2,001 passed**, versus the R1 baseline of 1,944.
- Reported overall coverage: **89%** (line and branch report).
- Isolated artifacts: `.tmp/quality-runs/20260910041810868-35796-bafd8dbd6b4741ca99f35771fab8335e/`.
- Additional explicit execution of the two review-document regressions and the
  four-document boundary regression: **3 passed**.

The original tests used synthetic data and injected transports; the production-composition
tests block socket connections. No operational database was migrated or used
as a fixture. No dependencies changed. Live SEC transport availability is not
established by that gate; the earlier offline inspection of the reviewed KO
filing supplements rather than replaces deterministic evidence.

## Follow-up: reported live KO failure

The original completion claim was premature. The user subsequently demonstrated
that `graham-number KO --no-cache` still returned `unsupported_evidence`.
The retained KO filing parsed successfully, but verifying its stockholders'
equity source failed: the verifier rejected every dimensioned occurrence of
that concept, including ordinary equity-component and investee disclosures.
Those disclosures coexist with the correct entity-wide total. The original
synthetic fixture omitted them, and parsing the real document alone did not
exercise source-value verification.

The corrected verifier excludes dimensioned disclosures from candidate
entity-wide totals. It still requires an exact aggregate source value, period,
and unit; conflicting aggregate values fail. The independent document-wide
share-class check still rejects financial share-class dimensions. It does not
use a component or investee value as an aggregate fallback.

The shared synthetic filing now includes equity-component and investee contexts,
so the real SEC/facade/service/CLI tests exercise the failing shape. This change
reproduced the user's unavailable result before the production fix. Additional
tests require the aggregate, reject conflicting totals, prevent component-value
substitution, and preserve financial share-class rejection.

Live verification on 2026-09-10 used the real configured providers and SEC
transport. `graham-number KO --no-cache` returned `Price relationship: 314.11%
above the Graham Number`. The existing zero-TTL setting was then applied for
one normal KO invocation to replace the legacy entries through ordinary cache
writes; the setting was restored afterward. A subsequent unmodified
`graham-number KO` returned the same relationship with cached EPS and BVPS.
The observed Graham Number was 21.14 USD and quote 87.55 USD. These are dated
smoke-test observations, not promised future output. No schema migration or
cache deletion was performed. The user guide now documents this existing
refresh mechanism and distinguishes it from `--no-cache`.

Follow-up managed gate: **2,004 tests passed**, **89% reported coverage**,
Ruff/format and strict mypy clean. Artifacts:
`.tmp/quality-runs/20260910064416352-40976-7aa4a661fcf7448fbf963b704a5fbf57/`.
This replaces the original 2,001-test run as the final verification record.

## Review limits and next gate

This is deliberately limited current-only evidence acquisition, not universal
equity support or exhaustive intervening-corporate-action detection. Historical,
ADR/ADS, ambiguous-class, unsupported-provider, and unverifiable-source cases
remain unavailable. Source-document failures can still suppress comparison.

Old cached inputs without source lineage remain unavailable with refresh guidance.
`--no-cache` obtains fresh inputs for that run; it does not rewrite old cache
entries. No automatic cache purge, schema change, migration, or durable filing
cache is part of this repair. JSON consumers pinned to version 3 must explicitly
accept version 4.

Review and accept R2/R3 before resuming Step 3.3A at its existing planning gate.
Step 3.4 remains deferred. Publication requires its own explicit authorization.
