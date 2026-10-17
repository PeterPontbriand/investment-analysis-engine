"""The generated documentation blocks are written from their sources and checked for drift."""

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import generate_strategy_docs as generator
from scripts.generate_strategy_docs import (
    BlockError,
    begin_marker,
    end_marker,
    render_edit_sites,
    replace_block,
    stale_blocks,
)
from scripts.strategy_sites import load_sites


def test_the_checked_in_blocks_are_current() -> None:
    assert stale_blocks() == []


def test_the_table_has_one_row_per_site_in_file_order() -> None:
    rows = render_edit_sites().splitlines()[2:]
    sites = load_sites()
    assert len(rows) == len(sites)
    assert [row.split("|")[1].strip() for row in rows] == [f"`{site.id}`" for site in sites]


def test_a_pipe_in_a_cell_is_escaped() -> None:
    site = load_sites()[0]
    row = render_edit_sites([replace(site, why="a | b")]).splitlines()[2]
    assert "a \\| b" in row


def test_the_begin_marker_names_the_generator_and_forbids_hand_edits() -> None:
    marker = begin_marker("edit-sites")
    assert marker.startswith("<!--")
    assert marker.endswith("-->")
    assert "scripts/generate_strategy_docs.py" in marker
    assert "generated" in marker
    assert "do not edit by hand" in marker


def test_replace_block_rewrites_only_the_body() -> None:
    text = f"before\n{begin_marker('x')}\nold\n{end_marker('x')}\nafter\n"
    assert replace_block(text, "x", "new") == f"before\n{begin_marker('x')}\nnew\n{end_marker('x')}\nafter\n"


def test_replace_block_requires_exactly_one_marker_pair() -> None:
    with pytest.raises(BlockError, match="exactly once"):
        replace_block("no markers\n", "x", "new")
    pair = f"{begin_marker('x')}\n{end_marker('x')}\n"
    with pytest.raises(BlockError, match="exactly once"):
        replace_block(pair + pair, "x", "new")


def test_a_stale_block_names_the_file_and_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = tmp_path / "guide.md"
    document.write_text(f"{begin_marker('edit-sites')}\nstale\n{end_marker('edit-sites')}\n", encoding="utf-8")
    block = generator.Block(document, "edit-sites", lambda: "fresh")
    monkeypatch.setattr(generator, "blocks", lambda: (block,))
    monkeypatch.setattr(generator, "REPOSITORY_ROOT", tmp_path)
    assert stale_blocks() == [
        "guide.md: the generated block 'edit-sites' is out of date; run scripts/generate_strategy_docs.py"
    ]
    assert generator.write_blocks() == [document]
    assert stale_blocks() == []
    assert generator.write_blocks() == []


def test_a_document_without_markers_is_reported_with_the_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = tmp_path / "guide.md"
    document.write_text("nothing\n", encoding="utf-8")
    monkeypatch.setattr(generator, "blocks", lambda: (generator.Block(document, "edit-sites", lambda: "x"),))
    monkeypatch.setattr(generator, "REPOSITORY_ROOT", tmp_path)
    (message,) = stale_blocks()
    assert message.startswith("guide.md: ")
    assert "scripts/generate_strategy_docs.py" in message


def test_main_check_reports_and_main_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    document = tmp_path / "guide.md"
    document.write_text(f"{begin_marker('b')}\nstale\n{end_marker('b')}\n", encoding="utf-8")
    monkeypatch.setattr(generator, "blocks", lambda: (generator.Block(document, "b", lambda: "fresh"),))
    monkeypatch.setattr(generator, "REPOSITORY_ROOT", tmp_path)
    assert generator.main(["--check"]) == 1
    assert "out of date" in capsys.readouterr().err
    assert generator.main([]) == 0
    assert capsys.readouterr().out == "wrote guide.md\n"
    assert generator.main(["--check"]) == 0
    assert generator.main([]) == 0
    assert capsys.readouterr().out == "generated blocks are current\n"
