[CmdletBinding()]
param(
    # Optional second pass: after the default gate, run the test suite on this interpreter
    # (for example "3.14") in its own ignored environment under .tmp/envs/, leaving .venv alone.
    [ValidatePattern('^\d+\.\d+$')]
    [string]$ExtraPython = ""
)

# Evidence: everything the run prints (every command's standard output and standard error, in
# order) is also written to gate-output.txt in the run's own directory under .tmp/quality-runs/.
# Each step prints its elapsed time when it ends, a closing summary lists every step with its
# time and result, and each pytest pass lists its failing and erroring tests by full name. The
# last line printed is the path of the output file.

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = "{0}-{1}-{2}" -f (Get-Date -Format "yyyyMMddHHmmssfff"), $PID, ([guid]::NewGuid().ToString("N"))
$runRoot = Join-Path $repositoryRoot ".tmp\quality-runs\$runId"
$pytestRoot = Join-Path $runRoot "pytest"
$coverageFile = Join-Path $runRoot ".coverage"
$coverageHtml = Join-Path $runRoot "htmlcov"
$mypyCache = Join-Path $runRoot "mypy-cache"
$uvCache = Join-Path $runRoot "uv-cache"
$logFile = Join-Path $runRoot "gate-output.txt"
$stepOutputFile = Join-Path $runRoot "step-output.txt"

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
        [string[]]$Arguments = @()
    )

    Write-Gate ""
    Write-Gate "== Step: $Name =="
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $stepWriter = New-Object System.IO.StreamWriter($stepOutputFile, $false, $utf8)
    $stepWriter.AutoFlush = $true
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Executable @Arguments 2>&1 | ForEach-Object {
            $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
            Write-Host $line
            $script:LogWriter.WriteLine($line)
            $stepWriter.WriteLine($line)
        }
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
        $stepWriter.Dispose()
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
    Write-Gate "Quality gate running on Python $pythonVersion, pandas $pandasVersion"

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
    Invoke-Step -Name "check_doc_links" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_doc_links.py"))
    Invoke-Step -Name "check_sequence_tables" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_sequence_tables.py"))
    Invoke-Step -Name "check_package_dependencies" -Executable $systemPython -Arguments ($systemPythonPrefix + @("scripts/check_package_dependencies.py"))
    Invoke-Step -Name "ruff check" -Executable "uv" -Arguments @("run", "--no-sync", "ruff", "check", "--no-cache", ".")
    Invoke-Step -Name "ruff format" -Executable "uv" -Arguments @("run", "--no-sync", "ruff", "format", "--check", ".")
    Invoke-Step -Name "mypy" -Executable "uv" -Arguments @(
        "run",
        "--no-sync",
        "mypy",
        "--strict",
        "--cache-dir",
        $mypyCache,
        "src",
        "tests",
        "scripts"
    )
    Invoke-Step -Name "pytest (Python $pythonVersion)" -Executable "uv" -Arguments @(
        "run",
        "--no-sync",
        "pytest",
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=html:$coverageHtml",
        "--basetemp=$pytestRoot",
        "tests"
    )

    Write-Gate "Quality gates passed on Python $pythonVersion, pandas $pandasVersion. Isolated artifacts: $runRoot"

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
        Invoke-Step -Name "pytest (Python $extraVersion)" -Executable "uv" -Arguments @(
            "run",
            "--no-sync",
            "pytest",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "--basetemp=$(Join-Path $runRoot 'pytest-extra')",
            "tests"
        )
        Write-Gate "Second-pass tests passed on Python $extraVersion, pandas $extraPandas."
    }
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
