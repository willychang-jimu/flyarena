"""行情 → 感覺輸入。

果蠅蘑菇體的主要輸入是嗅覺投射神經元（PN）。這裡把每天的市場狀態當成一種「氣味」：
每個特徵先用過去 250 天做標準化，再用 5 顆調諧曲線不同的 PN 做族群編碼。
第 t 天的輸入只使用第 t 天收盤（含）以前的資料。
"""

import numpy as np
import pandas as pd

CENTERS = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
WIDTH = 0.7


def features(df, market):
    c = df.close
    m = market.close.reindex(df.index).ffill()
    f = pd.DataFrame(index=df.index)
    for n in (1, 3, 5, 10, 20, 60):
        f[f"ret_{n}"] = np.log(c / c.shift(n))
    f["vol_20"] = np.log(c).diff().rolling(20).std()
    for n in (20, 60):
        lo = df.low.rolling(n).min()
        hi = df.high.rolling(n).max()
        f[f"range_{n}"] = (c - lo) / (hi - lo).replace(0, np.nan)
        f[f"ma_{n}"] = np.log(c / c.rolling(n).mean())
    f["volume_ratio"] = np.log(
        (df.volume.rolling(5).mean() + 1) / (df.volume.rolling(20).mean() + 1)
    )
    f["gap"] = np.log(df.open / c.shift(1))
    for n in (1, 5, 20):
        f[f"mkt_{n}"] = np.log(m / m.shift(n))
    f["rel_20"] = f.ret_20 - f.mkt_20
    return f


def normalize(f, window=250):
    mean = f.rolling(window, min_periods=60).mean()
    std = f.rolling(window, min_periods=60).std()
    z = (f - mean) / std.replace(0, np.nan)
    # 特徵在整個窗口內完全沒變化（例如停牌、成交量固定）→ 視為「和平常一樣」= 0；
    # 暖機期資料不足（std 為 NaN）才保留缺值
    return z.mask(std == 0, 0.0).clip(-3, 3)


def encode(z):
    """z: (天數, 特徵數) 或 (特徵數,) 的標準化值 → PN 發放率 0~1。"""
    z = np.asarray(z, dtype=np.float64)
    rates = np.exp(-((z[..., None] - CENTERS) ** 2) / (2 * WIDTH**2))
    return rates.reshape(z.shape[:-1] + (z.shape[-1] * len(CENTERS),))


def sensory_frame(df, market):
    """回傳 (標準化特徵 DataFrame, PN 發放率陣列)，只保留特徵齊全的日子。"""
    z = normalize(features(df, market)).dropna()
    return z, encode(z.to_numpy())


def feature_names(df_or_z):
    return list(df_or_z.columns)
