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

$exitCode = 1
try {
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    Set-Location $repositoryRoot

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
}

Write-Host "Live checks finished with exit code $exitCode. Results: $junitFile"
exit $exitCode
