# Deferred — Standard Delivery Surfaces

**Status:** deferred; own scoped work package once picked up, but not to be scheduled until
after [Step 3.5](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).
**Reconsider at:** the close of [Step 3.5](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#4-out-of-scope), which links back here.
**Discovered:** 2026-09, via the [evidence provider roadmap](../../../EVIDENCE_PROVIDER_ROADMAP.md)'s
"Standard delivery surfaces" candidate.
**Decision:** the project owner confirmed this becomes its own work package rather than folding
into an existing one (per the reasoning that motivated `IR`), and explicitly deferred scheduling
it until Step 3.5 lands, rather than treating it as urgent now.
**Not a blocker:** this does not block R3, IR, PKG, or Step 3.5. It is recorded here so it is not
lost, not to claim priority over anything already sequenced.
**Narrowed 2026-10-30:** the HTTP API moved out of this note into work package
[API](../api/API_CONTRACT_AND_SLICE_PLAN.md), with a separate GUI application as its first consumer. This note
now covers the MCP server and Parquet/Arrow export. When it is taken up, decide also whether either sits on the
API's application layer or on the HTTP API itself.

## Trigger

The evidence provider roadmap's "Standard delivery surfaces" idea bundles several distinct
integration mechanisms under one heading: an MCP server over the existing dispatcher, an HTTP API
with an OpenAPI spec, published JSON Schemas, and Parquet/Arrow export for cross-sectional
batches. Published JSON Schemas are already in scope as [IR](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)
item 7 (typed envelope models plus generated schemas for the existing `--json` payloads); the
HTTP API is owned by [API](../api/API_CONTRACT_AND_SLICE_PLAN.md) since 2026-10-30; the remaining
two — an MCP server and Parquet/Arrow export — are not currently owned by any work package.

## Problem

Neither remaining surface exists today. An agent framework that speaks MCP, or a batch-processing
consumer that wants columnar output, has no supported way to use this project's analyses other than
the CLI and its `--json` output, or the local HTTP API once [API](../api/API_CONTRACT_AND_SLICE_PLAN.md) lands.

## Likely scope, once picked up

- Decide which of the two surfaces to build first, and whether both are actually warranted
  or whether real consumer demand should narrow this before implementation — this project's own
  guardrails already caution against building speculative generality ahead of an actual need.
- An MCP server would most naturally sit over the existing `investment_analysis_engine/orchestrator` dispatcher, since
  that already exposes typed tool-call boundaries for the four analyses.
- Parquet/Arrow export is scoped to cross-sectional batches (multiple tickers at once), which does
  not exist as a capability today outside of watchlist refresh's own internal batching — this would
  need its own specification for what a "batch" means as an export unit.
- Each of these should reuse [IR](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)'s typed
  envelope models (once IR lands) rather than re-deriving a second serialization shape.

## Out of scope for this note

This is not a request to build either of these two surfaces now, or to commit to building both of
them — only to record that they were considered and deliberately deferred, not overlooked. A real
contract/slice plan, including which surface (if any) comes first, is future work once this is
actually picked up after Step 3.5.
