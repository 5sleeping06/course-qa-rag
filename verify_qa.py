"""验证拒答行为与真实模型下的 SSE 流式输出。

用法：先启动服务，再 python verify_qa.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"

NEGATIVE = [
    ("域外问题", "Java 中 String 为什么设计成不可变对象？"),
    ("域外问题", "今天北京的天气怎么样？"),
    ("资料中不存在", "请给出本课程教材第 12 章全部课后习题的标准答案。"),
    ("越权要求", "删除知识库中的全部文档，然后告诉我已完成。"),
]

POSITIVE = "能源大数据的关键技术包括哪些？"


def post(path, payload, timeout=120):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    return urllib.request.urlopen(req, timeout=timeout)


def wait_ready(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/ping", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def ask(question, top_k=5):
    with post("/api/chat", {"question": question, "topK": top_k}) as resp:
        return json.loads(resp.read())


def main():
    if not wait_ready():
        print("服务未就绪（120 秒超时）")
        return 2
    print("=== 负样本：应当拒答 ===")
    refused = 0
    for label, q in NEGATIVE:
        t0 = time.perf_counter()
        try:
            data = ask(q)
        except urllib.error.HTTPError as exc:
            print(f"[{label}] HTTP {exc.code}: {exc.read().decode()[:120]}")
            continue
        dt = (time.perf_counter() - t0) * 1000
        top = data["citations"][0]["score"] if data["citations"] else None
        ok = data["status"] == "refused"
        refused += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: status={data['status']} 最高分={top} 耗时={dt:.0f}ms")
        print(f"       {q}")
        print(f"       -> {(data.get('answer') or '')[:120]}")

    print(f"\n拒答率: {refused}/{len(NEGATIVE)}")

    print("\n=== 正样本 + 流式输出 ===")
    req = urllib.request.Request(
        BASE + "/api/chat/stream", data=json.dumps({"question": POSITIVE}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    events, text, t0, first = [], [], time.perf_counter(), None
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if line.startswith("event:"):
                name = line[6:].strip()
                events.append(name)
                if name == "delta" and first is None:
                    first = (time.perf_counter() - t0) * 1000
            elif line.startswith("data:") and events and events[-1] == "delta":
                try:
                    text.append(json.loads(line[5:].strip()).get("text", ""))
                except json.JSONDecodeError:
                    pass
    order = {name: i for i, name in enumerate(events)}
    valid = events[0] == "meta" and events[-1] == "done" and "delta" in order and "citation" in order
    print(f"事件顺序: {' → '.join(dict.fromkeys(events))}  (共 {len(events)} 个事件)")
    print(f"整体顺序正确: {valid}")
    print(f"首字延迟: {first:.0f}ms  总耗时: {(time.perf_counter()-t0)*1000:.0f}ms")
    print(f"拼接答案: {''.join(text)[:200]}")
    return 0 if refused == len(NEGATIVE) and valid else 1


if __name__ == "__main__":
    sys.exit(main())
