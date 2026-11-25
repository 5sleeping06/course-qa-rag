"""给报告插入代码展示：从源码按方法边界提取真实片段。"""
import re
from pathlib import Path

ROOT = Path(r"D:\study\projecct\b")
BR = ROOT / "build_report.py"
src = BR.read_text(encoding="utf-8")

HELPERS = '''

# ---------- 代码展示 ----------
def _dedent(lines):
    indents = [len(l) - len(l.lstrip(" ")) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    return [l[cut:] if len(l) >= cut else l for l in lines]


def method_snippet(rel_path, anchor, indent=4, max_lines=60):
    """按方法签名 + 缩进边界提取一段代码（含 Signature 行到同缩进的右花括号）。"""
    path = ROOT / rel_path
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if anchor in l), None)
    if start is None:
        return None
    close = " " * indent + "}"
    end = start
    for j in range(start + 1, min(len(lines), start + max_lines)):
        if lines[j] == close:
            end = j
            break
    return "\\n".join(_dedent(lines[start:end + 1]))


def range_snippet(rel_path, start_anchor, end_anchor, max_lines=60):
    """按起止锚点提取（用于非完整方法的片段，如 lambda 内部）。"""
    path = ROOT / rel_path
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if start_anchor in l), None)
    if start is None:
        return None
    end = start
    for j in range(start + 1, min(len(lines), start + max_lines)):
        if end_anchor in lines[j]:
            end = j
            break
    return "\\n".join(_dedent(lines[start:end + 1]))


def code_block(code, cap):
    if not code:
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    set_run(p.add_run(cap), size=9, bold=True, name=HEAD_FONT, color=(0x33, 0x33, 0x33))

    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.35)
    pf.space_before = Pt(2)
    pf.space_after = Pt(10)
    pf.line_spacing = 1.08
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F5F8")
    pPr.insert_element_before(shd, "w:spacing", "w:ind", "w:jc", "w:rPr")

    rows = code.split("\\n")
    for i, line in enumerate(rows):
        run = p.add_run(line)
        set_run(run, size=8.2, name="Consolas")
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        if i < len(rows) - 1:
            run.add_break()
'''

marker = '''def add_toc():'''
if "def code_block(" not in src:
    src = src.replace(marker, HELPERS.strip("\n") + "\n\n\n" + marker)
    print("helper 已插入")
else:
    print("helper 已存在")

# 六处插入
INSERTS = [
    ('     "偏移的作用是让引用可以定位到原文位置，而不只是给出一段文字。")',
     'code_block(method_snippet("src/main/java/course/qa/ingest/DocumentParser.java", "private static String decode", indent=4), '
     '"代码 1　中文编码探测：严格解码，两种编码都失败才报错（DocumentParser.java）")'),
    ('     "二元组的好处是不依赖词典、对专业术语友好；代价是词表膨胀（587 块产生 33147 个词项）。")',
     'code_block(method_snippet("src/main/java/course/qa/store/Bm25Index.java", "public List<ScoredChunk> search"), '
     '"代码 2　BM25 打分：IDF 与长度归一化项按标准公式实现（Bm25Index.java）")'),
    ('     "事件顺序固定，前端据此增量渲染；客户端断开时 `send` 抛异常，服务端捕获后结束任务，避免线程泄漏。")',
     'code_block(range_snippet("src/main/java/course/qa/chat/ChatService.java", '
     '"llm.streamAnswer(new LlmClient", "});"), '
     '"代码 3　流式推送：每次拿到增量就发一个 delta 事件，同时记录首字时间（ChatService.java）")'),
    ('     "若按全文匹配，这类有答案的回答会被误判成拒答——这是评测集 E15 暴露出来的真实缺陷，详见第七章。")',
     'code_block(method_snippet("src/main/java/course/qa/chat/ChatService.java", "private static boolean looksRefused"), '
     '"代码 4　拒答判定：只看回答开头 50 字，且极短回复直接视为拒答（ChatService.java）")'),
    ('     "异常统一由 `@RestControllerAdvice` 处理，返回 code/message 结构，与接口契约一致。")',
     'code_block(method_snippet("src/main/java/course/qa/support/RateLimitFilter.java", "synchronized boolean tryAcquire", indent=8), '
     '"代码 5　令牌桶：按时间差补充令牌，够 1 个才放行（RateLimitFilter.java）")'),
    ('     "改写结果只用于检索，原始问句进入提示词，历史以「学生／助教」形式附在提示词开头。")',
     'code_block(method_snippet("src/main/java/course/qa/chat/QueryRewriter.java", "public String rewrite"), '
     '"代码 6　追问改写：不像追问就直接返回，改写失败退化为「上一问 + 当前问」拼接（QueryRewriter.java）")'),
]

ok = 0
for anchor, call in INSERTS:
    if anchor not in src:
        print(f"[未命中] {anchor[:40]}")
        continue
    if call.split("(")[0] in src and call[:60] in src:
        continue
    src = src.replace(anchor, anchor + "\n\n" + call)
    ok += 1

BR.write_text(src, encoding="utf-8")
print(f"插入 {ok}/6 处代码块")
