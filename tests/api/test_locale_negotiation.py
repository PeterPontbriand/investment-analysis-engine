"""The Accept-Language parser: a pure function of the header, so no application is built."""

import pytest

from investment_analysis_engine.api import locale_negotiation
from investment_analysis_engine.api.locale_negotiation import negotiate_locale
from investment_analysis_engine.help.locales import DEFAULT_LOCALE


@pytest.fixture
def several(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare more locales than the engine ships, so a choice between them can be tested."""
    monkeypatch.setattr(locale_negotiation, "_DECLARED", frozenset({DEFAULT_LOCALE, "fr", "pt-br"}))


def test_an_absent_header_chooses_the_default() -> None:
    assert negotiate_locale(None) == DEFAULT_LOCALE
    assert negotiate_locale("") == DEFAULT_LOCALE


@pytest.mark.parametrize("header", ["EN", "en-CA", "en-Latn-CA", "EN-latn", "en;q=1", " en ; q=0.5 "])
def test_tags_match_case_insensitively_and_by_truncating_one_subtag_at_a_time(header: str) -> None:
    assert negotiate_locale(header) == "en"


@pytest.mark.usefixtures("several")
def test_truncation_matches_a_declared_region_tag_before_its_language() -> None:
    assert negotiate_locale("pt-BR") == "pt-br"
    assert negotiate_locale("pt-BR-x-private") == "pt-br"
    assert negotiate_locale("fr-CA, pt-BR") == "fr"
    assert negotiate_locale("pt") == DEFAULT_LOCALE  # a range never widens to a longer tag


@pytest.mark.usefixtures("several")
def test_q_values_order_the_ranges() -> None:
    assert negotiate_locale("fr;q=0.5, pt-BR;q=0.9") == "pt-br"
    assert negotiate_locale("fr;q=1, en;q=0.5") == "fr"
    assert negotiate_locale("en;q=0.2, fr;q=0.3") == "fr"


@pytest.mark.usefixtures("several")
def test_equal_q_values_keep_header_order() -> None:
    assert negotiate_locale("pt-BR, fr") == "pt-br"
    assert negotiate_locale("fr, pt-BR") == "fr"
    assert negotiate_locale("fr;q=0.5, pt-BR;q=0.5") == "fr"


@pytest.mark.usefixtures("several")
def test_q_zero_excludes_a_tag() -> None:
    assert negotiate_locale("fr;q=0, pt-BR;q=0.1") == "pt-br"
    assert negotiate_locale("fr;q=0.000, pt-BR;q=0.1") == "pt-br"
    assert negotiate_locale("en;q=0") == DEFAULT_LOCALE
    assert negotiate_locale("*;q=0, fr") == "fr"


@pytest.mark.usefixtures("several")
def test_a_wildcard_chooses_the_default() -> None:
    assert negotiate_locale("*") == DEFAULT_LOCALE
    assert negotiate_locale("fr;q=0.5, *;q=0.9") == DEFAULT_LOCALE
    assert negotiate_locale("de, *;q=0.1") == DEFAULT_LOCALE
    assert negotiate_locale("*;q=0.1, fr;q=0.5") == "fr"


@pytest.mark.usefixtures("several")
@pytest.mark.parametrize(
    "header",
    ["fr;q=abc, pt-BR", "fr;q=1.5, pt-BR", "fr;q=-1, pt-BR", "fr;q=nan, pt-BR", "fr;q=, pt-BR", "fr;x=1, pt-BR"],
)
def test_an_item_with_a_malformed_quality_is_skipped(header: str) -> None:
    assert negotiate_locale(header) == "pt-br"


@pytest.mark.usefixtures("several")
@pytest.mark.parametrize(
    "header", ["!!, pt-BR", "f r, pt-BR", "-fr, pt-BR", "fr--ca, pt-BR", "fr;q=1;q=1, pt-BR", ",,pt-BR"]
)
def test_an_item_with_a_malformed_tag_is_skipped(header: str) -> None:
    assert negotiate_locale(header) == "pt-br"


@pytest.mark.parametrize("header", ["!!", ";;;", "q=1", "fr;q=x", "\x00", "é", "a" * 5000, ",", ";q=1"])
def test_a_header_with_no_valid_item_chooses_the_default_and_never_raises(header: str) -> None:
    assert negotiate_locale(header) == DEFAULT_LOCALE
