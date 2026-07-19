@echo off
cd /d "%~dp0.."

git add -A 2>nul
git commit -m "Auto: save changes" 2>nul
git push 2>nul
