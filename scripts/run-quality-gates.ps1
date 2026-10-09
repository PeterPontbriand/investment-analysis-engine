[CmdletBinding()]
param(
    # Optional second pass: after the default gate, run the test suite on this interpreter
    # (for example "3.14") in its own ignored environment under .tmp/envs/, leaving .venv alone.
    [ValidatePattern('^\d+\.\d+$')]
    [string]$ExtraPython = ""
)

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = "{0}-{1}-{2}" -f (Get-Date -Format "yyyyMMddHHmmssfff"), $PID, ([guid]::NewGuid().ToString("N"))
$runRoot = Join-Path $repositoryRoot ".tmp\quality-runs\$runId"
$pytestRoot = Join-Path $runRoot "pytest"
$coverageFile = Join-Path $runRoot ".coverage"
$coverageHtml = Join-Path $runRoot "htmlcov"
$mypyCache = Join-Path $runRoot "mypy-cache"
$uvCache = Join-Path $runRoot "uv-cache"

$originalLocation = Get-Location
$originalTemp = $env:TEMP
$originalTmp = $env:TMP
$originalUvCache = $env:UV_CACHE_DIR
$originalCoverageFile = $env:COVERAGE_FILE
$originalProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT

function Invoke-QualityCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & uv @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Quality command failed with exit code $LASTEXITCODE`: uv $($Arguments -join ' ')"
    }
}

try {
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    Set-Location $repositoryRoot

    $env:TEMP = $runRoot
    $env:TMP = $runRoot
    $env:UV_CACHE_DIR = $uvCache
    $env:COVERAGE_FILE = $coverageFile

    $versionInfo = & uv run --no-sync python -c "import sys, pandas; print(f'{sys.version.split()[0]}|{pandas.__version__}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Quality command failed with exit code $LASTEXITCODE`: uv run --no-sync python -c <version check>"
    }
    $pythonVersion, $pandasVersion = ($versionInfo | Select-Object -Last 1) -split '\|'
    Write-Host "Quality gate running on Python $pythonVersion, pandas $pandasVersion"

    # The Markdown checkers import only the standard library, so they run with system Python
    # rather than through uv or the project virtualenv.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 scripts/check_doc_links.py
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python scripts/check_doc_links.py
    }
    else {
        throw "No system Python found (tried: py -3, python); cannot run scripts/check_doc_links.py"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Link check failed with exit code $LASTEXITCODE`: scripts/check_doc_links.py"
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 scripts/check_sequence_tables.py
    }
    else {
        & python scripts/check_sequence_tables.py
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Sequence-table check failed with exit code $LASTEXITCODE`: scripts/check_sequence_tables.py"
    }
    Invoke-QualityCommand -Arguments @("run", "--no-sync", "ruff", "check", "--no-cache", ".")
    Invoke-QualityCommand -Arguments @("run", "--no-sync", "ruff", "format", "--check", ".")
    Invoke-QualityCommand -Arguments @(
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
    Invoke-QualityCommand -Arguments @(
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

    if ($ExtraPython) {
        # The environment folder is persistent and ignored (/.tmp/), so it is built once from the
        # lock file and reused; the sync is a no-op afterwards and .venv is never touched.
        $extraEnv = Join-Path $repositoryRoot ".tmp\envs\py$ExtraPython"
        $env:UV_PROJECT_ENVIRONMENT = $extraEnv
        Invoke-QualityCommand -Arguments @("sync", "--frozen", "--python", $ExtraPython)
        $extraInfo = & uv run --no-sync python -c "import sys, pandas; print(f'{sys.version.split()[0]}|{pandas.__version__}')"
        if ($LASTEXITCODE -ne 0) {
            throw "Quality command failed with exit code $LASTEXITCODE`: uv run --no-sync python -c <version check>"
        }
        $extraVersion, $extraPandas = ($extraInfo | Select-Object -Last 1) -split '\|'
        if (-not $extraVersion.StartsWith("$ExtraPython.")) {
            throw "Second pass requested Python $ExtraPython but the environment runs $extraVersion"
        }
        Write-Host "Second pass running on Python $extraVersion, pandas $extraPandas"
        Invoke-QualityCommand -Arguments @(
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

Write-Host "Quality gates passed on Python $pythonVersion, pandas $pandasVersion. Isolated artifacts: $runRoot"
if ($ExtraPython) {
    Write-Host "Second-pass tests passed on Python $extraVersion, pandas $extraPandas."
}
