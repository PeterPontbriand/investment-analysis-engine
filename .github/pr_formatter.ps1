# Define the path to the draft file
$draftFile = Join-Path $PSScriptRoot ".pr_draft.md"

# Read PR draft content if file exists
if (Test-Path -Path $draftFile) {
    $prBody = Get-Content -Path $draftFile -Raw
}

# Exit cleanly if file is missing or empty
if ([string]::IsNullOrWhiteSpace($prBody)) {
    Write-Host "Please add a PR description draft in $draftFile"
    return
}

# 1. Clean up internal model citations
# Spaced string representation to bypass UI markup sanitizer
$rawSpacedPattern = '\ s * \ [ c i t e : \ s * \ d + ( , \ s * \ d + ) * \ ]'
$citationPattern = $rawSpacedPattern -replace ' ', ''

$cleanedBody = $prBody -replace $citationPattern, ''

# Fetch dynamic branch context for GitHub URLs
$currentBranch = (git branch --show-current).Trim()
$repoUrl = "https://github.com/PeterPontbriand/financial-data-agents/blob/$currentBranch"

# Regex matches backticked paths (supporting /, \, top-level dotfiles, and trailing periods)
$pattern = '`\\?/?((?:src|tests|docs|\.github|\.clinerules|\.gitignore|README\.md|pyproject\.toml)[^`\s]*?)\.?`'

$formattedBody = [regex]::Replace($cleanedBody, $pattern, {
    param($match)
    # Extract path and normalize backslashes to forward slashes for URLs and strip trailing dot
    $cleanPath = $match.Groups[1].Value -replace '\\', '/' -replace '\.$', ''
    
    # Use -f formatting to safely insert $cleanPath without backtick-escaping bugs
    return "[`{0}`]({1}/{0})" -f $cleanPath, $repoUrl
})

# Save formatted body back to .pr_draft.md
Set-Content -Path $draftFile -Value $formattedBody -NoNewline

Write-Host "Successfully cleaned citations and formatted links in $draftFile" -ForegroundColor Green

# Optional PR Creation
$confirmation = Read-Host "Do you want to create a PR on GitHub now? (Yes/No)"

if ($confirmation -eq "Yes" -or $confirmation -eq "Y") {
    gh pr create --body $formattedBody
}