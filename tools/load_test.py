"""并发压测：测吞吐、错误率与延迟分位。

三组实验（对应报告「性能需求」一章）：
  A. 服务端纯能力：用域外问题（命中拒答，不调用大模型），排除上游影响
  B. 端到端：真实问题（调用 DeepSeek），看系统在模型耗时下的表现
  C. 限流验证：默认配置（30 次/分）下连续请求，确认 429 生效

用法：
    python tools/load_test.py --concurrency 20 --requests 60 --mode refuse
    python tools/load_test.py --concurrency 5 --requests 20 --mode answer
    python tools/load_test.py --mode ratelimit --requests 40
"""

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"

REFUSE_QUESTIONS = [
    "Java 中 String 为什么设计成不可变对象？",
    "今天北京的天气怎么样？",
    "2026 年世界杯冠军是谁？",
    "请给出本课程教材第 12 章全部课后习题的标准答案。",
]

ANSWER_QUESTIONS = [
    "能源大数据的关键技术包括哪些？",
    "什么是能源大数据管理？",
    "碳交易市场的数据来源有哪些？",
    "企业能源管理系统一般包含哪些功能模块？",
    "资源禀赋的定义是什么？",
    "云计算服务类型按资源抽象层级划分为哪三类？",
]


def one_request(question, results, lock, index):
    payload = json.dumps({"question": question, "topK": 5}).encode()
    req = urllib.request.Request(BASE + "/api/chat", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    status = 0
    err = None
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            status = resp.status
            resp.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        err = exc.read()[:120].decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    cost = (time.perf_counter() - t0) * 1000
    with lock:
        results.append({"status": status, "ms": cost, "err": err})


def run(concurrency, total, mode):
    pool = REFUSE_QUESTIONS if mode == "refuse" else ANSWER_QUESTIONS
    results, lock = [], threading.Lock()
    counter = {"n": 0}
    idx_lock = threading.Lock()

    def worker():
        while True:
            with idx_lock:
                if counter["n"] >= total:
                    return
                i = counter["n"]
                counter["n"] += 1
            one_request(pool[i % len(pool)], results, lock, i)

    started = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - started

    lat = sorted(r["ms"] for r in results)
    ok = [r for r in results if r["status"] == 200]
    too_many = [r for r in results if r["status"] == 429]
    failed = [r for r in results if r["status"] not in (200, 429)]
    p = lambda q: lat[min(len(lat) - 1, int(len(lat) * q))]  # noqa: E731
    return {
        "concurrency": concurrency,
        "requests": len(results),
        "seconds": round(elapsed, 2),
        "qps": round(len(results) / elapsed, 2),
        "ok": len(ok),
        "rate_limited": len(too_many),
        "failed": len(failed),
        "error_rate": round(len(failed) / max(len(results), 1) * 100, 1),
        "p50": round(p(0.50)),
        "p95": round(p(0.95)),
        "p99": round(p(0.99)),
        "errors": [r["err"] for r in failed[:3]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--requests", type=int, default=30)
    ap.add_argument("--mode", choices=["refuse", "answer", "ratelimit"], default="answer")
    args = ap.parse_args()

    if args.mode == "ratelimit":
        out = run(1, args.requests, "answer")
    else:
        out = run(args.concurrency, args.requests, args.mode)

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
