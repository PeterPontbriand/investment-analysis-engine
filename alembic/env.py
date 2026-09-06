"""Run Alembic through the application's reviewed SQLite connection boundary."""

from src.data.repositories.migrations import run_migrations

run_migrations()
