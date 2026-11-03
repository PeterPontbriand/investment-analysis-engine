"""A database URL whose file is not a SQLite database, so opening it is a readiness error."""

from pathlib import Path


def unready_database_url(directory: Path) -> str:
    """Write a file of text where the database should be and return the URL that names it."""
    path = directory / "not-a-database.sqlite3"
    path.write_text("this is not a SQLite database file" * 8, encoding="utf-8")
    return f"sqlite:///{path.as_posix()}"
