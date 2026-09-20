# B1 Phase 2A repair evidence

Repair started from Cline's uncommitted original selections and partially
repaired requests.
This record covers Momentum and Graham Number only. B1 acceptance remains
pending; Phase 2B and later work have not been implemented.

## Changes and focused proof

- Consolidated implementation in `src/workspace/requests.py` and tests in
  `tests/workspace/test_requests.py`, matching the approved allowlist.
  Package exports use the requests module. The superseded selections source
  was preserved under ignored
  `.tmp/phase2a-repair-ce693e72d6ab43fd9c4f583966faac0a/selections.py`.
- Fixed canonical analysis/method pairs and version-1 literals;
  `test_identity_overrides_rejected` verifies mismatched values are rejected.
- Enforced supported security/quote providers and finite financial overrides;
  provider and nonfinite rejection tests exercise each affected field.
  Finite zero/negative overrides still reach existing analyzer configurations.
- Restored positive Momentum window/RSI constraints, including valid RSI period
  1. Invalid-value tests supply other required fields and verify the error
  location, avoiding false positives from missing arguments.
- Used timezone-aware datetime validation and typed EPS-basis literals.
  Existing normalization and provider compatibility tests remain applicable.
- Verified caller/settings mutation isolation, independently converted configs,
  and JSON reconstruction/conversion without settings rereads. Fully explicit
  Momentum construction through `from_settings` also avoids settings access.

## Verification scope

Before edits, the original selections tests plus Momentum analyzer, Graham
config and BVPS-basis suites passed: **109 passed in 1.36s**. The command used
`uv run --no-sync pytest -o addopts= -p no:cacheprovider`, a unique
`.tmp/quality-runs/repair-baseline-*` base directory, and these files:

- `tests/workspace/test_selections.py` (subsequently renamed/repaired)
- `tests/analysis/momentum/test_momentum_analyzer.py`
- `tests/analysis/graham_value/test_analyzer_config.py`
- `tests/analysis/graham_value/test_bvps_basis_semantics.py`

The sandbox could not query the existing interpreter; verification used approved
elevated execution with repository-local managed artifacts and no dependency sync.
Intermediate checks found formatting and a typed normalization-test call mismatch;
these were corrected before the final gate.

Final command: `& scripts/run-quality-gates.ps1` from the repository root.
All checks passed: Ruff; formatting (335 files); strict mypy (251 files);
**2,400 tests in 88.67s**, including all **62 repaired workspace tests**.
Reported overall coverage is **90%**; requests module combined line/branch
coverage is **98%** (98 of 99 statements covered).
Full output: `.tmp/phase2a-repair-quality.txt`.
Isolated coverage and cache artifacts:
`.tmp/quality-runs/20260913165202428-25140-fafd0f6de32248a5af73c4698c51ac49/`.

Phase 2A repair is ready for review. The remaining Growth/FCF selections,
selection union, bound request, default selection builder and parser belong
to subsequent phases and are intentionally absent.

Unrelated Step 3.5/PIOTROSKI documentation is preserved. No dependencies,
existing analyzers, CLI, storage or financial calculators were changed.
No commit, push or PR was performed.
