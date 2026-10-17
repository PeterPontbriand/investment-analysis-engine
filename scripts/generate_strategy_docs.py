"""Generate the marked blocks of documentation that are derived from the strategy wiring, or check them for drift.

A generated block sits between an HTML-comment begin and end pair. The begin comment names this script and
says the block is generated and must not be edited by hand; everything between the pair is rewritten from its
source. The conformance suite compares the checked-in text with the regenerated text, so a source change that
is not followed by a regeneration fails the standard test run.

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

from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import Site, load_sites

GENERATOR: Final[str] = "scripts/generate_strategy_docs.py"
GUIDE_FILE: Final[Path] = REPOSITORY_ROOT / "docs" / "project" / "ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md"


class BlockError(ValueError):
    """A document lacks the marker pair of a generated block, or has it more than once."""


@dataclass(frozen=True)
class Block:
    """One generated block: the document that holds it, its identifier and the function that renders its body."""

    file: Path
    block_id: str
    render: Callable[[], str]


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
        check = f"`{site.check}`: {site.fails}"
        rows.append(
            f"| `{site.id}` | {_cell(what)} | `{_cell(site.path)}` | {site.kind} | {generated} | {_cell(check)} |"
        )
    return "\n".join(rows)


def blocks() -> tuple[Block, ...]:
    """Return every generated block, in the order they are written."""
    return (Block(GUIDE_FILE, "edit-sites", render_edit_sites),)


def replace_block(text: str, block_id: str, body: str) -> str:
    """Return ``text`` with the body between the block's markers replaced by ``body``."""
    begin, end = begin_marker(block_id), end_marker(block_id)
    if text.count(begin) != 1 or text.count(end) != 1:
        raise BlockError(f"the marker pair of block {block_id!r} must appear exactly once.")
    head, rest = text.split(begin, maxsplit=1)
    old, tail = rest.split(end, maxsplit=1)
    if "\n" not in old:
        raise BlockError(f"the markers of block {block_id!r} must be on lines of their own.")
    return f"{head}{begin}\n{body}\n{end}{tail}"


def expected_text(block: Block) -> str:
    """Return the text of ``block``'s document with the block regenerated."""
    return replace_block(block.file.read_text(encoding="utf-8"), block.block_id, block.render())


def stale_blocks() -> list[str]:
    """Return one sentence per generated block that differs from its regenerated text, naming the file."""
    messages: list[str] = []
    for block in blocks():
        where = block.file.relative_to(REPOSITORY_ROOT).as_posix()
        try:
            current = expected_text(block) == block.file.read_text(encoding="utf-8")
        except BlockError as error:
            messages.append(f"{where}: {error} Add the markers, then run {GENERATOR}.")
            continue
        if not current:
            messages.append(f"{where}: the generated block {block.block_id!r} is out of date; run {GENERATOR}")
    return messages


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
