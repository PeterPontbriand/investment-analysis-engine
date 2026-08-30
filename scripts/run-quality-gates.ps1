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
        "tests"
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
}
finally {
    Set-Location $originalLocation

    if ($null -eq $originalTemp) { Remove-Item Env:TEMP -ErrorAction SilentlyContinue } else { $env:TEMP = $originalTemp }
    if ($null -eq $originalTmp) { Remove-Item Env:TMP -ErrorAction SilentlyContinue } else { $env:TMP = $originalTmp }
    if ($null -eq $originalUvCache) { Remove-Item Env:UV_CACHE_DIR -ErrorAction SilentlyContinue } else { $env:UV_CACHE_DIR = $originalUvCache }
    if ($null -eq $originalCoverageFile) { Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue } else { $env:COVERAGE_FILE = $originalCoverageFile }
}

Write-Host "Quality gates passed. Isolated artifacts: $runRoot"
