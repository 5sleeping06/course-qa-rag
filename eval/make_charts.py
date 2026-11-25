"""参数扫描图（复用 chartkit）。

输出：eval/charts/sweep.png（2×2 面板）
"""

import json
from pathlib import Path

from chartkit import canvas, panel

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "eval" / "sweep-results.json").read_text(encoding="utf-8"))
OUT = ROOT / "eval" / "charts" / "sweep.png"
OUT.parent.mkdir(parents=True, exist_ok=True)


def main():
    img, draw = canvas(1400, 900)
    chunk, topk = DATA["chunk"], DATA["topk"]
    sizes = [c["chunk_size"] for c in chunk]
    ks = [t["top_k"] for t in topk]

    panel(draw, (20, 10, 690, 430), "分块大小 → 索引块数（块）", sizes,
          [c["chunks"] for c in chunk], color=(94, 143, 240), bars=True)
    panel(draw, (710, 10, 1380, 430), "分块大小 → 延迟 P95（毫秒）", sizes,
          [c["p95_ms"] for c in chunk], color=(232, 122, 65))
    panel(draw, (20, 460, 690, 880), "检索条数 → 答对率（%）", ks,
          [t["answered_accuracy"] * 100 for t in topk], fmt="{:.1f}", color=(47, 158, 111))
    panel(draw, (710, 460, 1380, 880), "检索条数 → 延迟 P50（毫秒）", ks,
          [t["p50_ms"] for t in topk], color=(150, 92, 200))

    img.save(OUT)
    print(f"已生成 {OUT} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
