# Spec Workflow

How a unit of work goes from an approved decision list to a merged pull request through a spec committed on the
unit's branch, instead of a prompt pasted into the implementer's session. The workflow is being piloted on Step 3.5
slice 3.5.5 ([A.21](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a21-spec-workflow-pilot-on-355-2026-11-19));
[§7](#7-pilot-on-355) says how the pilot is judged and what happens after it.

## 1. At a glance

- **What it is:** one Markdown spec per unit of work, written from the [spec template](SPEC_TEMPLATE.md) and committed
  on the unit's branch before implementation starts. The implementer is given the spec's path and nothing else. The
  spec author and the implementer settle questions and review findings between themselves, through the spec.
- **What it is not:** a replacement for plans. The plan that owns the unit still owns its decisions, file inventories
  and records; the spec links to them and adds what a handoff needs. There is no separate analysis document, no
  baton or loop-state file and no automation outside the repository's own gate and CI ([§8](#8-left-out)).
- **Rules it follows:**
  - A spec is complete when it is committed: no placeholder, no open question, no template guidance left in it.
  - The spec is corrected first whenever reality differs from it ([§4](#4-when-reality-differs-from-the-spec)).
  - The implementer escalates by the table in [`AGENTS.md` §11](../../AGENTS.md#escalation-in-a-spec-driven-unit).
  - The project owner approves every decision list and every pull request opening, and merges every pull request
    ([`AGENTS.md` §11](../../AGENTS.md#11-user-approval-gates)).
- **Where it applies:** during the pilot, the sub-slices of 3.5.5 only. Other work keeps the prompt handoff until
  the pilot's outcome is recorded.

## 2. Roles

| Role | Who | What they do |
| :--- | :--- | :--- |
| Project owner | The repository owner | Approves or amends each decision list; answers escalations that would change a decision, scope, a dependency or anything that cannot be undone; approves opening each pull request; merges |
| Spec author | The agent that drafts the decision list and reviews the work | Writes the spec (and the slice plan, when the unit needs one); answers the implementer's questions within the approved decisions; corrects the spec; reviews; escalates to the project owner what the approved decisions do not settle |
| Implementer | A coding agent working in the project owner's checkout on the development machine | Implements the spec within its allowed files; runs the gate; reports; escalates by the table in [`AGENTS.md` §11](../../AGENTS.md#escalation-in-a-spec-driven-unit) |

## 3. The flow

1. **Decision list.** The spec author lists the unit's open decisions, each with a recommendation. The project owner
   approves or amends them. The approved decisions are recorded with their identifiers in the decision appendix of
   the plan that owns the unit, as before.
2. **Spec.** The spec author copies the [spec template](SPEC_TEMPLATE.md) to `specs/<unit>.md` in the folder of the
   plan that owns the unit (for 3.5.5a: `docs/project/milestones/v0.2/step-3.5/specs/3.5.5a.md`), fills every
   section, and commits it as the first commit of the unit's branch, named as the owning plan says. When the unit's
   slice plan does not exist yet, the first spec's steps write it, as 3.5.3a did.
3. **Implementation.** The implementer checks out the branch and implements the spec's steps in order, changing only
   its allowed files. It runs the slice check after each step that changes Python source, tests or a file the gate's
   tooling parses or executes, and the full gate once before pushing ([§6](#6-the-quality-gate-in-the-flow)). It
   escalates instead of improvising.
4. **Behaviour first.** Before review, the implementer reports what the spec's Report section asks for: at least the
   commit hash, the diff stat against `main`, the `gate-output.txt` path of the full gate run, the result of each
   acceptance check and smoke check, and every escalation with the table row that triggered it.
5. **Review.** The spec author reviews in this order: behaviour (the gate output, CI, the smoke checks), then
   architecture and the [architectural invariants](ARCHITECTURE.md#2-architectural-invariants), then logic and
   financial correctness, then scope (only allowed files changed, nothing beyond the spec). Each finding is tagged
   **spec change** or **code fix**. A spec change is committed to the spec before the code changes. A small defect is
   fixed in the branch before the pull request opens, or filed as an issue that the spec's PR text names; it is never
   left as a note. Review repeats until no finding remains.
6. **Pull request.** The spec's PR text is the pull request's title and description; it names every issue the change
   resolves with `Closes #N`. The pull request is opened once the project owner approves, and the project owner
   merges it. The merged spec stays in the repository as the record of what was built.

## 4. When reality differs from the spec

The implementer never settles a difference in code. When a step cannot be done as written, because the spec is
ambiguous, misses a decision, or contradicts the code, its plan or another current document, the implementer stops
that step and escalates to the spec author. The spec author corrects the spec, adds a dated line to its change log,
commits, and tells the implementer to continue. A correction that would change an approved decision goes to the
project owner first, and the owning plan's decision record is updated with it.

## 5. Escalation

The escalation table is in [`AGENTS.md` §11](../../AGENTS.md#escalation-in-a-spec-driven-unit), the one place it is
written. Every spec's Norms and safeguards section links to it rather than restating it, and adds any escalation that
is particular to the unit.

## 6. The quality gate in the flow

- **Slice check after each step.** The wrapper with `-Slice` / `--slice` ([`AGENTS.md` §7 and §10](../../AGENTS.md#7-tdd-verification--coverage)),
  after each spec step that changes Python source, tests or a file the gate's tooling parses or executes. A
  documentation-only step runs the documentation checks that [Quality gates](README.md#quality-gates) names.
- **Full gate once per pull request.** The wrapper with no mode option, before the branch is pushed for review, and
  also for a step that changes the strategy generator, its templates, sites or fills, or the strategy wiring.
- **CI is the authority** for Python 3.12 to 3.14 on Windows, macOS and Linux. The extra-interpreter pass is used only
  to reproduce a version-specific CI failure.
- **Agent hook.** The pilot's first spec, 3.5.5a, adds a hook that runs the slice check whenever the implementer ends
  its turn and sends any failure back to it, so it cannot report a step done on a failing check. The hook's
  configuration file is in that spec's allowed files.

## 7. Pilot on 3.5.5

Every sub-slice of 3.5.5 is handed off through a spec. The 3.5.5 slice plan's implementation record holds a table,
"Spec workflow pilot measures", with one row per sub-slice and one column per measure below. The implementer reports
the counts; the spec author fills the row before the sub-slice's pull request opens.

| Measure | Target |
| :--- | :--- |
| Prompts, PR texts or review findings the project owner copied by hand between agents | 0 |
| Project owner actions beyond approving decisions, answering escalations, approving the pull request opening and merging | 0 |
| Changes outside the allowed files, or in an escalation category, made without an escalation | 0 |
| Escalations, each with the table row that triggered it | Recorded; no target |
| Review rounds after the first review | At most one per sub-slice, on average across 3.5.5 |
| Differences between the merged spec and what was built | 0 |
| Defects found after merge that the spec's acceptance checks should have caught | 0 |

**Outcome.** After the last 3.5.5 sub-slice merges, and before the 3.5.4 slice plan is accepted, the project owner
decides one of three outcomes, recorded as a decision record in the
[Step 3.5 plan](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#appendix-a-decision-records-and-history):

- **Adopt:** every later unit is handed off through a spec. The change that records the outcome removes the pilot
  wording from this document and from `AGENTS.md`, and the desktop repository receives the same documents.
- **Adjust:** the record lists what changes and the work package that tries the adjusted workflow next. Until then,
  other work keeps the prompt handoff.
- **Drop:** the change that records the outcome removes this document, the spec template, and the spec-workflow
  rules in `AGENTS.md` §2, §4, §11 and §12. The 3.5.5 specs stay as records of what was built.

## 8. Left out

| Left out | Why |
| :--- | :--- |
| Separate analysis documents, design canvases, generated user stories and generated test prompts | Decision lists and slice plans already cover them; they serve team auditing and would cost time here |
| Custom slash commands for the workflow | The spec path is the whole instruction |
| A baton or loop-state file between agents | The spec author and the implementer message each other directly, and the spec carries the lasting record |
| Orchestration through GitHub Actions | One unit runs at a time, and the project owner approves each pull request |
| Separate worktrees per agent | One unit runs at a time on one branch |
