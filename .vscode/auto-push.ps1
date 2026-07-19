param($workspaceFolder)

Set-Location $workspaceFolder

# Check for changes
$status = git status --porcelain
if (-not $status) {
    exit 0
}

git add -A
git commit -m "Auto: save changes $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git push
