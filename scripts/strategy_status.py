"""Report which edit sites of a strategy are done and which are missing.

Usage, from the repository root::

    uv run python -m scripts.strategy_status <module_name> [--alias <alias>]
    uv run python -m scripts.strategy_status --specimen

For each site in ``scripts/strategy_sites.toml``, in file order, the command prints ``done`` or ``missing``,
the site id and the resolved path; a missing site is followed by one indented line per diagnostic. A site is
done exactly when its check function in ``scripts/strategy_conformance.py`` returns no gaps for the strategy,
so the command and the conformance tests cannot disagree. A file of a new-file site that still calls
``unfilled_stub`` is missing, with the line of each call; a site whose check runs stored code that needs another
site's unfilled body is reported ``not checked``, naming that site, its file and line. The command does not run
the type checker; the managed quality gate does.

When the package cannot be imported, no check can run. The command then matches the failing module or file,
from the exception and its traceback, against the strategy's site paths and prints ``missing <site-id>`` with
the file to change and the original error; an error that matches no site is printed as ``missing  import``.

``--specimen`` checks the specimen strategy of the conformance tests (``tests/specimen``) instead, in the site
context that strategy defines. Two sites are type-level and closed to the specimen; they are reported as
``covered`` with where they are checked, and their checks are not run.

Exit code 0 when every site is done or covered, 1 when any is missing or the package cannot be imported, 2 for a
usage error. This is a developer script, not an ``ian`` command.
"""

import argparse
import importlib
import sys
import traceback
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType

if __package__ in {None, ""}:
    # Run as a file, only this folder is on the import path; the documented working directory is the repository root.
    sys.path.insert(0, str(Path.cwd()))

from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError  # noqa: E402
from scripts.repository_root import REPOSITORY_ROOT  # noqa: E402 - after the path adjustment above
from scripts.strategy_sites import (  # noqa: E402 - after the path adjustment above
    Gap,
    Site,
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


def _module_file(module: str) -> str:
    """Return the repository-relative path of a dotted module name's file."""
    return module.replace(".", "/") + ".py"


def _repository_path(filename: str) -> str | None:
    """Return a file name's path relative to the repository root, or ``None`` when it lies outside it."""
    if filename.startswith("<"):
        return None
    try:
        return Path(filename).resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except (OSError, ValueError):
        return None


def _failing_files(error: BaseException) -> Iterator[str]:
    """Yield the repository-relative files an import failure points at, the most specific first.

    The order is the file or module the error itself names (a module that does not exist, a module that lacks a
    name, the class or module that lacks an attribute), then the frames of its traceback, innermost first.
    """
    if isinstance(error, ImportError):
        if error.path is not None and (relative := _repository_path(error.path)) is not None:
            yield relative
        if error.name:
            yield _module_file(error.name)
    elif isinstance(error, AttributeError):
        owner = error.obj if hasattr(error, "obj") else None
        module = owner.__name__ if isinstance(owner, ModuleType) else getattr(owner, "__module__", None)
        if isinstance(module, str):
            yield _module_file(module)
    for frame in reversed(traceback.extract_tb(error.__traceback__)):
        if (relative := _repository_path(frame.filename)) is not None:
            yield relative


def attributed_site(error: BaseException, names: StrategyNames, sites: Sequence[Site]) -> Site | None:
    """Return the site whose file is the first of those ``error`` points at that is a site's file, if any."""
    by_path: dict[str, Site] = {}
    for site in sites:
        by_path.setdefault(site.resolved_path(names), site)
    return next((by_path[path] for path in _failing_files(error) if path in by_path), None)


def wiring_failure_lines(error: BaseException, names: StrategyNames, culprit: Site, checked: Site) -> list[str]:
    """Return the report for a check that failed in the wiring of another site: that site and the file to change."""
    return [
        f"missing  {culprit.id}  {culprit.resolved_path(names)}",
        f"    the check of {checked.id} could not run; restore or write this site ({culprit.title}), "
        f"then run the command again. Original error: {type(error).__name__}: {error}",
    ]


def import_failure_lines(error: BaseException, names: StrategyNames) -> list[str]:
    """Return the report for a package that cannot be imported: the site it is attributed to, else ``import``."""
    site = attributed_site(error, names, load_sites())
    if site is None:
        gap = import_gap(error)
        return [f"missing  {gap.site_id}  {gap.path}", f"    {gap.message}"]
    return [
        f"missing  {site.id}  {site.resolved_path(names)}",
        "    the package could not be imported, so no other site was checked; restore or write this site "
        f"({site.title}), then run the command again. Original error: {type(error).__name__}: {error}",
    ]


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
        return import_failure_lines(error, names), False
    lookup = _checks(conformance)
    lines: list[str] = []
    complete = True
    covered: dict[str, str] = getattr(context, "covered", {})
    sites = load_sites()
    for site in sites:
        where = site.resolved_path(names) if context is None else conformance.site_path(site.id, names, context)
        if site.id in covered:
            lines.extend([f"covered  {site.id}  {where}", f"    {covered[site.id]}"])
            continue
        try:
            check = lookup(site.check)
            gaps = check(names) if context is None else check(names, context)
        except Exception as error:  # noqa: BLE001 - a check that raises is a site that cannot be shown done
            culprit = attributed_site(error, names, sites) if isinstance(error, UndeclaredStrategyError) else None
            if culprit is not None and culprit.id != site.id:
                # The wiring of another site is what this check needed: report that site, with the file to change.
                complete = False
                lines.extend(wiring_failure_lines(error, names, culprit, site))
                continue
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
