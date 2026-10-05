#!/usr/bin/env bash
# Runs the live provider checks (tests marked live_network) against the real services.
# Each invocation writes to its own directory below .tmp/live-runs/ and never deletes earlier runs.
# The exit status is pytest's, so a scheduler can use a non-zero status as the failure signal.
# Usage: run-live-checks.sh [-k <pytest -k expression>]
set -euo pipefail

selector=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -k)
            if [ "$#" -lt 2 ]; then
                printf 'run-live-checks.sh: -k requires a selector expression\n' >&2
                exit 2
            fi
            selector="$2"
            shift 2
            ;;
        *)
            printf 'run-live-checks.sh: unknown argument %s\nUsage: run-live-checks.sh [-k <expression>]\n' "$1" >&2
            exit 2
            ;;
    esac
done

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repository_root="$(cd -- "$script_dir/.." && pwd -P)"
cd "$repository_root"

run_id="$(date -u +%Y%m%d%H%M%S)-$$-${RANDOM}"
run_root="$repository_root/.tmp/live-runs/$run_id"
mkdir -p "$run_root"

if command -v cygpath >/dev/null 2>&1; then
    windows_run_root="$(cygpath -m "$run_root")"
else
    windows_run_root="$run_root"
fi

export TEMP="$windows_run_root"
export TMP="$windows_run_root"
export UV_CACHE_DIR="$windows_run_root/uv-cache"

pytest_arguments=(
    -o addopts=
    -p no:cacheprovider
    --live
    "--junitxml=$windows_run_root/live-results.xml"
    "--basetemp=$windows_run_root/pytest"
    -v
)
if [ -n "$selector" ]; then
    pytest_arguments+=(-k "$selector")
fi
pytest_arguments+=(tests/live)

exit_code=0
uv run --no-sync pytest "${pytest_arguments[@]}" || exit_code=$?

printf 'Live checks finished with exit code %s. Results: %s/live-results.xml\n' "$exit_code" "$run_root"
exit "$exit_code"
