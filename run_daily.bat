@echo off
rem Daily run after market close (15:30 or later): fetch data, replay league,
rem build reports and dashboard, then commit and push docs/ to GitHub.
rem Usage: run_daily.bat [league] [quiet]
rem   quiet = do not open the report afterwards (for Task Scheduler)
chcp 65001 >nul
cd /d "%~dp0"
set LEAGUE=%1
if "%LEAGUE%"=="" set LEAGUE=survivors-2026
if not exist leagues mkdir leagues
echo ===== %date% %time% ===== >> "leagues\daily.log"

".venv\Scripts\python.exe" -X utf8 -m flyarena daily %LEAGUE% >> "leagues\daily.log" 2>&1
if errorlevel 1 (
  echo 執行失敗，請看 leagues\daily.log
  exit /b 1
)

rem ---- push to GitHub: only the dashboard and the editable profiles ----
git add docs "leagues/%LEAGUE%/profiles.json" >> "leagues\daily.log" 2>&1
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "daily update %LEAGUE%" >> "leagues\daily.log" 2>&1
  git push >> "leagues\daily.log" 2>&1
  if errorlevel 1 (
    echo 推送 GitHub 失敗，請看 leagues\daily.log
    exit /b 2
  )
  echo 已推送到 GitHub
) else (
  echo 沒有新的變更，不需要推送
)

if /i not "%2"=="quiet" start "" "leagues\%LEAGUE%\reports\latest.html"
