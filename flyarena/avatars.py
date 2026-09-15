"""果蠅頭像：16×16 像素風 SVG，依個性自動配色、加配件。
想換成自己的圖：把圖片放進專案的 avatars/ 資料夾，並在 profiles.json 的 avatar 填檔名。"""

import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUSTOM = ROOT / "avatars"

SPRITE = [
    "......A..A......",
    ".......AA.......",
    ".....EHHHHE.....",
    "....EEHHHHEE....",
    ".....HHHHHH.....",
    "..WW.LBBBBL.WW..",
    ".WWWWBBBBBBWWWW.",
    "WWWWWBSSSSBWWWWW",
    "WWWWWBBBBBBWWWWW",
    ".WWWWBSSSSBWWWW.",
    "..WWLBBBBBBLWW..",
    "....LBSSSSBL....",
    "...L.BBBBBB.L...",
    "......BBBB......",
    ".......BB.......",
    "................",
]


def _box(r0, c0, r1, c1):
    return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
            if r in (r0, r1) or c in (c0, c1)]


ACCESSORIES = {
    "長記性": [("#1d1d1f", _box(1, 3, 4, 6) + _box(1, 9, 4, 12) + [(2, 7), (2, 8)])],
    "衝動多頭": [("#f08c00", [(14, 6), (14, 9), (15, 6), (15, 9)]), ("#ffd43b", [(15, 7), (15, 8)])],
    "佛系觀望": [("#f2c94c", [(0, c) for c in range(4, 12)])],
    "悲觀空頭": [("#4dabf7", [(1, 13), (2, 13), (2, 14), (3, 13)])],
    "冷靜保守": [("#364fc7", [(5, 6), (5, 9)]), ("#1c2b7a", [(5, 7), (5, 8)])],
    "學霸": [("#212529", [(0, c) for c in range(5, 11)] + [(1, c) for c in range(6, 10)]),
             ("#f2c94c", [(1, 10), (2, 11)])],
    "愛冒險": [("#e03131", [(4, c) for c in range(5, 11)])],
}


def fly_svg(name, profile):
    hue = int(hashlib.sha256(name.encode()).hexdigest(), 16) % 360
    nickname = profile.get("nickname", "")
    lean = (profile.get("traits") or {}).get("多空傾向", 0)
    body, head = f"hsl({hue},38%,40%)", f"hsl({hue},38%,54%)"
    if nickname.startswith("小黃"):
        body, head = "hsl(46,75%,50%)", "hsl(46,80%,62%)"
    elif nickname.startswith("烏木"):
        body, head = "hsl(30,10%,18%)", "hsl(30,10%,30%)"
    stripe = "#d0342c" if lean > 0.15 else "#16875a" if lean < -0.1 else f"hsl({hue},38%,26%)"
    colors = {
        "A": "#2b2b2b", "L": "#2b2b2b", "H": head, "B": body, "S": stripe,
        "E": "#ecece6" if nickname.startswith("小白") else "#e03131", "W": "#b9d3e8",
    }
    pixels = {}
    for r, row in enumerate(SPRITE):
        for c, ch in enumerate(row):
            if ch != ".":
                pixels[(r, c)] = ch
    rects = []
    for (r, c), ch in pixels.items():
        opacity = ' fill-opacity=".6"' if ch == "W" else ""
        rects.append(f'<rect x="{c}" y="{r}" width="1" height="1" fill="{colors[ch]}"{opacity}/>')
    for color, cells in ACCESSORIES.get(profile.get("title", ""), []):
        rects += [f'<rect x="{c}" y="{r}" width="1" height="1" fill="{color}"/>' for r, c in cells]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">'
            + "".join(rects) + "</svg>")


def badge_svg(emoji):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
            '<rect x="0.5" y="0.5" width="15" height="15" rx="3" fill="#e9e8e2"/>'
            f'<text x="8" y="12" font-size="10" text-anchor="middle">{emoji}</text></svg>')


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
    svg = badge_svg(profile.get("emoji", "📋")) if profile.get("control") else fly_svg(name, profile)
    (folder / f"{name}.svg").write_text(svg, encoding="utf-8")
    return f"avatars/{name}.svg"
