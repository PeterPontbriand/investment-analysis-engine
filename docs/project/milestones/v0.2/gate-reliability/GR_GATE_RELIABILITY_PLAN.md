# GR — Gate Reliability: Plan

Makes the local quality gate leave the evidence a failure needs, and removes the cause of its intermittent
failures once that cause is found. The [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) owns its
position and work-package status.

## 1. At a glance

- **What this work does:** GR.1 makes the gate wrappers keep their complete output, time each step and name each
  failing test. GR.2 follows a lead on the intermittent `WinError 10055` failures: event loops and sockets that
  tests leave open.
- **What it is not:** a change to what the gate checks, to its order, to its arguments, to its isolation directories
  or to its exit codes, and not a change to any strategy, formula or output.
- **Rules every slice follows:** the complete managed gate, with the 3.14 pass, at the end of the slice; no
  dependency change; `pyproject.toml` changes only with the project owner's explicit permission; explicit
  authorization before the next slice.
- **Where the detail lives:** the work is small enough that each slice's section below carries it; background and
  decisions are after the acceptance criteria and in [Appendix A](#appendix-a-decision-records).

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| GR.1 | [The gate wrappers keep their evidence](#gr1--the-gate-wrappers-keep-their-evidence) | In progress | |
| GR.2 | [Unclosed event loops](#gr2--unclosed-event-loops) | Planned | |

## 3. The slices

### GR.1 — The gate wrappers keep their evidence

- **Problem:** issues [#116](https://github.com/PeterPontbriand/investment-analysis-engine/issues/116) (a failing test
  that was never identified) and [#112](https://github.com/PeterPontbriand/investment-analysis-engine/issues/112) (gate
  run time varies with no known cause) stalled because the output was filtered and the wrappers reported no
  per-step timing.
- **Decision:** each wrapper writes its complete, unfiltered output to a file in the run's own directory while still
  printing it, and prints that file's path last; each step prints its elapsed time when it ends; each pytest pass
  lists its failing and erroring tests by full name; a closing summary shows every step, its time and its result,
  and the total. The PowerShell and shell wrappers print the same summary.
- **Scope:** `scripts/run-quality-gates.ps1`, `scripts/run-quality-gates.sh`, the managed-agent quality-gate section
  of `AGENTS.md` and the quality-gate section of `docs/project/README.md`; this plan and its milestone row.
- **Branch:** `chore/gate-wrapper-evidence`, from `main`.
- **Detail:** the three items (full output kept, step timings, failing tests named) are stated in
  [Quality gates](../../../README.md#quality-gates).

### GR.2 — Unclosed event loops

- **Problem:** the local gate has failed four times with `OSError: [WinError 10055]` (Windows ran out of socket
  buffers), in a different test each time, each passing on rerun ([#116](https://github.com/PeterPontbriand/investment-analysis-engine/issues/116)
  and its comments). Gate output carries warnings that Python prints when an asyncio event loop is discarded
  unclosed (`_ssock`, "never awaited"). On Windows each event loop holds a socket pair, so unclosed loops could
  exhaust socket buffers over a long run. This is a lead, not a cause.
- **Decision:** run the suite once with `ResourceWarning` raised as an error to name each test that leaves a loop or
  socket open; fix each at its source; then make such a leak fail the suite permanently through pytest's warning
  settings. Close #116 with the cause found, or record that none was found.
- **Scope:** the tests and any application code that leave a loop or socket open; one line of pytest warning
  settings in `pyproject.toml`, which needs the project owner's explicit permission before the slice edits it.
- **Branch:** `fix/gr-2-unclosed-event-loops`, from `main` after GR.1 has merged. It does not run while a LAY
  slice's branch is open.
- **Detail:** ⚠ no slice plan yet

## 4. Scope limits and acceptance criteria

Scope limits:

- Any change to the checks the gate runs, their order, their arguments, the isolation directories or the exit codes.
- Any formula, classification, command output, schema or stored-value change.
- A new dependency, or a change to `uv.lock`.
- Any change to `pyproject.toml` without the project owner's explicit permission.

Acceptance criteria:

- **Evidence kept (GR.1):** a gate run leaves its complete output in the run's own directory, the last line printed is
  its path, and the file equals what the terminal showed.
- **Timings and failures (GR.1):** each step prints its time, each pytest pass names its failing and erroring tests,
  and the closing summary lists every step with its time and result; a deliberately failing test is named, the
  summary shows the failure, and the exit code is not zero.
- **Same on both shells (GR.1):** the PowerShell and shell wrappers print the same summary.
- **Leaks named and closed (GR.2):** every test that leaves a loop or socket open is named and fixed, and a new leak
  fails the suite.
- **Quality gate:** the complete managed gate, with the 3.14 pass, at the end of every slice.

## 5. Background and origin

**Discovered:** while closing LAY.3 (2026-10-13), the 3.14 pass failed in
`tests/test_strategy_wiring_conformance.py` with `WinError 10055` while creating an event loop. The same error had
failed the gate three times before, in other tests, and each test passed when run again. The gate output that would
have shown the pattern across those runs had been filtered or not kept, and the wrappers gave no per-step timing, which
is also what kept the run-time spread in #112 unexplained.

**Why two slices:** keeping the evidence is a change to developer tooling only, and the next occurrence of the failure
is then recorded in full. The event-loop lead changes tests and possibly application code, and runs after GR.1 so
that it starts from kept evidence.

---

## Appendix A: Decision records

### A.1 Two slices (2026-10-13)

The project owner decided that the wrappers keep their evidence first (GR.1) and that the event-loop lead is a
separate slice (GR.2). GR.1 changes nothing the gate checks.

### A.2 GR.2 starts from a lead, not a cause (2026-10-13)

Unclosed event loops are a lead because the gate output carries the warnings Python prints for a discarded loop and
because a Windows loop holds a socket pair. No test has been shown to leak enough to exhaust the buffers. GR.2 closes
[#116](https://github.com/PeterPontbriand/investment-analysis-engine/issues/116) with the cause it finds, or records
that it found none.
