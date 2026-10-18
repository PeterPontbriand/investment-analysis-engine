"""The strategy generator: its insertions, its refusal to overwrite, its restoring and its templates."""

import ast
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from string import Template
from typing import Final

import pytest

from scripts import new_strategy
from scripts.new_strategy import (
    EDITED_FILES,
    EDITS,
    PACKAGE,
    STUB_ROLES,
    TEMPLATE_DIRECTORY,
    ConflictError,
    GenerationError,
    Spec,
    add_import_name,
    append_enum_member,
    append_imports,
    append_tuple_entry,
    append_union_member,
    apply_plan,
    bound_names,
    build_plan,
    enum_length,
    insert_before,
    main,
    tuple_length,
    union_length,
)
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import strategy_names

WHERE: Final = "example.py"


def _unchanged(path: Path, source: str) -> str:
    """Stand in for Ruff, so a test of the insertions does not start a subprocess per file."""
    del path
    return source


def _mini_tree(tmp_path: Path) -> Path:
    """Return a folder holding what the generator reads: the five files it edits and every strategy vocabulary."""
    root = tmp_path / "repository"
    shutil.copyfile(REPOSITORY_ROOT / "pyproject.toml", _ensure(root / "pyproject.toml"))
    sources = [REPOSITORY_ROOT / PACKAGE / name for name in EDITED_FILES]
    sources.extend((REPOSITORY_ROOT / PACKAGE / "strategies").glob("*/vocabulary.py"))
    for source in sources:
        shutil.copyfile(source, _ensure(root / source.relative_to(REPOSITORY_ROOT)))
    return root


def _ensure(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _run(root: Path, *arguments: str, clean: Callable[[Path, str], str] | None = _unchanged) -> int:
    return main(list(arguments), root=root, clean=clean)


# ---------------------------------------------------------------------------
# A generated strategy
# ---------------------------------------------------------------------------


def test_the_generator_writes_the_stubs_and_adds_exactly_one_entry_to_each_closed_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With Ruff running, every stub is written, each edited file parses, and each list grew by one."""
    root = _mini_tree(tmp_path)
    before = _snapshot(root)

    assert _run(root, "fresh_probe", "--label", "Fresh Probe", clean=None) == 0

    output = capsys.readouterr().out
    package = root / PACKAGE / "strategies" / "fresh_probe"
    assert sorted(path.name for path in package.iterdir()) == sorted(["__init__.py", *(f"{r}.py" for r in STUB_ROLES)])
    assert (package / "__init__.py").read_text(encoding="utf-8") == ""
    for role in STUB_ROLES:
        assert f"created  {PACKAGE}/strategies/fresh_probe/{role}.py" in output
    for entry in EDITS:
        path = root / PACKAGE / entry.relative
        old, new = before[path.relative_to(root).as_posix()].decode(), path.read_text(encoding="utf-8")
        ast.parse(new)
        for name in entry.tuples:
            assert tuple_length(new, name, entry.relative) == tuple_length(old, name, entry.relative) + 1
        for name in entry.unions:
            assert union_length(new, name, entry.relative) == union_length(old, name, entry.relative) + 1
        for name in entry.enums:
            assert enum_length(new, name, entry.relative) == enum_length(old, name, entry.relative) + 1
        assert f"edited   {PACKAGE}/{entry.relative}" in output
    wiring = (root / PACKAGE / "strategy_wiring.py").read_text(encoding="utf-8")
    assert 'alias="fresh-probe"' in wiring
    assert "settings_type=None" in wiring.split("FRESH_PROBE: Final")[1]
    assert "uv run python scripts/strategy_status.py fresh_probe --alias fresh-probe" in output


def test_a_second_run_refuses_and_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """After a successful run the same strategy conflicts everywhere it was added; exit 2 and no file changes."""
    root = _mini_tree(tmp_path)
    assert _run(root, "fresh_probe", "--label", "Fresh Probe") == 0
    after_first = _snapshot(root)
    capsys.readouterr()

    assert _run(root, "fresh_probe", "--label", "Fresh Probe") == 2

    error = capsys.readouterr().err
    assert "Nothing was written" in error
    assert f"{PACKAGE}/strategies/fresh_probe/codec.py already exists" in error
    assert f"{PACKAGE}/strategy_wiring.py: FRESH_PROBE is already defined" in error
    assert "the alias 'fresh-probe' is already declared" in error
    assert "the tool 'analyze_fresh_probe' is already declared" in error
    assert _snapshot(root) == after_first


@pytest.mark.parametrize(
    ("arguments", "conflict"),
    [
        (("fresh", "--alias", "momentum"), "the alias 'momentum' is already declared"),
        (("sma_crossover",), "the method id 'sma_crossover' is already used"),
        (("graham_number",), "the analysis id 'graham_number' is already used"),
        (("graham_growth_value",), "the tool 'analyze_graham_growth_value' is already declared"),
        (("momentum",), f"{PACKAGE}/strategies/momentum/vocabulary.py already exists"),
    ],
)
def test_a_name_that_exists_is_a_conflict_that_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], arguments: tuple[str, ...], conflict: str
) -> None:
    """The alias, method id, analysis id, tool and files of an existing strategy are each refused with exit 2."""
    root = _mini_tree(tmp_path)
    before = _snapshot(root)

    assert _run(root, *arguments, "--label", "Fresh") == 2

    assert conflict in capsys.readouterr().err
    assert _snapshot(root) == before


def test_a_name_an_edited_file_already_binds_is_a_conflict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A constant the insertion would add, already defined in the target file, is refused."""
    root = _mini_tree(tmp_path)
    wiring = root / PACKAGE / "strategy_wiring.py"
    wiring.write_text(wiring.read_text(encoding="utf-8") + "\nFRESH = 1\n", encoding="utf-8")
    before = _snapshot(root)

    assert _run(root, "fresh", "--label", "Fresh") == 2

    assert f"{PACKAGE}/strategy_wiring.py: FRESH is already defined" in capsys.readouterr().err
    assert _snapshot(root) == before


def test_an_existing_empty_package_folder_is_a_conflict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A folder of the strategy's name blocks the run even when none of the generated files is in it."""
    root = _mini_tree(tmp_path)
    (root / PACKAGE / "strategies" / "fresh").mkdir()

    assert _run(root, "fresh", "--label", "Fresh") == 2

    assert f"{PACKAGE}/strategies/fresh already exists" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# A failed write
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fail_at", [0, 6, 11, 12, 13, 16])
def test_a_failed_write_restores_every_original_and_removes_what_it_created(tmp_path: Path, fail_at: int) -> None:
    """Whichever replacement fails, the tree is byte-for-byte what it was, with no folder or temporary file left."""
    root = _mini_tree(tmp_path)
    before = _snapshot(root)
    plan = build_plan(root, strategy_names("fresh"), "Fresh", clean=_unchanged)
    calls: list[Path] = []

    def replace(source: Path, target: Path) -> None:
        if len(calls) == fail_at:
            raise OSError("disk full")
        calls.append(target)
        source.replace(target)

    with pytest.raises(OSError, match="disk full"):
        apply_plan(plan, replace=replace)

    assert len(calls) == fail_at
    assert _snapshot(root) == before
    assert not plan.package_directory.exists()


def test_a_failed_write_reports_that_the_originals_were_restored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command returns 1, not a traceback, and says what it did."""
    root = _mini_tree(tmp_path)

    def failing(_plan: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(new_strategy, "apply_plan", failing)

    assert _run(root, "fresh", "--label", "Fresh") == 1

    assert "Writing failed and the originals were restored: disk full" in capsys.readouterr().err


def test_a_change_that_cannot_be_built_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When Ruff rejects a generated file the command returns 1 and the tree is untouched."""
    root = _mini_tree(tmp_path)
    before = _snapshot(root)

    def rejecting(path: Path, _source: str) -> str:
        raise GenerationError(f"ruff reports violations in the generated {path.name}")

    assert _run(root, "fresh", "--label", "Fresh", clean=rejecting) == 1

    assert "Nothing was written: ruff reports violations" in capsys.readouterr().err
    assert _snapshot(root) == before


def test_the_conflicts_error_names_the_first_conflict() -> None:
    """The error that carries the list also summarizes it."""
    error = ConflictError(["a", "b"])
    assert error.conflicts == ("a", "b")
    assert "2 conflict(s): a" in str(error)


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arguments",
    [
        ["Fresh", "--label", "Fresh"],
        ["fresh", "--label", "Bad;Label"],
        ["fresh", "--label", '"quoted"'],
        ["fresh", "--label", "Fresh", "--alias", "Bad_Alias"],
        ["fresh"],
    ],
)
def test_a_malformed_name_label_or_alias_is_a_usage_error(tmp_path: Path, arguments: list[str]) -> None:
    """A name that is not snake_case, a label with punctuation, a bad alias or a missing label exits with 2."""
    root = _mini_tree(tmp_path)
    before = _snapshot(root)

    with pytest.raises(SystemExit) as raised:
        main(arguments, root=root, clean=_unchanged)

    assert raised.value.code == 2
    assert _snapshot(root) == before


def test_the_names_derive_from_the_module_name() -> None:
    """The class prefix, constant prefix and tool name follow the module name."""
    spec = Spec(strategy_names("fcf_growth"), "FCF Growth")
    assert (spec.class_name, spec.upper, spec.tool_member, spec.tool_value) == (
        "FcfGrowth",
        "FCF_GROWTH",
        "ANALYZE_FCF_GROWTH",
        "analyze_fcf_growth",
    )
    assert spec.names.alias == "fcf-growth"


# ---------------------------------------------------------------------------
# The insertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("T = (A, B)\n", "T = (A, B, C)\n"),
        ("T = (\n    A,\n    B,\n)\n", "T = (\n    A,\n    B,\n    C,\n)\n"),
        ("T = (\n    A,\n    B\n)\n", "T = (\n    A,\n    B, C\n)\n"),
        ("T: Final = (f(1), g(2))\n", "T: Final = (f(1), g(2), C)\n"),
    ],
)
def test_a_tuple_entry_is_appended_whatever_the_layout(source: str, expected: str) -> None:
    """The entry goes after the last element and its trailing comma, if there is one."""
    assert append_tuple_entry(source, "T", "C", WHERE) == expected
    assert tuple_length(expected, "T", WHERE) == tuple_length(source, "T", WHERE) + 1


def test_a_union_member_enum_member_and_import_are_inserted_where_the_tree_says() -> None:
    """Each insertion lands at the node's position and leaves the file parseable."""
    source = (
        '"""Doc."""\n\nimport os\nfrom a import b\n\nU = X | Y\n\n\nclass E(Enum):\n    """Doc."""\n\n    A = "a"\n'
    )
    edited = append_union_member(source, "U", "Z", WHERE)
    edited = append_enum_member(edited, "E", 'B = "b"', WHERE)
    edited = append_imports(edited, ["from c import d"], WHERE)
    assert edited == (
        '"""Doc."""\n\nimport os\nfrom a import b\nfrom c import d\n\nU = X | Y | Z\n\n\n'
        'class E(Enum):\n    """Doc."""\n\n    A = "a"\n    B = "b"\n'
    )
    assert (union_length(edited, "U", WHERE), enum_length(edited, "E", WHERE)) == (3, 2)


def test_an_import_name_is_added_to_the_existing_statement_and_a_constant_goes_before_its_tuple() -> None:
    """The existing ``from`` statement is rewritten with one more name, aliases kept."""
    source = "from m import (\n    a as b,\n    c,\n)\n\nT = (1,)\n"
    edited = add_import_name(source, "m", "d", WHERE)
    assert edited.startswith("from m import (\n    a as b,\n    c,\n    d,\n)\n")
    inserted = insert_before(edited, "T", "NEW = 1\nOTHER = 2\n", WHERE)
    assert inserted.endswith("NEW = 1\nOTHER = 2\n\nT = (1,)\n")


def test_a_position_after_non_ascii_text_is_found_by_bytes() -> None:
    """The syntax tree counts columns in bytes, so a line with a non-ASCII character still takes the entry in place."""
    source = 'NOTE = "é"; T = (A, B)\n'
    assert append_tuple_entry(source, "T", "C", WHERE) == 'NOTE = "é"; T = (A, B, C)\n'


def test_the_names_a_module_binds_are_found() -> None:
    """Imports, assignments, annotated assignments, functions and classes all bind a name."""
    source = (
        "import a.b\nfrom c import d as e\nF = 1\nG: int = 2\n\n\ndef h() -> None:\n    pass\n\n\nclass I:\n    pass\n"
    )
    assert bound_names(source, WHERE) == {"a", "e", "F", "G", "h", "I"}


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (lambda: tuple_length("X = 1\n", "T", WHERE), "has no module-level assignment to T"),
        (lambda: tuple_length("T = [1]\n", "T", WHERE), "T is not a tuple"),
        (lambda: enum_length("X = 1\n", "E", WHERE), "defines no class E"),
        (lambda: append_imports("X = 1\n", ["import y"], WHERE), "has no import to insert after"),
        (lambda: add_import_name("import x\n", "m", "d", WHERE), "has no 'from m import' statement"),
        (lambda: union_length("def (", "U", WHERE), "does not parse"),
    ],
)
def test_an_edit_that_cannot_be_located_is_an_error(operation: Callable[[], object], message: str) -> None:
    """A file that lacks the declaration, or does not parse, stops the generator with a reason."""
    with pytest.raises(GenerationError, match=message):
        operation()


def test_an_edit_that_does_not_grow_each_list_by_exactly_one_is_rejected() -> None:
    """The entry-count assertion fires for an edit that adds nothing, adds two, or breaks the syntax."""
    entry = new_strategy.EditedFile("x.py", lambda _spec, source, _where: (source, ()), tuples=("T",))
    before = "T = (A,)\n"
    with pytest.raises(GenerationError, match=re.escape("from [1] to [1], not up by one")):
        new_strategy._assert_grew_by_one(entry, before, before, "x.py")
    with pytest.raises(GenerationError, match=re.escape("from [1] to [3], not up by one")):
        new_strategy._assert_grew_by_one(entry, before, "T = (A, B, C)\n", "x.py")
    with pytest.raises(GenerationError, match="does not parse"):
        new_strategy._assert_grew_by_one(entry, before, "T = (A, B", "x.py")


# ---------------------------------------------------------------------------
# The templates
# ---------------------------------------------------------------------------


def test_every_stub_role_has_a_template_and_every_template_a_role() -> None:
    """The role list and the template folder agree."""
    assert sorted(path.name for path in TEMPLATE_DIRECTORY.glob("*.tmpl")) == sorted(f"{r}.py.tmpl" for r in STUB_ROLES)


@pytest.mark.parametrize("role", STUB_ROLES)
def test_a_template_contains_no_cast_and_no_type_ignore(role: str) -> None:
    """A generated file crosses the closed types by being named in them, never by ``cast`` or ``type: ignore``."""
    text = (TEMPLATE_DIRECTORY / f"{role}.py.tmpl").read_text(encoding="utf-8")
    assert "cast" not in text
    assert "type: ignore" not in text


@pytest.mark.parametrize("role", STUB_ROLES)
def test_a_template_substitutes_every_placeholder_into_valid_python(role: str) -> None:
    """Substituting the spec leaves no placeholder behind and yields a module that parses."""
    spec = Spec(strategy_names("fresh_probe"), "Fresh Probe")
    text = Template((TEMPLATE_DIRECTORY / f"{role}.py.tmpl").read_text(encoding="utf-8")).substitute(
        spec.substitutions()
    )
    assert "$" not in text
    ast.parse(text)
    assert "fresh_probe" in text or role == "analyzer"
