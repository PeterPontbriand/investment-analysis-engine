# Financial Data Agents Documentation

This directory contains project-wide reference material and milestone-specific implementation documentation.

## Project-wide documentation

These documents describe concepts, decisions, and conventions that apply across multiple milestones:

- [Master Plan](MASTER_PLAN.md) — project direction, milestone roadmap, scope, and sequencing.
- [Architecture](ARCHITECTURE.md) — system boundaries, component responsibilities, and architectural invariants.
- [Discovery Workbook](DISCOVERY_WORKBOOK.md) — design rationale, alternatives considered, and decision records.
- [Finance Math](FINANCE_MATH.md) — financial formulas, assumptions, units, and calculation policies.
- [Glossary](GLOSSARY.md) — financial, architectural, and project terminology.

Project-wide documents may describe work planned or introduced by a particular milestone, but they remain at the root of `docs/` because their subject matter continues beyond that milestone.

## Milestone documentation

Implementation plans and detailed specifications that belong to a particular milestone are grouped under [`milestones/`](milestones/).

### Milestone v0.2

Milestone v0.2 focuses on deterministic analysis foundations, telemetry, schema enforcement, and Graham valuation data contracts.

- [Implementation Plan](milestones/v0.2/IMPLEMENTATION_PLAN.md) — authoritative execution sequence and acceptance criteria for v0.2.
- [Step 2.3 Graham Design](milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md) — governing design for the dual-method Graham valuation and input-resolution layer.
- [Step 2.3 Graham Slice Plan](milestones/v0.2/STEP_2_3_GRAHAM_SLICE_PLAN.md) — bounded implementation slices, current status, coding-model workflow, and final cleanup requirements.

## Documentation conventions

- `MASTER_PLAN.md` governs project-level scope and milestone sequencing.
- A milestone's `IMPLEMENTATION_PLAN.md` governs work within that milestone.
- A step-specific design document governs the detailed contract for that step.
- A slice plan organizes implementation work but does not override its governing design or milestone plan.
- When documents disagree, follow the most specific approved document that is consistent with the higher-level plans, and resolve the inconsistency before implementation continues.
- Documentation must distinguish approved target design from functionality that is already implemented.
- Relative links must be updated whenever documentation is moved.
