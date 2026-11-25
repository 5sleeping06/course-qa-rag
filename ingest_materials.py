"""批量入库 + 领域问答实测。

用法：
    python ingest_materials.py              # 入库 materials/ 下所有文件
    python ingest_materials.py --ask        # 入库后跑几个领域问题

服务需已启动（start-ai.cmd 或 java -jar）。
"""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8080"
ROOT = Path(__file__).resolve().parent
MATERIALS = ROOT / "materials"

QUESTIONS = [
    "能源大数据有哪些特征？",
    "什么是能源大数据管理？",
    "煤炭产业大数据分析主要解决什么问题？",
    "碳交易市场的数据来源有哪些？",
    "企业能源管理系统一般包含哪些功能模块？",
    "能源大数据的关键技术包括哪些？",
]


def request(method, path, data=None, headers=None, timeout=180):
    req = urllib.request.Request(BASE + path, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def wait_ready(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            status, _ = request("GET", "/api/ping", timeout=3)
            if status == 200:
                return True
        except Exception:
            time.sleep(1.5)
    return False


def upload(path: Path):
    boundary = "----ingest" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    t0 = time.perf_counter()
    status, resp = request("POST", "/api/documents", body,
                           {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    dt = time.perf_counter() - t0
    data = json.loads(resp)
    if status != 201:
        print(f"  [FAIL] {path.name}: HTTP {status} {data.get('message')}")
        return None
    print(f"  [OK]   {path.name:<46} {data['chunks']:>4} 块  {data['chars']:>7} 字  {dt*1000:>6.0f}ms")
    return data


def ask(question):
    payload = json.dumps({"question": question, "topK": 5}).encode()
    t0 = time.perf_counter()
    status, resp = request("POST", "/api/chat", payload, {"Content-Type": "application/json"})
    dt = (time.perf_counter() - t0) * 1000
    data = json.loads(resp)
    cites = data.get("citations", [])
    print(f"\nQ: {question}")
    print(f"   status={data['status']}  耗时={dt:.0f}ms  引用={len(cites)} 条"
          + (f"  首条分数={cites[0]['score']}" if cites else ""))
    answer = (data.get("answer") or "").replace("\n", " ")
    print(f"   A: {answer[:260]}")
    for c in cites[:2]:
        print(f"      · 《{c['docName']}》第{c['chunkIndex']}块  score={c['score']}")


def main():
    if not wait_ready():
        print("服务未启动")
        return 1

    files = sorted(p for p in MATERIALS.iterdir()
                   if p.is_file() and p.suffix.lower() in {".txt", ".md", ".pdf", ".docx"})
    if not files:
        print(f"{MATERIALS} 下没有可入库的文件")
        return 1

    print(f"入库 {len(files)} 个文件：")
    total_chunks = 0
    for f in files:
        data = upload(f)
        if data:
            total_chunks += data["chunks"]

    status, resp = request("GET", "/api/documents")
    docs = json.loads(resp)
    print(f"\n库内共 {docs['total']} 篇 / {docs['chunkCount']} 块（本次新增 {total_chunks} 块）")

    if "--ask" in sys.argv:
        for q in QUESTIONS:
            try:
                ask(q)
            except urllib.error.HTTPError as exc:
                print(f"\nQ: {q}\n   失败: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
