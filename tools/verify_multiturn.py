"""多轮对话验证：同一追问，在「有历史」与「无历史」两种会话下的对照。

每个用例先问一个完整问题建立上下文，再问一个依赖指代的追问；
然后把同一句追问放到一个全新会话里再问一次，比较两者的检索与回答。

用法：服务启动后 python tools/verify_multiturn.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"

CASES = [
    {
        "name": "指代消解（这些数据）",
        "first": "碳交易市场的数据来源有哪些？",
        "follow": "这些数据主要用来做什么？",
        "expect": ["碳", "数据", "监测", "交易", "配额"],
    },
    {
        "name": "指代消解（它 vs 对比对象）",
        "first": "在中国碳交易制度中，TPS 是什么？",
        "follow": "它和 C&T 有什么区别？",
        "expect": ["TPS", "C&T", "总量", "强度"],
    },
    {
        "name": "省略主语（物联网在其中）",
        "first": "能源大数据的关键技术包括哪些？",
        "follow": "物联网在其中起什么作用？",
        "expect": ["物联网", "传感", "感知", "设备"],
    },
]


def ask(question, session_id, top_k=5, timeout=180):
    payload = json.dumps({"question": question, "sessionId": session_id, "topK": top_k}).encode()
    req = urllib.request.Request(BASE + "/api/chat", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data, (time.perf_counter() - t0) * 1000


def wait_ready(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/ping", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def hit_ratio(answer, keys):
    a = answer or ""
    hits = [k for k in keys if k.lower() in a.lower()]
    return len(hits) / len(keys), hits


def main():
    if not wait_ready():
        print("服务未就绪")
        return 2

    ok = 0
    for idx, case in enumerate(CASES, 1):
        sid = f"mt-test-{idx}-{int(time.time())}"
        print(f"\n=== 用例 {idx}：{case['name']} ===")

        d1, ms1 = ask(case["first"], sid)
        print(f"[第 1 轮] {case['first']}")
        print(f"   status={d1['status']} 引用={len(d1['citations'])} 耗时={ms1:.0f}ms")
        print(f"   A: {(d1.get('answer') or '')[:110]}")

        d2, ms2 = ask(case["follow"], sid)
        r_with, hits_with = hit_ratio(d2.get("answer"), case["expect"])
        print(f"[第 2 轮·有历史] {case['follow']}")
        print(f"   status={d2['status']} 引用={len(d2['citations'])} 耗时={ms2:.0f}ms 命中={r_with:.0%} {hits_with}")
        print(f"   A: {(d2.get('answer') or '')[:150]}")
        if d2["citations"]:
            top = d2["citations"][0]
            print(f"   首条引用: 《{top['docName']}》第{top['chunkIndex']}块 score={top['score']}")

        fresh = f"mt-fresh-{idx}-{int(time.time())}"
        d3, ms3 = ask(case["follow"], fresh)
        r_wo, hits_wo = hit_ratio(d3.get("answer"), case["expect"])
        print(f"[第 2 轮·无历史] {case['follow']}")
        print(f"   status={d3['status']} 引用={len(d3['citations'])} 耗时={ms3:.0f}ms 命中={r_wo:.0%} {hits_wo}")
        print(f"   A: {(d3.get('answer') or '')[:150]}")

        better = r_with > r_wo or (d2["status"] == "answered" and d3["status"] == "refused")
        ok += better
        print(f"   >>> 多轮{'更优' if better else '无差异/更差'}（命中 {r_with:.0%} vs {r_wo:.0%}）")

    print(f"\n结论：{ok}/{len(CASES)} 个用例在带历史时表现更好")
    return 0 if ok >= len(CASES) - 1 else 1


if __name__ == "__main__":
    sys.exit(main())
