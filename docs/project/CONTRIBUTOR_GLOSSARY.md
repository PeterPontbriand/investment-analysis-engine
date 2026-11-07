# Contributor Glossary

This glossary defines terms for people who change the code, the tests or the project's tooling. Terms an investor meets are in the [user glossary](../user/GLOSSARY.md), which this page may link to; the user glossary never links back here. Formula semantics live in [Financial Math & Data Conventions](../user/FINANCE_MATH.md).

Every entry follows the rules in [Glossary entries](README.md#glossary-entries): a permanent id on its own line above the heading, and a first paragraph that is a short definition.

---

## Analysis architecture

<a id="base-analyzer"></a>
### BaseAnalyzer
The common base class of every analysis strategy's analyzer. It gives all strategies one way of being invoked.

An [analysis strategy](../user/GLOSSARY.md#analysis-strategy) is implemented as an analyzer class that subclasses BaseAnalyzer. User documentation standardizes on analysis strategy rather than using internal class terminology as the product concept. Supporting multiple analyzers does not imply a separate strategy registry or plugin framework.

<a id="method-discriminator"></a>
### Method Discriminator
A stable field that tells the software which configuration, input requirements, calculation and result model apply to a strategy's own method.

<a id="discriminated-union"></a>
### Discriminated Union
A typed set of alternative models selected by a discriminator. It prevents invalid combinations of fields.

For example, it prevents supplying a growth rate to a Graham Number request or omitting growth-policy information from a Graham Growth Value result.

<a id="input-resolution-layer"></a>
### Input-Resolution Layer
The code between a request and a deterministic calculator. It obtains each required field and returns typed resolved inputs.

Each field comes from an explicit override, a valid cache entry, a configured provider, or a deterministic fixture.

<a id="resolved-input"></a>
### Resolved Input
An input value packaged with the information needed to interpret and reproduce it, such as units, source, dates and transformations.

That information includes units, source, provider field or series, reporting period, the as-of date, retrieval time, transformations, and override or cache status.

<a id="heterogeneous-strategy-independence"></a>
### Heterogeneous Strategy Independence
The principle that materially different strategies may use different inputs and outputs while sharing one invocation envelope.

Generic orchestration must not assume all analysis is Momentum.

---

## Market data architecture

<a id="base-data-client"></a>
### BaseDataClient
The historical-price provider boundary used by deterministic analyzers and data consumers.

Investment Analysis Engine supplements it with a separate financial-facts provider and resolution boundary for current quotes, company financial facts, macro observations, and valuation-cache semantics, rather than enlarging BaseDataClient into a generic financial-data interface.

<a id="fixture-adapter"></a>
### Fixture Adapter
A deterministic, no-network implementation of the data contracts, used to validate resolution behavior and run Golden cases.

It must never silently fall back to a live provider.

<a id="fixture"></a>
### Fixture
Version-controlled test data with fixed values and metadata.

The same fixture and configuration must produce the same resolved inputs and analytical results on every run.

<a id="production-persistence"></a>
### Production Persistence
SQLite and cache-backed durable access for persistent application data: market data, required financial facts, macro observations and telemetry.

Production persistence is separate from Golden fixtures.

---

## Evaluation

<a id="golden-benchmark-suite"></a>
### Golden Benchmark Suite
The project's deterministic benchmark of typed cases, fixtures, expected behavior and independently verified numerical results.

<a id="tool-selection-correctness"></a>
### Strategy/Tool-Selection Correctness
Whether the runtime selected the appropriate registered deterministic capability and supplied valid arguments for the case.

For example, it checks for Graham Number rather than Graham Growth Value, or either rather than Momentum. Each strategy is its own registered capability, so this single category covers both distinctions; there is no separate, narrower category for choosing between strategies that happen to share a fundamentals-valuation family.

<a id="numerical-correctness"></a>
### Numerical Correctness
Whether deterministic Python output matches independently verified expected values within case-specific tolerance.

<a id="overall-case-pass"></a>
### Overall Case Pass
Whether all required case-level acceptance criteria pass.

A correct strategy choice does not rescue an incorrect deterministic result, and vice versa.

<a id="deterministic-evaluation-mode"></a>
### Deterministic / No-LLM Mode
A test mode that validates fixtures, contracts, analyzers, evaluator logic and report serialization without a live model.

It cannot measure actual LLM strategy selection.

<a id="local-model-evaluation"></a>
### Real-Local-Ollama Evaluation
An empirical evaluation mode that measures actual local-model behavior.

It remains separate from deterministic regression testing.

<a id="golden-fixture"></a>
### Golden Fixture
A fixed, reviewable data set used by a Golden case.

It includes enough provenance and timestamps to reproduce the expected resolved inputs and numerical outputs without a network call.

<a id="numerical-tolerance"></a>
### Numerical Tolerance
The permitted difference between a calculated value and an independently verified expected value.

It accommodates controlled floating-point or rounding effects without masking substantive errors.

---

## Reliability and observability

<a id="trajectory-telemetry"></a>
### Trajectory Telemetry
Machine-readable structured execution history used to record observable application behavior.

<a id="operational-logging"></a>
### Operational Logging
Human-oriented runtime diagnostics.

It is separate from trajectory telemetry and from investor-facing result presentation.

<a id="circuit-breaker"></a>
### Circuit Breaker
Configured hard limits on execution steps, retries or errors, or wall-clock time that prevent unbounded execution.

<a id="wal"></a>
### WAL (Write-Ahead Logging)
A SQLite mode that allows readers to continue while writes are serialized appropriately.

---

## Software acronyms

<a id="ci"></a>
### CI (Continuous Integration)
Automated checks run when changes are proposed, including formatting, linting, type checking and tests.

<a id="dao"></a>
### DAO (Data Access Object)
A typed component that reads or writes persistent data while keeping database details out of analyzers and orchestration code.

<a id="di"></a>
### DI (Dependency Injection)
Providing a component's dependencies from outside rather than constructing them inside it.

It allows an analyzer to use a live provider, cache or deterministic fixture without changing its calculation code.

<a id="pr"></a>
### PR (Pull Request)
A proposed set of repository changes submitted for review before merge.

<a id="pydantic"></a>
### Pydantic
The Python validation library used to define typed request, configuration, result and telemetry models.

<a id="sql"></a>
### SQL (Structured Query Language)
The language used to define and query relational databases.

<a id="jsonl"></a>
### JSONL (JSON Lines)
A text format containing one JSON object per line.

Investment Analysis Engine uses JSONL for structured trajectory-telemetry records.
