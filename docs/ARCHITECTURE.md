# Financial Data Agents Architecture

**Related roadmap:** `MASTER_PLAN.md`  
**Active implementation detail:** `MILESTONE_v0_2_IMPLEMENTATION_PLAN.md`  
**Rationale:** `DISCOVERY_WORKBOOK.md`  
**Last updated:** 2026-08-19  
**Current status:** Step 2.2 implementation complete / merge-ready; Step 2.3 is the next architectural foundation step.

This document describes architectural boundaries. It does not override the active milestone plan's sequencing or review gates.

---

## 1. Architectural invariants

1. **LLM orchestration, deterministic execution:** The LLM plans/selects tools and synthesizes results; Python performs calculations, validation, data processing, and persistence.
2. **Typed boundaries:** Tool/analyzer/data inputs and outputs are explicitly typed at application boundaries.
3. **Heterogeneous strategies:** Different financial strategies may have different config/data/result shapes. The architecture must not make every analysis Momentum-shaped.
4. **No speculative strategy framework:** Reuse the existing `BaseAnalyzer` and current tool dispatch path unless implementation proves a new abstraction is necessary.
5. **Provider isolation:** External data providers remain behind `BaseDataClient`/provider adapters.
6. **Historical data and current quote are distinct capabilities:** Step 2.3 makes this distinction explicit.
7. **Evaluation is not persistence:** Golden fixtures, evaluation results, trajectory telemetry, and production market-data storage are separate concerns.
8. **Local-LLM boundary:** The LLM cannot directly execute shell/code or access the external network. Registered data tools may perform controlled provider access.
9. **Telemetry is observational:** Telemetry failures must not change business execution semantics.
10. **Light Mode first:** Core useful analysis must remain viable under the documented Light Mode path.

---

## 2. Current and near-term architecture

```text
                               CLI / caller
                                   │
                                   ▼
                         Agent Orchestrator
                   context + structured-output policy
                                   │
                                   ▼
                         Tool / analysis dispatch
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
          MomentumAnalyzer                 GrahamValueAnalyzer
          (existing)                       (Step 2.3)
          SMA/crossover                     intrinsic value / MOS
                   │                               │
                   └───────────────┬───────────────┘
                                   ▼
                          BaseAnalyzer boundary
                                   │
                                   ▼
                           BaseDataClient
                      ┌────────────┴────────────┐
                      ▼                         ▼
              historical series            current quote
                  Momentum                    Graham
                      │                         │
                      └────────────┬────────────┘
                                   ▼
                        provider / fixture adapter
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
                live provider               fixture data
                  adapter                    Step 2.3/2.4
                     │
                     ▼
             SQLite/cache persistence
                    Step 3.1
```

`BaseAnalyzer` is the existing common analyzer abstraction. The diagram does **not** imply a new strategy registry, plugin system, factory hierarchy, or unified strategy-result model.

---

## 3. Core entities and boundaries

### `BaseAnalyzer`
Existing abstract analysis boundary. A strategy owns:
- its configuration model;
- deterministic calculation;
- typed result/metrics;
- only the data capabilities it actually requires.

### `MomentumAnalyzer`
Existing deterministic SMA/crossover analyzer. It consumes historical market data and returns Momentum-specific metrics.

### `GrahamValueAnalyzer`
Step 2.3 deterministic intrinsic-value analyzer. It consumes EPS/growth/yield assumptions and optionally/currently obtains a market quote through the data-client boundary for margin-of-safety comparison.

Graham is intentionally not required to return `TrendStatus` or consume a historical DataFrame merely to look like Momentum.

### `BaseDataClient`
Provider boundary for market data.

Before Step 2.3 it exposes historical data through `fetch_data(...)`. Step 2.3 extends the smallest clean provider-neutral capability needed for current-price/quote access.

Do not implement current quote retrieval by invoking a one-day historical request simply to avoid extending the interface.

### Fixture-backed data adapter
Introduced minimally in Step 2.3 to prove the shared market-data contract:
- deterministic;
- historical data for Momentum;
- quote data for Graham;
- explicit failure when data is absent;
- no live network fallback.

Step 2.4 reuses this foundation for Golden cases.

### `TrajectoryEvent` / `TrajectoryRecorder` / `TrajectorySink`
Step 2.1 structured telemetry components. JSONL is the initial sink; SQLite is added in Step 3.1.

Telemetry records observable execution evidence and does not provide benchmark ground truth.

---

## 4. Structured-output boundary

Step 2.2 establishes structured-output enforcement with layered defenses:

1. use native Ollama/provider schema constraints when capability is confirmed;
2. retain Pydantic validation at the application boundary;
3. use the configured prompt-based schema fallback when native capability is unavailable or unknown;
4. retain legacy compatibility parsing only as the final fallback where required.

Empirical model-by-model validation of native-schema behavior for the supported Light Mode configuration remains a non-blocking validation item before Step 3.5 completion.

Do not rewrite the runtime around a model-specific assumption merely to make one model pass.

---

## 5. Module layout

```text
src/
├── config.py
├── core/
│   ├── constants.py
│   └── telemetry/
│       ├── models.py
│       ├── recorder.py
│       ├── run_context.py
│       ├── redaction.py
│       └── sinks/
├── llm/
├── tools/
├── orchestrator/
├── data/
│   ├── base_client.py
│   ├── yfinance_client.py
│   ├── massive_client.py
│   └── repositories/
├── analysis/
│   ├── base.py
│   └── momentum/
├── reporting/
└── utils/
```

Step 2.3 adds Graham under `src/analysis/` according to current package conventions. Step 3 persistence/repositories remain under `src/data/repositories/`, consistent with the existing repository layout.

---

## 6. Data flow and persistence boundaries

The project distinguishes:

```text
External Provider
      │
      ▼
Provider Adapter / BaseDataClient
      │
      ├── historical series
      └── current quote
      │
      ▼
Deterministic Analyzer
      │
      ▼
Typed Analysis Result
```

Separately:

```text
Golden fixture data ──► fixture adapter ──► analyzer/tool execution
trajectory events   ──► telemetry sink
production data     ──► SQLite/cache repositories
evaluation result   ──► Golden report/artifact
```

These stores/artifacts must not be collapsed merely because they can all be serialized.

---

## 7. Golden-Suite architecture (Step 2.4)

Step 2.4 consumes the stable Step 2.3 contracts.

```text
Golden Case
   │
   ├── prompt/task
   ├── fixture IDs
   ├── expected strategy/tool behavior
   └── independently verified numeric expectations
   │
   ▼
real orchestration path
   │
   ├── structured strategy/tool evidence
   └── deterministic result
   │
   ▼
Evaluator
   ├── strategy/tool-selection score
   ├── numerical-correctness score
   └── overall case pass/fail
```

Deterministic/no-LLM tests validate fixtures, contracts, analytics, evaluator behavior, and report serialization. They cannot measure actual model strategy selection.

Real-local-Ollama evaluation is an empirical mode and remains separate from deterministic regression/CI tests unless explicitly configured.

The ≥90% target is a measurement target, not permission to weaken cases until a model passes.

---

## 8. Logging and telemetry boundary

Operational logging and trajectory telemetry remain separate:

```text
Agent Runtime
   │
   ├── operational logging ──► human-readable diagnostics
   │
   └── trajectory telemetry ─► machine-readable execution evidence
                                ├── JSONL (Step 2.1)
                                └── SQLite (Step 3.1)
```

Telemetry may capture observable provider/model metadata, prompts/completions, tool arguments/results, latency, and exposed token metrics subject to retention/redaction policy.

Private model reasoning is never reconstructed.

---

## 9. Failure and reliability boundary

- Recoverable failures may enter a bounded retry/repair path.
- Non-recoverable failures halt with structured diagnostics.
- Step 2.5 owns hard execution/time/error caps.
- The configured limits are authoritative; runtime documents must not invent a separate fixed turn limit.
- Telemetry sink failures fail open.

---

## 10. Development guardrails

- Preserve existing behavior outside the active step.
- Use the smallest change that satisfies the current milestone plan.
- Do not create a generic strategy registry merely to support Momentum + Graham.
- Do not build Step 2.4 evaluator/reporting work during Step 2.3.
- Do not build Step 3.1 production persistence/cache during Step 2.3/2.4.
- Use `src/data/repositories/` for the planned repository layer.
- Run Ruff, `mypy --strict`, and pytest according to the active milestone plan.
