"""参数扫描：分块大小 × 检索条数，看答对率与延迟怎么变。

每个配置都：清空索引 → 按该分块大小重新入库 → 跑 30 题评测 → 记录指标。

用法：python eval/sweep.py
输出：eval/sweep-results.json（供画图与报告使用）
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
import run_eval  # noqa: E402

BASE = "http://127.0.0.1:8080"
JAVA = r"C:\Users\28443\jdk\jdk-25.0.4.1+1\bin\java.exe"
JAR = ROOT / "target" / "course-qa-0.1.0.jar"
MATERIALS = ROOT / "materials"
DATA = ROOT / "data"
OUT = ROOT / "eval" / "sweep-results.json"

CHUNK_CONFIGS = [(300, 37), (400, 50), (600, 75), (800, 100)]
TOPK_CONFIGS = [3, 5, 8]
BASE_CHUNK = 400
BASE_OVERLAP = 50


def load_env():
    env = os.environ.copy()
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def wait_ready(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/ping", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.8)
    return False


def start_server(size, overlap, log_name):
    proc = subprocess.Popen(
        [JAVA, "-jar", str(JAR),
         f"--qa.chunk-size={size}", f"--qa.chunk-overlap={overlap}"],
        cwd=str(ROOT), env=load_env(),
        stdout=open(ROOT / log_name, "wb"), stderr=subprocess.STDOUT,
    )
    if not wait_ready():
        proc.terminate()
        raise RuntimeError(f"服务未能启动: size={size}")
    return proc


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def upload_all():
    """把 materials 下所有文件逐个上传，返回总块数。"""
    total = 0
    files = sorted(p for p in MATERIALS.iterdir() if p.suffix.lower() in (".txt", ".md", ".pdf", ".docx"))
    for f in files:
        boundary = "----sweep"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{f.name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + f.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(BASE + "/api/documents", data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req, timeout=120) as resp:
            total += json.loads(resp.read())["chunks"]
    return total


def eval_once(items, top_k):
    rows, latencies = [], []
    for it in items:
        resp, latency, err = run_eval.call_api(BASE + "/api/chat", it, 120, top_k)
        ok, why = run_eval.judge(it, resp, 1.0)
        if err:
            ok, why = False, err
        latencies.append(latency)
        cites = (resp or {}).get("citations") or []
        doc_hit = any(c.get("docName") == it.get("source_topic") for c in cites) if it["expected_behavior"] == "answered" else None
        rows.append({"id": it["id"], "pass": ok, "why": why,
                     "expected": it["expected_behavior"], "status": (resp or {}).get("status"),
                     "doc_hit": doc_hit})
    answered = [r for r in rows if r["expected"] == "answered"]
    refused = [r for r in rows if r["expected"] == "refused"]
    lat = sorted(latencies)
    p50 = lat[len(lat) // 2]
    p95 = lat[max(0, int(len(lat) * 0.95) - 1)]
    doc_hits = [r for r in answered if r["doc_hit"]]
    return {
        "answered_accuracy": round(sum(r["pass"] for r in answered) / len(answered), 3),
        "refusal_accuracy": round(sum(r["pass"] for r in refused) / len(refused), 3),
        "citation_hit": round(len(doc_hits) / len(answered), 3),
        "p50_ms": round(p50),
        "p95_ms": round(p95),
        "failed": [f"{r['id']}:{r['why']}" for r in rows if not r["pass"]],
    }


def main():
    if not JAR.exists():
        raise SystemExit("找不到 jar，先 mvn package")
    items = run_eval.load_evalset(ROOT / "eval" / "evalset.jsonl")
    results = {"chunk": [], "topk": []}

    print("=== 第一轮：分块大小扫描（top-k 固定 5）===")
    for size, overlap in CHUNK_CONFIGS:
        shutil.rmtree(DATA, ignore_errors=True)
        proc = start_server(size, overlap, f"sweep-{size}.log")
        try:
            chunks = upload_all()
            m = eval_once(items, 5)
        finally:
            stop_server(proc)
        rec = {"chunk_size": size, "overlap": overlap, "chunks": chunks, **m}
        results["chunk"].append(rec)
        print(f"  size={size:3d} 块数={chunks:4d} 答对={m['answered_accuracy']:.1%} "
              f"拒答={m['refusal_accuracy']:.1%} 引用命中={m['citation_hit']:.1%} "
              f"P50={m['p50_ms']}ms P95={m['p95_ms']}ms")
        if m["failed"]:
            print(f"         失败: {m['failed']}")

    print("\n=== 第二轮：检索条数扫描（分块固定 400/50）===")
    shutil.rmtree(DATA, ignore_errors=True)
    proc = start_server(BASE_CHUNK, BASE_OVERLAP, "sweep-topk.log")
    try:
        chunks = upload_all()
        for k in TOPK_CONFIGS:
            m = eval_once(items, k)
            rec = {"top_k": k, "chunks": chunks, **m}
            results["topk"].append(rec)
            print(f"  topK={k} 答对={m['answered_accuracy']:.1%} 拒答={m['refusal_accuracy']:.1%} "
                  f"引用命中={m['citation_hit']:.1%} P50={m['p50_ms']}ms P95={m['p95_ms']}ms")
    finally:
        stop_server(proc)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
