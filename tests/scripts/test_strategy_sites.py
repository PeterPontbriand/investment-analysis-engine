"""The typed loader of the edit-site data file."""

from pathlib import Path

import pytest

from scripts.strategy_sites import SITES_FILE, SiteDataError, load_sites, strategy_names

_SITE = """
[[site]]
id = "{id}"
title = "A title"
why = "A reason"
kind = "{kind}"
path = "pkg/{{module}}/{{alias}}/{{guide}}.py"
generated = {generated}
check = "{check}"
fails = "it fails"
{extra}"""


def _write(tmp_path: Path, *sites: str) -> Path:
    path = tmp_path / "sites.toml"
    path.write_text("".join(sites), encoding="utf-8")
    return path


def _site(
    *,
    id: str = "one",  # noqa: A002
    kind: str = "edit",
    generated: str = "true",
    check: str = "site_one",
    extra: str = "",
) -> str:
    return _SITE.format(id=id, kind=kind, generated=generated, check=check, extra=extra)


def test_the_shipped_file_lists_every_section_17_row_and_the_two_commands_in_order() -> None:
    sites = load_sites()
    assert [site.id for site in sites] == [
        "vocabulary",
        "analyzer",
        "settings",
        "descriptor",
        "tool-name",
        "tool",
        "unions",
        "selection",
        "codec",
        "execution",
        "cli",
        "cli-tier",
        "presenter",
        "envelope",
        "replay",
        "evaluation",
        "evaluation-tier",
        "cases",
        "catalog",
        "direct-output",
        "strategy-documents",
        "help-snapshot",
        "guide",
        "watchlist-options",
        "schema",
        "strategy-docs",
    ]
    assert SITES_FILE.name == "strategy_sites.toml"


def test_a_site_resolves_its_placeholders(tmp_path: Path) -> None:
    names = strategy_names("graham_number")
    assert (names.module, names.alias, names.guide) == ("graham_number", "graham-number", "GRAHAM_NUMBER")
    site = load_sites(_write(tmp_path, _site()))[0]
    assert site.resolved_path(names) == "pkg/graham_number/graham-number/GRAHAM_NUMBER.py"


def test_an_alias_overrides_the_default_and_a_malformed_name_is_rejected() -> None:
    assert strategy_names("fcf_growth", "fcf").alias == "fcf"
    with pytest.raises(SiteDataError, match="snake_case"):
        strategy_names("Not-A-Module")
    with pytest.raises(SiteDataError, match="hyphenated"):
        strategy_names("momentum", "Bad_Alias")


def test_a_site_with_an_unknown_key_or_kind_or_type_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SiteDataError, match="keys"):
        load_sites(_write(tmp_path, _site() + 'extra = "x"\n'))
    with pytest.raises(SiteDataError, match="kind"):
        load_sites(_write(tmp_path, _site(kind="magic")))
    with pytest.raises(SiteDataError, match="generated"):
        load_sites(_write(tmp_path, _site(generated='"yes"')))


def test_a_duplicated_id_or_check_and_an_empty_file_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SiteDataError, match="id values"):
        load_sites(_write(tmp_path, _site(), _site(check="site_two")))
    with pytest.raises(SiteDataError, match="check values"):
        load_sites(_write(tmp_path, _site(), _site(id="two")))
    with pytest.raises(SiteDataError, match="no .*site"):
        load_sites(_write(tmp_path, "title = 1\n"))


def test_a_new_file_site_needs_defines_and_no_other_site_may_have_it(tmp_path: Path) -> None:
    with pytest.raises(SiteDataError, match="needs defines"):
        load_sites(_write(tmp_path, _site(kind="new_file")))
    with pytest.raises(SiteDataError, match="needs defines"):
        load_sites(_write(tmp_path, _site(kind="new_file", extra="defines = []\n")))
    for kind in ("edit", "command", "reviewed"):
        with pytest.raises(SiteDataError, match="only for new_file"):
            load_sites(_write(tmp_path, _site(kind=kind, extra='defines = ["X"]\n')))
    (site,) = load_sites(_write(tmp_path, _site(kind="new_file", extra='defines = ["{module_upper}_X", "y"]\n')))
    assert site.required_patterns(strategy_names("graham_number")) == ("GRAHAM_NUMBER_X", "y")


def test_every_shipped_new_file_site_declares_what_it_defines_and_the_table_shows_it() -> None:
    for site in load_sites():
        assert bool(site.defines) == (site.kind == "new_file")
        for pattern in site.defines:
            assert f"`{pattern}`" in site.describe()
