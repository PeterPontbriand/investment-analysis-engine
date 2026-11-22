"""Tests for the database boundary checker, on temporary source trees."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_database_boundary import (
    RAW_SQL,
    SOURCE_ROOT_NAME,
    SQLALCHEMY_DIALECT,
    SQLITE3_MODULE,
    SQLITE_ERRORCODE,
    check_repository,
)
from scripts.repository_root import REPOSITORY_ROOT

OUTSIDE = "application/module.py"
INSIDE = "data/repositories/module.py"


def write(tmp_path: Path, relative: str, text: str) -> None:
    """Write one source file below the temporary source root."""
    path = tmp_path / SOURCE_ROOT_NAME / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def kinds(tmp_path: Path, relative: str = OUTSIDE) -> list[tuple[int, str]]:
    """Return ``(line, kind)`` of every offence in the tree."""
    return [(offence.line, offence.kind) for offence in check_repository(tmp_path) if offence.path.endswith(relative)]


SQLITE3_FORMS = [
    "import sqlite3\n",
    "import sqlite3 as lite\n",
    "import sqlite3.dbapi2\n",
    "from sqlite3 import Error\n",
    "from sqlite3 import Error as E\n",
    "from sqlite3.dbapi2 import connect\n",
    "def f() -> None:\n    import sqlite3\n",
]

DIALECT_FORMS = [
    "import sqlalchemy.dialects.sqlite\n",
    "import sqlalchemy.dialects\n",
    "import sqlalchemy.dialects.postgresql as pg\n",
    "from sqlalchemy.dialects import sqlite\n",
    "from sqlalchemy.dialects.sqlite import insert\n",
    "from sqlalchemy.dialects.sqlite import insert as ins\n",
    "from sqlalchemy.dialects.postgresql import JSONB\n",
    "from sqlalchemy import dialects\n",
    "import sqlalchemy\n\nvalue = sqlalchemy.dialects.sqlite.insert\n",
    "import sqlalchemy as sa\n\nvalue = sa.dialects.sqlite.insert\n",
    "def f() -> None:\n    from sqlalchemy.dialects.sqlite import insert\n",
]

RAW_SQL_FORMS = [
    "from sqlalchemy import text\n",
    "from sqlalchemy import text as t\n",
    "from sqlalchemy.sql import text\n",
    "from sqlalchemy.sql.expression import text\n",
    "import sqlalchemy\n\nquery = sqlalchemy.text('x')\n",
    "import sqlalchemy as sa\n\nquery = sa.text('x')\n",
    "import sqlalchemy.sql\n\nquery = sqlalchemy.sql.text('x')\n",
    "from sqlalchemy import sql\n\nquery = sql.text('x')\n",
    "def run(connection):\n    connection.exec_driver_sql('PRAGMA x')\n",
    "def run(engine):\n    engine.connect().exec_driver_sql('x')\n",
    "def f() -> None:\n    from sqlalchemy import text\n",
]

ERRORCODE_FORMS = [
    "def code(error):\n    return error.sqlite_errorcode\n",
    "def code(error):\n    return error.orig.sqlite_errorcode & 0xFF\n",
    "def code(error):\n    return getattr(error, 'sqlite_errorcode', None)\n",
    "def code(error):\n    return hasattr(error, 'sqlite_errorcode')\n",
]


@pytest.mark.parametrize(
    ("kind", "source"),
    [(SQLITE3_MODULE, form) for form in SQLITE3_FORMS]
    + [(SQLALCHEMY_DIALECT, form) for form in DIALECT_FORMS]
    + [(RAW_SQL, form) for form in RAW_SQL_FORMS]
    + [(SQLITE_ERRORCODE, form) for form in ERRORCODE_FORMS],
)
def test_each_kind_is_caught_outside_the_allowed_folder_in_every_form_and_allowed_inside_it(
    tmp_path: Path, kind: str, source: str
) -> None:
    write(tmp_path, OUTSIDE, source)
    write(tmp_path, INSIDE, source)
    write(tmp_path, "data/repositories/migration_scripts/versions/0001.py", source)

    found = kinds(tmp_path)

    assert found
    assert {name for _, name in found} == {kind}
    assert kinds(tmp_path, INSIDE) == []
    assert kinds(tmp_path, "migration_scripts/versions/0001.py") == []


def test_an_offence_is_reported_with_its_file_line_and_kind(tmp_path: Path) -> None:
    write(tmp_path, OUTSIDE, "import os\nimport sqlite3\n")

    [offence] = check_repository(tmp_path)

    assert str(offence).startswith(f"{SOURCE_ROOT_NAME}/{OUTSIDE}:2: {SQLITE3_MODULE}: ")


def test_every_offence_in_every_file_is_reported_in_one_run(tmp_path: Path) -> None:
    write(tmp_path, "a/one.py", "import sqlite3\nfrom sqlalchemy import text\n")
    write(tmp_path, "b/two.py", "def f(c):\n    return c.sqlite_errorcode\n")

    offences = check_repository(tmp_path)

    assert [(o.path.rsplit("/", 1)[-1], o.line, o.kind) for o in offences] == [
        ("one.py", 1, SQLITE3_MODULE),
        ("one.py", 2, RAW_SQL),
        ("two.py", 2, SQLITE_ERRORCODE),
    ]


def test_dialect_neutral_sqlalchemy_and_url_parsing_are_not_reported(tmp_path: Path) -> None:
    write(
        tmp_path,
        OUTSIDE,
        "import sqlalchemy\n"
        "from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update\n"
        "from sqlalchemy.engine import URL, make_url\n"
        "from sqlalchemy.exc import DBAPIError, SQLAlchemyError\n"
        "import sqlalchemy.sql.expression\n"
        "\n"
        "stmt = sqlalchemy.select(sqlalchemy.func.count())\n"
        "url = make_url('sqlite:///x.sqlite3')\n"
        "DATABASE_FILE_NAME = 'investment-analysis-engine.sqlite3'\n",
    )

    assert check_repository(tmp_path) == []


def test_a_name_text_that_is_not_from_sqlalchemy_is_not_reported(tmp_path: Path) -> None:
    write(
        tmp_path,
        OUTSIDE,
        "from html.parser import HTMLParser\n"
        "import xml.dom.minidom as minidom\n"
        "\n"
        "def text(node):\n    return node.text()\n"
        "\n"
        "value = text(None) + minidom.text + HTMLParser.text\n"
        "other = something.sqlite3_like\n",
    )

    assert check_repository(tmp_path) == []


def test_assigning_an_attribute_named_like_the_error_code_is_not_a_read(tmp_path: Path) -> None:
    write(tmp_path, OUTSIDE, "def mark(error):\n    error.sqlite_errorcode = 5\n")

    assert check_repository(tmp_path) == []


def test_files_outside_the_source_root_are_not_checked(tmp_path: Path) -> None:
    write(tmp_path, OUTSIDE, "x = 1\n")
    for relative in ("tests/test_x.py", "scripts/tool.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("import sqlite3\n", encoding="utf-8")

    assert check_repository(tmp_path) == []


def test_a_look_alike_folder_is_not_the_allowed_folder(tmp_path: Path) -> None:
    write(tmp_path, "data/repositories_extra/module.py", "import sqlite3\n")
    write(tmp_path, "other/data/repositories/module.py", "import sqlite3\n")

    assert len(check_repository(tmp_path)) == 2


def test_a_clean_tree_passes(tmp_path: Path) -> None:
    write(tmp_path, OUTSIDE, "import os\n\nVALUE = os.sep\n")
    write(tmp_path, INSIDE, "import sqlite3\n")

    assert check_repository(tmp_path) == []


def test_the_repository_passes() -> None:
    assert check_repository(REPOSITORY_ROOT) == []
