"""Generate the marked blocks of documentation that are derived from the strategy wiring, or check them for drift.

A generated block sits between an HTML-comment begin and end pair. The begin comment names this script and
says the block is generated and must not be edited by hand; everything between the pair is rewritten from its
source. The conformance suite compares the checked-in text with the regenerated text, so a source change that
is not followed by a regeneration fails the standard test run.

The blocks are the contributor guide's edit-site table, the command list of ``docs/user/USAGE.md`` and the
strategy table of ``docs/user/WORKSPACE.md``; the last two have one entry per strategy in the closed tuple.

Usage, as a module from the repository root::

    uv run python -m scripts.generate_strategy_docs          # rewrite every block
    uv run python -m scripts.generate_strategy_docs --check  # report blocks that are out of date

This is a developer script, not an ``ian`` command.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import Site, load_sites

GENERATOR: Final[str] = "scripts/generate_strategy_docs.py"
GUIDE_FILE: Final[Path] = REPOSITORY_ROOT / "docs" / "project" / "ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md"
USAGE_FILE: Final[Path] = REPOSITORY_ROOT / "docs" / "user" / "USAGE.md"
WORKSPACE_FILE: Final[Path] = REPOSITORY_ROOT / "docs" / "user" / "WORKSPACE.md"
USAGE_BLOCK_ID: Final[str] = "strategy-help-commands"
WORKSPACE_BLOCK_ID: Final[str] = "strategy-table"


class BlockError(ValueError):
    """A document lacks the marker pair of a generated block, or has it more than once."""


@dataclass(frozen=True)
class Block:
    """One generated block: the document that holds it, its identifier and the function that renders its body.

    ``lists`` is set for a block that has one entry per strategy: it tells whether a body has the entry of an alias.
    """

    file: Path
    block_id: str
    render: Callable[[], str]
    lists: Callable[[str, str], bool] | None = None


def begin_marker(block_id: str) -> str:
    """Return the comment that opens a generated block."""
    return f"<!-- BEGIN GENERATED {block_id}: written by {GENERATOR}; generated, do not edit by hand. -->"


def end_marker(block_id: str) -> str:
    """Return the comment that closes a generated block."""
    return f"<!-- END GENERATED {block_id} -->"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_edit_sites(sites: Sequence[Site] | None = None) -> str:
    """Return the contributor guide's edit-site table, one row per site in the site data file."""
    rows = [
        "| Site | Edit | File | Kind | Generated | Check |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for site in load_sites() if sites is None else sites:
        what = f"{site.title}. {site.why}"
        generated = "yes" if site.generated else "no"
        check = f"`{site.check}`: {site.describe()}"
        rows.append(
            f"| `{site.id}` | {_cell(what)} | `{_cell(site.path)}` | {site.kind} | {generated} | {_cell(check)} |"
        )
    return "\n".join(rows)


def _help_command(alias: str) -> str:
    return f"uv run ian {alias} --help"


def guide_name(descriptor: StrategyDescriptor) -> str:
    """Return the file stem of the descriptor's user guide, the upper-case alias with underscores."""
    return descriptor.alias.upper().replace("-", "_")


def render_help_commands(descriptors: Sequence[StrategyDescriptor] | None = None) -> str:
    """Return the usage page's command list: one ``--help`` line per strategy, in the order of the closed tuple."""
    lines = [_help_command(item.alias) for item in (STRATEGIES if descriptors is None else descriptors)]
    return "\n".join(["```bash", *lines, "```"])


def render_strategy_table(descriptors: Sequence[StrategyDescriptor] | None = None) -> str:
    """Return the workspace page's strategy table: alias, name, stored method id and the guide's watchlist options."""
    rows = [
        "| `--analysis` value | Strategy | Stored method id | Method-specific flags |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for item in STRATEGIES if descriptors is None else descriptors:
        link = f"[Watchlist options](strategies/{guide_name(item)}.md#watchlist-options)"
        rows.append(f"| `{item.alias}` | {_cell(item.label)} | `{item.method_id}` | {link} |")
    return "\n".join(rows)


def _lists_help_command(body: str, alias: str) -> bool:
    return _help_command(alias) in body.splitlines()


def _lists_table_row(body: str, alias: str) -> bool:
    return any(line.startswith(f"| `{alias}` |") for line in body.splitlines())


def blocks() -> tuple[Block, ...]:
    """Return every generated block, in the order they are written."""
    return (
        Block(GUIDE_FILE, "edit-sites", render_edit_sites),
        Block(USAGE_FILE, USAGE_BLOCK_ID, render_help_commands, _lists_help_command),
        Block(WORKSPACE_FILE, WORKSPACE_BLOCK_ID, render_strategy_table, _lists_table_row),
    )


def strategy_list_blocks() -> tuple[Block, ...]:
    """Return the blocks that have one entry per strategy."""
    return tuple(block for block in blocks() if block.lists is not None)


def _split_block(text: str, block_id: str) -> tuple[str, str, str]:
    """Return the text before the begin marker, the text between the markers, and the text after the end marker."""
    begin, end = begin_marker(block_id), end_marker(block_id)
    if text.count(begin) != 1 or text.count(end) != 1:
        raise BlockError(f"the marker pair of block {block_id!r} must appear exactly once.")
    head, rest = text.split(begin, maxsplit=1)
    old, tail = rest.split(end, maxsplit=1)
    if "\n" not in old:
        raise BlockError(f"the markers of block {block_id!r} must be on lines of their own.")
    return head, old, tail


def replace_block(text: str, block_id: str, body: str) -> str:
    """Return ``text`` with the body between the block's markers replaced by ``body``."""
    head, _, tail = _split_block(text, block_id)
    return f"{head}{begin_marker(block_id)}\n{body}\n{end_marker(block_id)}{tail}"


def current_body(block: Block) -> str:
    """Return the checked-in text between the block's markers."""
    return _split_block(block.file.read_text(encoding="utf-8"), block.block_id)[1]


def expected_text(block: Block) -> str:
    """Return the text of ``block``'s document with the block regenerated."""
    return replace_block(block.file.read_text(encoding="utf-8"), block.block_id, block.render())


def block_problem(block: Block) -> str | None:
    """Return the sentence that says why ``block`` is missing its markers or differs from its regenerated text."""
    where = block.file.relative_to(REPOSITORY_ROOT).as_posix()
    try:
        current = expected_text(block) == block.file.read_text(encoding="utf-8")
    except BlockError as error:
        return f"{where}: {error} Add the markers, then run {GENERATOR}."
    if not current:
        return f"{where}: the generated block {block.block_id!r} is out of date; run {GENERATOR}"
    return None


def stale_blocks() -> list[str]:
    """Return one sentence per generated block that differs from its regenerated text, naming the file."""
    return [problem for problem in map(block_problem, blocks()) if problem is not None]


def write_blocks() -> list[Path]:
    """Rewrite every generated block, returning the documents whose text changed."""
    changed: list[Path] = []
    for block in blocks():
        updated = expected_text(block)
        if updated != block.file.read_text(encoding="utf-8"):
            block.file.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(block.file)
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    """Rewrite the blocks, or with ``--check`` report stale ones and return 1 when there are any."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="Report blocks that are out of date; write nothing.")
    arguments = parser.parse_args(argv)
    if arguments.check:
        messages = stale_blocks()
        sys.stderr.write("".join(f"{message}\n" for message in messages))
        return 1 if messages else 0
    changed = write_blocks()
    sys.stdout.write(
        "".join(f"wrote {path.relative_to(REPOSITORY_ROOT).as_posix()}\n" for path in changed)
        or "generated blocks are current\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
