"""Typed loader for the edit-site data of a strategy.

``scripts/strategy_sites.toml`` lists every place a contributor edits to add a strategy. This module reads it
with ``tomllib`` into immutable records and defines the two small types a site check works with: the names of
the strategy under test and the ``Gap`` a check returns. It imports nothing from the package under test, so
the status command can still report when that package cannot be imported.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast, get_args

SITES_FILE: Final[Path] = Path(__file__).resolve().parent / "strategy_sites.toml"

SiteKind = Literal["new_file", "edit", "command", "reviewed"]

_REQUIRED_KEYS: Final[frozenset[str]] = frozenset({"id", "title", "why", "kind", "path", "generated", "check", "fails"})
_KEYS: Final[frozenset[str]] = _REQUIRED_KEYS | {"defines"}
_MODULE_NAME: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*")
_ALIAS_NAME: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9-]*")

# The user guide of FCF Growth predates the rule that a guide is named for the alias; the rename removes this entry.
_LEGACY_GUIDE_NAMES: Final[dict[str, str]] = {"fcf-growth": "FCF_EARNINGS_GROWTH"}


class SiteDataError(ValueError):
    """The site data file or a strategy name is malformed."""


@dataclass(frozen=True)
class StrategyNames:
    """The names a site check works from: the package name, the command alias and the guide name."""

    module: str
    alias: str
    guide: str


@dataclass(frozen=True)
class Gap:
    """One missing or wrong piece of a site: which site, which file, and what is wrong."""

    site_id: str
    path: str
    message: str


@dataclass(frozen=True)
class Site:
    """One edit site, as declared in the site data file."""

    id: str
    title: str
    why: str
    kind: SiteKind
    path: str
    generated: bool
    check: str
    fails: str
    defines: tuple[str, ...]

    def resolved_path(self, names: StrategyNames) -> str:
        """Return the site's file for ``names``, with the placeholders replaced."""
        return self.path.format(module=names.module, alias=names.alias, guide=names.guide)

    def required_patterns(self, names: StrategyNames) -> tuple[str, ...]:
        """Return the regular expressions the site's file must each match a defined name with, for ``names``."""
        return tuple(
            pattern.format(module=names.module, alias=names.alias, guide=names.guide, module_upper=names.module.upper())
            for pattern in self.defines
        )

    def describe(self) -> str:
        """Return what fails when the site is missing: the file, the patterns from ``defines``, then ``fails``."""
        parts = []
        if self.kind == "new_file":
            parts.append("the file is missing, or defines no " + ", ".join(f"`{pattern}`" for pattern in self.defines))
        if self.fails:
            parts.append(self.fails)
        return "; ".join(parts)


def strategy_names(module: str, alias: str | None = None) -> StrategyNames:
    """Return the names of the strategy in package ``module``; the alias defaults to the hyphenated module name."""
    if not _MODULE_NAME.fullmatch(module):
        raise SiteDataError(f"{module!r} is not a snake_case module name.")
    resolved = alias if alias is not None else module.replace("_", "-")
    if not _ALIAS_NAME.fullmatch(resolved):
        raise SiteDataError(f"{resolved!r} is not a hyphenated command alias.")
    guide = _LEGACY_GUIDE_NAMES.get(resolved, resolved.upper().replace("-", "_"))
    return StrategyNames(module=module, alias=resolved, guide=guide)


def _text(table: dict[str, object], key: str, where: str, *, allow_empty: bool = False) -> str:
    value = table[key]
    if not isinstance(value, str) or not (value or allow_empty):
        raise SiteDataError(f"{where}: {key} must be a non-empty string.")
    return value


def _defines(table: dict[str, object], kind: str, where: str) -> tuple[str, ...]:
    value = table.get("defines")
    if kind != "new_file":
        if value is not None:
            raise SiteDataError(f"{where}: defines is only for new_file sites, not {kind!r}.")
        return ()
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise SiteDataError(f"{where}: a new_file site needs defines, a non-empty list of name patterns.")
    return tuple(value)


def _site(table: dict[str, object], index: int) -> Site:
    where = f"site {index + 1}"
    if not _REQUIRED_KEYS <= set(table) <= _KEYS:
        raise SiteDataError(
            f"{where}: keys {sorted(table)} differ from {sorted(_REQUIRED_KEYS)} plus optional defines."
        )
    kind = _text(table, "kind", where)
    if kind not in get_args(SiteKind):
        raise SiteDataError(f"{where}: kind {kind!r} is not one of {get_args(SiteKind)}.")
    generated = table["generated"]
    if not isinstance(generated, bool):
        raise SiteDataError(f"{where}: generated must be true or false.")
    return Site(
        id=_text(table, "id", where),
        title=_text(table, "title", where),
        why=_text(table, "why", where),
        kind=cast("SiteKind", kind),
        path=_text(table, "path", where),
        generated=generated,
        check=_text(table, "check", where),
        fails=_text(table, "fails", where, allow_empty=True),
        defines=_defines(table, kind, where),
    )


def load_sites(path: Path = SITES_FILE) -> tuple[Site, ...]:
    """Read the site data file into records, in file order; a malformed or duplicated entry raises."""
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    tables = document.get("site")
    if not isinstance(tables, list) or not tables:
        raise SiteDataError(f"{path.name} declares no [[site]] entries.")
    sites = tuple(_site(table, index) for index, table in enumerate(tables))
    for field in ("id", "check"):
        values = [getattr(site, field) for site in sites]
        duplicated = sorted({value for value in values if values.count(value) > 1})
        if duplicated:
            raise SiteDataError(f"{path.name}: {field} values used by more than one site: {duplicated}.")
    return sites
