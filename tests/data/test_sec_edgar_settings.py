"""The SEC adapter's settings: the shipped table, the per-user file, validation and how composition passes them on."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from investment_analysis_engine import cli_composition
from investment_analysis_engine.config import settings, strategy_settings
from investment_analysis_engine.config.strategy_settings import (
    clear_strategy_settings_cache,
    load_strategy_settings,
    shipped_settings_path,
    user_settings_path,
)
from investment_analysis_engine.core.settings_error import StrategySettingsError
from investment_analysis_engine.data.sec_edgar.settings import (
    PROVIDER_SETTINGS_FOLDER,
    SEC_EDGAR_ALIAS,
    SecEdgarSettings,
)


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    clear_strategy_settings_cache()
    yield
    clear_strategy_settings_cache()


def _load(folder: Path) -> SecEdgarSettings:
    return load_strategy_settings(SEC_EDGAR_ALIAS, SecEdgarSettings, folder, PROVIDER_SETTINGS_FOLDER)


def _write_user(folder: Path, text: str) -> Path:
    path = user_settings_path(SEC_EDGAR_ALIAS, folder, PROVIDER_SETTINGS_FOLDER)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_shipped_file_sits_beside_the_model_and_its_override_table_is_empty(tmp_path: Path) -> None:
    path = shipped_settings_path(SecEdgarSettings)

    assert path.name == "settings.toml"
    assert path.parent.name == "sec_edgar"
    assert _load(tmp_path).ticker_overrides == {}


def test_the_user_file_is_in_the_providers_folder_of_the_settings_folder(tmp_path: Path) -> None:
    assert user_settings_path("sec_edgar", tmp_path, "providers") == tmp_path / "providers" / "sec_edgar.toml"


def test_a_user_file_gives_overrides_in_any_case_with_a_number_or_digits(tmp_path: Path) -> None:
    _write_user(tmp_path, '[ticker_overrides]\nxom = 34088\nBRK-B = "0001067983"\n')

    assert _load(tmp_path).ticker_overrides == {"XOM": "0000034088", "BRK-B": "0001067983"}


def test_a_user_file_overrides_the_shipped_file_per_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shipped = tmp_path / "shipped" / "settings.toml"
    shipped.parent.mkdir()
    shipped.write_text("[ticker_overrides]\nXOM = 1\n", encoding="utf-8")
    monkeypatch.setattr(strategy_settings, "shipped_settings_path", lambda _model: shipped)
    assert _load(tmp_path).ticker_overrides == {"XOM": "0000000001"}

    clear_strategy_settings_cache()
    _write_user(tmp_path, "[ticker_overrides]\nXOM = 34088\n")
    assert _load(tmp_path).ticker_overrides == {"XOM": "0000034088"}


@pytest.mark.parametrize(
    "text",
    ["[ticker_overrides]\nXOM = 0\n", '[ticker_overrides]\nXOM = "abc"\n', "[ticker_overrides]\nXOM = 12345678901\n"],
)
def test_an_invalid_cik_is_refused_naming_the_file_and_the_key_but_not_the_value(tmp_path: Path, text: str) -> None:
    path = _write_user(tmp_path, text)

    with pytest.raises(StrategySettingsError) as error:
        _load(tmp_path)

    assert str(error.value).startswith(f"Settings file {path} is invalid: ticker_overrides")
    assert "XOM" in str(error.value)
    assert "abc" not in str(error.value)


def test_a_repeated_ticker_and_an_unknown_key_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="more than once"):
        SecEdgarSettings.model_validate({"ticker_overrides": {"xom": 1, "XOM": 2}})
    _write_user(tmp_path, "unknown = 1\n")
    with pytest.raises(StrategySettingsError, match="unknown"):
        _load(tmp_path)


def test_composition_loads_the_settings_and_hands_the_overrides_to_the_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_user(tmp_path, "[ticker_overrides]\nXOM = 34088\n")
    given: dict[str, Any] = {}

    class _Recorder:
        def __init__(self, **keywords: Any) -> None:
            given.update(keywords)

    monkeypatch.setattr(cli_composition, "_settings_folder", lambda: tmp_path)
    monkeypatch.setattr(settings, "sec_user_agent", "Fixture Tester fixture@example.com")
    monkeypatch.setattr(cli_composition, "SecEdgarFinancialFactsAdapter", _Recorder)
    monkeypatch.setattr(cli_composition, "ProductionFinancialFactsProvider", lambda **_keywords: object())

    cli_composition.build_sec_production_provider()

    assert given["ticker_overrides"] == {"XOM": "0000034088"}
    assert given["user_agent"] == "Fixture Tester fixture@example.com"


def test_loading_every_settings_file_at_startup_includes_the_sec_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_user(tmp_path, "[ticker_overrides]\nXOM = 0\n")
    monkeypatch.setattr(cli_composition, "_settings_folder", lambda: tmp_path)

    with pytest.raises(StrategySettingsError, match="sec_edgar.toml"):
        cli_composition.load_all_strategy_settings()


def test_composition_builds_the_adapter_with_the_identity_alone_when_the_table_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given: dict[str, Any] = {}

    class _Recorder:
        def __init__(self, **keywords: Any) -> None:
            given.update(keywords)

    monkeypatch.setattr(cli_composition, "_settings_folder", lambda: tmp_path)
    monkeypatch.setattr(settings, "sec_user_agent", "Fixture Tester fixture@example.com")
    monkeypatch.setattr(cli_composition, "SecEdgarFinancialFactsAdapter", _Recorder)
    monkeypatch.setattr(cli_composition, "ProductionFinancialFactsProvider", lambda **_keywords: object())

    cli_composition.build_sec_production_provider()

    assert given == {"user_agent": "Fixture Tester fixture@example.com"}
