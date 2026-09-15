@echo off
rem Local only: fetch data, replay league and open today's report.
rem The public dashboard is built and pushed by GitHub Actions (.github/workflows/daily.yml),
rem so this script does not touch docs/ and does not push.
rem Usage: run_daily.bat [league]
chcp 65001 >nul
cd /d "%~dp0"
set LEAGUE=%1
if "%LEAGUE%"=="" set LEAGUE=survivors-2026
if not exist leagues mkdir leagues
echo ===== %date% %time% ===== >> "leagues\daily.log"

".venv\Scripts\python.exe" -X utf8 -m flyarena daily %LEAGUE% --no-site >> "leagues\daily.log" 2>&1
if errorlevel 1 (
  echo 執行失敗，請看 leagues\daily.log
  exit /b 1
)
start "" "leagues\%LEAGUE%\reports\latest.html"
