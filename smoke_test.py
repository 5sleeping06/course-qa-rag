"""端到端冒烟测试：ping → 上传 → 同步问答 → 拒答 → 流式问答"""

import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8080"


def call(method, path, data=None, headers=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, body, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), (time.perf_counter() - started) * 1000


def wait_ready(seconds=90):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            code, body, _ = call("GET", "/api/ping", timeout=3)
            if code == 200:
                print(f"[1] 服务就绪: {body.decode()}")
                return True
        except Exception:
            pass
        time.sleep(1.5)
    print("[1] 服务未在时限内启动")
    return False


def upload(path: Path):
    boundary = "----smoke" + uuid.uuid4().hex
    content = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: text/markdown\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    code, resp, _ = call(
        "POST", "/api/documents", body,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    print(f"[2] 上传 {path.name}: HTTP {code} -> {resp.decode()[:200]}")
    return code == 201


def ask(question):
    payload = json.dumps({"question": question}).encode()
    code, resp, ms = call("POST", "/api/chat", payload, {"Content-Type": "application/json"})
    data = json.loads(resp)
    print(f"[3] 问答 HTTP {code} status={data.get('status')} 耗时={ms:.0f}ms")
    print(f"    答案: {data.get('answer', '')[:110]}")
    cites = data.get("citations", [])
    print(f"    引用: {len(cites)} 条" + (f" | 首条: 《{cites[0]['docName']}》第{cites[0]['chunkIndex']}块 score={cites[0]['score']}" if cites else ""))
    return data


def ask_refuse(question):
    payload = json.dumps({"question": question}).encode()
    code, resp, ms = call("POST", "/api/chat", payload, {"Content-Type": "application/json"})
    data = json.loads(resp)
    print(f"[4] 拒答测试 HTTP {code} status={data.get('status')} 耗时={ms:.0f}ms")
    print(f"    答案: {data.get('answer', '')[:80]}")
    return data


def stream_test(question):
    payload = json.dumps({"question": question}).encode()
    req = urllib.request.Request(BASE + "/api/chat/stream", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    events, text, t0 = [], [], time.perf_counter()
    first_ms = None
    with urllib.request.urlopen(req, timeout=90) as resp:
        print(f"[5] 流式问答 HTTP {resp.status} content-type={resp.headers.get('Content-Type')}")
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if line.startswith("event:"):
                name = line[6:].strip()
                events.append(name)
                if name == "delta" and first_ms is None:
                    first_ms = (time.perf_counter() - t0) * 1000
            elif line.startswith("data:") and events and events[-1] == "delta":
                try:
                    text.append(json.loads(line[5:].strip()).get("text", ""))
                except json.JSONDecodeError:
                    pass
    print(f"    事件序列: {' → '.join(events)}")
    print(f"    首字延迟: {first_ms:.0f}ms  总耗时: {(time.perf_counter()-t0)*1000:.0f}ms")
    print(f"    流式拼出的答案: {''.join(text)[:110]}")
    return events


if __name__ == "__main__":
    if not wait_ready():
        raise SystemExit(1)
    material = Path(__file__).resolve().parent / "tools" / "sample-tcp.md"
    upload(material)
    ask("为什么 TCP 建立连接需要三次握手？")
    ask_refuse("请给出本课程教材第 12 章全部课后习题的标准答案。")
    ev = stream_test("TIME_WAIT 为什么必须等待 2MSL？")
    ok = "meta" in ev and "delta" in ev and "done" in ev
    print("\n结论: " + ("全部通过 ✅" if ok else "流式事件不完整 ❌"))
    raise SystemExit(0 if ok else 1)
