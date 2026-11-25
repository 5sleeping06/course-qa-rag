"""压测结果图：服务端能力 / 端到端 / 限流。

输出：eval/charts/load.png
"""

import json
from pathlib import Path

from chartkit import canvas, panel, px

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "eval" / "load-results.json").read_text(encoding="utf-8"))
OUT = ROOT / "eval" / "charts" / "load.png"
OUT.parent.mkdir(parents=True, exist_ok=True)


def main():
    img, draw = canvas(1400, 900)
    a = DATA["server_only"]
    b = DATA["end_to_end"]
    c = DATA["rate_limit"]

    conc_a = [f"{r['concurrency']}" for r in a]
    panel(draw, (20, 10, 690, 430), "服务端纯能力：吞吐（QPS）", conc_a,
          [r["qps"] for r in a], fmt="{:.0f}", color=(94, 143, 240), bars=True)
    panel(draw, (710, 10, 1380, 430), "服务端纯能力：P95 延迟（毫秒）", conc_a,
          [r["p95"] for r in a], fmt="{:.0f}", color=(232, 122, 65))

    conc_b = [f"{r['concurrency']}" for r in b]
    panel(draw, (20, 460, 690, 880), "端到端：吞吐（QPS）", conc_b,
          [r["qps"] for r in b], fmt="{:.2f}", color=(47, 158, 111))
    panel(draw, (710, 460, 1380, 880), "端到端：P95 延迟（毫秒）", conc_b,
          [r["p95"] for r in b], fmt="{:.0f}", color=(150, 92, 200))

    img.save(OUT)
    print(f"已生成 {OUT} ({img.size[0]}x{img.size[1]})")

    # 限流单图
    img2, draw2 = canvas(700, 430)
    panel(draw2, (10, 10, 690, 420), "限流验证：40 次突发请求（30 次/分）", ["成功", "被限流 429"],
          [c["ok"], c["rate_limited"]], fmt="{:.0f}", color=(232, 122, 65), bars=True)
    out2 = ROOT / "eval" / "charts" / "ratelimit.png"
    img2.save(out2)
    print(f"已生成 {out2}")


if __name__ == "__main__":
    main()
