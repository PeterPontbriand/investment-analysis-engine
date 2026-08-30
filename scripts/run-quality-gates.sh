#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repository_root="$(cd -- "$script_dir/.." && pwd -P)"
cd "$repository_root"

run_id="$(date -u +%Y%m%d%H%M%S)-$$-${RANDOM}"
run_root="$repository_root/.tmp/quality-runs/$run_id"
pytest_root="$run_root/pytest"
coverage_html="$run_root/htmlcov"
mypy_cache="$run_root/mypy-cache"

mkdir -p "$run_root"

if command -v cygpath >/dev/null 2>&1; then
    windows_run_root="$(cygpath -m "$run_root")"
    windows_pytest_root="$(cygpath -m "$pytest_root")"
    windows_coverage_html="$(cygpath -m "$coverage_html")"
    windows_mypy_cache="$(cygpath -m "$mypy_cache")"
else
    windows_run_root="$run_root"
    windows_pytest_root="$pytest_root"
    windows_coverage_html="$coverage_html"
    windows_mypy_cache="$mypy_cache"
fi

export TEMP="$windows_run_root"
export TMP="$windows_run_root"
export UV_CACHE_DIR="$windows_run_root/uv-cache"
export COVERAGE_FILE="$windows_run_root/.coverage"

uv run --no-sync ruff check --no-cache .
uv run --no-sync ruff format --check .
uv run --no-sync mypy --strict --cache-dir "$windows_mypy_cache" src tests
uv run --no-sync pytest \
    -o addopts= \
    -p no:cacheprovider \
    --cov=src \
    --cov-report=term-missing \
    --cov-report="html:$windows_coverage_html" \
    --basetemp="$windows_pytest_root" \
    tests

printf 'Quality gates passed. Isolated artifacts: %s\n' "$run_root"
