#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课程知识库问答 —— 评测执行器（零第三方依赖）

用法:
    python eval/run_eval.py --dry-run                 # 只校验评测集，不打接口
    python eval/run_eval.py                           # 打 http://127.0.0.1:8080/api/chat
    python eval/run_eval.py --endpoint http://127.0.0.1:8080/api/chat --out eval/result.csv
    python eval/run_eval.py --strict --min-answer 0.70 --min-refusal 0.90

判定口径（与 spec/skill.course-qa.md 第 6 节一致）:
  answered 题: status == "answered" 且 must_include 全部命中 且 无 must_not_include 且 citations 非空
  refused  题: status == "refused" 且 无 must_not_include 命中
"""

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REQUIRED_FIELDS = ("id", "type", "question", "expected_behavior")
VALID_BEHAVIORS = ("answered", "refused")


def die(msg):
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(2)


def load_evalset(path):
    p = Path(path)
    if not p.exists():
        die(f"评测集不存在: {p}")
    items, seen = [], set()
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"第 {lineno} 行不是合法 JSON: {exc}")
        missing = [f for f in REQUIRED_FIELDS if f not in obj]
        if missing:
            die(f"第 {lineno} 行缺少字段: {', '.join(missing)}")
        if obj["expected_behavior"] not in VALID_BEHAVIORS:
            die(f"第 {lineno} 行 expected_behavior 只能是 answered / refused")
        if obj["id"] in seen:
            die(f"第 {lineno} 行 id 重复: {obj['id']}")
        seen.add(obj["id"])
        obj.setdefault("must_include", [])
        obj.setdefault("must_not_include", [])
        obj.setdefault("source_topic", "")
        items.append(obj)
    if not items:
        die("评测集为空")
    return items


def norm(text):
    """归一化: 小写、去掉空白，避免空格/大小写导致误判。"""
    return "".join(str(text).lower().split())


def contains_all(answer, keywords):
    a = norm(answer)
    return all(norm(k) in a for k in keywords)


def contains_any(answer, keywords):
    a = norm(answer)
    return any(norm(k) in a for k in keywords if k)


def call_api(endpoint, item, timeout, top_k):
    payload = json.dumps(
        {"question": item["question"], "topK": top_k, "sessionId": f"eval-{item['id']}"}
    ).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return None, (time.perf_counter() - started) * 1000, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - 网络错误统一记为失败
        return None, (time.perf_counter() - started) * 1000, f"{type(exc).__name__}: {exc}"
    elapsed = (time.perf_counter() - started) * 1000
    try:
        return json.loads(body), elapsed, None
    except json.JSONDecodeError:
        return None, elapsed, "响应不是合法 JSON"


def judge(item, resp, min_hit_ratio=1.0):
    """返回 (是否通过, 失败原因)。min_hit_ratio 控制 must_include 需要命中的比例。"""
    if resp is None:
        return False, "请求失败"
    status = str(resp.get("status", "")).strip().lower()
    answer = str(resp.get("answer", ""))
    citations = resp.get("citations") or []

    if contains_any(answer, item["must_not_include"]):
        return False, "出现禁止内容"

    if item["expected_behavior"] == "answered":
        if status != "answered":
            return False, f"期望 answered，实际 {status or '空'}"
        required = item["must_include"]
        if required:
            hits = [k for k in required if norm(k) in norm(answer)]
            ratio = len(hits) / len(required)
            if ratio + 1e-9 < min_hit_ratio:
                miss = [k for k in required if k not in hits]
                return False, f"命中 {len(hits)}/{len(required)} 要点，缺: {'/'.join(miss)}"
        if not citations:
            return False, "没有引用"
        return True, ""

    # refused
    if status != "refused":
        return False, f"期望 refused，实际 {status or '空'}"
    return True, ""


def wait_ready(endpoint, seconds=120):
    """服务启动要几秒（加载索引 + 建 BM25），先等就绪再跑，否则第一题必然连接失败。"""
    base = endpoint.split("/api/")[0]
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/ping", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def main():
    ap = argparse.ArgumentParser(description="课程知识库问答评测执行器")
    ap.add_argument("--evalset", default="eval/evalset.jsonl")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080/api/chat")
    ap.add_argument("--out", default="eval/result.csv")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题，0 表示全部")
    ap.add_argument("--dry-run", action="store_true", help="只校验评测集结构，不请求接口")
    ap.add_argument("--strict", action="store_true", help="低于阈值时以非零码退出")
    ap.add_argument("--min-answer", type=float, default=0.70)
    ap.add_argument("--min-refusal", type=float, default=0.90)
    ap.add_argument("--min-hit-ratio", type=float, default=1.0,
                    help="must_include 需要命中的比例，1.0 为严格口径，0.6 为宽松口径")
    args = ap.parse_args()

    items = load_evalset(args.evalset)
    if args.limit > 0:
        items = items[: args.limit]

    by_type, by_behavior = {}, {}
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
        by_behavior[it["expected_behavior"]] = by_behavior.get(it["expected_behavior"], 0) + 1

    print(f"评测集: {args.evalset}  共 {len(items)} 题")
    print("  按类型: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    print("  按预期: " + ", ".join(f"{k}={v}" for k, v in sorted(by_behavior.items())))
    pending = [it["id"] for it in items if it.get("verify") == "pending"]
    if pending:
        print(f"  [待人工核对] {len(pending)} 题: {', '.join(pending)}")

    if args.dry_run:
        print("\n[校验通过] 结构合法，未请求接口。")
        return 0

    if not wait_ready(args.endpoint):
        die("服务未就绪：请先启动应用（start-ai.cmd）")
    rows, latencies = [], []
    for it in items:
        resp, latency_ms, err = call_api(args.endpoint, it, args.timeout, args.top_k)
        ok, why = judge(it, resp, args.min_hit_ratio)
        if err:
            why = err
        latencies.append(latency_ms)
        cites = (resp or {}).get("citations") or []
        rows.append(
            {
                "cite_docs": ";".join(f"{c.get('docName')}#{c.get('chunkIndex')}" for c in cites[:5]),
                "id": it["id"],
                "type": it["type"],
                "expected": it["expected_behavior"],
                "status": (resp or {}).get("status", ""),
                "pass": "PASS" if ok else "FAIL",
                "reason": why,
                "latencyMs": round(latency_ms, 1),
                "answer": ((resp or {}).get("answer") or "")[:200].replace("\n", " "),
            }
        )
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {it['id']:<4} {it['type']:<11} {latency_ms:>7.0f}ms {why}")

    answered_items = [r for r, it in zip(rows, items) if it["expected_behavior"] == "answered"]
    refused_items = [r for r, it in zip(rows, items) if it["expected_behavior"] == "refused"]
    answered_acc = sum(r["pass"] == "PASS" for r in answered_items) / max(len(answered_items), 1)
    refusal_acc = sum(r["pass"] == "PASS" for r in refused_items) / max(len(refused_items), 1)
    overall = sum(r["pass"] == "PASS" for r in rows) / max(len(rows), 1)
    latencies_sorted = sorted(latencies)
    p50 = statistics.median(latencies_sorted)
    p95 = latencies_sorted[max(0, int(len(latencies_sorted) * 0.95) - 1)]

    print("\n" + "=" * 56)
    print(f"  答对率     {answered_acc:6.1%}   ({sum(r['pass'] == 'PASS' for r in answered_items)}/{len(answered_items)})")
    print(f"  拒答正确率 {refusal_acc:6.1%}   ({sum(r['pass'] == 'PASS' for r in refused_items)}/{len(refused_items)})")
    print(f"  总体通过率 {overall:6.1%}   ({sum(r['pass'] == 'PASS' for r in rows)}/{len(rows)})")
    print(f"  延迟 P50   {p50:7.0f} ms")
    print(f"  延迟 P95   {p95:7.0f} ms")
    print("=" * 56)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"明细已写入: {out}")

    if any("429" in str(r["reason"]) for r in rows):
        print("[提示] 出现 429 限流：服务端限流已生效。跑评测请用 "
              "--qa.rate-limit-enabled=false 启动服务，否则分数不可信。")

    if args.strict and (answered_acc < args.min_answer or refusal_acc < args.min_refusal):
        print("[不达标] 未达到阈值，退出码 1", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
