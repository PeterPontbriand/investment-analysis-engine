[CmdletBinding()]
param()

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
    # Force colour for this step only so CLI output carries the same ANSI styling as CI runners.
    $originalForceColor = $env:FORCE_COLOR
    $env:FORCE_COLOR = "1"
    try {
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
    }
    finally {
        if ($null -eq $originalForceColor) { Remove-Item Env:FORCE_COLOR -ErrorAction SilentlyContinue } else { $env:FORCE_COLOR = $originalForceColor }
    }
}
finally {
    Set-Location $originalLocation

    if ($null -eq $originalTemp) { Remove-Item Env:TEMP -ErrorAction SilentlyContinue } else { $env:TEMP = $originalTemp }
    if ($null -eq $originalTmp) { Remove-Item Env:TMP -ErrorAction SilentlyContinue } else { $env:TMP = $originalTmp }
    if ($null -eq $originalUvCache) { Remove-Item Env:UV_CACHE_DIR -ErrorAction SilentlyContinue } else { $env:UV_CACHE_DIR = $originalUvCache }
    if ($null -eq $originalCoverageFile) { Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue } else { $env:COVERAGE_FILE = $originalCoverageFile }
}

Write-Host "Quality gates passed on Python $pythonVersion, pandas $pandasVersion. Isolated artifacts: $runRoot"
