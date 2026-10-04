"""Verify that string-based mock targets in ``tests/`` resolve to existing attributes.

Strict forms: the dotted string of ``patch("a.b.c")`` and the string form of
``monkeypatch.setattr("a.b.c", value)``. Every one must import and resolve. A target the scanner cannot
evaluate to literal strings (a name, a conditional, a concatenation, an f-string or ``.replace`` over
literals, ``parametrize`` values, ``for`` loops over literals) is reported, never skipped.

Object forms: ``patch.object(obj, "name")`` and ``monkeypatch.setattr(obj, "name", value)``. They are
checked only where ``obj`` is a name or attribute chain whose only binding in the module is a
module-level import resolving to a module or class. Any other ``obj`` is left to the runtime, which
raises on a missing attribute.
"""

from __future__ import annotations

import ast
import importlib
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

_TESTS_ROOT = Path(__file__).resolve().parent
_PATCH = frozenset({"patch", "mock.patch", "unittest.mock.patch"})
_PATCH_OBJECT = frozenset({"patch.object", "mock.patch.object", "unittest.mock.patch.object"})
_MINIMUM_DOTTED_TARGETS = 250
_MISSING = object()

type _Function = ast.FunctionDef | ast.AsyncFunctionDef
type _Env = dict[str, tuple[str, ...]]


@dataclass
class _Scan:
    """What one module's scan checked and what failed."""

    dotted: int = 0
    objects: int = 0
    errors: list[str] = field(default_factory=list)


def _resolve(dotted: str) -> object:
    """Import the longest module prefix of a dotted path and follow the remaining attributes."""
    parts = dotted.split(".")
    for end in range(len(parts), 0, -1):
        try:
            value: object = importlib.import_module(".".join(parts[:end]))
        except (ImportError, ValueError):
            continue
        for attribute in parts[end:]:
            if not hasattr(value, attribute):
                return _MISSING
            value = getattr(value, attribute)
        return value
    return _MISSING


def _combine(parts: list[tuple[str, ...]]) -> tuple[str, ...]:
    """Return every concatenation of one value from each part."""
    return tuple(dict.fromkeys("".join(choice) for choice in itertools.product(*parts)))


def _values(node: ast.expr, env: _Env) -> tuple[str, ...] | None:  # noqa: PLR0911 -- one exit per supported form.
    """Evaluate an expression to the literal strings it can take, or ``None`` when it cannot be evaluated."""
    if isinstance(node, ast.Constant):
        return (node.value,) if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.IfExp):
        body, orelse = _values(node.body, env), _values(node.orelse, env)
        return tuple(dict.fromkeys((*body, *orelse))) if body is not None and orelse is not None else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _values(node.left, env), _values(node.right, env)
        return _combine([left, right]) if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        pieces: list[tuple[str, ...]] = []
        for part in node.values:
            if isinstance(part, ast.FormattedValue) and (part.conversion != -1 or part.format_spec):
                return None
            piece = _values(part.value if isinstance(part, ast.FormattedValue) else part, env)
            if piece is None:
                return None
            pieces.append(piece)
        return _combine(pieces)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "replace"
        and len(node.args) == 2
    ):
        base, old, new = _values(node.func.value, env), _values(node.args[0], env), _values(node.args[1], env)
        if base is None or old is None or new is None:
            return None
        return tuple(dict.fromkeys(b.replace(o, n) for b in base for o in old for n in new))
    return None


def _literal_strings(node: ast.expr) -> tuple[str, ...] | None:
    """Return the strings of a tuple or list made only of string literals."""
    if not isinstance(node, (ast.Tuple, ast.List)):
        return None
    items = [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
    return tuple(items) if len(items) == len(node.elts) else None


def _parametrized(function: _Function) -> _Env:
    """Collect string values bound by ``pytest.mark.parametrize`` decorators."""
    env: _Env = {}
    for decorator in function.decorator_list:
        if not (isinstance(decorator, ast.Call) and ast.unparse(decorator.func).endswith("parametrize")):
            continue
        if len(decorator.args) < 2 or not isinstance(decorator.args[0], ast.Constant):
            continue
        names = [name.strip() for name in str(decorator.args[0].value).split(",")]
        rows = decorator.args[1]
        if not isinstance(rows, (ast.Tuple, ast.List)):
            continue
        for index, name in enumerate(names):
            cells = [
                row.elts[index]
                if len(names) > 1 and isinstance(row, (ast.Tuple, ast.List)) and index < len(row.elts)
                else row
                for row in rows.elts
            ]
            strings = [cell.value for cell in cells if isinstance(cell, ast.Constant) and isinstance(cell.value, str)]
            if strings and len(strings) == len(cells):
                env[name] = tuple(strings)
    return env


def _environment(nodes: list[ast.AST], base: _Env) -> _Env:
    """Evaluate the ``for`` loops over literals and simple assignments found in ``nodes``."""
    env = dict(base)
    assigns: list[tuple[str, ast.expr]] = []
    for root in nodes:
        for node in ast.walk(root):
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                if (strings := _literal_strings(node.iter)) is not None:
                    env[node.target.id] = strings
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                assigns.append((node.targets[0].id, node.value))
    for _ in assigns:
        for name, value in assigns:
            if (strings := _values(value, env)) is not None:
                env[name] = tuple(dict.fromkeys((*env.get(name, ()), *strings)))
    return env


def _importable_bindings(tree: ast.Module) -> dict[str, object]:
    """Map each module-level import bound once, and nowhere rebound, to the module or class it names."""
    rebound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            rebound.add(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            rebound.update(a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs))
            rebound.update(a.arg for a in (arguments.vararg, arguments.kwarg) if a)
        if isinstance(node, ast.ExceptHandler) and node.name:
            rebound.add(node.name)
    found: dict[str, object] = {}
    seen: set[str] = set()
    for node in tree.body:
        pairs: list[tuple[str, str]] = []
        if isinstance(node, ast.Import):
            pairs = [
                (a.asname or a.name.split(".")[0], a.name if a.asname else a.name.split(".")[0]) for a in node.names
            ]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            pairs = [(a.asname or a.name, f"{node.module}.{a.name}") for a in node.names if a.name != "*"]
        for name, dotted in pairs:
            value = _resolve(dotted)
            if name not in seen and name not in rebound and isinstance(value, (type, ModuleType)):
                found[name] = value
            elif name in seen:
                found.pop(name, None)
            seen.add(name)
    return found


def _bound_object(node: ast.expr, bindings: dict[str, object]) -> object:
    """Resolve a name or attribute chain over the bindings to a module or class, else ``_MISSING``."""
    if isinstance(node, ast.Name):
        return bindings.get(node.id, _MISSING)
    if isinstance(node, ast.Attribute):
        base = _bound_object(node.value, bindings)
        value = getattr(base, node.attr, _MISSING) if base is not _MISSING else _MISSING
        return value if isinstance(value, (type, ModuleType)) else _MISSING
    return _MISSING


def _call_form(call: ast.Call) -> str | None:
    """Classify a call as ``patch``, ``patch.object``, ``setattr-string`` or ``setattr-object``."""
    name = ast.unparse(call.func)
    if name in _PATCH:
        return "patch" if call.args else None
    if name in _PATCH_OBJECT:
        return "patch.object" if len(call.args) >= 2 else None
    if isinstance(call.func, ast.Attribute) and call.func.attr == "setattr" and isinstance(call.func.value, ast.Name):
        if len(call.args) == 2:
            return "setattr-string"
        return "setattr-object" if len(call.args) >= 3 else None
    return None


def _scan(source: str, filename: str) -> _Scan:
    """Check every covered mock call in one module's source."""
    tree = ast.parse(source, filename=filename)
    bindings = _importable_bindings(tree)
    module_env = _environment(list(tree.body), {})
    owner: dict[int, _Env] = {}
    functions = sorted(
        (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))),
        key=lambda node: node.lineno,
    )
    for function in functions:
        env = _environment([function], {**module_env, **_parametrized(function)})
        owner.update({id(node): env for node in ast.walk(function) if isinstance(node, ast.Call)})
    scan = _Scan()
    calls = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Call)), key=lambda node: (node.lineno, node.col_offset)
    )
    for call in calls:
        form, env = _call_form(call), owner.get(id(call), module_env)
        where = f"{filename}:{call.lineno}"
        if form in {"patch", "setattr-string"}:
            targets = _values(call.args[0], env)
            if targets is None:
                scan.errors.append(f"{where}: cannot evaluate patch target {ast.unparse(call.args[0])}")
                continue
            scan.dotted += len(targets)
            scan.errors.extend(f"{where}: unresolved patch target {t!r}" for t in targets if _resolve(t) is _MISSING)
        elif form in {"patch.object", "setattr-object"}:
            target = _bound_object(call.args[0], bindings)
            names = _values(call.args[1], env)
            if target is _MISSING or names is None:
                continue
            scan.objects += len(names)
            scan.errors.extend(
                f"{where}: {ast.unparse(call.args[0])} has no attribute {n!r}" for n in names if not hasattr(target, n)
            )
    return scan


def test_all_string_patch_targets_resolve() -> None:
    """Every dotted target resolves and every checkable object-form attribute exists, across ``tests/``."""
    total = _Scan()
    for path in sorted(_TESTS_ROOT.rglob("*.py")):
        scan = _scan(path.read_text(encoding="utf-8"), path.relative_to(_TESTS_ROOT.parent).as_posix())
        total.dotted += scan.dotted
        total.objects += scan.objects
        total.errors.extend(scan.errors)
    assert not total.errors, "Unresolved test patch targets:\n" + "\n".join(total.errors)
    assert total.dotted >= _MINIMUM_DOTTED_TARGETS, f"Only {total.dotted} dotted patch targets were checked."


def test_patch_with_a_dotted_string_fails_on_a_bad_target() -> None:
    """``patch("a.b.c")`` passes for a real attribute and names a missing one."""
    scan = _scan('from unittest.mock import patch\npatch("os.path.join")\npatch("os.path.missing")\n', "t.py")
    assert (scan.dotted, scan.errors) == (2, ["t.py:3: unresolved patch target 'os.path.missing'"])


def test_monkeypatch_setattr_with_a_dotted_string_fails_on_a_bad_target() -> None:
    """The two-argument string form of ``monkeypatch.setattr`` is checked like ``patch``."""
    source = (
        "def test(monkeypatch):\n"
        '    monkeypatch.setattr("os.path.join", None)\n'
        '    monkeypatch.setattr("os.nope.join", None)\n'
    )
    scan = _scan(source, "t.py")
    assert (scan.dotted, scan.errors) == (2, ["t.py:3: unresolved patch target 'os.nope.join'"])


def test_patch_object_fails_on_a_bad_attribute_of_an_imported_module_or_class() -> None:
    """``patch.object(obj, "name")`` is checked when ``obj`` is an imported module or class."""
    source = (
        "import os\nfrom pathlib import Path\nfrom unittest.mock import patch\n"
        'patch.object(os, "getcwd")\npatch.object(os, "missing")\npatch.object(Path, "missing_too")\n'
    )
    scan = _scan(source, "t.py")
    assert scan.objects == 3
    assert scan.errors == ["t.py:5: os has no attribute 'missing'", "t.py:6: Path has no attribute 'missing_too'"]


def test_monkeypatch_setattr_object_form_fails_on_a_bad_attribute() -> None:
    """``monkeypatch.setattr(obj, "name", value)`` is checked when ``obj`` is an imported module or class."""
    source = (
        "import os\n"
        "def test(monkeypatch):\n"
        '    monkeypatch.setattr(os, "getcwd", None)\n'
        '    monkeypatch.setattr(os, "missing", None)\n'
    )
    scan = _scan(source, "t.py")
    assert (scan.objects, scan.errors) == (2, ["t.py:4: os has no attribute 'missing'"])


def test_object_forms_are_left_to_the_runtime_when_the_object_is_not_an_import() -> None:
    """A local, a parameter or a rebound import is ambiguous, so the scanner makes no claim about it."""
    source = (
        "import os\nfrom unittest.mock import patch\n"
        "def test(thing):\n"
        "    local = thing.make()\n"
        '    patch.object(local, "missing")\n'
        '    patch.object(thing, "missing")\n'
        "def other():\n"
        "    os = object()\n"
        '    patch.object(os, "missing")\n'
    )
    scan = _scan(source, "t.py")
    assert (scan.objects, scan.errors) == (0, [])


def test_a_target_that_cannot_be_evaluated_is_reported() -> None:
    """A non-literal dotted target is an error, not a skip."""
    source = "from unittest.mock import patch\ndef test(make_target):\n    patch(make_target())\n"
    assert _scan(source, "t.py").errors == ["t.py:3: cannot evaluate patch target make_target()"]
    source = 'def test(monkeypatch, name):\n    monkeypatch.setattr(f"os.path.{name}", None)\n'
    assert _scan(source, "t.py").errors == ["t.py:2: cannot evaluate patch target f'os.path.{name}'"]


def test_literal_expressions_over_known_strings_are_evaluated_and_each_value_checked() -> None:
    """Parametrized values, literal loops, f-strings, concatenation and ``replace`` expand to every target."""
    source = (
        "import pytest\nfrom unittest.mock import patch\n"
        '@pytest.mark.parametrize("name", ["join", "nope"])\n'
        'def test_a(name):\n    patch("os.path." + name.replace("x", "y"))\n'
        "def test_b(monkeypatch):\n"
        '    for attribute in ("getcwd", "missing"):\n        monkeypatch.setattr(f"os.{attribute}", None)\n'
        '    target = "os.sep" if monkeypatch else "os.gone"\n    patch(target)\n'
    )
    scan = _scan(source, "t.py")
    assert scan.dotted == 6
    assert scan.errors == [
        "t.py:5: unresolved patch target 'os.path.nope'",
        "t.py:8: unresolved patch target 'os.missing'",
        "t.py:10: unresolved patch target 'os.gone'",
    ]
