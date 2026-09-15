"""果蠅存檔：<資料夾>/brains/<名字>.npz（接線、權重）＋ roster.json（參數與族譜）。
不使用 pickle，存檔可以安全地分享。"""

import json
from pathlib import Path

import numpy as np

from .brains import from_state


def save_brains(folder, entries):
    """entries：[(名字, 大腦, meta dict), ...]"""
    folder = Path(folder)
    (folder / "brains").mkdir(parents=True, exist_ok=True)
    roster = []
    for name, brain, meta in entries:
        state = brain.state()
        arrays = {k: v for k, v in state.items() if isinstance(v, np.ndarray)}
        rest = {k: v for k, v in state.items() if not isinstance(v, np.ndarray)}
        if arrays:
            np.savez_compressed(folder / "brains" / f"{name}.npz", **arrays)
        roster.append({"name": name, "state": rest, "arrays": sorted(arrays), "meta": meta})
    (folder / "roster.json").write_text(
        json.dumps(roster, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_brains(folder):
    folder = Path(folder)
    roster = json.loads((folder / "roster.json").read_text(encoding="utf-8"))
    out = []
    for r in roster:
        state = dict(r["state"])
        if r["arrays"]:
            with np.load(folder / "brains" / f"{r['name']}.npz", allow_pickle=False) as a:
                state.update({k: a[k] for k in r["arrays"]})
        out.append((r["name"], from_state(state), r["meta"]))
    return out
