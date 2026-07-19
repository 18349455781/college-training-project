# Auto add, commit, and push on save
$repoRoot = Split-Path -Parent $PSScriptRoot
$logFile = Join-Path $repoRoot ".vscode\auto-push.log"

# Log that script was triggered
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Script triggered" | Out-File -Append $logFile -Encoding UTF8

Set-Location $repoRoot

# Check for changes
$status = git status --porcelain 2>&1
if (-not $status) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - No changes, exiting" | Out-File -Append $logFile -Encoding UTF8
    exit 0
}

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Changes detected, committing..." | Out-File -Append $logFile -Encoding UTF8

git add -A 2>&1 | Out-File -Append $logFile -Encoding UTF8
$commitResult = git commit -m "Auto: save changes $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" 2>&1
$commitResult | Out-File -Append $logFile -Encoding UTF8
$pushResult = git push 2>&1
$pushResult | Out-File -Append $logFile -Encoding UTF8

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Done. Commit: $commitResult, Push: $pushResult" | Out-File -Append $logFile -Encoding UTF8
