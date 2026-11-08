"""The declared locales, and the rule that the package ships exactly one bundle file for each."""

import re
from importlib.resources import files

import pytest

from investment_analysis_engine.help.bundle import help_bundle_file_name, load_help_bundle
from investment_analysis_engine.help.locales import DEFAULT_LOCALE, LOCALES

_WELL_FORMED = re.compile(r"[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*")


def test_the_default_locale_is_declared() -> None:
    assert DEFAULT_LOCALE in {item.tag for item in LOCALES}


def test_tags_are_unique_ignoring_case_and_well_formed() -> None:
    tags = [item.tag for item in LOCALES]
    assert len(tags) == len({tag.lower() for tag in tags})
    assert all(_WELL_FORMED.fullmatch(tag) for tag in tags)
    assert all(item.name.strip() for item in LOCALES)


def test_the_package_ships_exactly_one_bundle_file_for_each_declared_locale() -> None:
    shipped = {
        entry.name.removeprefix("help_bundle.").removesuffix(".json")
        for entry in files("investment_analysis_engine.help").iterdir()
        if re.fullmatch(r"help_bundle\..+\.json", entry.name)
    }
    assert shipped == {item.tag for item in LOCALES}
    assert all(
        files("investment_analysis_engine.help").joinpath(help_bundle_file_name(item.tag)).is_file() for item in LOCALES
    )


def test_every_declared_locale_loads_and_is_cached_per_tag() -> None:
    for item in LOCALES:
        assert load_help_bundle(item.tag) is load_help_bundle(item.tag)


@pytest.mark.parametrize("tag", ["xx", "EN", "en-CA", ""])
def test_an_undeclared_tag_raises_a_value_error_naming_it(tag: str) -> None:
    with pytest.raises(ValueError, match=re.escape(repr(tag))):
        load_help_bundle(tag)
