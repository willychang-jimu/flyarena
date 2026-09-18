"""角色卡：卡片配色，以及「新果蠅的角色圖提示詞」自動產生。

配色沿用卡片產生器的設計稿；沒有對應設計的新果蠅，依名字自動配一組同風格的顏色。
新果蠅誕生時，prompt() 會依牠的基因與個性寫出同一套格式的英文提示詞，
貼到影像生成工具就能做出風格一致的角色圖（本程式無法直接畫寫實插畫）。
"""

import hashlib

from .avatars import _parts

# 設計稿的 19 張卡：(漸層起, 漸層迄, 名牌色, 編號代碼, 背景色描述)
CARDS = {
    "ff-tipsy": ("#f8d6a2", "#eeb56d", "#c9772a", "TIPSY", "warm honey-amber"),
    "ff-tinman": ("#bfdcf6", "#8dbfe8", "#2f6fa8", "TINMAN", "soft sky blue"),
    "ff-turnip": ("#cfe6b4", "#a5d089", "#4e8b3a", "TURNIP", "fresh leaf green"),
    "ff-curly": ("#f8cddd", "#eda8c2", "#c2467c", "CURLY", "candy pink"),
    "ff-radish": ("#fad3ad", "#f3ad79", "#d1652c", "RADISH", "apricot orange"),
    "ff-cheese": ("#f7e7a6", "#ecd167", "#a8890f", "CHEESE", "buttery yellow"),
    "ff-thor": ("#d5cbf4", "#b3a5ea", "#6a4fb8", "THOR", "lavender violet"),
    "ff-dice": ("#bfe0f5", "#8ec8ec", "#2b7ab0", "DICE", "clear azure"),
    "ff-uncle": ("#dbe8ab", "#bcd183", "#6f8a2e", "DIVIDEND UNCLE", "olive green"),
    "ff-chaser": ("#f7b9b9", "#ef9090", "#c93a3a", "CHASER", "coral red"),
    "ff-hedgehog": ("#d7c9f2", "#b8a3e6", "#6b4bb5", "HEDGEHOG", "periwinkle purple"),
    "ff-notch": ("#c2e4f2", "#94cfe6", "#2c85a8", "NOTCH", "pale cyan"),
    "ff-eternal": ("#b8e3d5", "#8ccfba", "#2b8a72", "ETERNAL", "jade teal"),
    "ff-ebony": ("#c8ccd2", "#a2a8b1", "#4a4f57", "EBONY", "cool graphite grey"),
    "ff-couch": ("#d3e6a9", "#b0cd7e", "#5f8c2f", "COUCH POTATO", "grass green"),
    "ff-hyper": ("#f8bcbc", "#f09595", "#cc3b3b", "HYPERKINETIC", "hot coral"),
    "ff-shaker": ("#d3c6f0", "#b09ce4", "#6a45ab", "SHAKER", "soft lilac"),
    "ff-bar": ("#c0ddf5", "#8fc3e9", "#2b6fa8", "BAR", "powder blue"),
    "ff-fruitless": ("#e4cfc9", "#cdaaa2", "#8e5b52", "FRUITLESS", "dusty mauve"),
}
HUE_NAMES = [(20, "warm amber"), (45, "buttery yellow"), (80, "fresh leaf green"), (150, "jade teal"),
             (200, "soft sky blue"), (250, "periwinkle purple"), (290, "soft lilac"), (330, "candy pink"),
             (360, "coral red")]

STYLE = ("ultra-detailed 3D rendered stylised character illustration, glossy toy-like surfaces, "
         "cinematic soft studio lighting, shallow depth of field")
BODY_PLAN = ("chibi anthropomorphic fruit fly, oversized round head, huge glossy compound eyes with bright "
             "specular highlights, two curved antennae, translucent iridescent wings, plump furry tan abdomen, "
             "thin dark segmented legs, full body visible, standing centered, facing the viewer, three-quarter view")
FRAMING = ("1:1 square, character occupying about 78% of the frame height, generous even margins, "
           "no text, no watermark, no border")
SERIES = ("identical lighting, eye gloss, wing translucency and line weight across the whole cast")

TITLE_EN = {
    "佛系觀望": "serene and unhurried, eyes gently closed, content to wait",
    "衝動多頭": "excited and impulsive, leaning forward as if chasing a rally",
    "悲觀空頭": "worried and cautious, glancing away from a small rain cloud",
    "長記性": "thoughtful and studious, remembering every lesson",
    "冷靜保守": "calm and composed, steady posture, minimal fuss",
    "學霸": "bookish and eager, quick to learn",
    "愛冒險": "adventurous and curious, ready to explore",
    "均衡": "balanced and even-tempered",
}
HAT_EN = {"grad": "a black graduation cap", "helmet": "a riveted steel helmet", "horns": "a small horned helmet",
          "cap": "a flat newsboy cap", "adventurer": "a worn explorer hat", "dunce": "a tall pointed cap",
          "headband": "a red headband", "halo": "a soft golden halo floating above", "spikes": "tall spiky quills"}
EYES_EN = {"glasses": "big round glasses", "shades": "black sunglasses", "sleepy": "eyes closed and content",
           "bar": "narrow vertical bar-shaped eyes", "wide": "wide startled eyes", "pale": "pale white eyes",
           "happy": "bright happy eyes"}
PROP_EN = {"bottle": "hugging a green glass bottle", "book": "holding an open thick blue book",
           "carrot": "hugging an oversized orange carrot", "turnip": "holding a white turnip",
           "dice": "holding a large white dice", "cane": "leaning on a wooden cane",
           "clock": "holding a small round clock", "arrow": "pointing at a rising arrow",
           "flower": "holding a single small flower"}
EXTRA_EN = {"holes": "cheese-yellow body dotted with holes", "motion": "cartoon motion lines around it",
            "blush": "rosy blushing cheeks", "question": "small question marks floating nearby",
            "beard": "a bushy white moustache", "rain": "a tiny rain cloud overhead",
            "curly": "tightly curled antennae", "notch": "wing edges with scalloped notches"}


# 基因（與對照組）對應到設計稿的卡片，換頭像檔名也不會影響配色
GENE_SLOT = {
    "cheapdate": "ff-tipsy", "tinman": "ff-tinman", "rutabaga": "ff-turnip", "Curly": "ff-curly",
    "radish": "ff-radish", "swiss cheese": "ff-cheese", "Toll": "ff-thor", "hedgehog": "ff-hedgehog",
    "Notch": "ff-notch", "timeless": "ff-eternal", "ebony": "ff-ebony", "couch potato": "ff-couch",
    "Hyperkinetic": "ff-hyper", "Shaker": "ff-shaker", "Bar": "ff-bar", "fruitless": "ff-fruitless",
    "random": "ff-dice", "buyhold": "ff-uncle", "momentum": "ff-chaser",
}


def slot(name, profile):
    """這隻果蠅對應到設計稿的哪張卡：先看基因，其次看頭像檔名。"""
    key = GENE_SLOT.get(profile.get("gene")) or GENE_SLOT.get(name)
    if key:
        return key
    stem = (profile.get("avatar") or "").rsplit(".", 1)[0]
    return stem if stem in CARDS else None


def colours(name, profile):
    """回傳 (漸層起, 漸層迄, 名牌色, 編號代碼, 背景色描述)。新果蠅依名字自動配色。"""
    key = slot(name, profile)
    if key:
        return CARDS[key]
    hue = int(hashlib.sha256(name.encode()).hexdigest(), 16) % 360
    label = (profile.get("gene") or profile.get("nickname") or name).upper()
    backdrop = next(n for limit, n in HUE_NAMES if hue <= limit)
    return (f"hsl({hue},72%,84%)", f"hsl({hue},60%,68%)", f"hsl({hue},52%,40%)", label, backdrop)


def prompt(name, profile, extra=""):
    """新果蠅的角色圖提示詞：格式與既有 19 張一致，方便做出風格統一的圖。"""
    hat, eyes, prop, body, extra_kind = _parts(name, profile)
    bits = [TITLE_EN.get(profile.get("title"), "balanced and even-tempered")]
    if body == "dark":
        bits.append("glossy jet-black body")
    elif body == "yellow":
        bits.append("cheese-yellow body")
    elif body == "pale":
        bits.append("pale sandy body")
    if eyes == "sleepy" and "eyes" in bits[0]:
        eyes = None  # 個性描述已經講過閉眼，不重複
    for table, key, lead in ((HAT_EN, hat, "with " if hat == "halo" else "wearing "), (EYES_EN, eyes, "with "),
                             (PROP_EN, prop, ""), (EXTRA_EN, extra_kind, "with ")):
        if key in table:
            bits.append(lead + table[key])
    backdrop = colours(name, profile)[4]
    note = profile.get("gene_note")
    subject = f"a fruit fly that is {', '.join(bits)}"
    return "\n\n".join(filter(None, [
        STYLE + ".",
        f"Subject: {subject}.",
        f"Body plan: {BODY_PLAN}.",
        f"Extra: {extra}." if extra else "",
        "Background: fully transparent background (export as PNG with alpha), no backdrop, no scenery, "
        "no colour fill behind the character; keep only a soft contact shadow directly under its feet. "
        f"（若工具不支援透明背景，改用單色 {backdrop} pastel 背景。）",
        f"Framing: {FRAMING}.",
        f"Series consistency: {SERIES}.",
        f"（暱稱典故：{profile.get('gene')}——{note}）" if note else "",
    ]))
