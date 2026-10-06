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

version_info="$(uv run --no-sync python -c "import sys, pandas; print(f'{sys.version.split()[0]}|{pandas.__version__}')")"
python_version="${version_info%%|*}"
pandas_version="${version_info##*|}"
printf 'Quality gate running on Python %s, pandas %s\n' "$python_version" "$pandas_version"

# The Markdown checkers import only the standard library, so they run with system Python
# rather than through uv or the project virtualenv.
system_python=()
for candidate in "py -3" python3 python; do
    # shellcheck disable=SC2086
    if $candidate --version >/dev/null 2>&1; then
        read -r -a system_python <<<"$candidate"
        break
    fi
done
if [ "${#system_python[@]}" -eq 0 ]; then
    printf 'No working system Python found (tried: py -3, python3, python); cannot run Markdown checks\n' >&2
    exit 1
fi
"${system_python[@]}" scripts/check_doc_links.py
"${system_python[@]}" scripts/check_sequence_tables.py
uv run --no-sync ruff check --no-cache .
uv run --no-sync ruff format --check .
uv run --no-sync mypy --strict --cache-dir "$windows_mypy_cache" src tests scripts
uv run --no-sync pytest \
    -o addopts= \
    -p no:cacheprovider \
    --cov=src \
    --cov-report=term-missing \
    --cov-report="html:$windows_coverage_html" \
    --basetemp="$windows_pytest_root" \
    tests

printf 'Quality gates passed on Python %s, pandas %s. Isolated artifacts: %s\n' "$python_version" "$pandas_version" "$run_root"
