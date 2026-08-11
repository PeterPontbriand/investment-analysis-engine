# /run-tests

**Purpose**: Run the full test suite and show coverage.

**Usage**: 
/run-tests
/run-tests -k momentum   (run only tests with "momentum" in name)

**Instructions for Claude**:
- Execute: pytest -v --cov=src --cov-report=term-missing
- If failures occur, analyze the error, suggest fixes, and apply them.
- Aim for >80% coverage on new code.
- Use pytest fixtures from tests/conftest.py for mocking yfinance responses.