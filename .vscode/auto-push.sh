#!/bin/bash
# Auto add, commit, and push on save

cd "C:/Users/33230/Desktop/实训项目/大二实训项目/大二实训Git项目"

# Check if there are any changes
if [[ -z $(git status --porcelain) ]]; then
  exit 0
fi

git add -A
git commit -m "Auto: save changes $(date '+%Y-%m-%d %H:%M:%S')"
git push
