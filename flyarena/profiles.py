"""果蠅角色檔：依大腦參數與交易行為，自動產生暱稱、個性、特質分數。

存在 leagues/<聯賽>/profiles.json，可以直接修改：
- nickname（暱稱）、title（個性類型）、emoji、bio（介紹）：你改過的欄位不會被自動覆蓋。
- avatar：自訂圖片檔名（放在專案的 avatars/ 資料夾），留 null 則使用自動生成的像素果蠅。
- traits、family 每天依最新資料自動更新。
暱稱取自真實的果蠅突變基因名稱，附上典故。
"""

import hashlib
import json
from pathlib import Path

GENES = [
    ("笨笨", "dunce", "史上第一個被找到的果蠅學習缺陷突變，學不會氣味和電擊的關聯"),
    ("蕪菁", "rutabaga", "學習記憶突變，蘑菇體裡的 cAMP 訊號出了問題"),
    ("健忘", "amnesiac", "學得會、但記憶很快就消失的突變"),
    ("蘿蔔", "radish", "缺少「抗麻醉記憶」的突變"),
    ("大頭菜", "turnip", "另一個學習缺陷突變，和蕪菁、蘿蔔同屬「蔬菜家族」"),
    ("週期", "period", "第一個被找到的生理時鐘基因，相關研究獲 2017 年諾貝爾獎"),
    ("永恆", "timeless", "和 period 搭檔運作的生理時鐘基因"),
    ("瑪土撒拉", "methuselah", "突變後壽命變長，以聖經裡最長壽的人物命名"),
    ("印第", "Indy", "I'm Not Dead Yet 的縮寫，突變後更長壽"),
    ("鐵皮人", "tinman", "心臟發育基因，突變的胚胎長不出心臟，名字來自綠野仙蹤"),
    ("刺蝟", "hedgehog", "胚胎發育基因，突變的幼蟲表面長滿細刺"),
    ("缺口", "Notch", "突變後翅膀邊緣出現缺口，是重要的細胞訊號基因"),
    ("托爾", "Toll", "發現者驚呼德文「Toll！（太棒了）」，後來證實是先天免疫的關鍵"),
    ("無果", "fruitless", "影響雄蠅求偶行為的基因"),
    ("小黃", "yellow", "身體變成黃色的突變"),
    ("小白", "white", "摩根在 1910 年發現的白眼突變，現代遺傳學的起點之一"),
    ("卷卷", "Curly", "翅膀向上捲起的突變"),
    ("棒眼", "Bar", "複眼縮成細長棒狀的突變"),
    ("烏木", "ebony", "身體顏色變深的突變"),
    ("淺酌", "cheapdate", "對酒精特別敏感、一喝就倒的突變"),
    ("沙發馬鈴薯", "couch potato", "活動量明顯變少的突變"),
    ("抖抖", "Shaker", "麻醉時腳會抖個不停的突變，是鉀離子通道基因"),
    ("過動", "Hyperkinetic", "腳動個不停的突變"),
    ("起司", "swiss cheese", "突變後腦中出現空洞，像瑞士起司"),
]

CONTROLS = {
    "random": {"nickname": "骰子", "title": "隨機對照組", "emoji": "🎲",
               "bio": "每天隨機買、賣或不動。果蠅要贏過牠，才能說不是運氣。"},
    "buyhold": {"nickname": "存股阿伯", "title": "買進持有對照組", "emoji": "👴",
                "bio": "買到部位上限就抱著不放。大盤上漲時，任何偏多的交易員都會看起來像高手。"},
    "momentum": {"nickname": "追高哥", "title": "動能規則對照組", "emoji": "📈",
                 "bio": "20 日漲勢和均線乖離都強就買、都弱就賣的簡單規則。"},
}

AUTO_FIELDS = ("nickname", "title", "emoji", "bio")
TRAIT_NAMES = ("學習速度", "記性", "冒險心", "專注", "積極")


def _rank(values, x):
    """族群內百分位（0~1），讓個性反映和其他果蠅比起來的相對差異。"""
    return sum(v < x for v in values) / max(1, len(values) - 1)


def traits(row, pop):
    p = row["params"]
    col = lambda k: [r["params"][k] for r in pop]
    return {
        "學習速度": _rank(col("learning_rate"), p["learning_rate"]),
        "記性": _rank(col("trace_decay"), p["trace_decay"]),
        "冒險心": _rank(col("exploration"), p["exploration"]),
        "專注": 1 - _rank(col("kc_sparsity"), p["kc_sparsity"]),
        "積極": _rank([1 - r["hold_share"] for r in pop], 1 - row["hold_share"]),
        "多空傾向": row["buy_share"] - row["sell_share"],
    }


def archetype(t, row):
    lean = t["多空傾向"]
    if row["hold_share"] >= 0.6:
        return "佛系觀望", "🧘", "大多數時候按兵不動，寧可錯過也不願做錯"
    if t["冒險心"] <= 0.15:
        return "冷靜保守", "🧊", "決策幾乎不帶隨機性，行為最穩定可預測"
    if t["積極"] >= 0.7 and lean >= 0.3:
        return "衝動多頭", "🔥", "出手頻繁、偏愛買進，看到機會就衝"
    if lean <= -0.1:
        return "悲觀空頭", "🌧️", "賣出多於買進，對行情總是有點擔心"
    if t["記性"] >= 0.8:
        return "長記性", "🧠", "記憶痕跡消退得慢，好幾天前的教訓都還記得"
    if t["學習速度"] >= 0.8:
        return "學霸", "🎓", "每次獎懲後大腦改變得最多，學得快也可能忘得快"
    if t["冒險心"] >= 0.8:
        return "愛冒險", "🎲", "決策帶有較多隨機探索，常做出意料之外的選擇"
    return "均衡", "⚖️", "各項特質都在族群中段，沒有明顯偏好"


def _pick_gene(name, taken):
    start = int(hashlib.sha256(name.encode()).hexdigest(), 16) % len(GENES)
    for i in range(len(GENES)):
        gene = GENES[(start + i) % len(GENES)]
        if gene[0] not in taken:
            return gene
    gene = GENES[start]
    n = 2
    while f"{gene[0]}{n}" in taken:
        n += 1
    return (f"{gene[0]}{n}", gene[1], gene[2])


def _auto(row, pop, prev, taken):
    name = row["name"]
    meta = row.get("meta") or {}
    if meta.get("control"):
        return dict(CONTROLS.get(name, {"nickname": name, "title": "對照組", "emoji": "📋", "bio": ""}),
                    gene=None, gene_note=None, traits=None)
    t = traits(row, pop)
    title, emoji, sentence = archetype(t, row)
    if prev.get("gene"):
        nickname, gene, note = prev["_auto"]["nickname"], prev["gene"], prev["gene_note"]
    else:
        nickname, gene, note = _pick_gene(name, taken)
    taken.add(nickname)
    parent = meta.get("parent")
    family = f"第 {meta.get('generation', 0)} 代" + (f"，父親是 {parent}" if parent else "，初代果蠅")
    bio = f"{sentence}。{family}。暱稱典故：{gene}——{note}。"
    return {"nickname": nickname, "title": title, "emoji": emoji, "bio": bio,
            "gene": gene, "gene_note": note, "traits": t}


def build(folder, rows, save=True):
    """save=False：只在記憶體中產生（本機預覽用），不改寫 profiles.json，避免和雲端推送衝突。"""
    path = Path(folder) / "profiles.json"
    old = json.loads(path.read_text(encoding="utf-8"))["flies"] if path.exists() else {}
    pop = [r for r in rows if not (r.get("meta") or {}).get("control")]
    taken = {p["nickname"] for p in old.values()}
    flies = {}
    for row in sorted(rows, key=lambda r: r["name"]):
        name = row["name"]
        prev = old.get(name, {})
        auto = _auto(row, pop, prev, taken)
        prof = dict(prev)
        last = prev.get("_auto", {})
        for f in AUTO_FIELDS:
            if f not in prev or prev[f] == last.get(f):  # 沒被手動改過才更新
                prof[f] = auto[f]
        prof.setdefault("avatar", None)
        meta = row.get("meta") or {}
        prof.update(
            gene=auto["gene"], gene_note=auto["gene_note"], traits=auto["traits"],
            family={"generation": meta.get("generation"), "parent": meta.get("parent")},
            control=bool(meta.get("control")),
            _auto={f: auto[f] for f in AUTO_FIELDS},
        )
        flies[name] = prof
    doc = {"_說明": "可修改 nickname、title、emoji、bio、avatar（avatars/ 資料夾內的檔名）；改過的欄位不會被覆蓋",
           "flies": flies}
    if save:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return flies
