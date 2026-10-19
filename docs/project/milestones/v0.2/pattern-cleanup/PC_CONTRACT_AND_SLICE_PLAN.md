# PC — Pattern Cleanup before Step 3.5: Contract and Slice Plan

Removes the patterns that the Step 3.5 strategies would otherwise copy, while the consolidation period still allows
interface changes.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work package does:** removes a small, fixed set of patterns that a contributor adding a Step 3.5
  strategy would copy from existing code: an option that can hold only one value, a word the project no longer uses
  for user-facing text, test helpers that hide their own setup, and a help screen that cannot be printed on a Windows
  console.
- **Why now:** `AGENTS.md` §0 still permits public interface and signature changes. Once Step 3.5 starts, seven
  strategies copy whatever is there, and §0 is removed.
- **What it is not:** a formula, classification or stored-shape change, a new strategy, or a sweep over code no
  Step 3.5 strategy would copy. The excluded issues and the reason for each are in [Out of scope](#4-out-of-scope).
- **Rules every slice follows:** this is a consolidation package under `AGENTS.md` §0, so it follows §0's rules: no
  formula or classification change, no NaN or Inf, no network or LLM calls in tests outside `live_network`, the full
  managed quality gate on every slice, and no AI or tool attribution. A slice's open decisions go to the project
  owner before implementation ([decision rule](#decision-rule)).
- **Where the history lives:** why this work package exists is in
  [Background](#6-background-origin-of-this-work-package); the decision record is in
  [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Each slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PC.1 | [Interfaces and names](#pc1--interfaces-and-names) | Planned | |
| PC.2 | [Test helpers](#pc2--test-helpers) | Planned | |
| PC.3 | [Help encoding](#pc3--help-encoding) | Planned | |

PC starts after SWC.8 completes and finishes before Step 3.5 begins. One more slice, PC.4, exists only if the project
owner decides [issue #111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111) in favour of a
shared mapping; see [Decision pending: #111](#decision-pending-111).

## 3. The slices

### PC.1 — Interfaces and names

- **Problem:** two patterns a new strategy would copy. `--data-provider` is an option that accepts only `sec_edgar`
  ([#143](https://github.com/PeterPontbriand/investment-analysis-engine/issues/143)); `AGENTS.md` §9 already records it
  as a known exception. User-facing failure text is called a "sentence" in names and docs, where the project's word is
  "message" ([#140](https://github.com/PeterPontbriand/investment-analysis-engine/issues/140)); the inventory in that
  issue predates the package rename and must be refreshed first.
- **Decision:** to be decided by the project owner before implementation. For #143 the question is: remove the option,
  or keep it for a planned second provider? For #140 the rename follows the issue once its inventory is current.
- **Scope:** the option, its tests and its documentation (#143); every name, test and document in the refreshed
  inventory (#140). A stored shape is not changed.
- **Branch:** to be named when the slice starts.
- **Detail:** ⚠ no slice plan yet

### PC.2 — Test helpers

- **Problem:** two test patterns a new strategy's tests would copy. CLI test isolation is switched on by an import that
  looks unused ([#148](https://github.com/PeterPontbriand/investment-analysis-engine/issues/148)). The Alembic setup is
  repeated across tests ([#145](https://github.com/PeterPontbriand/investment-analysis-engine/issues/145)), which is also
  item 3 of [#156](https://github.com/PeterPontbriand/investment-analysis-engine/issues/156).
- **Decision:** to be decided by the project owner before implementation.
- **Scope:** the test helpers and the tests that use them. No production code.
- **Branch:** to be named when the slice starts.
- **Detail:** ⚠ no slice plan yet

### PC.3 — Help encoding

- **Problem:** `fcf-growth --help` crashes on a console that uses the cp1252 code page
  ([#147](https://github.com/PeterPontbriand/investment-analysis-engine/issues/147)). Every strategy command is
  generated with the same help pattern, so each Step 3.5 command would inherit the defect.
- **Decision:** to be decided by the project owner before implementation. The slice adds a test that every command's
  help encodes in cp1252.
- **Scope:** the help text that cannot be encoded, and the one test.
- **Branch:** to be named when the slice starts.
- **Detail:** ⚠ no slice plan yet

### Decision pending: #111

[Issue #111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111) asks whether every strategy uses
one shared mapping from statuses to a run outcome. The project owner decides it before PC starts.

- **If yes:** it becomes slice PC.4, with the same Problem, Decision, Scope, Branch and Detail sections, and a row in
  the sequence table.
- **If no:** it stays with Step 3.5.0, as
  [Appendix A.9 of the Step 3.5 contract](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a9-one-shared-mapping-from-statuses-to-a-run-outcome-question-from-esc-29-2026-10-10)
  already records.

### Decision rule

- Each slice's open decisions go to the project owner before implementation. An open item is not an acceptable outcome
  of a design decision in the consolidation period (`AGENTS.md` §0): the slice decides, or escalates.

## 4. Out of scope

- [#156](https://github.com/PeterPontbriand/investment-analysis-engine/issues/156) except item 3 (which is #145 and is in
  PC.2): the other items reduce gate run time and change no pattern a strategy copies.
- [#112](https://github.com/PeterPontbriand/investment-analysis-engine/issues/112) and
  [#116](https://github.com/PeterPontbriand/investment-analysis-engine/issues/116): both wait for the evidence that GR.3
  collects.
- [#149](https://github.com/PeterPontbriand/investment-analysis-engine/issues/149): a v0.3 decision about how the engine
  connects to a language model.
- Any formula, classification, stored-shape or strategy change, and any new framework, registry or factory.

## 5. Acceptance criteria

- **No formula or classification change.** A calculation believed incorrect is reported, not fixed here.
- **Quality gate:** the complete managed gate, with at least 85% line coverage, after every slice.
- **Each slice** removes the pattern it names and adds the test that keeps it removed; the slice's plan names that
  test.
- **Completion record:** each slice's row is updated to Complete with its date in the same change, and the next row is
  set to Next.

## 6. Background: origin of this work package

The SWC.7b independent review and the preparation for Step 3.5 listed the open issues a first Step 3.5 strategy
would hit or copy. Most describe a pattern, not a defect: a strategy author reads existing code to learn the
conventions and reproduces what is there. On 2026-10-19 the project owner chose to clean these up in one work package
placed after SWC and before Step 3.5, while `AGENTS.md` §0 still allows interface changes.

## Appendix A: Decision records and history

### A.1 PC created and its first slices (2026-10-19)

Decision of the project owner, 2026-10-19; this plan records it and implements nothing.

- **New work package PC**, a consolidation package under `AGENTS.md` §0, with slices PC.1 (interfaces and names:
  #143 and #140), PC.2 (test helpers: #148 and #145) and PC.3 (help encoding: #147).
- **#111** is decided by the project owner before PC starts; yes makes it PC.4, no leaves it with Step 3.5.0.
- **Placement.** Its row in the milestone plan is numbered `14B` so the other rows keep their numbers, and it sits
  after SWC and before Step 3.5.
- **Out of scope**, with reasons: #156 except #145, #112 and #116, and #149 ([§4](#4-out-of-scope)).
