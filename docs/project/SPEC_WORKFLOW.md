# Spec Workflow

How a unit of work goes from an approved decision list to a merged pull request through a spec committed on the
unit's branch, instead of a prompt pasted into the implementer's session. The workflow is being piloted on every
unit in both repositories from IAD issue #39 on (A.21, widened by A.22 in the Step 3.5 plan's
[decision records](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#appendix-a-decision-records-and-history));
[§7](#7-pilot) says how the pilot is judged and what happens after it.

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
- **Where it applies:** during the pilot, every unit in both repositories from IAD issue #39 on. The desktop
  repository receives the same documents in its own pull request.

## 2. Roles

| Role | Who | What they do |
| :--- | :--- | :--- |
| Project owner | The repository owner | Approves or amends each decision list; answers escalations that would change a decision, scope, a dependency or anything that cannot be undone; approves opening each pull request; merges |
| Spec author | The agent that drafts the decision list and reviews the work | Writes the spec (and the slice plan, when the unit needs one); answers the implementer's questions within the approved decisions; corrects the spec; reviews; escalates to the project owner what the approved decisions do not settle |
| Implementer | A coding agent (currently Sonnet 5.5 in Claude Code) on the project owner's development machine, started by the spec author through Remote Control in the owner's checkout; the owner's machine stays on while a unit runs | Implements the spec within its allowed files; runs the slice check; reports; opens the unit's pull request after a clean review; escalates by the table in [`AGENTS.md` §11](../../AGENTS.md#escalation-in-a-spec-driven-unit) |

## 3. The flow

1. **Decision list.** The spec author lists the unit's open decisions, each with a recommendation, in one list per
   slice that covers all its sub-slices. The project owner approves or amends them; approving the list also approves
   opening the unit's pull request once the spec author's review is clean. The approved decisions are recorded with their identifiers in the decision appendix of
   the plan that owns the unit, as before.
2. **Spec.** The spec author copies the [spec template](SPEC_TEMPLATE.md) to `specs/<unit>.md` in the folder of the
   plan that owns the unit (for 3.5.5a: `docs/project/milestones/v0.2/step-3.5/specs/3.5.5a.md`), fills every
   section, and writes it into the owner's checkout; the implementer commits it as the first commit of the unit's
   branch, named as the owning plan says. All GitHub writes happen on the owner's machine under the owner's identity. When the unit's
   slice plan does not exist yet, the first spec's steps write it, as 3.5.3a did.
3. **Implementation.** The implementer checks out the branch and implements the spec's steps in order, changing only
   its allowed files. It runs the slice check after each step that changes Python source, tests or a file the gate's
   tooling parses or executes, enforced by the Stop hook, and runs no full gate before pushing
   ([§6](#6-the-quality-gate-in-the-flow)). It escalates instead of improvising.
4. **Behaviour first.** Before review, the implementer reports what the spec's Report section asks for: at least the
   commit hash, the diff stat against `main`, the last slice-check result, the result of each
   acceptance check and smoke check, and every escalation with the table row that triggered it.
5. **Review.** The spec author reviews in this order: behaviour (the gate output, CI, the smoke checks), then
   architecture and the [architectural invariants](ARCHITECTURE.md#2-architectural-invariants), then logic and
   financial correctness, then scope (only allowed files changed, nothing beyond the spec). Each finding is tagged
   **spec change** or **code fix**. A spec change is committed to the spec before the code changes. A small defect is
   fixed in the branch before the pull request opens, or filed as an issue that the spec's PR text names; it is never
   left as a note. Review repeats until no finding remains.
6. **Pull request.** The spec's PR text is the pull request's title and description; it names every issue the change
   resolves with `Closes #N`. After a clean review the implementer opens the pull request with that text, the spec
   author watches CI and sends fixes, and the project owner gets one message that it is ready to merge, then merges
   it. The merged spec stays in the repository as the record of what was built.

**Fast lane.** A change with no decision in it (fixing a red `main`, fixing or quarantining a flaky test, a small
defect found after merge, a documentation correction) skips the decision list. The spec author writes a short spec and
the flow continues from step 2. A fast-lane change that turns out to need a decision goes to the project owner.

**Batching.** While a pull request waits for merge, the spec author may draft the next unit's decision list. One
implementer runs per repository at a time; one engine unit and one desktop unit may run at once.

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

Three tiers, each owning one question:

- **Inner loop: the slice check.** The wrapper with `-Slice` / `--slice` ([`AGENTS.md` §7 and §10](../../AGENTS.md#7-tdd-verification--coverage)),
  after each spec step that changes Python source, tests or a file the gate's tooling parses or executes. A
  documentation-only step runs the documentation checks that [Quality gates](README.md#quality-gates) names. For the
  implementer, `scripts/agent_stop_hook.py`, run by the Stop hook in `.claude/settings.json`, does this whenever a
  turn ends with files changed since the last passing run: it runs the documentation checks for a documentation-only
  change and the slice check otherwise, sends any failure back to the implementer (so it cannot report a step done on
  a failing check), never loops, and stops the implementer on issue #116 evidence.
- **Pull-request CI: the full check.** Ubuntu, Python 3.12 and 3.14, with coverage and the `slow` tests. No full gate
  runs locally before the push; the wrapper with no mode option is for reproducing a CI failure, or when the project
  owner or a spec asks for it.
- **After merge: every version and operating system.** Python 3.12 to 3.14 on Windows, macOS and Linux. A failure opens
  or updates the `main-red` issue and is fixed first, in the fast lane. The extra-interpreter pass is used only to
  reproduce a version-specific CI failure.

## 7. Pilot

Every unit in both repositories from IAD issue #39 on is handed off through a spec. Each unit's spec has a "Pilot
measures" line in its Report, with one value per measure below. The implementer reports the counts; the spec author
checks them before the unit's pull request opens.

| Measure | Target |
| :--- | :--- |
| Prompts, PR texts or review findings the project owner copied by hand between agents | 0 |
| Project owner actions beyond approving decisions, answering escalations, approving the pull request opening and merging | 0 |
| Changes outside the allowed files, or in an escalation category, made without an escalation | 0 |
| Escalations, each with the table row that triggered it | Recorded; no target |
| Review rounds after the first review | At most one per unit, on average across the pilot |
| Differences between the merged spec and what was built | 0 |
| Defects found after merge that the spec's acceptance checks should have caught | 0 |
| Pull-request CI wall time | Recorded; no target |
| CI runs that failed for a reason unrelated to the change | 0 |

**Outcome.** After the first three spec-driven units merge, across both repositories, the project owner decides one
of three outcomes, recorded as a decision record in the
[Step 3.5 plan](milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#appendix-a-decision-records-and-history):

- **Adopt:** every later unit is handed off through a spec. The change that records the outcome removes the pilot
  wording from this document and from `AGENTS.md`.
- **Adjust:** the record lists what changes and the work package that tries the adjusted workflow next. Until then,
  other work keeps the prompt handoff.
- **Drop:** the change that records the outcome removes this document, the spec template, and the spec-workflow
  rules in `AGENTS.md` §2, §4, §11 and §12. The specs stay as records of what was built.

## 8. Left out

| Left out | Why |
| :--- | :--- |
| Separate analysis documents, design canvases, generated user stories and generated test prompts | Decision lists and slice plans already cover them; they serve team auditing and would cost time here |
| Custom slash commands for the workflow | The spec path is the whole instruction |
| A baton or loop-state file between agents | The spec author and the implementer message each other directly, and the spec carries the lasting record |
| Orchestration through GitHub Actions | One unit runs at a time per repository, and the project owner approves each pull request; the `main-red` report is not orchestration |
| Separate worktrees per agent | One unit runs at a time on one branch |
