"""台股日線：Yahoo Finance 公開 chart API，快取為 data/*.csv。

價格一律使用還原股價（開高低依還原收盤比例調整），避免除權息、分割造成假漲跌。
Yahoo 的台股還原資料偶有錯誤；重要結論請用其他資料源交叉確認。
"""

import datetime as dt
import time
from pathlib import Path

import pandas as pd
import requests

try:
    import truststore

    # 使用 Windows 憑證庫：防毒軟體或網路設備做 HTTPS 檢查時，其根憑證只在系統憑證庫裡
    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
TW = dt.timezone(dt.timedelta(hours=8))


def _get(symbol, attempts=4):
    """雲端伺服器偶爾會被 Yahoo 限流（HTTP 429），失敗時等待後重試。"""
    for attempt in range(attempts):
        try:
            r = requests.get(
                URL.format(symbol),
                params={
                    "period1": 0,
                    "period2": int(time.time()) + 86400,
                    "interval": "1d",
                    "events": "div,split",
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == attempts - 1:
                raise
            wait = 5 * 3**attempt
            print(f"{symbol} 下載失敗（{e}），{wait} 秒後重試")
            time.sleep(wait)


def fetch(symbol):
    chart = _get(symbol)["chart"]
    if not chart["result"]:
        raise RuntimeError(f"{symbol}: {chart['error']}")
    res = chart["result"][0]
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    df = pd.DataFrame(
        {
            "date": [dt.datetime.fromtimestamp(t, TW).date() for t in res["timestamp"]],
            "open": q["open"],
            "high": q["high"],
            "low": q["low"],
            "close": q["close"],
            "adjclose": adj,
            "volume": q["volume"],
        }
    )
    df = df.dropna(subset=["open", "close", "adjclose"])
    df = df[(df.close > 0) & (df.open > 0)].drop_duplicates("date", keep="last")
    factor = df.adjclose / df.close
    for c in ["open", "high", "low"]:
        df[c] = df[c].fillna(df.close) * factor
    df["close"] = df.adjclose
    df["volume"] = df.volume.fillna(0)
    df["date"] = pd.to_datetime(df.date)
    return clean(df.drop(columns="adjclose").set_index("date").sort_index())


def clean(df, limit=0.105):
    """台股單日漲跌幅上限 10%（2015 年前 7%）。超過 10.5% 的收盤變動視為資料斷點
    （例如還原錯誤、分割未調整），把斷點之前的價格等比例接到斷點當天，該日變動視為 0。"""
    df = df.copy()
    cols = ["open", "high", "low", "close"]
    change = df.close / df.close.shift(1)
    breaks = change[(change - 1).abs() > limit]
    for date, ratio in breaks.items():
        before = df.index < date
        df.loc[before, cols] = df.loc[before, cols] * ratio
    df.attrs["breaks"] = len(breaks)
    return df


def _path(symbol):
    return DATA / (symbol.replace("^", "_") + ".csv")


def load(symbol, refresh=False):
    path = _path(symbol)
    if refresh or not path.exists():
        DATA.mkdir(exist_ok=True)
        df = fetch(symbol)
        # 收盤後資料才完整：台灣時間 14:30 前不收錄當天這根 K 線
        now = dt.datetime.now(TW)
        if now.hour * 60 + now.minute < 14 * 60 + 30:
            df = df[df.index.date < now.date()]
        df.to_csv(path)
    return pd.read_csv(path, index_col="date", parse_dates=["date"])


def load_all(config, refresh=False):
    symbols = list(config["symbols"]) + [config["benchmark"]]
    return {s: load(s, refresh) for s in symbols}
