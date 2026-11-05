"""The shared SEC adapter builder in the application layer, and the provider builder that calls it.

Piotroski needs the adapter itself (it is the as-filed SIC source) as well as the provider composed from it, so the
construction of the adapter is one function that ``build_sec_production_provider`` calls and Piotroski calls beside it.
Composition reads its settings from the context it is given: two contexts with different settings folders read each
folder's files, and no composition module reads a module-level settings object.
"""

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from investment_analysis_engine.application import providers
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.config.component_settings import clear_component_settings_cache
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.strategies.graham_growth.application import graham_growth_settings
from investment_analysis_engine.strategies.momentum.application import momentum_settings

NOT_CONFIGURED = (
    "SEC EDGAR access is not configured. "
    'Set SEC_USER_AGENT to a declared identity such as "Your Name your-email@example.com" and retry.'
)
IDENTITY = "Fixture Tester fixture@example.com"


class _Recorder:
    """Stands in for the adapter and records how the builder constructed it."""

    given: dict[str, Any] = {}

    def __init__(self, **keywords: Any) -> None:
        _Recorder.given = dict(keywords)


def _context(folder: Path, identity: str | None = IDENTITY) -> ApplicationContext:
    """Return a context whose settings folder is ``folder``, with the SEC identity ``identity``."""
    values: dict[str, Any] = {"config_dir": folder}
    if identity is not None:
        values["SEC_USER_AGENT"] = identity
    return ApplicationContext(settings=ProjectSettings.model_validate(values))


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    clear_component_settings_cache()
    yield
    clear_component_settings_cache()


@pytest.fixture
def configured(tmp_path: Path) -> ApplicationContext:
    (tmp_path / "providers").mkdir()
    (tmp_path / "providers" / "sec_edgar.toml").write_text("[ticker_overrides]\nXOM = 34088\n", encoding="utf-8")
    return _context(tmp_path)


def test_the_adapter_builder_hands_the_identity_and_the_ticker_overrides_to_the_adapter(
    configured: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(providers, "SecEdgarFinancialFactsAdapter", _Recorder)
    providers.build_sec_edgar_adapter(configured)
    assert _Recorder.given == {"user_agent": IDENTITY, "ticker_overrides": {"XOM": "0000034088"}}


@pytest.mark.parametrize("identity", [None, "", "   "])
def test_both_builders_refuse_without_a_declared_identity_with_the_same_message(
    identity: str | None, tmp_path: Path
) -> None:
    context = _context(tmp_path, identity)
    for build in (providers.build_sec_edgar_adapter, providers.build_sec_production_provider):
        with pytest.raises(AnalysisConfigurationError) as raised:
            build(context)
        assert str(raised.value) == NOT_CONFIGURED


def test_the_provider_builder_wraps_the_adapter_the_shared_builder_made(
    configured: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SecEdgarFinancialFactsAdapter(user_agent="Synthetic test")
    calls: list[ApplicationContext] = []

    def build(context: ApplicationContext) -> SecEdgarFinancialFactsAdapter:
        calls.append(context)
        return adapter

    monkeypatch.setattr(providers, "build_sec_edgar_adapter", build)
    provider = providers.build_sec_production_provider(configured)
    assert calls == [configured]
    assert isinstance(provider, ProductionFinancialFactsProvider)
    assert provider._providers["sec_edgar"] is adapter


def test_the_adapter_builder_makes_a_real_adapter_that_the_provider_builder_does_not_share(
    configured: ApplicationContext,
) -> None:
    first = providers.build_sec_edgar_adapter(configured)
    assert isinstance(first, SecEdgarFinancialFactsAdapter)
    provider = providers.build_sec_production_provider(configured)
    assert provider._providers["sec_edgar"] is not first


def test_two_contexts_with_different_settings_folders_read_each_folders_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The settings of the SEC adapter, Momentum and Graham Growth come from the folder of the context given."""
    first, second = tmp_path / "first", tmp_path / "second"
    for folder, override, window in ((first, 34088, 7), (second, 51143, 9)):
        (folder / "providers").mkdir(parents=True)
        (folder / "strategies").mkdir()
        (folder / "providers" / "sec_edgar.toml").write_text(
            f"[ticker_overrides]\nXOM = {override}\n", encoding="utf-8"
        )
        (folder / "strategies" / "momentum.toml").write_text(f"short_window = {window}\n", encoding="utf-8")
    (second / "strategies" / "graham-growth.toml").write_text("base_pe = 9.5\n", encoding="utf-8")
    monkeypatch.setattr(providers, "SecEdgarFinancialFactsAdapter", _Recorder)

    overrides = []
    for folder in (first, second):
        providers.build_sec_edgar_adapter(_context(folder))
        overrides.append(_Recorder.given["ticker_overrides"])

    assert overrides == [{"XOM": "0000034088"}, {"XOM": "0000051143"}]
    assert [momentum_settings(_context(folder)).short_window for folder in (first, second)] == [7, 9]
    assert graham_growth_settings(_context(first)).base_pe != graham_growth_settings(_context(second)).base_pe
    assert graham_growth_settings(_context(second)).base_pe == 9.5


def _modules_that_compose() -> list[Path]:
    """Return the modules whose job is composition: those of ``application`` and each strategy's ``application.py``."""
    return sorted(
        [*(PACKAGE_ROOT / "application").glob("*.py"), *(PACKAGE_ROOT / "strategies").glob("*/application.py")]
    )


def _reads_the_module_level_settings(path: Path) -> list[str]:
    """Return a message for each import of the module-level ``settings`` object."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == "investment_analysis_engine.config":
            names = [alias.name for alias in node.names]
            if "settings" in names:
                found.append(f"{path.name}:{node.lineno}: imports the module-level settings object")
    return found


def test_no_composition_module_reads_the_module_level_settings_object() -> None:
    modules = _modules_that_compose()
    assert PACKAGE_ROOT / "application" / "providers.py" in modules
    assert len(modules) > 6
    assert [message for path in modules for message in _reads_the_module_level_settings(path)] == []


def test_the_check_finds_an_import_of_the_module_level_settings_object(tmp_path: Path) -> None:
    offender = tmp_path / "application.py"
    offender.write_text("from investment_analysis_engine.config import settings\n", encoding="utf-8")
    assert _reads_the_module_level_settings(offender) == ["application.py:1: imports the module-level settings object"]


_PROBE_BUILDERS = frozenset({"build_provider_probe", "ProviderProbe"})
_MAY_BUILD_A_PROBE = frozenset({"application", "cli_workspace.py"})
"""The unit that builds a probe, and the one command that does until its refresh operation moves into it."""


def test_only_the_application_and_the_refresh_command_build_a_probe() -> None:
    """A direct command, the CLI's failure translation and the API never build one; the operation does."""
    offenders = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = path.relative_to(PACKAGE_ROOT)
        if relative.parts[0] in _MAY_BUILD_A_PROBE or relative.name in _MAY_BUILD_A_PROBE:
            continue
        if relative.parts[:2] == ("data", "provider_probe.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                function = node.func
                name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
                if name in _PROBE_BUILDERS:
                    offenders.append(f"{relative.as_posix()}:{node.lineno}")
    assert offenders == []
