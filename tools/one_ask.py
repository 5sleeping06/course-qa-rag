"""单次提问并打印运行模式（从 SSE 的 meta 事件读取），用于对照两种启动方式。

用法：python tools/one_ask.py "问题"
"""

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8080"
QUESTION = sys.argv[1] if len(sys.argv) > 1 else "能源大数据的关键技术包括哪些？"


def wait_ready(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/ping", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.8)
    return False


def main():
    if not wait_ready():
        print("服务未就绪")
        return 2
    req = urllib.request.Request(
        BASE + "/api/chat/stream", data=json.dumps({"question": QUESTION}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")

    mode = None
    text = []
    t0 = time.perf_counter()
    first = None
    with urllib.request.urlopen(req, timeout=180) as resp:
        last = "message"
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if line.startswith("event:"):
                last = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if last == "meta":
                    mode = data.get("mode")
                    print(f"  模式: {mode}   检索: {data.get('retrieval')}   命中块数: {data.get('retrieved')}")
                elif last == "delta":
                    if first is None:
                        first = (time.perf_counter() - t0) * 1000
                    text.append(data.get("text", ""))
    total = (time.perf_counter() - t0) * 1000
    answer = "".join(text).replace("\n", " ")
    print(f"  首字: {first:.0f}ms  总耗时: {total:.0f}ms")
    print(f"  答案: {answer[:170]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
