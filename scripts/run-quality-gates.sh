#!/usr/bin/env bash
set -euo pipefail

# Optional second pass: --extra-python <major.minor> runs the test suite on that interpreter in
# its own ignored environment under .tmp/envs/ after the default gate, leaving .venv alone.
extra_python=""
case "${1:-}" in
    "") ;;
    --extra-python)
        extra_python="${2:-}"
        if ! [[ "$extra_python" =~ ^[0-9]+\.[0-9]+$ ]] || [ "$#" -ne 2 ]; then
            printf 'Usage: %s [--extra-python <major.minor>]\n' "$0" >&2
            exit 2
        fi
        ;;
    *)
        printf 'Usage: %s [--extra-python <major.minor>]\n' "$0" >&2
        exit 2
        ;;
esac

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

if [ -n "$extra_python" ]; then
    # The environment folder is persistent and ignored (/.tmp/), so it is built once from the
    # lock file and reused; the sync is a no-op afterwards and .venv is never touched.
    if command -v cygpath >/dev/null 2>&1; then
        export UV_PROJECT_ENVIRONMENT="$(cygpath -m "$repository_root/.tmp/envs/py$extra_python")"
    else
        export UV_PROJECT_ENVIRONMENT="$repository_root/.tmp/envs/py$extra_python"
    fi
    uv sync --frozen --python "$extra_python"
    extra_info="$(uv run --no-sync python -c "import sys, pandas; print(f'{sys.version.split()[0]}|{pandas.__version__}')")"
    extra_version="${extra_info%%|*}"
    extra_pandas="${extra_info##*|}"
    case "$extra_version" in
        "$extra_python".*) ;;
        *)
            printf 'Second pass requested Python %s but the environment runs %s\n' "$extra_python" "$extra_version" >&2
            exit 1
            ;;
    esac
    printf 'Second pass running on Python %s, pandas %s\n' "$extra_version" "$extra_pandas"
    uv run --no-sync pytest \
        -o addopts= \
        -p no:cacheprovider \
        --basetemp="$windows_run_root/pytest-extra" \
        tests
    printf 'Second-pass tests passed on Python %s, pandas %s.\n' "$extra_version" "$extra_pandas"
fi
