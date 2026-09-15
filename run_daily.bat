@echo off
rem Local only: fetch data, replay all seasons, write dashboard and season reports to preview\ and open it.
rem The public website is built and pushed by GitHub Actions, so this script does not touch docs\ or push.
chcp 65001 >nul
cd /d "%~dp0"
if not exist leagues mkdir leagues
echo ===== %date% %time% ===== >> "leagues\daily.log"

".venv\Scripts\python.exe" -X utf8 -m flyarena publish --preview >> "leagues\daily.log" 2>&1
if errorlevel 1 (
  echo 執行失敗，請看 leagues\daily.log
  exit /b 1
)
start "" "preview\index.html"
