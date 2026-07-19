#!/bin/bash
# Auto add, commit, and push on save

# Change to the repository root (parent of .vscode folder)
cd "$(dirname "$0")/.."

# Check if there are any changes
if [[ -z $(git status --porcelain) ]]; then
  exit 0
fi

git add -A
git commit -m "Auto: save changes $(date '+%Y-%m-%d %H:%M:%S')"
git push
