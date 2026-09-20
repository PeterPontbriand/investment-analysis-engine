# Deferred — Prefix Matching for Analysis Run/Refresh IDs

**Status:** deferred; not started; scope/contract review required before implementation.
**Discovered:** 2026-09-20 (America/Toronto), during review of `runs show`'s
error message for an invalid Analysis Run ID.
**Not a blocker:** this does not block Step 3.4 acceptance or any other
active v0.2 work package. It is recorded here so it is not lost, not to
claim priority over anything already sequenced.

## Trigger

`runs show RUN_ID` and `runs list --refresh-id` both require an exact,
full UUID (`SQLiteAnalysisRunRepository.get()`/`RunQuery.refresh_id` compare
by equality). `runs list`'s own text output prints that full 36-character
UUID with no shorter handle next to it, so a user who wants to act on a
result they just listed has to copy-paste the whole thing exactly — there
is nothing resembling git's short-hash convenience. A user hitting the
resulting "not a valid Analysis Run ID" error may reasonably have assumed a
typed prefix (`0562...`) would resolve the way a git short hash does; it
does not, and nothing in the CLI says so until this error, which the
2026-09-20 message fix now names as "not a shortened or partial value."

## Problem

Full UUIDs are exact-match-only today, everywhere they are accepted:
`runs show RUN_ID`, `runs list --refresh-id`. There is no shorter,
typeable, still-unique-enough handle a person can use instead, unlike a
watchlist's entries (Amendment A1 gave those a 1-based display index
specifically because typing/reading a full identifier is bad UX for a
non-technical investor-user — the same underlying concern applies here).

## Likely scope, once picked up

- A repository-level prefix lookup (`SQLiteAnalysisRunRepository`, and the
  equivalent for refresh IDs via `RunQuery`), most naturally a `LIKE
  'prefix%'` query bounded by a minimum prefix length (mirroring git's
  4-character floor) to keep an accidental one- or two-character prefix
  from matching an unreasonable number of rows.
- Explicit ambiguity handling: zero matches is today's "not found"; more
  than one match needs its own clear error (likely listing the matching IDs
  with enough context — ticker, method, completed-at — to tell them apart
  and ask for more characters) rather than silently picking one.
- CLI-level: `runs show`/`runs list --refresh-id` would need to try a
  full-UUID parse first and fall back to prefix lookup, or accept a prefix
  unconditionally and treat a full UUID as the single-character-run limit
  of the same lookup — a design decision, not just an implementation detail.
- Whether `runs list`'s own text and `--json` output should print a
  shorter handle alongside the full ID (closer to git's abbreviated-hash
  display) is a related but separable display question.

## Out of scope for this note

This is not a request to change Analysis Run ID generation (still a full
UUID, unabbreviated, as the durable identifier) or to add prefix matching
anywhere outside `runs show`/`runs list --refresh-id`.
