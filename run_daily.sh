#!/usr/bin/env bash
# 本機（Mac / Linux）：更新資料、重播聯賽、產生今日戰報與 dashboard 預覽並打開。
# 公開網站由 GitHub Actions 更新；這個腳本只寫 preview/，不會動到 docs/，也不會推送。
# 用法：./run_daily.sh [聯賽名稱]
set -euo pipefail
cd "$(dirname "$0")"
LEAGUE="${1:-survivors-2026}"
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "找不到 .venv，請先依 README 的「安裝」步驟建立虛擬環境"
  exit 1
fi
mkdir -p leagues
echo "===== $(date '+%F %T') =====" >> leagues/daily.log
if ! "$PY" -X utf8 -m flyarena daily "$LEAGUE" >> leagues/daily.log 2>&1; then
  echo "執行失敗，最後幾行紀錄："
  tail -20 leagues/daily.log
  exit 1
fi
tail -12 leagues/daily.log
if command -v open >/dev/null 2>&1; then
  open "leagues/$LEAGUE/reports/latest.html" "preview/index.html"
fi
