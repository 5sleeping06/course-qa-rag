"""诊断：为什么「能源大数据的关键技术包括哪些」命中了错误的块。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "materials" / "第二章 能源大数据关键技术与管理应用-学生课件.txt"
CHUNK_SIZE, OVERLAP = 400, 50
QUERY = "能源大数据的关键技术包括哪些"


def read_text(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit("decode failed")


def chunk(text: str):
    t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    step = CHUNK_SIZE - OVERLAP
    out = []
    for i in range(0, len(t), step):
        piece = t[i:i + CHUNK_SIZE].strip()
        if piece:
            out.append((i, piece))
        if i + CHUNK_SIZE >= len(t):
            break
    return out


def tokenize(text: str):
    """与 Java Tokenizer 一致：CJK 二元组 + 拉丁词。"""
    s = text.lower()
    toks, latin, cjk = [], [], []

    def flush_latin():
        if latin:
            toks.append("".join(latin))
            latin.clear()

    def flush_cjk():
        n = len(cjk)
        if n == 1:
            toks.append(cjk[0])
        elif n > 1:
            toks.extend(cjk[i] + cjk[i + 1] for i in range(n - 1))
        cjk.clear()

    for ch in s:
        if "\u4e00" <= ch <= "\u9fff":
            flush_latin()
            cjk.append(ch)
        elif ch.isalnum():
            flush_cjk()
            latin.append(ch)
        else:
            flush_latin()
            flush_cjk()
    flush_latin()
    flush_cjk()
    return toks


def main():
    text = read_text(DOC)
    chunks = chunk(text)
    print(f"文档: {DOC.name}  共 {len(chunks)} 块\n")

    # 正确内容在哪些块
    print("【含『采集技术/存储技术/分析技术/可视化技术』的块】")
    for idx, (off, piece) in enumerate(chunks):
        hits = [k for k in ("采集技术", "存储技术", "分析技术", "可视化技术", "挖掘技术") if k in piece]
        if hits:
            print(f"  第{idx:>3}块 (偏移{off:>5}): {hits}")
            print(f"        {piece[:90].replace(chr(10), ' ')}")

    # BM25 排序
    K1, B = 1.2, 0.75
    tokenized = [tokenize(p) for _, p in chunks]
    lengths = [max(len(t), 1) for t in tokenized]
    avgdl = sum(lengths) / len(lengths)
    df = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    N = len(chunks)
    query = tokenize(QUERY)
    qtf = {}
    for t in query:
        qtf[t] = qtf.get(t, 0) + 1

    scored = []
    for i, toks in enumerate(tokenized):
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t, q in qtf.items():
            if t not in tf:
                continue
            idf = __import__("math").log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            denom = tf[t] + K1 * (1 - B + B * lengths[i] / avgdl)
            score += idf * (tf[t] * (K1 + 1)) / denom
        scored.append((score, i))

    scored.sort(reverse=True)
    print(f"\n【查询: {QUERY}】")
    print(f"查询词: {query}")
    print("\nBM25 Top 8:")
    for score, i in scored[:8]:
        piece = chunks[i][1].replace("\n", " ")
        print(f"  第{i:>3}块  score={score:6.2f}  长度={lengths[i]:>3}")
        print(f"        {piece[:80]}")

    # 正确块的排名
    print("\n【正确块（含采集/存储/分析/可视化技术）的排名】")
    for rank, (score, i) in enumerate(scored, 1):
        piece = chunks[i][1]
        if sum(1 for k in ("采集技术", "存储技术", "分析技术", "可视化技术") if k in piece) >= 2:
            print(f"  第{i}块 排名第 {rank}，score={score:.2f}")
            break


if __name__ == "__main__":
    main()
