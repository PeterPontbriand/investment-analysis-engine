# Deferred — Deduplicate Momentum's Instrument-Profile Composition Sites

**Status:** deferred; not started; scope/contract review required before implementation.
**Discovered:** 2026-09-21, during the P2-Profiles Slice D reconnaissance
([inventory](p2-profiles/P2_PROFILES_SLICE_D_INVENTORY.md#2-composition-pattern-map)),
and raised again during PR #39 review.
**Not a blocker:** this does not block P2-Profiles acceptance or any other
active v0.2 work package. It is recorded here so it is not lost, not to
claim priority over anything already sequenced.

## Trigger

P2-Profiles Slice D needed a complete inventory of every production
instrument-profile composition call site before it could wire the durable
cache into any of them. That inventory found Graham Number/Growth and FCF
Growth already share exactly one composition helper
(`src.workspace.graham_shared.compose_graham_profile`), reached from both
their direct CLI commands and watchlist refresh — but Momentum has never had
an equivalent shared helper, and now has three independently duplicated
inline copies of the same `_identity_candidate()`-closure-over-a-fresh-
`YFinanceClient()` pattern:

- `src/cli.py`'s `momentum` command, `--save-run` branch
- `src/cli.py`'s `momentum` command, default branch
- `src/cli_workspace.py`'s `_execute_momentum` (watchlist refresh)

## Problem

Three copies of the same composition logic means three places that must be
kept in sync by hand. P2-Profiles Slice D already had to touch all three
individually to thread `CachedInstrumentProfileResolver`/`profile_cache`
through each one; any future change to how Momentum's identity/kind
candidates are constructed carries the same tripled maintenance cost, with
no compiler or test failure forcing the third copy to be remembered if only
two are updated.

This is a maintainability observation, not a correctness defect: nothing
about the current tripled logic is wrong, and P2-Profiles' own production
wiring is complete and correct with the duplication left in place.

## Likely scope, once picked up

- Extract a `compose_momentum_profile`-style helper (naming TBD) into a
  shared module — most naturally alongside `src/workspace/graham_shared.py`,
  or its own `src/workspace/momentum_shared.py` if Momentum's identity/kind
  candidate construction doesn't fit Graham's helper signature cleanly
  (Momentum uses one `YFinanceClient` as both the identity and kind
  candidate; Graham's helper supports a primary/Yahoo precedence split that
  Momentum has never needed).
- Update all three call sites (`cli.py` ×2, `cli_workspace.py`) to use the
  shared helper, preserving the exact existing candidate construction,
  `profile_cache` threading, and CLI/refresh behavior established by
  P2-Profiles Slice D.
- Update the affected tests' patch targets
  (`src.cli.compose_instrument_profile`, and any new equivalent for
  `cli_workspace.py`) to the new shared helper's location.

## Out of scope for this note

This is not a request to change Momentum's identity/kind candidate
construction, provider precedence, or the `CachedInstrumentProfileResolver`
wiring P2-Profiles already established at each of the three sites — only to
collapse three duplicated copies of identical logic into one.
