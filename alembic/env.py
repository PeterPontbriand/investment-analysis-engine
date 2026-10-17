"""Run Alembic through the application's reviewed SQLite connection boundary."""

from investment_analysis_engine.data.repositories.migrations import run_migrations

run_migrations()
