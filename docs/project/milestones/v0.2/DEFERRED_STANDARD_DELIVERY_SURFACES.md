# Deferred — Standard Delivery Surfaces

**Status:** deferred; own scoped work package once picked up, but not to be scheduled until
after [Step 3.5](step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status).
**Discovered:** 2026-09, via the [evidence provider roadmap](../../EVIDENCE_PROVIDER_ROADMAP.md)'s
"Standard delivery surfaces" candidate.
**Decision:** the project owner confirmed this becomes its own work package rather than folding
into an existing one (per the reasoning that motivated `IR`), and explicitly deferred scheduling
it until Step 3.5 lands, rather than treating it as urgent now.
**Not a blocker:** this does not block R3, IR, PKG, or Step 3.5. It is recorded here so it is not
lost, not to claim priority over anything already sequenced.

## Trigger

The evidence provider roadmap's "Standard delivery surfaces" idea bundles several distinct
integration mechanisms under one heading: an MCP server over the existing dispatcher, an HTTP API
with an OpenAPI spec, published JSON Schemas, and Parquet/Arrow export for cross-sectional
batches. Published JSON Schemas are already in scope as [IR](integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)
item 7 (typed envelope models plus generated schemas for the existing `--json` payloads); the
remaining three — an MCP server, an HTTP API, and Parquet/Arrow export — are not currently owned
by any work package.

## Problem

None of these three remaining surfaces exist today. The project's only current consumer-facing
boundary is the CLI (`ian ...`) and its `--json` output. An external harness, agent framework, or
batch-processing consumer that wants to call this project's analyses programmatically, rather than
shelling out to the CLI, has no supported way to do so yet.

## Likely scope, once picked up

- Decide which of the three surfaces to build first, and whether all three are actually warranted
  or whether real consumer demand should narrow this before implementation — this project's own
  guardrails already caution against building speculative generality ahead of an actual need.
- An MCP server would most naturally sit over the existing `src/orchestrator` dispatcher, since
  that already exposes typed tool-call boundaries for the four analyses.
- An HTTP API and its OpenAPI spec would need an explicit decision on hosting/process model,
  authentication (if any), and how it relates to the CLI's own error/exit-code conventions.
- Parquet/Arrow export is scoped to cross-sectional batches (multiple tickers at once), which does
  not exist as a capability today outside of watchlist refresh's own internal batching — this would
  need its own specification for what a "batch" means as an export unit.
- Each of these should reuse [IR](integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)'s typed
  envelope models (once IR lands) rather than re-deriving a second serialization shape.

## Out of scope for this note

This is not a request to build any of these three surfaces now, or to commit to building all of
them — only to record that they were considered and deliberately deferred, not overlooked. A real
contract/slice plan, including which surface (if any) comes first, is future work once this is
actually picked up after Step 3.5.
