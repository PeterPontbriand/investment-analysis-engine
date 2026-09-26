# IR.4 — Python-version Reproducibility

Fixes the codebase's declared support for Python 3.12–3.14 so it is actually true and
continuously verified, rather than only true on whichever interpreter happens to run the gate.

## 1. Problem

On a clean checkout running Python 3.13.13, `uv sync --frozen` installed the pinned dependencies
and `pytest` failed with 51 collection errors across most of `tests/`. The cause was
`src/data/repositories/market_data.py`'s `_index_storage`/`_restore_index` signatures, both typed
with `pd.Index[Any]` with no `from __future__ import annotations` in the module. On Python ≤3.13
that annotation is evaluated at function-definition time; runtime `pandas.Index` is not
subscriptable (only `pandas-stubs` makes it generic for type checkers), so the import raised
`TypeError: type 'Index' is not subscriptable`. The same failure reproduced with both
`pandas==2.3.3` and `pandas==3.0.5`, so it was not a pandas-3 regression.

Two conditions hid this from every prior quality-gate run. First, Python 3.14 defers annotation
evaluation by default (PEP 649), so the same signatures imported cleanly there without the
annotation ever being evaluated. Second, `.github/workflows/ci.yaml`'s matrix ran a single Python
version (3.14) across all three operating systems, and no `.python-version` file existed, so a
fresh `uv sync` on any 3.12 or 3.13 interpreter reproduced the failure with nothing in CI to catch
it.

A repository-wide audit (`compileall` plus a full `src` package import walk plus
`pytest --collect-only`, run on Python 3.12) found the same defect class in two further places:
`src/analysis/strategy/momentum/momentum_analyzer.py`'s `_calculate_rsi(close: pd.Series[float],
...)`, and `src/utils/worker.py`'s `worker(log_queue: Queue[Any], ...)`, where `Queue` is
`multiprocessing.Queue`, a factory function that is not subscriptable at runtime regardless of
Python version. A textual grep for `pd.Index[`/`pd.Series[`/`pd.DataFrame[` finds only the first
two; it does not generalize to other stub-only generics, non-pandas runtime-unsubscriptable
callables, or any other 3.13+/3.14-only construct evaluated at import time, which is why the audit
above, not the grep, is the authority for "every occurrence is fixed."

## 2. Remedy

`from __future__ import annotations` was added to all three files. This is the project's existing,
precedented remedy for this defect class and keeps one remedy style across the codebase, rather
than quoting individual annotations or introducing a `TYPE_CHECKING`-only alias.

`market_data.py` also defines two `@dataclass(frozen=True)` classes (`MarketDataCacheKey`,
`MarketDataCacheEntry`), a `TypeAdapter(MarketDataCacheKey)`, and a Pydantic `_FrameMetadata
(BaseModel)`, all of which read annotations at runtime. Every field on all three is a plain,
always-real-at-runtime type — none is a pandas stub-only generic — and both `TypeAdapter` and
Pydantic resolve `from __future__ import annotations`-deferred annotations correctly (standard PEP
563 support). A regression test in `tests/data/repositories/test_market_data.py` exercises
`_KEY_ADAPTER` and `_FrameMetadata` directly, with both valid and invalid input, to guard this.

If a future occurrence involves a type with genuinely real-type-dependent runtime introspection
where a file-wide future import is not obviously safe, the fallback is to quote just that one
annotation (e.g. `index: "pd.Index[Any]"`) and record the reason in an inline comment at that call
site, rather than applying the file-wide remedy by default.

## 3. Python policy

`requires-python = ">=3.12"` in `pyproject.toml` is unchanged; the policy was already correct, it
was simply never honored or tested.

`.python-version` now pins `3.12`, the floor of the declared range rather than the newest
available interpreter. A `uv sync` run without an explicit interpreter picks this file's version by
default, so routine local development now exercises the strictest, most eager-evaluation-prone
supported interpreter, and a regression of this kind fails immediately for a developer instead of
waiting for someone to happen to run an older interpreter.

`.github/workflows/ci.yaml`'s matrix covers `["3.12", "3.13", "3.14"]`. Each job also sets
`UV_PYTHON` from `matrix.python-version` and runs a verification step that asserts the synced
interpreter matches the declared version. Both are necessary: `actions/setup-python` puts the
matrix's interpreter on `PATH`, but `uv` gives `.python-version` precedence over `PATH` when
choosing which interpreter to sync, so without `UV_PYTHON` every job would silently sync and run
against `.python-version`'s pinned 3.12, regardless of which version the matrix entry names.

`[tool.mypy] python_version` is set to `"3.12"`, matching the floor rather than the ceiling of the
declared range, so type checking cannot silently rely on a 3.13+/3.14-only construct that would
break on 3.12. `[tool.ruff] target-version` is already `"py312"` and needs no change.

`uv.lock` was re-resolved after the fix; the resolution is unchanged, confirming it was already
consistent across the full `>=3.12` range rather than narrowly resolved against one version.

## 4. Acceptance criteria

From a fresh clone, each version is run explicitly rather than relying on `.python-version`'s
default:

```
uv run --frozen --python 3.12 python --version   # must print 3.12.x
uv run --frozen --python 3.12 pytest

uv run --frozen --python 3.13 python --version   # must print 3.13.x
uv run --frozen --python 3.13 pytest

uv run --frozen --python 3.14 python --version   # must print 3.14.x
uv run --frozen --python 3.14 pytest
```

On Python 3.12, the authoritative audit passes clean:

```
uv run --frozen --python 3.12 python -m compileall -q src tests
uv run --frozen --python 3.12 python -c "import pkgutil, importlib, src; [importlib.import_module(m.name) for m in pkgutil.walk_packages(src.__path__, 'src.')]"
uv run --frozen --python 3.12 pytest --collect-only -q
```

The managed quality gate (`scripts/run-quality-gates.ps1` / `.sh`) reports the Python and pandas
version it ran on. `.github/workflows/ci.yaml`'s matrix exercises all three declared versions as
distinct entries, each verified to run the version it claims, and is green on all of them.

## 5. Completion record

Verified on a Windows checkout: the full test suite (3,129 tests) passed independently under
Python 3.12.14, 3.13.15, and 3.14.7, each run with an explicit `--python` flag and a preceding
`python --version` check. The 3.12 audit (`compileall`, full `src` import walk,
`pytest --collect-only`) passed clean. `ruff check`, `ruff format --check`, and `mypy --strict`
passed repository-wide on Python 3.12. The managed quality gate passed end-to-end and reported
"Python 3.12.14, pandas 3.0.5". `uv lock` produced no diff on re-resolution.

## 6. Relationship to the IR plan

This is slice IR.4 in the renumbered slice table on `feat/ir-integration-readiness`'s copy of this
document. `main`'s copy of this document predates that renumbering, where "IR.4" labels a
different, unrelated slice (the momentum series API). When `feat/ir-integration-readiness` next
merges `main`, its own IR.4 section is replaced by a link to this file, which becomes the single
source for IR.4.
