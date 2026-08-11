# /refactor-modernize

**Purpose**: Modernize legacy code (add type hints, async where useful, proper error handling).

**Usage**: 
/refactor-modernize src/data/yfinance_client.py

**Instructions for Claude**:
- Apply Black/ruff standards (run ruff format . && ruff check --fix . afterward).
- Add comprehensive type hints and Pydantic models where appropriate.
- Improve logging and docstrings.
- Preserve original functionality.
- Update tests if needed.