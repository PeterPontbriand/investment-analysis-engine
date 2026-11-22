#!/usr/bin/env bash
set -euo pipefail

# Two tiers: the full gate (no mode option) runs once per pull request, and the slice check
# (--slice) runs after each sub-slice: every step of the full gate, except that pytest runs with no
# coverage and leaves out tests marked "slow". It cannot be combined with --extra-python.
#
# Optional second pass: --extra-python <major.minor> runs the test suite on that interpreter in
# its own ignored environment under .tmp/envs/ after the default gate, leaving .venv alone.
#
# --workers <n> (default 4) caps the pytest worker processes (pytest-xdist): "-n auto
# --maxprocesses <n>", so as many workers as cores but never more than n. Each worker opens its own
# sockets and issue #116 is a Windows socket-buffer exhaustion failure, so the count is capped.
# --workers 0 runs pytest serially in one process.
#
# Every run shares one mypy cache, <repository root>/.tmp/mypy-cache, so only the first run after a
# change is slow; deleting that folder resets it. Every other cache and temp path is unique per run.
#
# Evidence: everything the run prints (every command's standard output and standard error, in
# order) is also written to gate-output.txt in the run's own directory under .tmp/quality-runs/.
# Each step prints its elapsed time when it ends, a closing summary lists every step with its
# time and result, and each pytest pass lists its failing and erroring tests by full name and its
# 20 slowest tests. The last line printed is the path of the output file.
#
# Housekeeping: the first step, "prune old runs", deletes whole run directories under
# .tmp/quality-runs/ beyond the newest 20 (never one under 24 hours old, never one whose name is not a
# gate run directory's). When every step has passed, the step "clean run folder" deletes everything in
# this run's directory except gate-output.txt; a run that fails keeps its whole directory. The rules
# live in scripts/prune_quality_runs.py, run with system Python. A deletion that fails is a warning and
# never fails the gate. A run's gate-output.txt path stays valid only until its directory is pruned.
usage() {
    printf 'Usage: %s [--slice | --extra-python <major.minor>] [--workers <n>]; --slice cannot be combined with --extra-python\n' "$0" >&2
    exit 2
}

extra_python=""
slice_mode=0
workers=4
while [ "$#" -gt 0 ]; do
    case "$1" in
        --slice)
            slice_mode=1
            shift
            ;;
        --workers)
            [ "$#" -ge 2 ] || usage
            workers="$2"
            [[ "$workers" =~ ^[0-9]+$ ]] || usage
            shift 2
            ;;
        --extra-python)
            [ "$#" -ge 2 ] || usage
            extra_python="$2"
            [[ "$extra_python" =~ ^[0-9]+\.[0-9]+$ ]] || usage
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done
if [ "$slice_mode" -eq 1 ] && [ -n "$extra_python" ]; then
    usage
fi
workers=$((10#$workers))
if [ "$workers" -ge 1 ]; then
    worker_args=(-n auto --maxprocesses "$workers")
else
    worker_args=(-n 0)
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repository_root="$(cd -- "$script_dir/.." && pwd -P)"
cd "$repository_root"

run_id="$(date -u +%Y%m%d%H%M%S)-$$-${RANDOM}"
run_root="$repository_root/.tmp/quality-runs/$run_id"
pytest_root="$run_root/pytest"
coverage_html="$run_root/htmlcov"
mypy_cache="$repository_root/.tmp/mypy-cache"
log_file="$run_root/gate-output.txt"
step_output="$run_root/step-output.txt"
# Where a step's output copy goes; the final cleanup step sends it to /dev/null so that nothing holds
# step-output.txt open while the step deletes it.
step_sink="$step_output"

mkdir -p "$run_root"

if command -v cygpath >/dev/null 2>&1; then
    windows_run_root="$(cygpath -m "$run_root")"
    windows_runs_root="$(cygpath -m "$repository_root/.tmp/quality-runs")"
    windows_pytest_root="$(cygpath -m "$pytest_root")"
    windows_coverage_html="$(cygpath -m "$coverage_html")"
    windows_mypy_cache="$(cygpath -m "$mypy_cache")"
    printed_log_path="$(cygpath -w "$log_file")"
else
    windows_run_root="$run_root"
    windows_runs_root="$repository_root/.tmp/quality-runs"
    windows_pytest_root="$pytest_root"
    windows_coverage_html="$coverage_html"
    windows_mypy_cache="$mypy_cache"
    printed_log_path="$log_file"
fi

export TEMP="$windows_run_root"
export TMP="$windows_run_root"
export UV_CACHE_DIR="$windows_run_root/uv-cache"
export COVERAGE_FILE="$windows_run_root/.coverage"

# Coverage is measured once per run: on the extra pass when there is one (Python 3.14 measures it
# with sys.monitoring, which costs far less than on 3.12), otherwise on the default pass. The run
# fails below the project target of 85% total coverage.
coverage_args=(
    --cov=investment_analysis_engine
    --cov-report=term-missing
    --cov-report="html:$windows_coverage_html"
    --cov-fail-under=85
)

now_ms() {
    local micros="${EPOCHREALTIME/./}"
    printf '%s' "$((micros / 1000))"
}

format_seconds() {
    local ms="$1"
    printf '%d.%d' "$((ms / 1000))" "$(((ms % 1000) / 100))"
}

summary_names=()
summary_results=()
summary_times=()
gate_start_ms="$(now_ms)"
summary_printed=0

print_summary() {
    local overall="$1"
    local index
    summary_printed=1
    printf '\nGate summary\n'
    for index in ${summary_names[@]+"${!summary_names[@]}"}; do
        printf '  %-44s %-7s %9s s\n' "${summary_names[$index]}" "${summary_results[$index]}" "${summary_times[$index]}"
    done
    printf '  %-44s %-7s %9s s\n' "total" "$overall" "$(format_seconds "$(($(now_ms) - gate_start_ms))")"
}

# Print the failing and erroring tests of a pytest pass by full name, from the pass's own output.
print_failing_tests() {
    local failing
    failing="$(sed -E 's/\x1b\[[0-9;]*m//g' "$step_output" | { grep -E '^(FAILED|ERROR) ' || true; } | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | awk '!seen[$0]++')"
    if [ -z "$failing" ]; then
        printf 'Failing or erroring tests: none\n'
    else
        printf 'Failing or erroring tests (%s):\n' "$(printf '%s\n' "$failing" | wc -l | tr -d ' ')"
        printf '%s\n' "$failing" | sed 's/^/  /'
    fi
}

# run_step <name> <command...>: run one step, print its elapsed time, record it for the summary,
# and stop the gate at the first failing step with that step's exit code.
run_step() {
    local name="$1"
    local code start_ms elapsed
    shift
    start_ms="$(now_ms)"
    printf '\n== Step: %s ==\n' "$name"
    set +e
    "$@" 2>&1 | tee "$step_sink"
    code="${PIPESTATUS[0]}"
    set -e
    elapsed="$(format_seconds "$(($(now_ms) - start_ms))")"
    summary_names+=("$name")
    summary_times+=("$elapsed")
    if [ "$code" -eq 0 ]; then
        summary_results+=("ok")
        printf 'Step %s: ok in %s s\n' "$name" "$elapsed"
    else
        summary_results+=("FAILED")
        printf 'Step %s: FAILED (exit %s) in %s s\n' "$name" "$code" "$elapsed"
    fi
    case "$name" in
        pytest*) print_failing_tests ;;
    esac
    if [ "$code" -ne 0 ]; then
        print_summary "FAILED"
        exit "$code"
    fi
}

main() {
    set -e
    # Any other failure (a missing system Python, a wrong interpreter) still ends with the summary.
    trap 'if [ "$?" -ne 0 ] && [ "$summary_printed" -eq 0 ]; then print_summary "FAILED"; fi' EXIT
    local version_info python_version pandas_version
    version_info="$(uv run --no-sync python -c "import sys, pandas; print(f'{sys.version.split()[0]}|{pandas.__version__}')")"
    python_version="${version_info%%|*}"
    pandas_version="${version_info##*|}"
    local mode_name="full gate"
    if [ "$slice_mode" -eq 1 ]; then
        mode_name="slice check"
    fi
    printf 'Quality gate (%s) on Python %s, pandas %s; pytest workers: up to %s (0 = serial)\n' "$mode_name" "$python_version" "$pandas_version" "$workers"

    # The Markdown checkers import only the standard library, so they run with system Python
    # rather than through uv or the project virtualenv.
    local system_python=() candidate
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
    run_step "prune old runs" "${system_python[@]}" scripts/prune_quality_runs.py prune "$windows_runs_root" "$windows_run_root"
    run_step "check_doc_links" "${system_python[@]}" scripts/check_doc_links.py
    run_step "check_help_content" "${system_python[@]}" scripts/check_help_content.py
    run_step "check_sequence_tables" "${system_python[@]}" scripts/check_sequence_tables.py
    run_step "check_package_dependencies" "${system_python[@]}" scripts/check_package_dependencies.py
    run_step "check_database_boundary" "${system_python[@]}" scripts/check_database_boundary.py
    run_step "generate_openapi --check" uv run --no-sync python -m scripts.generate_openapi --check
    run_step "generate_help --check" uv run --no-sync python -m scripts.generate_help --check
    run_step "ruff check" uv run --no-sync ruff check --no-cache .
    run_step "ruff format" uv run --no-sync ruff format --check .
    run_step "mypy" uv run --no-sync mypy --strict --cache-dir "$windows_mypy_cache"
    local mode_args=("${coverage_args[@]}")
    local pytest_name="pytest (Python $python_version)"
    local passed_label="Quality gates passed"
    if [ "$slice_mode" -eq 1 ]; then
        mode_args=(-m "not slow")
        pytest_name="pytest slice (Python $python_version)"
        passed_label="Slice check passed"
    elif [ -n "$extra_python" ]; then
        mode_args=()
    fi
    run_step "$pytest_name" uv run --no-sync pytest \
        -o addopts= \
        -p no:cacheprovider \
        -rfEs \
        --durations=20 \
        "${worker_args[@]}" \
        ${mode_args[@]+"${mode_args[@]}"} \
        --basetemp="$windows_pytest_root" \
        tests

    printf '%s on Python %s, pandas %s. Isolated artifacts: %s\n' "$passed_label" "$python_version" "$pandas_version" "$run_root"

    if [ -n "$extra_python" ]; then
        # The environment folder is persistent and ignored (/.tmp/), so it is built once from the
        # lock file and reused; the sync is a no-op afterwards and .venv is never touched.
        if command -v cygpath >/dev/null 2>&1; then
            export UV_PROJECT_ENVIRONMENT="$(cygpath -m "$repository_root/.tmp/envs/py$extra_python")"
        else
            export UV_PROJECT_ENVIRONMENT="$repository_root/.tmp/envs/py$extra_python"
        fi
        run_step "uv sync (Python $extra_python)" uv sync --frozen --python "$extra_python"
        local extra_info extra_version extra_pandas
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
        run_step "pytest (Python $extra_version)" uv run --no-sync pytest \
            -o addopts= \
            -p no:cacheprovider \
            -rfEs \
            --durations=20 \
            "${worker_args[@]}" \
            "${coverage_args[@]}" \
            --basetemp="$windows_run_root/pytest-extra" \
            tests
        printf 'Second-pass tests passed on Python %s, pandas %s.\n' "$extra_version" "$extra_pandas"
    fi

    # Every step passed: keep only gate-output.txt in this run's directory.
    step_sink=/dev/null run_step "clean run folder" "${system_python[@]}" scripts/prune_quality_runs.py clean "$windows_run_root"

    print_summary "passed"
}

# The whole run is shown on the terminal and kept, unfiltered and in order, in the output file.
# A failing step leaves the pipeline with its own exit code, which becomes the wrapper's.
set +e
main 2>&1 | tee "$log_file"
status="${PIPESTATUS[0]}"
set -e
printf '%s\n' "$printed_log_path"
exit "$status"
