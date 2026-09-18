# 🪰 FlyArena：果蠅交易員研究平台

受 stonkfly（果蠅連接圖交易實驗）啟發的**研究用模擬平台**：讓以果蠅蘑菇體為藍本的小大腦看台股行情、
做買賣決策、接受多巴胺獎懲，然後做訊號反應測試、回測、淘汰賽與每日聯賽。

> **只做模擬交易，不連任何券商帳戶，不是投資建議。** 目前沒有任何證據顯示果蠅交易員能穩定賺錢，
> 這個平台的目的正是用對照組去檢驗這件事。

## 安裝

需要 Python 3.11 以上。

**Mac**（內建 Python 太舊時，到 python.org 下載或 `brew install python@3.12`）：

```sh
git clone https://github.com/willychang-jimu/flyarena.git
cd flyarena
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m flyarena fetch
```

**Windows**：

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m flyarena fetch
```

以下指令的 `python` 指的是虛擬環境裡的 Python（Mac 先 `source .venv/bin/activate`）。

## 指令

| 指令 | 做什麼 |
|---|---|
| `python -m flyarena fetch` | 更新台股日線（Yahoo，還原股價，自動清除不可能的跳動） |
| `python -m flyarena probe --seed 0` | 訊號反應測試：制約學習、規則反轉、各訊號反應強度 → `reports/` |
| `python -m flyarena tournament --seed 7` | 訓練期淘汰賽＋測試期最終驗證（含對照組）→ `runs/`、`reports/` |
| `python -m flyarena league-create 名稱 --from runs/tournament-seed7/survivors --start 2026-01-02` | 用存活果蠅建立聯賽 |
| `python -m flyarena league-create 名稱 --new 12 --start 2026-09-16` | 用新生果蠅建立聯賽 |
| `python -m flyarena daily 名稱` | 收盤後重播聯賽、產生今日戰報與 dashboard 本機預覽（`preview/`） |
| `./run_daily.sh 名稱`（Mac）／`run_daily.bat 名稱`（Windows） | 同上並自動打開；不影響公開網站 |
| `python -m flyarena season-report 名稱` | 季賽報告（Markdown）：各季排名、前三名總結、淘汰果蠅失敗報告 → `notes/season-reports/` |
| `python -m flyarena season-create 名稱 --title 標題 --start 開賽日 --veterans-from 上一屆` | 建立新一屆：市值排名選股、老將帶記憶參賽、新秀補滿 |
| `python -m flyarena publish` | 發布所有屆（雲端每天執行）：各屆 dashboard、季賽報告、總覽首頁；加 `--preview` 只輸出本機預覽 |
| `python -m flyarena prompts 賽季 [--all]` | 為還沒有角色圖的果蠅產生影像生成提示詞 → `notes/prompts/` |
| `python -m pytest -q` | 核心正確性測試 |

研究筆記與常見問題（修改限制、個性遺傳、賽制調整、果蠅的能力）見 [notes/FAQ.md](notes/FAQ.md)。

所有指令都可加 `--config 其他設定檔.json`，方便同時比較不同賽制。

## 聯賽屆次

所有屆次列在 `leagues/seasons.json`；每一屆裡，每 20 個交易日為「一季」，季末淘汰最後一名。

| 屆 | 期間 | 選股 | 資金規則 | 參賽 |
|---|---|---|---|---|
| 第 1 屆 `survivors-2026` | 2026-01-02 ～ 2026-09-30 | 7 檔權值股與 ETF | 本金 100 萬、單筆 10 萬、單檔上限 30 萬 | 淘汰賽存活的 16 隻 |
| 第 2 屆 `season2-top150` | 2026-10-01 起 | 上市市值前 150 大（排除 ETF、特別股、創新板，名單整屆固定） | 本金 100 萬、單筆 5 萬、單檔上限 10 萬、每天最多新買 3 檔 | 第 1 屆存活老將（帶記憶）＋新秀補滿 16 隻 |

每天最多新買 3 檔時，果蠅會對 150 檔都做判斷，只執行「最想買」的前 3 檔；沒入選的判斷不下單，但仍結算獎懲。
已達單檔上限或現金不足的股票不佔名額。

## Dashboard（可公開在 GitHub Pages）

**公開網站 `docs/` 只由 GitHub Actions 產生**（`daily --publish`）。在本機執行 `daily` 或
`python -m flyarena site 名稱 --offline` 只會輸出預覽到 `preview/index.html`，不改 `docs/` 和 `profiles.json`，
所以不會和雲端每天的推送衝突。
網頁是單一 HTML 檔（資料內嵌），直接雙擊就能看，也能原封不動放上 GitHub Pages。

- 角色卡採用卡片產生器的版型：正方形卡、專屬漸層底色、角色圖、圓角名牌，點卡片看完整資料。
- 卡片稀有度依戰績決定：**閃卡**＝拿過季冠軍、**金卡**＝1 屆冠軍、**彩虹卡**＝2 屆以上冠軍；
  冠軍次數會跟著果蠅帶到下一屆。卡面顯示名次、累積報酬、Sharpe、命中率與冠軍徽章。
  全息效果是自己寫的 CSS（靈感來自 pokemon-cards-css，但未使用其程式碼或素材，因此不受 GPL 影響）。
- 每隻果蠅自動取暱稱（真實果蠅突變基因名）並推算個性。
- 角色圖放在 `avatars/`，用 `profiles.json` 的 `avatar` 指定。新果蠅可用 `prompts` 指令取得
  同一套格式的英文提示詞（畫風、身形、背景、構圖、系列一致性都寫好），生成 1:1 圖片後放進 `avatars/` 即可。
- 還沒有角色圖的果蠅，會自動生成卡通頭像（SVG）遞補：底色由名字決定，配件依基因典故與個性挑選
  （學士帽、眼鏡、頭巾、光環、刺、酒瓶、紅蘿蔔、骰子…），所以不會有果蠅沒頭像。
- 修改暱稱、個性、頭像：編輯 `leagues/名稱/profiles.json`，自訂圖片放 `avatars/`（見 `avatars/README.md`）。
- 內容只有模擬成績、報酬率曲線與決策紀錄，不含原始股價；頁首固定顯示「模擬實驗、非投資建議」。

### 發布到 GitHub Pages

1. 在 GitHub 建立一個公開 repository，把這個資料夾推上去（`.gitignore` 已排除資料、大腦與虛擬環境）。
2. repository 的 **Settings → Pages**：Source 選 **Deploy from a branch**，Branch 選 `main`、資料夾選 `/docs`。
3. 每日更新由 **GitHub Actions** 在雲端自動執行（`.github/workflows/daily.yml`），不需要開電腦：
   週一到週五台灣時間 15:30 抓資料、重播聯賽、產生 dashboard，有變更才推送。
   也可以到 repository 的 **Actions → 每日果蠅聯賽 → Run workflow** 手動執行；失敗時 GitHub 會寄信通知。
4. 改暱稱、個性：直接在 GitHub 網頁編輯 `leagues/survivors-2026/profiles.json`，下次執行就會套用。

## 可調整的機制（`arena.json`）

| 區塊 | 參數 | 說明 |
|---|---|---|
| `symbols` / `benchmark` | 股票代號 | 上市 `.TW`、上櫃 `.TWO`；大盤 `^TWII` 作為基準與市場感覺輸入 |
| `broker` | `capital`、`order_value`、`max_position_value` | 本金、單筆金額、單檔部位上限 |
| | `trade_every_days` | 交易頻率：每 N 個交易日決策一次 |
| | `odd_lot`、`fee_rate`、`fee_discount`、`min_fee`、`tax_rate`、`etf_tax_rate` | 零股、手續費與折扣、證交稅 |
| `brain` | `n_kc`、`kc_sparsity`、`learning_rate`、`trace_decay`、`weight_recovery`、`exploration`、`frozen` | 大腦結構與學習參數 |
| `reward` | `mode` | `action_contingent`（預設）、`equity_binary`（stonkfly 式）、`equity_proportional`、`shuffled`（對照組）、`none` |
| | `horizon_days`、`cost`、`scale`、`deadband` | 幾天後結算、成本門檻、刺激強度 |
| `periods` | `train_start`、`train_end`、`test_start` | 訓練期與沒比過的測試期 |
| `tournament` | `population`、`rounds`、`eliminate`、`score`、`mutation`、`seed` | 族群大小、回合、每回合淘汰數、評分（sharpe/return/hit_rate/calmar）、突變幅度 |

## 設計重點

- **不偷看未來**：第 t 天收盤後決策，第 t+1 天開盤成交；感覺輸入只用第 t 天以前的資料。
- **大腦可替換**：實作 `flyarena/brains/base.py` 的 `Brain` 介面，並在 `brains/__init__.py` 註冊，
  回測、淘汰賽、聯賽都不用改。之後可以加入 MaleCNS 真實蘑菇體接線版。
- **對照組是研究的核心**：隨機、買進持有、動能規則，以及冠軍的「凍結」「失憶」「亂獎懲雙胞胎」。
- **聯賽用確定性重播**：只存果蠅出生時的大腦與設定，每天從開賽日重播，結果可完全重現。
- **淘汰賽的遺傳**：子代繼承接線與參數（基因），記憶不遺傳。

## 已知限制

- Yahoo 還原股價偶有錯誤；已自動修補超過漲跌幅的跳動，但重要結論請用其他資料源交叉確認。
- 使用還原價計算股數；未模擬漲跌停鎖死、流動性、滑價。
- 資料源若改寫歷史，聯賽重播的過去名次可能改變（戰報會顯示資料指紋）。
- 輕量蘑菇體是抽象計算模型，不是果蠅生理的精確重現。

## 第一次淘汰賽的結果（seed 7，16 隻、6 回合）

測試期 2022-01 ~ 2026-09，大盤 +151%：買進持有 +298%、動能規則 +231%（Sharpe 1.61）、
冠軍果蠅 +118%（Sharpe 0.89）、亂獎懲雙胞胎 +93%、凍結 +74%、失憶 +78%、隨機 +54%。
冠軍的判斷命中率 48.7%、IC 為負：**沒有預測能力的證據**。它贏過凍結版本，主要是因為學會了少交易
（成交 1,276 筆 vs 3,932 筆），省下交易成本，而不是看準方向。
