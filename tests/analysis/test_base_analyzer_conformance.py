"""Structural conformance tests for the shared analyzer invocation envelope.

Every strategy subclasses ``BaseAnalyzer[ConfigT, ResultT]`` and is invoked identically as
``run_analysis(ticker, config, context)`` (see ``AGENTS.md`` §9). These tests hold that shape
in place across all four analyzers, using only fixture-backed test doubles — no network access.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, get_args, get_origin
from unittest.mock import patch

import pytest

from src.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from src.analysis.strategy.fcf_earnings_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.analysis.strategy.fcf_earnings_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthConfig, FCFEarningsGrowthPolicy
from src.analysis.strategy.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_number.analyzer import GrahamNumberAnalyzer
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.graham import NOW, PROVIDER_ID, SECURITY_ID, FixtureFinancialFactsProvider
from src.evaluation.fixtures.market_data import FixtureDataClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_STRATEGY_PACKAGE = _SRC_ROOT / "analysis" / "strategy"

_GROWTH_POLICY = GrahamGrowthCalculationPolicy(base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4)
_MOMENTUM_SETTINGS = {"default": {"default_ticker": "AAPL", "data_start_date": "2026-01-01"}}


class _FixtureDataClientWithIdentity(FixtureDataClient):
    """``FixtureDataClient`` with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


def _context() -> AnalysisContext:
    return AnalysisContext(as_of=NOW, executed_at=NOW, use_cache=True)


def _momentum_analyzer() -> MomentumAnalyzer:
    with patch("src.config.ProjectSettings.get_analysis_settings", return_value=_MOMENTUM_SETTINGS):
        return MomentumAnalyzer(default_ticker="AAPL", data_client=_FixtureDataClientWithIdentity())


def _momentum_config() -> MomentumConfig:
    return MomentumConfig(short_window=2, long_window=3, rsi_period=3)


def _graham_number_analyzer() -> GrahamNumberAnalyzer:
    resolver = GrahamNumberInputResolver(FixtureFinancialFactsProvider(), clock=lambda: NOW)
    return GrahamNumberAnalyzer(resolver)


def _graham_number_config() -> GrahamNumberConfig:
    return GrahamNumberConfig.model_validate({"security_provider_id": PROVIDER_ID})


def _graham_growth_analyzer() -> GrahamGrowthAnalyzer:
    resolver = GrahamGrowthInputResolver(FixtureFinancialFactsProvider(), clock=lambda: NOW)
    return GrahamGrowthAnalyzer(resolver, policy=_GROWTH_POLICY)


def _graham_growth_config() -> GrahamGrowthConfig:
    return GrahamGrowthConfig.model_validate(
        {"security_provider_id": PROVIDER_ID, "expected_growth": 5.0, "aaa_yield_override": 4.5}
    )


def _fcf_analyzer() -> FCFEarningsGrowthAnalyzer:
    facts = tuple(
        replace(
            fact,
            provider_id=SEC_PROVIDER_ID,
            provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}",
        )
        for fact in annual_series(range(2020, 2026))
    )
    provider = ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))
    resolver = ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: NOW)
    return FCFEarningsGrowthAnalyzer(resolver)


def _fcf_config() -> FCFEarningsGrowthConfig:
    return FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD", provider_id=SEC_PROVIDER_ID)


@dataclass(frozen=True)
class _Case:
    """One strategy's analyzer class plus fixture-backed factories to exercise it live."""

    name: str
    analyzer_class: type[BaseAnalyzer[Any, Any]]
    build_analyzer: Callable[[], BaseAnalyzer[Any, Any]]
    build_config: Callable[[], object]
    ticker: str


_CASES: tuple[_Case, ...] = (
    _Case("momentum", MomentumAnalyzer, _momentum_analyzer, _momentum_config, "AAPL"),
    _Case("graham_number", GrahamNumberAnalyzer, _graham_number_analyzer, _graham_number_config, SECURITY_ID),
    _Case("graham_growth", GrahamGrowthAnalyzer, _graham_growth_analyzer, _graham_growth_config, SECURITY_ID),
    _Case("fcf_earnings_growth", FCFEarningsGrowthAnalyzer, _fcf_analyzer, _fcf_config, "ACME"),
)


def _generic_args(analyzer_class: type[BaseAnalyzer[Any, Any]]) -> tuple[type, type]:
    """Return ``(ConfigT, ResultT)`` as declared directly on ``BaseAnalyzer[ConfigT, ResultT]``."""
    for base in getattr(analyzer_class, "__orig_bases__", ()):
        if get_origin(base) is BaseAnalyzer:
            config_type, result_type = get_args(base)
            return config_type, result_type
    raise AssertionError(f"{analyzer_class!r} does not directly subclass BaseAnalyzer[ConfigT, ResultT].")


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.name)
def test_analyzer_subclasses_base_analyzer(case: _Case) -> None:
    """Item 1: every strategy's analyzer is a genuine ``BaseAnalyzer`` subclass."""
    assert issubclass(case.analyzer_class, BaseAnalyzer)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.name)
def test_run_analysis_signature_matches_the_shared_envelope(case: _Case) -> None:
    """Item 2: every ``run_analysis`` matches ``(self, ticker, config, context) -> ResultT`` exactly."""
    config_type, result_type = _generic_args(case.analyzer_class)
    signature = inspect.signature(case.analyzer_class.run_analysis, eval_str=True)
    parameters = list(signature.parameters.values())

    assert [parameter.name for parameter in parameters] == ["self", "ticker", "config", "context"]
    assert all(parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in parameters)

    annotations = {parameter.name: parameter.annotation for parameter in parameters}
    assert annotations["ticker"] is str
    assert annotations["config"] is config_type
    assert annotations["context"] is AnalysisContext
    assert signature.return_annotation is result_type


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.name)
def test_run_analysis_returns_its_declared_result_type(case: _Case) -> None:
    """Item 3: calling ``run_analysis`` with fakes returns an instance of the declared ``ResultT``."""
    _, result_type = _generic_args(case.analyzer_class)
    result = case.build_analyzer().run_analysis(case.ticker, case.build_config(), _context())
    assert isinstance(result, result_type)


def _python_files_outside_strategy_package() -> Iterator[Path]:
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        try:
            path.relative_to(_STRATEGY_PACKAGE)
        except ValueError:
            yield path


def _strategy_boundary_function_imports() -> list[str]:
    """Return one ``module:qualified_name`` entry per plain-function import crossing the boundary."""
    violations: list[str] = []
    for path in _python_files_outside_strategy_package():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module != "src.analysis.strategy" and not node.module.startswith("src.analysis.strategy."):
                continue
            module = importlib.import_module(node.module)
            for alias in node.names:
                imported = getattr(module, alias.name, None)
                if inspect.isfunction(imported):
                    relative_path = path.relative_to(_REPO_ROOT)
                    violations.append(f"{relative_path}: from {node.module} import {alias.name}")
    return violations


def test_no_plain_function_imports_cross_the_strategy_boundary() -> None:
    """Item 4: only classes may be imported from ``src.analysis.strategy.**`` outside that package."""
    violations = _strategy_boundary_function_imports()
    assert not violations, "Plain-function imports crossing the strategy boundary:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Item 5: no bare wall-clock reads outside the composition roots (§6.11).
#
# `src.core.clock.utc_now()` is the one call site permitted to read the real
# clock; every other module must receive its clock through an injected
# parameter. A plain textual grep for `datetime.now`/`datetime.utcnow`/
# `time.time()` misses `datetime.today()`, `date.today()`, `time.time_ns()`,
# `pandas.Timestamp.now()/.today()/.utcnow()`, an aliased import
# (`import datetime as _dt`, `from datetime import datetime as dt`,
# `from time import time`), and a bare, uncalled reference such as
# `field(default_factory=datetime.now)`. This scan catches all of those by
# resolving each file's own import aliases and walking every `ast.Attribute`
# node, not only ones a `Call` wraps.
#
# Known gap, not covered here: a clock read hidden inside a string literal
# passed to a constructor (`pd.Timestamp("now")`, `pd.to_datetime("today")`,
# `np.datetime64("now")`). Grepped `src/` for these directly: none exist
# today. This scan cannot see that shape at all; it is not silently treated
# as covered.
# ---------------------------------------------------------------------------

_FORBIDDEN_CLOCK_ATTRS: dict[str, frozenset[str]] = {
    "datetime": frozenset({"now", "utcnow", "today"}),
    "date": frozenset({"today"}),
    "Timestamp": frozenset({"now", "today", "utcnow"}),
    "time_module": frozenset({"time", "time_ns"}),
}
_TIME_DURATION_EXEMPT = frozenset({"monotonic", "perf_counter"})
_ALLOWED_CLOCK_READ_PATHS = frozenset({Path("core/clock.py"), Path("utils/logger_util.py")})


def _clock_import_aliases(tree: ast.Module) -> dict[str, str]:
    """Map each local name one file's imports bind to a canonical clock-related target.

    Values are one of ``"module:datetime"``, ``"module:time_module"``, ``"module:pandas"``,
    ``"class:datetime"``, ``"class:date"``, ``"class:Timestamp"``, or
    ``"boundfunc:time_module.time"``/``"boundfunc:time_module.time_ns"``. A name this file
    imports for an unrelated reason is simply absent.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                if alias.name == "datetime":
                    aliases[local] = "module:datetime"
                elif alias.name == "time":
                    aliases[local] = "module:time_module"
                elif alias.name == "pandas":
                    aliases[local] = "module:pandas"
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                local = alias.asname or alias.name
                if node.module == "datetime" and alias.name in ("datetime", "date"):
                    aliases[local] = f"class:{alias.name}"
                elif node.module == "time" and alias.name in ("time", "time_ns"):
                    aliases[local] = f"boundfunc:time_module.{alias.name}"
                elif node.module == "pandas" and alias.name == "Timestamp":
                    aliases[local] = "class:Timestamp"
    return aliases


def _dotted_chain(node: ast.expr) -> tuple[str, ...] | None:
    """Return ``(root_name, *attrs)`` for a `Name`/`Attribute` chain, or ``None`` otherwise."""
    attrs: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        attrs.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return (current.id, *reversed(attrs))


def _is_forbidden_attribute_read(target: str, rest: tuple[str, ...], attr: str) -> bool:
    """Return whether an ``Attribute`` chain resolving to *target* reads a forbidden clock."""
    if target == "module:datetime":
        return len(rest) >= 2 and rest[0] in _FORBIDDEN_CLOCK_ATTRS and attr in _FORBIDDEN_CLOCK_ATTRS[rest[0]]
    if target == "module:time_module":
        return attr in _FORBIDDEN_CLOCK_ATTRS["time_module"] and attr not in _TIME_DURATION_EXEMPT
    if target == "module:pandas":
        return len(rest) >= 2 and rest[0] == "Timestamp" and attr in _FORBIDDEN_CLOCK_ATTRS["Timestamp"]
    if target.startswith("class:"):
        cls = target.removeprefix("class:")
        return attr in _FORBIDDEN_CLOCK_ATTRS.get(cls, frozenset())
    return False


def _is_forbidden_bound_function_read(target: str) -> bool:
    """Return whether a bare `Name` reference resolving to *target* reads a forbidden clock."""
    if not target.startswith("boundfunc:"):
        return False
    bound = target.removeprefix("boundfunc:")
    return not bound.endswith((".monotonic", ".perf_counter"))


def _clock_read_violations_in_module(tree: ast.Module) -> list[str]:
    """Return one description per forbidden wall-clock read found in *tree*."""
    aliases = _clock_import_aliases(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain = _dotted_chain(node)
            if chain is None:
                continue
            root, *rest = chain
            target = aliases.get(root)
            if target is not None and _is_forbidden_attribute_read(target, tuple(rest), node.attr):
                violations.append(f"{'.'.join(chain)} (line {node.lineno})")
        elif isinstance(node, ast.Name):
            target = aliases.get(node.id)
            if target is not None and _is_forbidden_bound_function_read(target):
                bound = target.removeprefix("boundfunc:")
                violations.append(f"bare `{node.id}` (aliases {bound}, line {node.lineno})")
    return violations


def _clock_read_violations_in_src() -> list[str]:
    """Return one description per forbidden wall-clock read anywhere under ``src/``."""
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if path.relative_to(_SRC_ROOT) in _ALLOWED_CLOCK_READ_PATHS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_path = path.relative_to(_REPO_ROOT)
        violations.extend(f"{relative_path}: {violation}" for violation in _clock_read_violations_in_module(tree))
    return violations


def test_no_bare_clock_reads_outside_the_shared_helper() -> None:
    """Item 5: only two modules read the real wall clock.

    ``src/core/clock.py`` and the named ``logger_util.py`` exemption; every other module
    receives its clock through an injected parameter.
    """
    violations = _clock_read_violations_in_src()
    assert not violations, "Bare wall-clock reads outside src/core/clock.py:\n" + "\n".join(violations)


@pytest.mark.parametrize(
    ("snippet", "expect_violation"),
    [
        ("import datetime as _dt\ndef f():\n    return _dt.datetime.now()\n", True),
        ("from datetime import datetime as dt\ndef f():\n    return dt.now()\n", True),
        ("import pandas as pd\ndef f():\n    return pd.Timestamp.now()\n", True),
        ("from datetime import date\ndef f():\n    return date.today()\n", True),
        ("from datetime import datetime\ndef f():\n    return datetime.today()\n", True),
        ("import time\ndef f():\n    return time.time_ns()\n", True),
        (
            "from datetime import datetime\nfrom dataclasses import field\nx = field(default_factory=datetime.now)\n",
            True,
        ),
        ("from time import time\ndef f():\n    return time()\n", True),
        ("import time\ndef f():\n    return time.monotonic()\n", False),
        ("import time\ndef f():\n    return time.perf_counter()\n", False),
    ],
)
def test_clock_scan_self_test(snippet: str, expect_violation: bool) -> None:
    """The scan itself fires on every pattern it claims to catch, and only those."""
    tree = ast.parse(snippet)
    violations = _clock_read_violations_in_module(tree)
    assert bool(violations) is expect_violation, violations


def test_clock_scan_covers_more_than_zero_files() -> None:
    """An empty or broken file glob must not silently pass as "no violations"."""
    assert sum(1 for _ in _SRC_ROOT.rglob("*.py")) > 0
