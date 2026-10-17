[CmdletBinding()]
param(
    # Optional pytest -k expression to run a subset, for example "yahoo" or "sec_edgar".
    [Alias("k")]
    [string]$Selector = ""
)

# Runs the live provider checks (tests marked live_network) against the real services.
# Each invocation writes to its own directory below .tmp/live-runs/ and never deletes earlier runs.
# The exit status is pytest's, so a scheduler can use a non-zero status as the failure signal.

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = "{0}-{1}-{2}" -f (Get-Date -Format "yyyyMMddHHmmssfff"), $PID, ([guid]::NewGuid().ToString("N"))
$runRoot = Join-Path $repositoryRoot ".tmp\live-runs\$runId"
$pytestRoot = Join-Path $runRoot "pytest"
$junitFile = Join-Path $runRoot "live-results.xml"
$uvCache = Join-Path $runRoot "uv-cache"

$originalLocation = Get-Location
$originalTemp = $env:TEMP
$originalTmp = $env:TMP
$originalUvCache = $env:UV_CACHE_DIR
$originalUserAgent = $env:SEC_USER_AGENT

# The test session ignores the per-user settings folder, so the one key the live checks need is read from its .env file
# here, located by the package's own resolver (which honours IAN_CONFIG_DIR). The value is never printed or logged.
$readUserAgent = "import os; from dotenv import dotenv_values; from investment_analysis_engine.config.user_folders import resolve_settings_folder; print(dotenv_values(resolve_settings_folder(os.environ) / '.env').get('SEC_USER_AGENT') or '')"

$exitCode = 1
try {
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    Set-Location $repositoryRoot

    if (-not $env:SEC_USER_AGENT) {
        $userAgent = (& uv run --no-sync python -c $readUserAgent) -join ""
        if ($LASTEXITCODE -ne 0) { throw "Could not read the settings folder to look for SEC_USER_AGENT." }
        if ($userAgent.Trim() -ne "") { $env:SEC_USER_AGENT = $userAgent.Trim() }
    }

    $env:TEMP = $runRoot
    $env:TMP = $runRoot
    $env:UV_CACHE_DIR = $uvCache

    $pytestArguments = @(
        "run",
        "--no-sync",
        "pytest",
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
        "--live",
        "--junitxml=$junitFile",
        "--basetemp=$pytestRoot",
        "-v"
    )
    if ($Selector -ne "") {
        $pytestArguments += @("-k", $Selector)
    }
    $pytestArguments += "tests/live"

    & uv @pytestArguments
    $exitCode = $LASTEXITCODE
}
finally {
    Set-Location $originalLocation

    if ($null -eq $originalTemp) { Remove-Item Env:TEMP -ErrorAction SilentlyContinue } else { $env:TEMP = $originalTemp }
    if ($null -eq $originalTmp) { Remove-Item Env:TMP -ErrorAction SilentlyContinue } else { $env:TMP = $originalTmp }
    if ($null -eq $originalUvCache) { Remove-Item Env:UV_CACHE_DIR -ErrorAction SilentlyContinue } else { $env:UV_CACHE_DIR = $originalUvCache }
    if ($null -eq $originalUserAgent) { Remove-Item Env:SEC_USER_AGENT -ErrorAction SilentlyContinue } else { $env:SEC_USER_AGENT = $originalUserAgent }
}

Write-Host "Live checks finished with exit code $exitCode. Results: $junitFile"
exit $exitCode
