@echo off
REM Push this repo to GitHub. Usage: publish_github.bat [owner/repo]   (default ljrseals-dev/LA2A-VST3)
REM Uses GitHub CLI if installed (gh auth login first); otherwise sets the remote and runs git push.
set REPO=%1
if "%REPO%"=="" set REPO=ljrseals-dev/LA2A-VST3
cd /d "%~dp0"
if not exist ".git" ( git init -b main & git add . & git commit -m "LA-2A manual-faithful VST3 (initial)" )
where gh >nul 2>nul
if not errorlevel 1 (
  gh repo create %REPO% --private --source . --remote origin --push
  if not errorlevel 1 ( echo Pushed to https://github.com/%REPO% (private) & exit /b 0 )
)
git remote remove origin 2>nul
git remote add origin https://github.com/%REPO%.git
git push -u origin main
