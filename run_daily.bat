@echo off
rem 每日收盤後執行（建議 15:00 以後）：更新資料、重播聯賽、產生戰報並打開
rem 用法：run_daily.bat [聯賽名稱]，預設 survivors-2026
chcp 65001 >nul
cd /d "%~dp0"
set LEAGUE=%1
if "%LEAGUE%"=="" set LEAGUE=survivors-2026
".venv\Scripts\python.exe" -X utf8 -m flyarena daily %LEAGUE% >> "leagues\daily.log" 2>&1
if errorlevel 1 (
  echo 執行失敗，請看 leagues\daily.log
  exit /b 1
)
start "" "leagues\%LEAGUE%\reports\latest.html"
