# Spec Template

The fixed shape of a unit spec in the [spec workflow](SPEC_WORKFLOW.md). A spec is a handoff to the implementer, not a
planning document: it follows this template instead of the planning document structure in
[`AGENTS.md` §4](../../AGENTS.md#planning-document-structure).

## How to use it

- Copy the skeleton below to `specs/<unit>.md` in the folder of the plan that owns the unit, for example
  `docs/project/milestones/v0.2/step-3.5/specs/3.5.5a.md`.
- Replace every section's guidance with the unit's content, and keep the headings in this order. A section with
  nothing to say states that in one line ("None.") rather than being removed.
- The spec is complete when it is committed: no placeholder, no open question, no guidance text from this template.
  Missing information is found, or asked of the project owner, before the spec is committed.
- The spec links to the owning plan for decisions, inventories and formulas, and does not restate them.

## Skeleton

````markdown
# Spec <unit>: <title>

- **Owning plan:** link to the plan section that owns the unit.
- **Branch:** the branch name, as the owning plan names it, and the `main` commit it starts from.
- **Decisions approved:** the date the project owner approved the decision list.

## Goal

One or two sentences: what is true once the pull request merges, and for whom.

## Decisions

One line per approved decision this unit implements: its identifier, a short statement, and a link to its record in
the owning plan's decision appendix. A spec makes no decision of its own.

## Out of scope

What this unit does not do, including the changes a careful implementer might be tempted to make on the way, and the
later unit that owns each when there is one.

## Allowed files

Every file the unit may change or create, one per line, with what may change in it when that is narrower than the
whole file (for example "§7 only"). New files are listed by their exact paths. A change to any other file is an
escalation.

## Steps

Numbered steps, in order. Each says exactly what to change and ends with its check: the slice check when the step
changes Python source, tests or a file the gate's tooling parses or executes; otherwise the documentation checks. The
last steps run the full gate, commit with the title from PR text, and push the branch. The implementer does not open
the pull request.

## Norms and safeguards

A link to the escalation table in `AGENTS.md` §11, the repository rules this unit is most likely to meet (for example:
no new dependency, no attribution, a persisted shape's version bump, issue #116 evidence), and any escalation that is
particular to the unit.

## Acceptance checks

Observable results, each with the command that shows it: the gate results, smoke checks with their expected output
(an `ian` command run with `IAN_CONFIG_DIR`, `IAN_DATA_DIR` and `IAN_LOG_DIR` under `.tmp/`, or a request to the local
HTTP API), and `git --no-pager diff --stat origin/main...HEAD` listing only allowed files.

## Report

What the implementer reports when it finishes: at least the commit hash, the diff stat, the `gate-output.txt` path of
the full gate run, the result of each acceptance check, every escalation with the table row that triggered it, and
the counts the pilot measures ask for.

## PR text

The pull request's title, in the form `AGENTS.md` §11 sets, and its complete description, including `Closes #N` for
every issue the change resolves. No attribution.

## Change log

One dated line per correction made to this spec after its first commit, saying what changed and why.
````

## What each section is for

| Section | Purpose |
| :--- | :--- |
| Header | Ties the spec to its plan, its branch and its starting point |
| Goal | Lets the implementer and the reviewer judge a step against its purpose |
| Decisions | Shows which approved decisions the unit implements, without restating them |
| Out of scope | Stops scope creep before it starts |
| Allowed files | Makes the edit boundary of [`AGENTS.md` §4](../../AGENTS.md#implementation-preservation) checkable |
| Steps | The work, in order, each with its check |
| Norms and safeguards | The rules most at risk in this unit, and where to escalate |
| Acceptance checks | What the review checks first: behaviour |
| Report | What the implementer hands back, so nothing needs to be asked for |
| PR text | The pull request description, so nothing is written by hand later |
| Change log | Keeps the spec a true record when reality differed from it |
