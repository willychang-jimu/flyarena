"""果蠅頭像：自動生成的向量卡通果蠅（SVG）。

每隻果蠅依「暱稱的基因典故」與「個性類型」自動挑配件，底色由名字決定，
所以新加入的果蠅不必畫圖，也會拿到同一套風格的頭像。
想換成自己的圖：把圖片放進專案的 avatars/ 資料夾，並在 profiles.json 的 avatar 填檔名。
"""

import hashlib
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUSTOM = ROOT / "avatars"

BODY = {"plain": ("#ecc99c", "#d9ad78"), "dark": ("#5d5349", "#453d35"),
        "yellow": ("#f3d05a", "#dcb337"), "pale": ("#f2e7d7", "#dccbb4")}
DARK = "#3b342e"

# 基因典故 → (帽子, 眼睛, 手持道具, 身體, 附加效果)
GENES = {
    "cheapdate": ("headband", "happy", "bottle", "plain", "blush"),
    "tinman": ("helmet", "round", None, "pale", None),
    "rutabaga": ("grad", "glasses", "book", "plain", None),
    "Curly": ("none", "happy", None, "plain", "curly"),
    "radish": ("none", "round", "carrot", "plain", None),
    "turnip": ("none", "round", "turnip", "plain", None),
    "swiss cheese": ("none", "round", None, "yellow", "holes"),
    "Toll": ("horns", "round", None, "plain", None),
    "Bar": ("none", "bar", None, "pale", None),
    "ebony": ("none", "round", None, "dark", None),
    "yellow": ("none", "happy", None, "yellow", None),
    "white": ("none", "pale", None, "pale", None),
    "hedgehog": ("spikes", "round", None, "plain", None),
    "couch potato": ("none", "sleepy", None, "plain", None),
    "Shaker": ("none", "wide", None, "plain", "motion"),
    "Hyperkinetic": ("none", "wide", None, "plain", "motion"),
    "Notch": ("none", "round", None, "plain", "notch"),
    "period": ("none", "round", "clock", "plain", None),
    "timeless": ("none", "round", "clock", "plain", None),
    "methuselah": ("none", "sleepy", "cane", "pale", "beard"),
    "Indy": ("adventurer", "happy", None, "plain", None),
    "dunce": ("dunce", "round", None, "plain", None),
    "amnesiac": ("none", "round", None, "plain", "question"),
    "fruitless": ("none", "happy", "flower", "plain", None),
}
# 對照組：不是果蠅選手，但用同一套風格
CONTROLS = {
    "random": ("none", "happy", "dice", "plain", None),
    "buyhold": ("cap", "sleepy", "cane", "plain", "beard"),
    "momentum": ("headband", "shades", "arrow", "plain", "motion"),
}
# 沒有對應基因時，依個性類型決定
TITLES = {
    "長記性": ("none", "glasses", "book", "plain", None),
    "衝動多頭": ("headband", "wide", "arrow", "plain", "motion"),
    "佛系觀望": ("halo", "sleepy", None, "plain", None),
    "學霸": ("grad", "glasses", "book", "plain", None),
    "冷靜保守": ("none", "shades", None, "pale", None),
    "愛冒險": ("adventurer", "happy", None, "plain", None),
    "悲觀空頭": ("none", "sleepy", None, "pale", "rain"),
    "均衡": ("none", "round", None, "plain", None),
}


def _parts(name, profile):
    gene = profile.get("gene")
    if profile.get("control"):
        return CONTROLS.get(name, TITLES["均衡"])
    if gene in GENES:
        return GENES[gene]
    return TITLES.get(profile.get("title"), TITLES["均衡"])


def _eyes(kind, colour):
    """大眼睛：眼白 + 虹膜 + 兩點高光。"""
    white = '<ellipse cx="{x}" cy="43" rx="10.5" ry="11.5" fill="#fffdf8"/>'
    out = []
    for x, side in ((39, -1), (61, 1)):
        out.append(white.format(x=x))
        if kind == "bar":
            out.append(f'<rect x="{x - 2.4}" y="33.5" width="4.8" height="19" rx="2.4" fill="{colour}"/>')
        elif kind == "sleepy":
            out.append(f'<path d="M{x - 9} 44 q9 7 18 0" fill="none" stroke="{DARK}" stroke-width="2.6" stroke-linecap="round"/>')
            continue
        elif kind == "pale":
            out.append(f'<circle cx="{x}" cy="44" r="6.5" fill="#e6e2da"/>')
        else:
            r = 8 if kind == "wide" else 7
            out.append(f'<circle cx="{x}" cy="44" r="{r}" fill="{colour}"/>')
            out.append(f'<circle cx="{x}" cy="44" r="{r * 0.45:.1f}" fill="#20242c"/>')
        out.append(f'<circle cx="{x + side * 2.6}" cy="39.5" r="2.6" fill="#ffffff"/>')
        out.append(f'<circle cx="{x - side * 2.8}" cy="48" r="1.4" fill="#ffffff" opacity=".8"/>')
    if kind == "glasses":
        out.append(f'<g fill="none" stroke="{DARK}" stroke-width="2.2"><circle cx="39" cy="43.5" r="13"/>'
                   f'<circle cx="61" cy="43.5" r="13"/><path d="M52 43.5h-4"/><path d="M26 41l-6-3"/><path d="M74 41l6-3"/></g>')
    if kind == "shades":
        out.append(f'<g fill="{DARK}"><rect x="25" y="35" width="24" height="15" rx="6"/>'
                   f'<rect x="51" y="35" width="24" height="15" rx="6"/><rect x="47" y="39" width="6" height="3"/></g>'
                   '<path d="M29 38h10" stroke="#ffffff" stroke-width="2" opacity=".5" stroke-linecap="round"/>')
    return "".join(out)


def _hat(kind, hue):
    if kind == "grad":
        return (f'<g><rect x="36" y="14" width="28" height="7" rx="2" fill="{DARK}"/>'
                f'<polygon points="50,6 78,15 50,24 22,15" fill="{DARK}"/>'
                f'<path d="M74 16v10" stroke="#f2c94c" stroke-width="2"/><circle cx="74" cy="27" r="2.6" fill="#f2c94c"/></g>')
    if kind == "helmet":
        return ('<g><path d="M27 24a23 23 0 0 1 46 0z" fill="#b9c2cc"/><rect x="25" y="22" width="50" height="6" rx="3" fill="#95a1ad"/>'
                '<circle cx="34" cy="25" r="1.8" fill="#6f7b86"/><circle cx="66" cy="25" r="1.8" fill="#6f7b86"/>'
                '<path d="M35 14a17 17 0 0 1 20 2" stroke="#ffffff" stroke-width="2.5" fill="none" opacity=".6" stroke-linecap="round"/></g>')
    if kind == "horns":
        return ('<g><path d="M27 24a23 23 0 0 1 46 0z" fill="#8f7a5f"/>'
                '<path d="M27 22q-12-2-12-12 10 1 14 8z" fill="#f0e6d2"/><path d="M73 22q12-2 12-12-10 1-14 8z" fill="#f0e6d2"/></g>')
    if kind == "cap":
        return ('<g><path d="M26 25q24-16 48-2l-2 4H26z" fill="#6b7a4e"/>'
                '<path d="M20 27q10-6 22-4l-1 5-19 2z" fill="#586640"/></g>')
    if kind == "adventurer":
        return ('<g><ellipse cx="50" cy="25" rx="30" ry="6" fill="#8a6234"/>'
                '<path d="M31 25q4-18 19-18t19 18z" fill="#a3743f"/><rect x="29" y="21" width="42" height="5" rx="2.5" fill="#6d4b28"/></g>')
    if kind == "dunce":
        return f'<g><polygon points="50,2 63,26 37,26" fill="hsl({hue},70%,60%)"/><circle cx="50" cy="3" r="3" fill="#f2c94c"/></g>'
    if kind == "headband":
        return ('<g><path d="M26 27q24-10 48 0l-1 6q-23-9-46 0z" fill="#d0342c"/>'
                '<path d="M73 30l13 3-11 6z" fill="#d0342c"/></g>')
    if kind == "halo":
        return '<ellipse cx="50" cy="9" rx="17" ry="5" fill="none" stroke="#f2c94c" stroke-width="3.4"/>'
    if kind == "spikes":  # 沿著頭部輪廓長出來的刺
        spikes = []
        for i in range(11):
            a = math.radians(200 + i * 14)
            bx, by = 50 + 24 * math.cos(a), 45 + 24 * math.sin(a)
            tx, ty = 50 + 36 * math.cos(a), 45 + 36 * math.sin(a)
            nx, ny = -math.sin(a) * 4.5, math.cos(a) * 4.5
            spikes.append(f'<polygon points="{bx + nx:.1f},{by + ny:.1f} {tx:.1f},{ty:.1f} {bx - nx:.1f},{by - ny:.1f}" fill="#8a6a4a"/>')
        return "<g>" + "".join(spikes) + "</g>"
    return ""


def _prop(kind, hue):
    """右手的道具（手臂 + 物品）。"""
    if not kind:
        return ""
    arm = f'<path d="M69 72q10-2 13-9" stroke="{DARK}" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
    items = {
        "bottle": '<g transform="translate(76,52)"><rect x="-5" y="0" width="10" height="17" rx="3" fill="#3f7d4f"/>'
                  '<rect x="-2" y="-6" width="4" height="7" fill="#3f7d4f"/><rect x="-4" y="5" width="8" height="6" fill="#f0e6d2" opacity=".85"/></g>',
        "book": '<g transform="translate(74,52)"><rect x="-8" y="0" width="17" height="14" rx="2" fill="#2f6fdf"/>'
                '<rect x="-5" y="2.5" width="11" height="9" rx="1" fill="#eef3fb"/><path d="M0.5 2.5v9" stroke="#2f6fdf" stroke-width="1.4"/></g>',
        "carrot": '<g transform="translate(78,50)"><polygon points="0,20 -5,2 5,2" fill="#e8762a"/>'
                  '<path d="M-4 2q-2-7 2-8M0 2q0-8 3-9M4 3q2-7 6-6" stroke="#3f7d4f" stroke-width="2.4" fill="none" stroke-linecap="round"/></g>',
        "turnip": '<g transform="translate(78,52)"><path d="M0 18q-8-4-8-10a8 8 0 0 1 16 0q0 6-8 10z" fill="#efe6f2"/>'
                  '<path d="M-7 6q-2-6 3-7M1 4q1-7 6-6" stroke="#5f8f4a" stroke-width="2.2" fill="none" stroke-linecap="round"/></g>',
        "dice": '<g transform="translate(74,50) rotate(12)"><rect x="0" y="0" width="17" height="17" rx="4" fill="#fffdf8" stroke="#cfc7b8"/>'
                '<circle cx="5" cy="5" r="1.8" fill="#d0342c"/><circle cx="12" cy="12" r="1.8" fill="#20242c"/>'
                '<circle cx="12" cy="5" r="1.8" fill="#20242c"/><circle cx="5" cy="12" r="1.8" fill="#20242c"/></g>',
        "cane": '<path d="M80 50q7 0 7 7v22" stroke="#8a6234" stroke-width="3.6" fill="none" stroke-linecap="round"/>',
        "clock": '<g transform="translate(76,52)"><circle r="9" cx="4" cy="8" fill="#fffdf8" stroke="#8a6234" stroke-width="2"/>'
                 '<path d="M4 8V3M4 8l4 3" stroke="#20242c" stroke-width="1.8" stroke-linecap="round"/></g>',
        "arrow": '<g transform="translate(72,46)"><path d="M0 20L8 8l5 6 7-12" stroke="#d0342c" stroke-width="3.2" fill="none" '
                 'stroke-linecap="round" stroke-linejoin="round"/><path d="M14 2h7v7" stroke="#d0342c" stroke-width="3.2" fill="none" '
                 'stroke-linecap="round" stroke-linejoin="round"/></g>',
        "flower": f'<g transform="translate(78,52)"><path d="M0 18V8" stroke="#5f8f4a" stroke-width="2.4"/>'
                  f'<circle cx="0" cy="4" r="4" fill="hsl({hue},75%,65%)"/><circle cx="-5" cy="7" r="3.4" fill="hsl({hue},75%,72%)"/>'
                  f'<circle cx="5" cy="7" r="3.4" fill="hsl({hue},75%,72%)"/><circle cx="0" cy="6" r="2" fill="#f2c94c"/></g>',
    }
    return arm + items.get(kind, "")


def _extra(kind, hue, body):
    if kind == "blush":
        return ('<ellipse cx="30" cy="53" rx="5" ry="3.2" fill="#e8737d" opacity=".5"/>'
                '<ellipse cx="70" cy="53" rx="5" ry="3.2" fill="#e8737d" opacity=".5"/>')
    if kind == "holes":
        return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#d0a52c" opacity=".9"/>'
                       for x, y, r in ((39, 77, 3.4), (57, 73, 2.6), (49, 85, 3), (63, 82, 2.2)))
    if kind == "motion":
        return ('<g stroke="#6b7280" stroke-width="2.6" stroke-linecap="round" opacity=".85">'
                '<path d="M12 46h7M10 56h7M14 66h6"/><path d="M88 46h-7M90 56h-7M86 66h-6"/></g>')
    if kind == "question":
        return (f'<g fill="hsl({hue},60%,45%)" font-family="system-ui" font-size="14" font-weight="700">'
                '<text x="14" y="26">?</text><text x="80" y="20" font-size="11">?</text></g>')
    if kind == "beard":
        return ('<path d="M40 62q10 12 20 0q-3 12-10 12t-10-12z" fill="#f2efe8"/>'
                '<path d="M50 58q-4-4-9-1M50 58q4-4 9-1" stroke="#e8e3da" stroke-width="3.4" fill="none" stroke-linecap="round"/>')

    if kind == "rain":
        return ('<g><ellipse cx="50" cy="12" rx="20" ry="8" fill="#b9c2cc"/><ellipse cx="38" cy="14" rx="10" ry="6" fill="#cdd5dd"/>'
                '<g stroke="#6f9cff" stroke-width="2.4" stroke-linecap="round"><path d="M40 21v5M50 22v6M60 21v5"/></g></g>')
    if kind == "notch":
        return '<path d="M78 46l7-4 1 7z" fill="#fdfcfa"/>'
    if kind == "curly":
        return ''  # 觸角本身改成捲的，在 _antennae 處理
    return ""


def _antennae(curly):
    if curly:
        return (f'<g fill="none" stroke="{DARK}" stroke-width="2.6" stroke-linecap="round">'
                '<path d="M40 22q-6-10-13-8a5 5 0 0 0 4 8"/><path d="M60 22q6-10 13-8a5 5 0 0 1-4 8"/></g>')
    return (f'<g stroke="{DARK}" stroke-width="2.6" stroke-linecap="round" fill="none">'
            '<path d="M41 21q-5-11-12-13"/><path d="M59 21q5-11 12-13"/></g>'
            f'<circle cx="28" cy="7" r="3.4" fill="{DARK}"/><circle cx="72" cy="7" r="3.4" fill="{DARK}"/>')


def fly_svg(name, profile):
    digest = hashlib.sha256(name.encode()).hexdigest()
    hue = int(digest, 16) % 360
    uid = digest[:6]  # 同一個網頁放多張時，漸層代號不能重複
    hat, eyes, prop, body, extra = _parts(name, profile)
    main, shade = BODY[body]
    eye_colour = f"hsl({(hue + 150) % 360},72%,42%)"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="256" height="256">'
        f'<defs><linearGradient id="bg{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue},78%,92%)"/><stop offset="1" stop-color="hsl({hue},58%,74%)"/></linearGradient>'
        f'<linearGradient id="wing{uid}" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#ffffff" stop-opacity=".92"/><stop offset="1" stop-color="#a8cbe8" stop-opacity=".78"/></linearGradient></defs>'
        f'<rect width="100" height="100" rx="14" fill="url(#bg{uid})"/>'
        # 翅膀（在身體後面）
        f'<g stroke="#7fa9cc" stroke-width="1.1" opacity=".95">'
        f'<ellipse cx="22" cy="60" rx="19" ry="10" fill="url(#wing{uid})" transform="rotate(-26 22 60)"/>'
        f'<ellipse cx="78" cy="60" rx="19" ry="10" fill="url(#wing{uid})" transform="rotate(26 78 60)"/></g>'
        # 腳
        f'<g stroke="{DARK}" stroke-width="3" stroke-linecap="round">'
        '<path d="M38 86l-6 8"/><path d="M50 88v8"/><path d="M62 86l6 8"/></g>'
        # 肚子
        f'<ellipse cx="50" cy="74" rx="22" ry="19" fill="{main}"/>'
        f'<path d="M30 79q20 9 40 0" stroke="{shade}" stroke-width="4" fill="none" stroke-linecap="round"/>'
        + _extra("holes" if extra == "holes" else "", hue, body) +
        # 頭
        f'<circle cx="50" cy="45" r="25" fill="{main}"/>'
        + _antennae(extra == "curly")
        + _eyes(eyes, eye_colour)
        # 嘴巴
        + (f'<path d="M45 60q5 5 10 0" stroke="{DARK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
           if eyes in ("happy", "wide") else
           f'<path d="M46 60q4 3 8 0" stroke="{DARK}" stroke-width="2.2" fill="none" stroke-linecap="round"/>')
        + _extra(extra if extra != "holes" else "", hue, body)
        + _hat(hat, hue)
        + _prop(prop, hue)
        + "</svg>"
    )


def resolve(name, profile, out_dir):
    """產生或複製頭像到 out_dir/avatars/，回傳網頁用的相對路徑。"""
    folder = Path(out_dir) / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    custom = profile.get("avatar")
    if custom:
        src = CUSTOM / custom
        if src.is_file():
            dst = folder / f"{name}{src.suffix.lower()}"
            shutil.copyfile(src, dst)
            return f"avatars/{dst.name}"
        print(f"找不到 {name} 的自訂頭像 avatars/{custom}，改用自動生成")
    (folder / f"{name}.svg").write_text(fly_svg(name, profile), encoding="utf-8")
    return f"avatars/{name}.svg"
