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
- [Analysis Strategy Development Guide](../TOOL_DEVELOPMENT.md) — the one guide for adding a strategy: the step-by-step workflow, the edit sites, the settings convention, and how a strategy fits into the code (the analyzer contract, execution/capture flow, and what's strategy-specific versus shared).
- [Provider Debugging Runbook](PROVIDER_DEBUGGING.md) — running the live provider checks and `ian health`, reading the scheduled run's kept results, and what a failed Yahoo or SEC EDGAR check means.
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
- [Milestone plans](milestones/README.md) — index of implementation plans plus step/slice specifications for each milestone.
- [`deploy/`](deploy) — deployment/configuration artifacts intended for project development and review.

User-facing financial semantics remain authoritative in:

- [Financial Math & Data Conventions](../user/FINANCE_MATH.md)
- [Glossary](../user/GLOSSARY.md)
- [Contributor Glossary](CONTRIBUTOR_GLOSSARY.md)
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

## Diagrams

Documentation contains no Mermaid. Draw a diagram as a plain text block or express it as a table; `scripts/check_doc_links.py` fails on a fenced block whose language is `mermaid`. The packages under `investment_analysis_engine/` and the imports between them are declared once, in the table in [Architecture §13](ARCHITECTURE.md#13-module-boundaries).

## Glossary entries

There are three audiences, and each term lives with one of them.

- **Investor terms** are in [`docs/user/GLOSSARY.md`](../user/GLOSSARY.md). An entry is interface-neutral: it contains no command, flag, command-line output convention or closed list of strategies.
- **Command-line terms** are in the user glossary's last section, which carries the exclude marker. They explain the command line and are not served as help content. No investor entry links to one.
- **Contributor terms** are in [`CONTRIBUTOR_GLOSSARY.md`](CONTRIBUTOR_GLOSSARY.md). It may link to investor terms; no investor entry links to it.

Every entry in both glossaries follows these rules, which `python scripts/check_help_content.py` checks:

- **Id:** a permanent id, lowercase ASCII words joined by single hyphens, written as `<a id="<id>"></a>` on its own line directly above the entry's heading. It is unique within its glossary and may equal its own entry's heading slug but not a different entry's. Every link to an entry targets the id, never the heading slug; `scripts/check_doc_links.py` fails a link that targets a slug.
- **Name:** the heading is plain text, with no code span. A combined heading stays one entry unless one short definition cannot cover its parts.
- **Short definition:** the first paragraph is at most 200 characters and two sentences, in plain text with no link, backtick, `*`, `_` or `[`. It stands alone; that is a review rule, not a checked one. Formulas and links belong in the paragraphs that follow.
- **Exclude marker:** `<!-- help:exclude -->` on the line directly after a heading excludes that section and its subsections from served content. There are no inline ranges.

## Served documents

The help bundle serves some user documents. Their rules are decided in [H24](milestones/v0.2/api/API_5_SLICE_PLAN.md#h24-served-sections-are-interface-neutral-2026-11-07), [H25](milestones/v0.2/api/API_5_SLICE_PLAN.md#h25-command-line-material-stays-in-its-guide-2026-11-07), [H27](milestones/v0.2/api/API_5_SLICE_PLAN.md#h27-the-leak-rules-2026-11-07) and [H28](milestones/v0.2/api/API_5_SLICE_PLAN.md#h28-command-names-in-code-spans-2026-11-07) of the API.5 slice plan.

- **Which documents:** the [Beginner Guide](../user/BEGINNER_GUIDE.md), [Finance Math](../user/FINANCE_MATH.md), the investor entries of the [user glossary](../user/GLOSSARY.md), and one guide per strategy, found as every `docs/user/strategies/*.md` except `README.md`.
- **Interface-neutral:** a served section contains no command, flag, option, environment variable, exit code or command-line output mode. It says "an analysis", not "a command".
- **Command-line material:** a section that is entirely command-line material carries the exclude marker. A mixed section ends with an excluded "On the command line" subsection, one heading level below it and its last subsection.
- **Leak rules:** `python scripts/check_help_content.py` fails served content on a code span that starts with `ian `, `--`, `uv ` or `IAN_`; a fenced block with an `ian` command line or in a shell language; and a link to a file that is not served, to an excluded section, to a term that is not served, or to the user glossary without an entry id.
- **Command names:** `tests/scripts/test_served_content.py` fails on a served code span that starts with the name of an `ian` command or command group, read from the Typer application.
- **The help bundle:** after editing a served document, regenerate the bundle with `uv run python -m scripts.generate_help`; the gate fails on drift. The generator refuses to write while scripts/check_help_content.py reports any problem, glossary entry rules included.

## Quality gates

Run the complete non-mutating repository gate from the repository root before requesting technical review or declaring implementation work complete, whenever the change touches Python source, tests, or any file the gate's own tooling actually parses or executes (this includes `pyproject.toml` fields that affect dependency resolution, build, or tool configuration):

```bash
python3 scripts/check_doc_links.py
python3 scripts/check_help_content.py
python3 scripts/check_sequence_tables.py
python3 scripts/check_package_dependencies.py
uv run python -m scripts.generate_openapi --check
uv run python -m scripts.generate_help --check
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict investment_analysis_engine tests scripts
uv run pytest
```

Standard-library-only gate scripts run with system Python (`py -3` on Windows), not through `uv run` or the project virtualenv.

These commands verify that every local link and heading anchor across every Markdown file resolves (files git tracks and new files git does not ignore, staged or not), that every planning sequence table is well formed and correctly ordered, that the package table in the Architecture Guide matches the imports between the top-level `investment_analysis_engine/` packages, lint, formatting, strict typing (including the `scripts/` developer tooling, not only `investment_analysis_engine`/`tests`), deterministic unit/integration behavior, and the pytest-cov configuration in `pyproject.toml`. The project target is at least 85% aggregate line coverage; new financial-analysis code should directly cover meaningful branches and edge cases. Automated tests must not make real external API or LLM calls. Real provider calls are permitted only in tests marked `live_network`, which are excluded from the default run and the managed gate, make at most three requests per check, assert response shape and never values, and never log or persist secrets.

A documentation-only change must pass `python scripts/check_doc_links.py`, `python scripts/check_help_content.py`, `python scripts/check_sequence_tables.py`, `python scripts/check_package_dependencies.py`, and both Ruff checks (`uv run ruff check .` and `uv run ruff format --check .`). A change to a served document must also pass `uv run pytest tests/scripts/test_served_content.py` and `uv run python -m scripts.generate_help --check`. Ruff lints and formats Python code blocks in Markdown, so prose-only edits can still affect Ruff results. CI runs MyPy and pytest for every pull request; those checks remain part of CI, but a documentation-only local gate may omit them unless the change also affects code or test behavior. A change confined to non-executable declarative metadata with no import-time or runtime effect — for example, a single project-metadata field such as `license` — does not require the full pytest run. Confirm the file still parses (e.g. the relevant `uv`/build command succeeds) and note in the record that no source changed; that is sufficient. If there is any doubt whether a change is actually confined in this sense, run the full gate.

The commands above are the ordinary developer and CI interface. Managed agents whose sandbox cannot write to Windows user-profile temp/cache directories should run the portable wrapper for their active shell instead:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

The wrappers run the same six gates with `uv run --no-sync` and isolate writable pytest, coverage, mypy, Ruff, and UV artifacts under a unique ignored `/.tmp/quality-runs/` directory. They are safe for concurrent managed-agent runs and contain no machine-specific repository path. Developers with normal user-directory access do not need the wrappers.

Each wrapper writes its complete, unfiltered output (every command's standard output and standard error, in order) to `gate-output.txt` in that run's own directory, while still printing it; the last line it prints is the path of that file. Each step (each check, and each pytest pass separately) prints its elapsed time when it ends. Each pytest pass lists its failing and erroring tests by full name at the end of its output, every skipped test by full name with its reason (`-rs`), and its 20 slowest tests (`--durations=20`). A closing summary lists every step with its time and result, and the total time; a failing step stops the gate there, and the summary still prints. The PowerShell and shell wrappers print the same summary.

The default gate runs on the interpreter pinned in `.python-version` (3.12, the floor of the supported range), so eager-annotation regressions fail locally; the reasoning is in [IR.4](milestones/v0.2/integration-readiness/IR4_PYTHON_VERSION_REPRODUCIBILITY.md#3-python-policy). Pass `-ExtraPython 3.14` to the PowerShell wrapper (`--extra-python 3.14` to the shell wrapper) to also run the test suite on that interpreter after the default gate, in a separate ignored environment under `/.tmp/envs/` that is built once from the lock file and leaves `.venv` untouched. Run the 3.14 pass once before pushing a pull request.

Coverage is measured on one pass per run. With the extra pass, the extra pass carries it (terminal report with missing lines, and the HTML report) and the default pass runs without coverage; without the extra pass, the default pass carries it. coverage.py measures with `sys.monitoring` on Python 3.14, which costs far less than on 3.12. The gate fails below 85% total coverage on the pass that measures it, and CI's test step fails below 85% as well. `pyproject.toml` sets no threshold, so a focused run such as `uv run pytest tests/<file>` is not failed by it.

The test suite forces coloured CLI output itself (`tests/conftest.py` sets `FORCE_COLOR=1`), so every pytest run sees the same ANSI styling as a CI runner. CLI help and output assertions must therefore go through `normalize_cli_output` (`tests/_cli_helpers.py`) rather than compare raw text.

The suite fails on a `ResourceWarning` and on an unraisable exception, so a socket, file or `HTTPError` a test leaves open fails a test, which may be a different test from the one that created it because the warning is reported when the object is freed. An event loop left open is reported at the end of the session with no test named. In both cases rerun with `PYTHONTRACEMALLOC=25` to see where the object was created.

When a test fails in its setup, call or teardown with an `OSError` whose `winerror` is 10055 (Windows ran out of socket buffers) anywhere in the exception's cause chain, a pytest hook (`tests/_socket_snapshot.py`) records the machine's state at that moment and prints it in that test's failure output as a `socket snapshot` section: TCP connections by state, the ten processes owning the most connections, the dynamic TCP port range, non-paged pool and available memory, and the number of Python processes with their total handle count. It appears once per pytest session, on the first such failure, so it is in `gate-output.txt` under either wrapper and in CI logs. It needs no admin rights and makes no network call. Off Windows the hook does nothing, and if the snapshot cannot be collected the section says why; the test's result never changes. Keep the `gate-output.txt` of a run that shows the section and add it to [#116](https://github.com/PeterPontbriand/investment-analysis-engine/issues/116).

When local repair is required, the recommended order is:

```bash
uv run ruff check --fix .
uv run ruff format .
uv run mypy --strict investment_analysis_engine tests scripts
uv run pytest
```

The first two repair commands intentionally mutate files. Review their diff before rerunning the non-mutating gate. Do not install or update dependencies, edit `pyproject.toml` or `uv.lock`, or weaken a gate merely to obtain a passing result without explicit authorization.

## Documentation conventions

- Planning document structure: follow the [planning document structure rules](../../AGENTS.md#planning-document-structure), using the [IR contract and slice plan](milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md) as the reference example.
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
