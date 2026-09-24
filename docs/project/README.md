# Project & Technical Documentation

This section is for implementation, architectural review, project planning, and engineering evaluation.

If you want to install or use Investment Analysis Engine, start with the [Investor & User Documentation](../user/README.md).

## Planning and status

The [milestone table](milestones/v0.2/IMPLEMENTATION_PLAN.md#sequence-and-status)
is the work-package status and sequencing source. Companion plans own local
slice tables. Review records retain evidence; Git retains approval and publication
history. Update the owner instead of copying status into indexes or other guides.

## Project-wide documents

- [Master Plan](MASTER_PLAN.md) — project direction, milestone ordering, and long-term scope.
- [Evidence Provider Roadmap](EVIDENCE_PROVIDER_ROADMAP.md) — non-authoritative candidate backlog of future strategies and platform features; the Master Plan and implementation plan remain authoritative for scope and sequencing.
- [Architecture](ARCHITECTURE.md) — current architectural boundaries and approved target seams.
- [Discovery Workbook](DISCOVERY_WORKBOOK.md) — rationale, alternatives, decisions, and product/engineering context.
- [Evaluations & Golden Suite](../EVALUATIONS.md) — Step 2.5 benchmark purpose, execution modes, scoring boundaries, fixtures, and maintenance rules.
- [Step 2.5 Golden Suite Slice Plan](milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md) — component contracts and local review gates.
- [Step 2.5 Gate M Review](milestones/v0.2/step-2.5/STEP_2_5_GATE_M_REVIEW.md) — independent checkpoint audit, blocking findings, mandatory Slice H scope, and Gate M re-entry criteria.
- [Step 2.5 Closeout Verification Record](milestones/v0.2/step-2.5/STEP_2_5_CLOSEOUT_RECORD.md) — complete quality-gate evidence, final deterministic metrics, explicit empirical absence, acceptance reconciliation, and verification limits.
- [SEC EDGAR FPI / IFRS D0 Mapping Record](milestones/v0.2/step-2.5a/SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md) — approved corrected foreign annual-form/IFRS mapping and explicit deferrals.
- [SEC EDGAR FPI / IFRS Slice Plan](milestones/v0.2/step-2.5a/SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md) — completed Step 2.5A implementation order, review gates, and acceptance criteria.
- [Step 2.5A D0 Evidence Freeze and Implementation Handoff](milestones/v0.2/step-2.5a/STEP_2_5A_D0_EVIDENCE_FREEZE.md) — frozen source/fixture checksums, exact test matrix, ownership audit, baseline, and mandatory Gate A decisions.
- [Step 2.5A A0 Identity/Security-Unit Boundary Review](milestones/v0.2/step-2.5a/STEP_2_5A_A0_REVIEW.md) — bounded identity/unit correction, fail-closed preservation, deterministic proof, and complete quality-gate evidence.
- [Step 2.5A Slice E Closeout Verification Record](milestones/v0.2/step-2.5a/STEP_2_5A_E_CLOSEOUT.md) — final approved scope, explicit deferrals, deterministic Golden result, and complete repository gate.
- [Step 2.6 Reliability Limits Slice Plan](milestones/v0.2/step-2.6/STEP_2_6_RELIABILITY_SLICE_PLAN.md) — reliability contracts and verification evidence.
- [Milestone plans](milestones) — implementation plans plus step/slice specifications for each milestone.
- [`deploy/`](deploy) — deployment/configuration artifacts intended for project development and review.

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

## Quality gates

Run the complete non-mutating repository gate from the repository root before requesting technical review or declaring implementation work complete:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src tests
uv run pytest
```

These commands verify lint, formatting, strict typing, deterministic unit/integration behavior, and the pytest-cov configuration in `pyproject.toml`. The project target is at least 85% aggregate line coverage; new financial-analysis code should directly cover meaningful branches and edge cases. Automated tests must not make real external API or LLM calls.

The commands above are the ordinary developer and CI interface. Managed agents whose sandbox cannot write to Windows user-profile temp/cache directories should run the portable wrapper for their active shell instead:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

The wrappers run the same four gates with `uv run --no-sync` and isolate writable pytest, coverage, mypy, Ruff, and UV artifacts under a unique ignored `/.tmp/quality-runs/` directory. They are safe for concurrent managed-agent runs and contain no machine-specific repository path. Developers with normal user-directory access do not need the wrappers.

When local repair is required, the recommended order is:

```bash
uv run ruff check --fix .
uv run ruff format .
uv run mypy --strict src tests
uv run pytest
```

The first two repair commands intentionally mutate files. Review their diff before rerunning the non-mutating gate. Do not install or update dependencies, edit `pyproject.toml` or `uv.lock`, or weaken a gate merely to obtain a passing result without explicit authorization.

## Documentation conventions

- The root README and `docs/user/` describe the product without duplicating active milestone/step/slice status.
- This index links to planning owners; it does not maintain work status.
- User-facing analysis details belong in strategy guides; project design contracts belong here.
- Every implemented deterministic analysis strategy should have its own user-facing guide under `docs/user/strategies/`.
- General documentation should give each analysis strategy only a short overview and link to its strategy guide. Formula details, assumptions, data-source choices, interpretation, reasons other calculators may disagree, and method-specific limitations belong in that strategy guide and/or Financial Math.
- Relative links must be updated whenever documentation is moved.
- When two or more glossary-defined terms appear together as an adjacent list, sequence, or contrast, and any term in that group is linked to the Glossary, link **all** glossary-defined terms in that adjacent group. This consistency rule overrides the normal preference to link only a term's first occurrence in a document.
- Human-readable terminology must not be mechanically derived from internal machine identifiers when explicit display wording is required.
- Use the word **path** when it literally means a filesystem path, URL path, or another technically precise path. Avoid using it as vague shorthand for a data source, provider configuration, workflow, operating mode, or implementation choice.
- Intentional Markdown hard line breaks in changed material use `<br/>` rather than trailing spaces.
