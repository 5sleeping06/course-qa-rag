"""压测驱动：自动起停服务，跑完三组实验，结果写入 eval/load-results.json。"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import load_test  # noqa: E402

JAVA = r"C:\Users\28443\jdk\jdk-25.0.4.1+1\bin\java.exe"
JAR = ROOT / "target" / "course-qa-0.1.0.jar"
OUT = ROOT / "eval" / "load-results.json"


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def wait_ready(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(load_test.BASE + "/api/ping", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.8)
    return False


def start(extra_args, log_name):
    env = dict(**__import__("os").environ)
    env.update(load_env())
    proc = subprocess.Popen(
        [JAVA, "-jar", str(JAR)] + extra_args,
        cwd=str(ROOT), env=env,
        stdout=open(ROOT / log_name, "wb"), stderr=subprocess.STDOUT,
    )
    if not wait_ready():
        proc.terminate()
        raise RuntimeError("服务未启动")
    return proc


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    results = {"server_only": [], "end_to_end": [], "rate_limit": None}

    print("=== A. 服务端纯能力（拒答路径，不调用大模型）===")
    # 高阈值让 BM25 一定不返回候选 → 直接拒答，不调用大模型，测出服务端纯能力
    proc = start(["--qa.rate-limit-enabled=false", "--qa.bm25-min-score=100000"], "load-a.log")
    try:
        for conc, n in [(1, 10), (5, 50), (20, 100)]:
            r = load_test.run(conc, n, "refuse")
            results["server_only"].append(r)
            print(f"  并发 {conc:2d}  请求 {n:3d}  QPS={r['qps']:6.1f}  "
                  f"P50={r['p50']}ms P95={r['p95']}ms P99={r['p99']}ms 失败={r['failed']} 限流={r['rate_limited']}")
    finally:
        stop(proc)

    print("\n=== B. 端到端（真实问题，调用 DeepSeek）===")
    proc = start(["--qa.rate-limit-enabled=false"], "load-b.log")
    try:
        for conc, n in [(1, 10), (5, 20), (10, 20)]:
            r = load_test.run(conc, n, "answer")
            results["end_to_end"].append(r)
            print(f"  并发 {conc:2d}  请求 {n:2d}  QPS={r['qps']:5.2f}  "
                  f"P50={r['p50']}ms P95={r['p95']}ms P99={r['p99']}ms "
                  f"失败={r['failed']} 限流={r['rate_limited']}")
            if r["errors"]:
                print(f"       错误样例: {r['errors'][0][:110]}")
    finally:
        stop(proc)

    print("\n=== C. 限流验证（默认 30 次/分，突发并发触发）===")
    proc = start([], "load-c.log")
    try:
        r = load_test.run(10, 40, "answer")
        results["rate_limit"] = r
        print(f"  顺序 40 次请求: 成功={r['ok']} 限流429={r['rate_limited']} "
              f"其他失败={r['failed']} 用时={r['seconds']}s")
    finally:
        stop(proc)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
