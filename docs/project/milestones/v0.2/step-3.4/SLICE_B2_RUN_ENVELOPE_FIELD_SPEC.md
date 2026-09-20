# Slice B2 — Run Envelope Field Spec (Final, Reviewed)

**Contract:** `step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md`
**Slice:** B2 (Run envelope) — prerequisite B1 accepted
**Status:** Reviewed and finalized after three Cline design-plan rounds. This is the
authoritative spec for implementation — not a starting point to be reinterpreted.

This table incorporates every correction across three review rounds, plus two
additional fixes found on final cross-check against the contract (`config_schema_version`
and `native_reason` were both present in round 2 and silently dropped by round 3
with no note — both are restored below).

---

## Supporting types

- **`RunOutcome(StrEnum)`**: `completed`, `unavailable`, `not_applicable`, `failed`,
  `cancelled` — terminal only. No `running` value. (§4: *"a versioned, immutable
  terminal record"*; *"no `running` row is required."*)
- **`JsonValue`**: `bool | int | float | str | None | list[JsonValue] | dict[str, JsonValue]`,
  with a recursive validator rejecting NaN/Inf and any non-primitive.
- **`StrictJsonMapping`**: `dict[str, JsonValue]`.
- **`EffectiveBoundary(BaseModel)`**, frozen: `start: date | None = None`,
  `end: date | None = None`; invariant `end >= start` when both present.
  *(Flagged: dates rather than timestamps is a reasonable design choice, not
  literal contract text — confirm before implementation if you disagree.)*

---

## `AnalysisRun` — frozen, `extra="forbid"`

### Identity  [§4 L65]

| Field | Type | Default | Notes |
|---|---|---|---|
| `analysis_run_id` | `UUID` | required | PK |
| `refresh_id` | `UUID \| None` | `None` | paired with `batch_position` |
| `batch_position` | `int \| None` (`ge=0`) | `None` | zero-based; paired with `refresh_id` |
| `watchlist_id` | `UUID \| None` | `None` | paired with `watchlist_name` |
| `watchlist_name` | `str \| None` | `None` | snapshot; survives later rename/delete |
| `telemetry_run_id` | `UUID \| None` | `None` | correlation only, no FK |

### Request  [§4 L66; §3 method matrix]

| Field | Type | Default | Notes |
|---|---|---|---|
| `ticker` | `str` | required | normalized, non-empty |
| `analysis_id` | `str` | required | canonical — restored (dropped in round 3) |
| `method_id` | `str` | required | canonical |
| `config_schema_version` | `int` (`ge=1`) | required | restored (dropped in round 3) |
| `requested_config` | `AnalysisSelection` | required | B1's discriminated union |
| `effective_config` | `AnalysisSelection \| None` | `None` | null when nothing materialized before failure/cancellation — reverted round 3's regression |

Consistency rule: `analysis_id` / `method_id` / `config_schema_version` must equal
`requested_config`'s own values, and `effective_config`'s values when present.

### Time  [§4 L67]

| Field | Type | Default | Notes |
|---|---|---|---|
| `started_at` | aware `datetime` | required | both timestamps required — reverted round 3's regression |
| `completed_at` | aware `datetime` | required | must be `>= started_at` |
| `requested_as_of` | aware `datetime \| None` | `None` | |
| `effective_boundary` | `EffectiveBoundary \| None` | `None` | |
| `source_observation_dates` | `tuple[date, ...]` | `()` | |
| `source_retrieval_at` | aware `datetime \| None` | `None` | |

### Versions  [§4 L68]

| Field | Type | Default | Notes |
|---|---|---|---|
| `run_schema_version` | `Literal[1]` | `1` | this envelope's schema |
| `method_version` | `int` (`ge=1`) | required, explicit | |
| `result_schema_version` | `int` (`ge=1`) | required, explicit | |
| `evidence_codec_version` | `int` (`ge=1`) | required, explicit | |
| `projection_version` | `Literal[1]` | `1` | |

### Outcome  [§4 L69, L74]

| Field | Type | Default | Notes |
|---|---|---|---|
| `status` | `RunOutcome` | required | |
| `native_status` | `CalculationStatus \| None` | `None` | |
| `native_reason` | `str \| None` | `None` | restored (dropped in round 3) — contract says preserve native status/reason |
| `failure_reason_code` | `str \| None` | `None` | required non-empty iff `status == failed` |

### Evidence / Presentation  [§4 L70–72, L74]

| Field | Type | Default | Notes |
|---|---|---|---|
| `result_evidence` | `StrictJsonMapping \| None` | `None` | required non-null iff `status == completed`; optional for all other statuses, including `unavailable` (that status is *defined by* missing evidence) |
| `presentation_inputs` | `StrictJsonMapping \| None` | `None` | |

---

## `AnalysisRunSummary`  [§5 L89 — indexed columns exactly]

| Field | Type |
|---|---|
| `analysis_run_id` | `UUID` (PK) |
| `ticker` | `str` |
| `method_id` | `str` |
| `status` | `RunOutcome` |
| `completed_at` | aware `datetime` (ordering key) |
| `refresh_id` | `UUID \| None` |

No `analysis_id`, no `started_at` — §5's column list doesn't name either; this
differs from the full envelope on purpose.

---

## `RunQuery`  [§5 L98 — filters exactly]

| Field | Type | Default |
|---|---|---|
| `ticker` | `str \| None` | `None` |
| `method_id` | `str \| None` | `None` |
| `status` | `RunOutcome \| None` | `None` |
| `refresh_id` | `UUID \| None` | `None` |
| `limit` | `int` (`ge=1, le=100`) | `20` |
| `offset` | `int` (`ge=0`) | `0` |

---

## `Watchlist`  [§3, §5 L86]

| Field | Type | Default | Notes |
|---|---|---|---|
| `watchlist_id` | `UUID` | required | |
| `display_name` | `str` | required | preserved spelling |
| `normalized_name` | `str` | required | `display_name.strip().casefold()`, used for uniqueness |
| `created_at` | aware `datetime` | required | |
| `updated_at` | aware `datetime \| None` | `None` | |
| `members` | `tuple[str, ...]` | `()` | ordered, unique |
| `selections` | `tuple[AnalysisSelection, ...]` | `()` | distinct `method_id` per entry |

## `WatchlistSummary`

| Field | Type |
|---|---|
| `watchlist_id` | `UUID` |
| `display_name` | `str` |
| `member_count` | `int` (`ge=0`) |
| `selection_count` | `int` (`ge=0`) |
| `created_at` | aware `datetime` |
| `updated_at` | aware `datetime \| None` |

---

## Validation rules

**`AnalysisRun`:**
1. `completed_at >= started_at`
2. `status == failed` ⇒ `failure_reason_code` non-empty
3. `status == completed` ⇒ `result_evidence` not null — all other statuses optional
4. `analysis_id` / `method_id` / `config_schema_version` match embedded config(s)
5. `EffectiveBoundary.end >= start` when both present
6. All floats in evidence/presentation finite; JSON primitives only
7. Ticker normalized
8. `refresh_id` ⟷ `batch_position` and `watchlist_id` ⟷ `watchlist_name` both-set-or-both-null
9. Version fields are strict `int` (not `bool`/`float`)

**`Watchlist`:**
- **W1** — no duplicate `method_id` across `selections`
- **W2** — `members` unique, order preserved
- **W3** — `display_name` non-empty after trim; `normalized_name` matches the derived form and is non-empty

---

## Open items flagged for confirmation (genuine ambiguity, not errors)

- `EffectiveBoundary` as dates rather than timestamps — reasonable default, not
  stated outright in the contract.
- §4's Failure row says *"reason code/message"* — this spec keeps only
  `failure_reason_code` (matching every prior review round). If a separate
  human-readable `failure_message` field is wanted, add it before implementation.
