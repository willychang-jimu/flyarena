"""選股範圍：依證交所公開資料計算上市公司市值排名。建立賽季時執行一次，整季固定不變。"""

import re

import requests

from . import data  # noqa: F401  匯入時會啟用 Windows 憑證庫

PRICES = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
COMPANIES = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

INDUSTRY = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械",
    "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業",
    "12": "汽車工業", "14": "建材營造", "15": "航運業", "16": "觀光餐旅", "17": "金融保險",
    "18": "貿易百貨", "19": "綜合", "20": "其他", "21": "化學工業", "22": "生技醫療",
    "23": "油電燃氣", "24": "半導體", "25": "電腦及週邊設備", "26": "光電業", "27": "通信網路",
    "28": "電子零組件", "29": "電子通路", "30": "資訊服務", "31": "其他電子", "32": "文化創意",
    "33": "農業科技", "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
}


def _get(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    return r.json()


def _roc_date(s):
    """證交所日期是民國年，例如 1150914 → 2026-09-14。"""
    return f"{int(s[:-4]) + 1911}-{s[-4:-2]}-{s[-2:]}"


def rank(prices, companies):
    """回傳 (依市值排序的上市普通股清單, 資料日期)。排除 ETF、特別股、存託憑證與創新板。"""
    px = {r["Code"]: r for r in prices}
    rows = []
    for c in companies:
        code = c["公司代號"].strip()
        if not re.fullmatch(r"[1-9]\d{3}", code) or code not in px:
            continue
        name = c["公司簡稱"].strip()
        if "-創" in name or "-創" in px[code]["Name"]:  # 創新板：一般投資人需符合資格才能交易
            continue
        try:
            price = float(px[code]["ClosingPrice"])
            shares = float(c["已發行普通股數或TDR原股發行股數"])
            value = float(px[code]["TradeValue"])
        except (KeyError, ValueError):
            continue
        if price <= 0 or shares <= 0:
            continue
        industry = c.get("產業別", "").strip()
        rows.append({
            "symbol": f"{code}.TW", "code": code, "name": name,
            "industry": INDUSTRY.get(industry, industry),
            "market_cap": price * shares, "trade_value": value,
        })
    rows.sort(key=lambda r: -r["market_cap"])
    return rows, _roc_date(next(iter(px.values()))["Date"])


def top(n):
    rows, date = rank(_get(PRICES), _get(COMPANIES))
    return rows[:n], date
