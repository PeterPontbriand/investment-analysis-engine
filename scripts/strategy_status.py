"""Report which edit sites of a strategy are done and which are missing.

Usage, from the repository root::

    uv run python scripts/strategy_status.py <module_name> [--alias <alias>]
    uv run python scripts/strategy_status.py --specimen

For each site in ``scripts/strategy_sites.toml``, in file order, the command prints ``done`` or ``missing``,
the site id and the resolved path; a missing site is followed by one indented line per diagnostic. A site is
done exactly when its check function in ``scripts/strategy_conformance.py`` returns no gaps for the strategy,
so the command and the conformance tests cannot disagree. The command does not run the type checker; the
managed quality gate does.

``--specimen`` checks the specimen strategy of the conformance tests (``tests/specimen``) instead, in the site
context that strategy defines. Two sites are type-level and closed to the specimen; they are reported as
``covered`` with where they are checked, and their checks are not run.

Exit code 0 when every site is done or covered, 1 when any is missing or the package cannot be imported, 2 for a
usage error. This is a developer script, not an ``ian`` command.
"""

import argparse
import importlib
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

if __package__ in {None, ""}:
    # Run as a file, only this folder is on the import path; the documented working directory is the repository root.
    sys.path.insert(0, str(Path.cwd()))

from scripts.strategy_sites import (  # noqa: E402 - after the path adjustment above
    Gap,
    SiteDataError,
    StrategyNames,
    load_sites,
    strategy_names,
)

IMPORT_SITE_ID = "import"
CONFORMANCE_MODULE = "scripts.strategy_conformance"
SPECIMEN_MODULE = "tests.specimen.site_context"


def import_gap(error: BaseException) -> Gap:
    """Return the gap that reports a package which cannot be imported, so no site can be checked."""
    return Gap(
        IMPORT_SITE_ID,
        CONFORMANCE_MODULE.replace(".", "/") + ".py",
        f"the package could not be imported, so no site was checked: {type(error).__name__}: {error}; "
        "a strategy file or a wiring entry that the descriptor needs was probably removed or renamed",
    )


def _checks(module: ModuleType) -> Callable[[str], Callable[..., list[Gap]]]:
    def lookup(name: str) -> Callable[..., list[Gap]]:
        found: Callable[..., list[Gap]] = getattr(module, name)
        return found

    return lookup


def report(names: StrategyNames, context: object | None = None) -> tuple[list[str], bool]:
    """Return the report lines for ``names`` and whether every site is done or covered.

    ``context`` is the site context the checks look at; the production wiring when ``None``.
    """
    try:
        conformance = importlib.import_module(CONFORMANCE_MODULE)
    except Exception as error:  # noqa: BLE001 - any import failure is the first gap being reported
        gap = import_gap(error)
        return [f"missing  {gap.site_id}  {gap.path}", f"    {gap.message}"], False
    lookup = _checks(conformance)
    lines: list[str] = []
    complete = True
    covered: dict[str, str] = getattr(context, "covered", {})
    for site in load_sites():
        where = site.resolved_path(names) if context is None else conformance.site_path(site.id, names, context)
        if site.id in covered:
            lines.extend([f"covered  {site.id}  {where}", f"    {covered[site.id]}"])
            continue
        try:
            check = lookup(site.check)
            gaps = check(names) if context is None else check(names, context)
        except Exception as error:  # noqa: BLE001 - a check that raises is a site that cannot be shown done
            gaps = [Gap(site.id, where, f"the check {site.check} raised {type(error).__name__}: {error}")]
        if gaps:
            complete = False
            lines.append(f"missing  {site.id}  {where}")
            lines.extend(f"    {gap.message}" for gap in gaps)
        else:
            lines.append(f"done     {site.id}  {where}")
    return lines, complete


def main(argv: Sequence[str] | None = None) -> int:
    """Print the status of one strategy's sites and return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument(
        "module_name",
        nargs="?",
        help="The strategy's package name under investment_analysis_engine/strategies.",
    )
    parser.add_argument("--alias", help="The strategy's command alias; defaults to the module name with hyphens.")
    parser.add_argument(
        "--specimen", action="store_true", help="Check the specimen strategy of tests/specimen instead of a module."
    )
    arguments = parser.parse_args(argv)
    if arguments.specimen:
        if arguments.module_name is not None or arguments.alias is not None:
            parser.error("--specimen takes no module name or alias.")
        specimen = importlib.import_module(SPECIMEN_MODULE)
        lines, complete = report(specimen.SPECIMEN_NAMES, specimen.SPECIMEN_CONTEXT)
    else:
        if arguments.module_name is None:
            parser.error("a module name is required unless --specimen is given.")
        try:
            names = strategy_names(arguments.module_name, arguments.alias)
        except SiteDataError as error:
            parser.error(str(error))
        lines, complete = report(names)
    sys.stdout.write("".join(f"{line}\n" for line in lines))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
