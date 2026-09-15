"""賽季功能測試：每日買進上限、尚未開賽、老將帶記憶進入新賽季、資料快取範圍。全部離線。"""

import numpy as np
import pytest

from flyarena import backtest, data, league
from flyarena.brains import BUY, Brain, make_brain
from test_core import config, frames


class Picky(Brain):
    """每檔都想買，但想買的程度不同。"""

    kind = "picky"

    def __init__(self, scores):
        self.scores = scores

    def decide(self, obs, rng):
        return BUY, {"conviction": self.scores[obs.symbol]}


def test_max_buys_per_day_picks_highest_conviction():
    cfg, fr = config(), frames()
    cfg["broker"]["max_buys_per_day"] = 1
    m = backtest.Market(fr, cfg)
    days = m.days()
    first = next(d for d in days if d in m.rows["1111.TW"] and d in m.rows["0099.TW"])
    i = days.index(first)
    t = backtest.Trader("t", Picky({"1111.TW": 0.1, "0099.TW": 0.9}), cfg)
    backtest.run([t], m, cfg, first, first)
    assert {e["symbol"]: e["selected"] for e in t.journal} == {"1111.TW": False, "0099.TW": True}
    backtest.run([t], m, cfg, days[i + 1], days[i + 1])
    assert [f.symbol for f in t.broker.fills] == ["0099.TW"]  # 沒入選的不下單
    assert len(t.rewards.pending) == 2  # 但兩個判斷都會結算獎懲


def test_capped_positions_do_not_use_buy_slots():
    cfg, fr = config(), frames()
    cfg["broker"]["max_buys_per_day"] = 1
    m = backtest.Market(fr, cfg)
    first = next(d for d in m.days() if d in m.rows["1111.TW"] and d in m.rows["0099.TW"])
    t = backtest.Trader("t", Picky({"1111.TW": 0.1, "0099.TW": 0.9}), cfg)
    t.broker.positions["0099.TW"] = 10**6  # 遠超過單檔部位上限
    backtest.run([t], m, cfg, first, first)
    assert {e["symbol"]: e["selected"] for e in t.journal} == {"1111.TW": True, "0099.TW": False}


def _patch(monkeypatch, tmp_path, fr):
    monkeypatch.setattr(league, "LEAGUES", tmp_path)
    monkeypatch.setattr(league.data, "load_all", lambda c, refresh=False: fr)


def test_future_season_is_not_started(tmp_path, monkeypatch):
    cfg, fr = config(), frames()
    _patch(monkeypatch, tmp_path, fr)
    m = backtest.Market(fr, cfg)
    league.create("future", cfg, [("fly-0", make_brain("mushroom", m.n_pn, cfg["brain"], 0), {})], "2099-01-01")
    with pytest.raises(league.NotStarted):
        league.replay("future")


def test_veterans_carry_memory_and_rookies_fill_field(tmp_path, monkeypatch):
    cfg, fr = config(), frames()
    _patch(monkeypatch, tmp_path, fr)
    m = backtest.Market(fr, cfg)
    cal = m.calendar
    s1 = [(f"fly-{i}", make_brain("mushroom", m.n_pn, cfg["brain"], i), {"generation": 0}) for i in range(5)]
    league.create("s1", cfg, s1, str(cal[300].date()), 20, 1, 3, end=str(cal[340].date()))
    rookies = [(f"fly-1{i}", make_brain("mushroom", m.n_pn, cfg["brain"], 10 + i), {"generation": 0}) for i in range(5)]
    league.create("s2", cfg, rookies, str(cal[341].date()), 20, 1, 3, veterans_from="s1", field_size=6)

    first = league.replay("s1")
    survivors = first["active"] - {"random", "buyhold", "momentum"}
    assert first["days"][-1] == cal[340]  # 結束日之後不再比賽
    s2_cfg, s2_rules = league.load_rules("s2")
    vets = league._veterans("s2", s2_rules, s2_cfg, False)
    final = {t.name: t.brain for t in first["traders"]}
    assert {t.name for t in vets} == survivors
    for t in vets:
        assert t.meta["veteran"] and np.array_equal(t.brain.W, final[t.name].W)  # 記憶原封不動帶進新賽季
        assert t.brain is not final[t.name]

    second = league.replay("s2")
    flies = [t for t in second["traders"] if not t.meta.get("control")]
    assert len(flies) == 6 and sum(1 for t in flies if t.meta.get("veteran")) == len(survivors)


def test_cache_coverage_rules():
    assert data._covers("full", "2024-06-01")
    assert data._covers("2024-01-01", "2024-06-01")
    assert not data._covers("2024-06-01", "2024-01-01")
    assert not data._covers("2024-06-01", "full")
