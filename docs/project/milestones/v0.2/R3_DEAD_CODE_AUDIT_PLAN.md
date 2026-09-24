# R3 — Repository-Wide Dead Code Audit

**Status:** next in sequence per `IMPLEMENTATION_PLAN.md` row 10; not yet started; scope/contract
review required before implementation, matching this project's convention for any nontrivial
work package.
**Discovered:** 2026-09-23, during ESC-D.4 reconnaissance (ESC-18's correction in
[the defect ledger](existing-strategy-correctness/ESC_A_DEFECT_LEDGER.md)).
**Why scheduled here:** deliberately placed before Step 3.5, which adds five new
quantitative-screen analyzers, so this audit covers a smaller, more tractable codebase than it
would after that expansion. See this milestone's own
[work-package identifiers list](IMPLEMENTATION_PLAN.md#sequence-and-status) for how this `R3` code
relates to (and is unrelated to) other `R`-prefixed identifiers in this project.

## Trigger

While live-testing Momentum end-to-end for ESC-D.4, tracing a suspected regression (ESC-18)
through `src/data/cached_client.py` found that the code path it described — two
`if error is not None: raise DataQualityError(error)` sites — was unreachable, and had been since
before the ESC-C baseline: the underlying `_quality_error` helper always raises internally
instead of returning a value whenever it is called the way those two sites call it. ESC-18 was
corrected in the ledger once this was confirmed; the dead code itself was not fixed as part of
ESC-D, since removing it is not an output-correctness concern within that audit's charter.

## Problem

That one confirmed instance was found only because an unrelated investigation happened to trace
through that exact function. There has been no deliberate, repository-wide search for other
unreachable code before now. The longer unreachable code accumulates, the more it can mislead a
future reader (or agent) about what a code path actually does, and the larger and more
error-prone a first audit becomes — which is exactly why this plan exists.

## Likely scope, once picked up

- A systematic pass over `src/` for unreachable branches, functions, classes, and files —
  not limited to the shape of the one confirmed instance (a branch whose guard condition can
  never be true given its caller's fixed arguments). Other shapes are plausible: unused private
  helpers, unreferenced modules, superseded code paths left behind by refactors (`R1`/`R2`,
  Step 3.4's execution-adapter extraction, P2-Profiles' cache wiring).
- A defensible method for distinguishing genuinely unreachable code from code that is reachable
  but merely untested or rarely exercised — this audit removes the former, not the latter.
- Removal, with the regression suite as the safety net: if removing something breaks a test, it
  was reachable and the audit was wrong about it, not the test.
- A brief evidence record (mirroring this project's other audit records) of what was found and
  removed, for the same reason ESC-A's ledger exists: so a future reader can see this happened
  and why, rather than rediscovering the same instances independently.

## Out of scope for this note

This is not a request to refactor, rename, or restructure reachable code encountered along the
way — only to find and remove code that cannot execute. A pre-existing rule violation or
stylistic issue in a file touched during this audit is not permission to fix it here; that
follows the same "opportunistic cleanup belongs in a separate task" boundary as any other work
package.
