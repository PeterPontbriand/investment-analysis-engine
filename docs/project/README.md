# Project & Technical Documentation

This section is for implementation, architectural review, project planning, and engineering evaluation.

If you want to install or use Financial Data Agents, start with the [Investor & User Documentation](../user/README.md).

## Current work — single source of truth

**Active milestone:** v0.2<br/>
**Completed step:** Step 2.3 — dual-method Graham valuation and investor-facing direct analysis — complete and approved<br/>
**Next planned step:** Step 2.4 — Golden Suite and evaluation — not started<br/>
**Detailed Step 2.3 completion record:** [Step 2.3 Graham Slice Plan](milestones/v0.2/STEP_2_3_GRAHAM_SLICE_PLAN.md)<br/>
**Governing Step 2.3 design:** [Step 2.3 Graham Design](milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md)

Update **this section** when the active milestone, step, or slice changes. General user documentation and the root README should link here rather than duplicating current project status.

## Project-wide documents

- [Master Plan](MASTER_PLAN.md) — project direction, milestone ordering, and long-term scope.
- [Architecture](ARCHITECTURE.md) — current architectural boundaries and approved target seams.
- [Discovery Workbook](DISCOVERY_WORKBOOK.md) — rationale, alternatives, decisions, and product/engineering context.
- [Milestone plans](milestones/) — implementation plans plus step/slice specifications for each milestone.
- [`deploy/`](deploy/) — deployment/configuration artifacts intended for project development and review.

User-facing financial semantics remain authoritative in:

- [Financial Math & Data Conventions](../user/FINANCE_MATH.md)
- [Glossary](../user/GLOSSARY.md)
- [Analysis Strategy Guides](../user/strategies/README.md)

## Documentation authority for implementation work

Unless a more specific approved task says otherwise, use the following precedence:

1. the explicit implementation request, issue, or agreed task currently being worked on;
2. the active milestone implementation plan identified above;
3. the applicable step design and slice/execution plan;
4. the Master Plan;
5. the Architecture Guide and Discovery Workbook;
6. specialized references such as Financial Math and strategy guides; and
7. convenience/readme material.

If governing documents conflict, surface the conflict rather than blending incompatible requirements.

## Documentation conventions

- The root README and `docs/user/` describe the product without duplicating active milestone/step/slice status.
- This index is the single documentation navigation point for **current** milestone, step, and slice work.
- User-facing analysis details belong in strategy guides; project design contracts belong here.
- Every implemented deterministic analysis strategy should have its own user-facing guide under `docs/user/strategies/`.
- General documentation should give each analysis strategy only a short overview and link to its strategy guide. Formula details, assumptions, data-source choices, interpretation, reasons other calculators may disagree, and method-specific limitations belong in that strategy guide and/or Financial Math.
- Relative links must be updated whenever documentation is moved.
- When two or more glossary-defined terms appear together as an adjacent list, sequence, or contrast, and any term in that group is linked to the Glossary, link **all** glossary-defined terms in that adjacent group. This consistency rule overrides the normal preference to link only a term's first occurrence in a document.
- Human-readable terminology must not be mechanically derived from internal machine identifiers when explicit display wording is required.
- Use the word **path** when it literally means a filesystem path, URL path, or another technically precise path. Avoid using it as vague shorthand for a data source, provider configuration, workflow, operating mode, or implementation choice.
- Intentional Markdown hard line breaks in changed material use `<br/>` rather than trailing spaces.
