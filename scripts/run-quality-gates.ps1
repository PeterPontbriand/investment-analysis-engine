[CmdletBinding()]
param(
    # Optional second pass: after the default gate, run the test suite on this interpreter
    # (for example "3.14") in its own ignored environment under .tmp/envs/, leaving .venv alone.
    [ValidatePattern('^\d+\.\d+$')]
    [string]$ExtraPython = "",

    # Slice check: the per-sub-slice tier. Every step of the full gate runs, except that pytest runs
    # with no coverage and leaves out tests marked "slow". It cannot be combined with -ExtraPython.
    [switch]$Slice,

    # Upper bound on pytest worker processes (pytest-xdist). Each worker opens its own sockets, and
    # issue #116 is a Windows socket-buffer exhaustion failure, so the count is capped instead of
    # using every core. 0 runs pytest serially in one process.
    [ValidateRange(0, 1024)]
    [int]$Workers = 4
)

# Two tiers: the full gate (no mode option) runs once per pull request, and the slice check
# (-Slice) runs after each sub-slice. Pytest runs with "-n auto --maxprocesses <Workers>" in both.
# Every run shares one mypy cache, <repository root>/.tmp/mypy-cache, so only the first run after
# a change is slow; deleting that folder resets it. Every other cache and temp path is unique per run.
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

$ErrorActionPreference = "Stop"

if ($Slice -and $ExtraPython) {
    [Console]::Error.WriteLine("Usage: run-quality-gates.ps1 [-Slice | -ExtraPython <major.minor>] [-Workers <n>]; -Slice cannot be combined with -ExtraPython")
    exit 2
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = "{0}-{1}-{2}" -f (Get-Date -Format "yyyyMMddHHmmssfff"), $PID, ([guid]::NewGuid().ToString("N"))
$runRoot = Join-Path $repositoryRoot ".tmp\quality-runs\$runId"
$pytestRoot = Join-Path $runRoot "pytest"
$coverageFile = Join-Path $runRoot ".coverage"
$coverageHtml = Join-Path $runRoot "htmlcov"
$mypyCache = Join-Path $repositoryRoot ".tmp\mypy-cache"
$uvCache = Join-Path $runRoot "uv-cache"
$logFile = Join-Path $runRoot "gate-output.txt"
$stepOutputFile = Join-Path $runRoot "step-output.txt"

# Coverage is measured once per run: on the extra pass when there is one (Python 3.14 measures it
# with sys.monitoring, which costs far less than on 3.12), otherwise on the default pass. The run
# fails below the project target of 85% total coverage.
$coverageArguments = @(
    "--cov=investment_analysis_engine",
    "--cov-report=term-missing",
    "--cov-report=html:$coverageHtml",
    "--cov-fail-under=85"
)

$workerArguments = if ($Workers -ge 1) { @("-n", "auto", "--maxprocesses", "$Workers") } else { @("-n", "0") }

$originalLocation = Get-Location
$originalTemp = $env:TEMP
$originalTmp = $env:TMP
$originalUvCache = $env:UV_CACHE_DIR
$originalCoverageFile = $env:COVERAGE_FILE
$originalProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT

$utf8 = New-Object System.Text.UTF8Encoding($false)
$script:LogWriter = $null
$script:StepFailed = $false
$script:SummaryRows = New-Object System.Collections.Generic.List[object]
$gateTimer = [System.Diagnostics.Stopwatch]::StartNew()

function Format-Seconds {
    param([Parameter(Mandatory = $true)][int64]$Milliseconds)

    return "{0}.{1}" -f [int64][math]::Floor($Milliseconds / 1000), [int64][math]::Floor(($Milliseconds % 1000) / 100)
}

function Write-Gate {
    param([string]$Text)

    Write-Host $Text
    if ($null -ne $script:LogWriter) {
        $script:LogWriter.WriteLine($Text)
    }
}

function Write-FailingTests {
    $escape = [regex]([string][char]27 + '\[[0-9;]*m')
    $failing = @(
        Get-Content -LiteralPath $stepOutputFile -Encoding UTF8 |
            ForEach-Object { $escape.Replace($_, "") } |
            Where-Object { $_ -match '^(FAILED|ERROR) ' } |
            ForEach-Object { ($_ -replace '^(FAILED|ERROR) ', '') -replace ' - .*$', '' } |
            Select-Object -Unique
    )
    if ($failing.Count -eq 0) {
        Write-Gate "Failing or erroring tests: none"
    }
    else {
        Write-Gate "Failing or erroring tests ($($failing.Count)):"
        foreach ($name in $failing) {
            Write-Gate "  $name"
        }
    }
}

function Write-Summary {
    param([Parameter(Mandatory = $true)][string]$Overall)

    Write-Gate ""
    Write-Gate "Gate summary"
    foreach ($row in $script:SummaryRows) {
        Write-Gate ('  {0,-44} {1,-7} {2,9} s' -f $row.Name, $row.Result, $row.Time)
    }
    Write-Gate ('  {0,-44} {1,-7} {2,9} s' -f "total", $Overall, (Format-Seconds $gateTimer.ElapsedMilliseconds))
}

# Ask the active environment for "<python version>|<pandas version>". Anything the command writes to
# standard error is part of the run's output, so it is printed and kept.
function Get-VersionInfo {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& uv run --no-sync python -c "import sys, pandas; print(f'{sys.version.split()[0]}|{pandas.__version__}')" 2>&1)
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    $standardOutput = @()
    foreach ($item in $output) {
        if ($item -is [System.Management.Automation.ErrorRecord]) {
            Write-Gate $item.Exception.Message
        }
        else {
            $standardOutput += "$item"
        }
    }
    if ($code -ne 0) {
        throw "Quality command failed with exit code $code`: uv run --no-sync python -c <version check>"
    }
    return $standardOutput | Select-Object -Last 1
}

# Run one step, print its elapsed time, record it for the summary, and stop the gate at the first
# failing step.
function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$Arguments = @(),
        # The step deletes this run's directory contents, so it must not hold step-output.txt open.
        [switch]$NoStepOutput
    )

    Write-Gate ""
    Write-Gate "== Step: $Name =="
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $stepWriter = $null
    if (-not $NoStepOutput) {
        $stepWriter = New-Object System.IO.StreamWriter($stepOutputFile, $false, $utf8)
        $stepWriter.AutoFlush = $true
    }
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Executable @Arguments 2>&1 | ForEach-Object {
            $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
            Write-Host $line
            $script:LogWriter.WriteLine($line)
            if ($null -ne $stepWriter) { $stepWriter.WriteLine($line) }
        }
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
        if ($null -ne $stepWriter) { $stepWriter.Dispose() }
    }

    $elapsed = Format-Seconds $timer.ElapsedMilliseconds
    if ($code -eq 0) {
        $script:SummaryRows.Add([pscustomobject]@{ Name = $Name; Result = "ok"; Time = $elapsed })
        Write-Gate "Step ${Name}: ok in $elapsed s"
    }
    else {
        $script:SummaryRows.Add([pscustomobject]@{ Name = $Name; Result = "FAILED"; Time = $elapsed })
        Write-Gate "Step ${Name}: FAILED (exit $code) in $elapsed s"
    }
    if ($Name.StartsWith("pytest")) {
        Write-FailingTests
    }
    if ($code -ne 0) {
        $script:StepFailed = $true
        throw "Quality command failed with exit code $code`: $Executable $($Arguments -join ' ')"
    }
}

$exitCode = 0
try {
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    $script:LogWriter = New-Object System.IO.StreamWriter($logFile, $false, $utf8)
    $script:LogWriter.AutoFlush = $true
    Set-Location $repositoryRoot

    $env:TEMP = $runRoot
    $env:TMP = $runRoot
    $env:UV_CACHE_DIR = $uvCache
    $env:COVERAGE_FILE = $coverageFile

    $pythonVersion, $pandasVersion = (Get-VersionInfo) -split '\|'
    $modeName = if ($Slice) { "slice check" } else { "full gate" }
    Write-Gate "Quality gate ($modeName) on Python $pythonVersion, pandas $pandasVersion; pytest workers: up to $Workers (0 = serial)"

    # The Markdown checkers import only the standard library, so they run with system Python
    # rather than through uv or the project virtualenv.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $systemPython = "py"
        $systemPythonPrefix = @("-3")
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $systemPython = "python"
        $systemPythonPrefix = @()
    }
    else {
        throw "No system Python found (tried: py -3, python); cannot run Markdown checks"
    }
    $pruneScript = "scripts/prune_quality_runs.py"
    Invoke-Step -Name "prune old runs" -Executable $systemPython -Arguments ($systemPythonPrefix + @($pruneScript, "prune", (Join-Path $repositoryRoot ".tmp\quality-runs"), $runRoot))
    Invoke-Step -Name "check_doc_links" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_doc_links.py"))
    Invoke-Step -Name "check_help_content" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_help_content.py"))
    Invoke-Step -Name "check_sequence_tables" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_sequence_tables.py"))
    Invoke-Step -Name "check_package_dependencies" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_package_dependencies.py"))
    Invoke-Step -Name "generate_openapi --check" -Executable "uv" -Arguments @("run", "--no-sync", "python", "-m", "scripts.generate_openapi", "--check")
    Invoke-Step -Name "generate_help --check" -Executable "uv" -Arguments @("run", "--no-sync", "python", "-m", "scripts.generate_help", "--check")
    Invoke-Step -Name "ruff check" -Executable "uv" -Arguments @("run", "--no-sync", "ruff", "check", "--no-cache", ".")
    Invoke-Step -Name "ruff format" -Executable "uv" -Arguments @("run", "--no-sync", "ruff", "format", "--check", ".")
    Invoke-Step -Name "mypy" -Executable "uv" -Arguments @(
        "run",
        "--no-sync",
        "mypy",
        "--strict",
        "--cache-dir",
        $mypyCache
    )
    $pytestName = if ($Slice) { "pytest slice (Python $pythonVersion)" } else { "pytest (Python $pythonVersion)" }
    $modeArguments = if ($Slice) { @("-m", "not slow") } elseif ($ExtraPython) { @() } else { $coverageArguments }
    Invoke-Step -Name $pytestName -Executable "uv" -Arguments (@(
            "run",
            "--no-sync",
            "pytest",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "-rfEs",
            "--durations=20"
        ) + $workerArguments + $modeArguments + @(
            "--basetemp=$pytestRoot",
            "tests"
        ))

    $passedLabel = if ($Slice) { "Slice check passed" } else { "Quality gates passed" }
    Write-Gate "$passedLabel on Python $pythonVersion, pandas $pandasVersion. Isolated artifacts: $runRoot"

    if ($ExtraPython) {
        # The environment folder is persistent and ignored (/.tmp/), so it is built once from the
        # lock file and reused; the sync is a no-op afterwards and .venv is never touched.
        $extraEnv = Join-Path $repositoryRoot ".tmp\envs\py$ExtraPython"
        $env:UV_PROJECT_ENVIRONMENT = $extraEnv
        Invoke-Step -Name "uv sync (Python $ExtraPython)" -Executable "uv" -Arguments @("sync", "--frozen", "--python", $ExtraPython)
        $extraVersion, $extraPandas = (Get-VersionInfo) -split '\|'
        if (-not $extraVersion.StartsWith("$ExtraPython.")) {
            throw "Second pass requested Python $ExtraPython but the environment runs $extraVersion"
        }
        Write-Gate "Second pass running on Python $extraVersion, pandas $extraPandas"
        Invoke-Step -Name "pytest (Python $extraVersion)" -Executable "uv" -Arguments (@(
                "run",
                "--no-sync",
                "pytest",
                "-o",
                "addopts=",
                "-p",
                "no:cacheprovider",
                "-rfEs",
                "--durations=20"
            ) + $workerArguments + $coverageArguments + @(
                "--basetemp=$(Join-Path $runRoot 'pytest-extra')",
                "tests"
            ))
        Write-Gate "Second-pass tests passed on Python $extraVersion, pandas $extraPandas."
    }

    # Every step passed: keep only gate-output.txt in this run's directory.
    Invoke-Step -Name "clean run folder" -Executable $systemPython -Arguments ($systemPythonPrefix + @($pruneScript, "clean", $runRoot)) -NoStepOutput
}
catch {
    $exitCode = 1
    if (-not $script:StepFailed) {
        Write-Gate $_.Exception.Message
    }
}
finally {
    Set-Location $originalLocation

    if ($null -eq $originalTemp) { Remove-Item Env:TEMP -ErrorAction SilentlyContinue } else { $env:TEMP = $originalTemp }
    if ($null -eq $originalTmp) { Remove-Item Env:TMP -ErrorAction SilentlyContinue } else { $env:TMP = $originalTmp }
    if ($null -eq $originalUvCache) { Remove-Item Env:UV_CACHE_DIR -ErrorAction SilentlyContinue } else { $env:UV_CACHE_DIR = $originalUvCache }
    if ($null -eq $originalCoverageFile) { Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue } else { $env:COVERAGE_FILE = $originalCoverageFile }
    if ($null -eq $originalProjectEnvironment) { Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue } else { $env:UV_PROJECT_ENVIRONMENT = $originalProjectEnvironment }
}

if ($null -ne $script:LogWriter) {
    Write-Summary -Overall $(if ($exitCode -eq 0) { "passed" } else { "FAILED" })
    $script:LogWriter.Dispose()
}
Write-Host $logFile
exit $exitCode
