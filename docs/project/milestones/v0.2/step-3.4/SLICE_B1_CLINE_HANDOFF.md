# Slice B1 — Typed Workspace Requests

## Authority and entry

Gate A was approved by the project owner on 2026-09-13 (America/Toronto).
The [contract](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md) owns slice status and gates;
its §3 method/config matrix owns the request semantics. This handoff makes B1
concrete without extending its scope. B2 and later slices require further review.

Work on `feat/step-3.4-local-research-workspace`, after the documentation checkpoint
is committed by the project owner. Verify that HEAD contains the readiness
closeout and this approved contract. Record the actual starting commit in the
completion evidence; do not substitute an older test baseline for verification
of the implementation.

## Allowed files and boundaries

- Add `src/workspace/__init__.py` and `src/workspace/requests.py`.
- Add `tests/workspace/test_requests.py` and a test-package initializer only if
  required by existing test conventions.
- Record B1 completion evidence in a companion document in this directory.

Do not edit existing analyzers, configs, calculators, presenters, CLI commands,
settings, dependencies, migrations or repositories. Do not create B2 models,
result codecs, run storage, execution adapters or refresh infrastructure.
The default builder returns typed selections, not a watchlist aggregate; it must
not depend on the future B2 watchlist model.

## Required interfaces

Use explicit typed variants in `requests.py`, with no generic registry:

1. Four selection variants, discriminated by canonical `method_id`, representing
   method configuration without a ticker. Define their union as `AnalysisSelection`.
   Each carries fixed `config_schema_version=1`; reject an unsupported version.
   Preserve the canonical analysis identifier from the contract matrix as a fixed
   value, not an independently editable field that can disagree with the method.
2. `AnalysisRequest` binds a normalized, nonempty ticker to a selection. Requested
   `as_of` and cache choices belong to the method configuration; do not duplicate
   mutable values at the request root. Momentum accepts no `as_of` option.
3. `parse_selection(alias: str, config_json: str) -> AnalysisSelection` accepts the
   four exact CLI aliases in the contract and the method-specific configuration
   object. It does not read a file; CLI file I/O belongs to F1. Reject unknown
   aliases, extra fields, malformed/non-object JSON, duplicate JSON keys and
   non-finite numeric values. Parse request configuration only, not result evidence.
4. `default_selections() -> tuple[AnalysisSelection, ...]` materializes Momentum,
   Graham Number and FCF Growth in that order, with the existing defaults. Never
   include Graham Growth automatically. Construct fresh independent values per
   call, and preserve earlier snapshots after settings or caller inputs change.

Model class names for the four variants are an implementation choice. Use
strict Pydantic models or equivalently validated typed structures consistent with
the contract. A frozen outer wrapper alone is insufficient if it retains a mutable
caller-owned `MomentumConfig`: copy and protect nested snapshot values. Typed
conversion back to existing analyzer configs must preserve their semantics.

The JSON bodies are `{"config": {...}}` for Momentum and both Graham methods;
FCF uses `{"policy": {...}, "currency": "USD", "provider_id": "sec_edgar",
"as_of": null, "use_cache": true}` with omitted fields taking the existing defaults.
An omitted `config`/`policy` object may use existing defaults for the three default
methods; Growth must still reject omitted required assumptions. Ticker, method,
analysis identifier and version cannot be overridden inside the config-file body.
Versions/discriminators belong to the typed selection, not the user body.

Apply the contract's field allowlists at the workspace boundary. In particular,
the current `MomentumConfig` does not itself forbid extra fields, and the FCF
policy is a dataclass; neither fact permits silently ignored workspace fields.
Validate nested values without changing those public types. Preserve existing
finite financial-value semantics: zero/negative values classified by execution
must not acquire new financial thresholds here. No calculator is invoked to
validate a request. Growth always requires explicit growth and AAA yield values.

Use native enum strings for FCF policy (`longest_available`, `3`, `4`, `5`;
`total_fcf`, `fcf_per_share`; `display_only`, `confirmation`, `hard_gate`). Preserve
Graham's provider-dependent EPS/quote defaults and Massive Number's required
`bvps_override`. Check supported provider choices against current CLI composition;
do not construct providers, fetch metadata or read credentials to validate them.
Effective Growth calculation-policy capture belongs to D3 execution evidence;
B1 does not read `_growth_assumptions()` or freeze a new user-editable policy.

## Verification and stop

Before editing, run the relevant existing config/model tests identified from
source inspection. After implementation, test:

- All four alias-to-canonical-identifier mappings and configuration version 1.
- Exact default selection order, absence of Growth, resolved defaults, and
  independence from later settings/caller mutation.
- Venue-suffixed ticker normalization and empty ticker rejection.
- Explicit Growth assumptions; Number/Growth foreign-field rejection; provider
  and EPS-basis compatibility; no invented forecast or new financial thresholds.
- FCF policy enum/default fidelity, currency normalization, aware optional time,
  and cache choice; Momentum rejects `as_of` and foreign fields.
- Malformed JSON, duplicate keys, unknown/nested extra fields, mismatched typed
  discriminators, unsupported versions and NaN/Inf rejection.
- Deterministic config JSON round trips without settings rereads, credentials,
  provider calls, storage or LLM activity. Result-evidence codecs remain deferred.

Run the complete managed quality wrapper specified in the contract. Report the
starting revision, files, API choices, focused tests, full gate and limitations.
Stop for B1 acceptance; do not start B2, commit, push or open a PR automatically.

## Phased Cline prompts

Send only the current phase's prompt. Each phase ends the agent turn and waits
for the next instruction; listing the phases here does not authorize automatic
continuation. These are execution checkpoints within B1, not new acceptance
slices. B1 acceptance still requires every interface and verification item above
and a passing full managed quality gate. B2 remains subject to B1 acceptance.

Implementation is divided into 2A–2C so the four variants, parser and complete
test suite do not have to be generated together. Add meaningful tests with each
increment; do not defer all testing until the end. Each checkpoint must leave
valid, complete code for the implemented subset, without stubs or placeholders.
An interface deferred to a later phase remains explicitly pending.

### Context and output discipline

- Follow AGENTS.md, this handoff and the approved contract. Read the contract's
  §3 request matrix and §§9–10 scope/review rules, plus other sections when a
  concrete dependency requires them. Do not repeatedly paste the full contract,
  handoff, source files or test logs into the conversation.
- Use edit/write tools for code and bounded edits for one coherent change at a
  time. Never paste an entire source file into chat. Tool-call payloads also
  need to remain small; using a write tool does not remove generation limits.
- Keep status reports to roughly 200 words: completed work, changed files,
  exact check commands/results, blockers and next phase. Prefer evidence paths
  and concise failure excerpts over full logs. Do not narrate every tool call.
- Do not rely on detecting an exact 8k-token threshold. If the next change is
  too large, finish the current coherent increment, report what remains and
  stop for a continuation instruction. Never truncate a file to meet a budget.
- Use `uv run --no-sync` and repository-local unique temp/cache locations for
  focused managed checks where needed; retain the full wrapper for acceptance.
  Test-generated ignored artifacts are permitted during verification.

Continue in the same Cline task while its context remains useful. For a fresh
task, supply this handoff path, the next phase prompt and the latest checkpoint
report. The report should retain the original starting commit, current HEAD,
baseline evidence, completed interfaces/tests and remaining work. Reinspect
Git status and relevant files rather than trusting a summary over current code.
Do not repeat unchanged baselines when their recorded revision and scope remain
valid; explain and rerun affected checks when the revision or relevant code differs.

### Phase 1 — Verification only (start or restart here)

```text
Work on Slice B1 ONLY. Follow AGENTS.md and
docs/project/milestones/v0.2/step-3.4/SLICE_B1_CLINE_HANDOFF.md,
including its linked Step 3.4 contract and output discipline.
Execute Phase 1 only, then report and stop for the next instruction.
Do not implement B2+, commit, push or open a PR.

Confirm the branch is feat/step-3.4-local-research-workspace. Verify that
HEAD contains readiness closeout 60eb55501f3b19cbbd92444dceb8d97acc7b9bf3
and the approved contract/documentation checkpoint. Record actual HEAD.
Inspect Git status and any existing B1 edits from the interrupted attempt;
preserve them and unrelated work. Do not reset or overwrite existing work.
Retain the original implementation starting commit if verified evidence exists;
otherwise distinguish the restart revision from an unknown original baseline.

Inspect the relevant existing configs/models and identify their focused tests;
the handoff specifies test categories, not an exact test-file list. Run those
existing tests and record commands/results. If prior B1 edits already exist,
do not describe today's run as a pre-edit baseline for those edits.
Report entry checks, baseline results, existing B1 progress and the next
unfinished phase. If entry requirements fail, report the blocker and stop.
Do not edit source, tests or documentation in this phase.
```

### Phase 2A — First typed selections and tests

```text
Execute B1 Phase 2A only under the handoff and approved contract. Confirm
Phase 1 entry checks passed. Inspect existing work before editing and preserve
completed valid changes. Stay within the B1 allowlist.

Create or extend src/workspace/__init__.py and src/workspace/requests.py.
Implement the Momentum and Graham Number selection variants with fixed
identifiers/version, strict field validation, independent immutable snapshots
and typed conversion to existing configs. Preserve defaults and financial
semantics. Add and run corresponding tests in tests/workspace/test_requests.py;
add a test-package initializer only if existing conventions require it.
Do not add placeholder interfaces for the remaining work.

Run the relevant focused tests, report results and remaining interfaces, then
stop. No full gate or completion claim yet. Do not commit, push, open a PR
or begin the next phase.
```

### Phase 2B — Remaining selections, request and defaults

```text
Execute B1 Phase 2B only under the same handoff, contract and allowlist.
Implement Graham Growth and FCF selection variants, AnalysisSelection,
AnalysisRequest and default_selections. Preserve explicit Growth assumptions,
FCF's distinct policy fields, ticker normalization, version/identifier checks,
typed config conversions and independent snapshots of resolved defaults.
Do not add the parser yet unless it already exists from the interrupted work;
preserve existing valid work rather than removing it to match phase order.

Add meaningful focused tests alongside these changes and run all current
tests/workspace/test_requests.py tests. Report results and remaining work,
then stop. Do not run the full gate, claim B1 completion, commit, push,
open a PR or begin the next phase.
```

### Phase 2C — Parser and complete boundary coverage

```text
Execute B1 Phase 2C only under the same handoff, contract and allowlist.
Implement parse_selection exactly as specified, using bounded edits. Add
parser tests incrementally, including malformed/non-object JSON, duplicate
keys, nonfinite values, aliases and nested extra-field rejection.
Audit every item in the handoff's Verification and stop checklist and close
remaining coverage gaps, including mutation isolation and deterministic
round trips. Do not invoke providers, credentials, storage or LLMs.

Run all B1 focused tests and the relevant existing config/model regressions.
Report exact results and any unresolved requirements, then stop for the
Phase 3 instruction. Do not claim full acceptance, commit, push or open a PR.
```

### Phase 3 — Full managed quality gate and evidence

```text
Execute B1 Phase 3 only under the handoff, contract and allowlist. Review the
complete B1 diff against the required interfaces and verification checklist.
Run from the repository in PowerShell:
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')

Fix B1-caused failures within the allowlist and rerun affected checks and the
full gate after code changes. Report unrelated failures or conflicts requiring
out-of-scope changes as blockers; do not silently broaden scope or claim a pass.

Write docs/project/milestones/v0.2/step-3.4/SLICE_B1_COMPLETION_EVIDENCE.md
with verified starting/restart revisions, changed files, concise API/snapshot
decisions, requirement-to-test mapping, exact focused/full-gate commands and
results, coverage, artifact paths and limitations. Distinguish verified facts
from missing evidence. Do not embed raw logs or repeat the full contract.
Label the outcome ready for B1 review only when requirements and checks pass;
approval remains pending. Give a concise final report and stop for B1 review.
Do not implement B2+, commit, push or open a PR.
```
