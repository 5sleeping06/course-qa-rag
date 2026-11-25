"""系统架构图：分层堆叠画法。输出 eval/charts/architecture.png"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "charts" / "architecture.png"

S = 2
W, H = 1200, 820
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]


def font(size):
    for p in FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, int(size * S))
            except Exception:
                continue
    return ImageFont.load_default()


def px(v):
    return int(v * S)


img = Image.new("RGB", (W * S, H * S), "white")
d = ImageDraw.Draw(img)

TEXT = (28, 34, 46)
MUTED = (88, 96, 114)
BAND = (245, 247, 251)
CHIP = (255, 255, 255)
CHIP_BORDER = (150, 160, 180)
ACCENT = (47, 111, 237)

d.text((px(30), px(26)), "图 1  系统分层架构", font=font(21), fill=TEXT, anchor="la")
d.text((px(30), px(58)), "箭头表示调用方向；同一层内的组件由下层组合而成", font=font(13), fill=MUTED, anchor="la")


def band(y, height, label, chips, note=None):
    d.rounded_rectangle([px(30), px(y), px(W - 30), px(y + height)], radius=px(8), fill=BAND, outline=(210, 216, 228), width=px(1))
    d.text((px(48), px(y + 18)), label, font=font(15), fill=MUTED, anchor="lm")
    # 水平排列 chips，按文字宽度自适应
    total = sum(chip_width(c) for c in chips) + 18 * (len(chips) - 1)
    x = (W - total) / 2
    cy = y + height / 2 + 6
    for c in chips:
        w = chip_width(c)
        d.rounded_rectangle([px(x), px(cy - 30), px(x + w), px(cy + 30)], radius=px(6), fill=CHIP, outline=CHIP_BORDER, width=px(2))
        d.text((px(x + w / 2), px(cy - 6)), c[0], font=font(17), fill=TEXT, anchor="mm")
        if len(c) > 1:
            d.text((px(x + w / 2), px(cy + 15)), c[1], font=font(12), fill=MUTED, anchor="mm")
        x += w + 18
    if note:
        d.text((px(W / 2), px(y + height + 16)), note, font=font(12), fill=MUTED, anchor="ma")


_cache = {}


def chip_width(c):
    key = c[0] + (c[1] if len(c) > 1 else "")
    if key in _cache:
        return _cache[key]
    f1, f2 = font(17), font(12)
    w1 = d.textlength(c[0], font=f1) / S
    w2 = d.textlength(c[1], font=f2) / S if len(c) > 1 else 0
    w = max(w1, w2) + 44
    _cache[key] = w
    return w


def down_arrow(x, y0, y1, label=""):
    d.line([px(x), px(y0), px(x), px(y1)], fill=ACCENT, width=px(2))
    d.polygon([(px(x - 6), px(y1 - 9)), (px(x + 6), px(y1 - 9)), (px(x), px(y1))], fill=ACCENT)
    if label:
        d.text((px(x + 10), px((y0 + y1) / 2)), label, font=font(12), fill=MUTED, anchor="lm")


# 1 表示层
band(90, 100, "表示层", [("浏览器单页 index.html", "SSE 流式渲染 · 引用展示 · 上传")])

# 2 接入层
band(220, 100, "接入层", [
    ("ChatController", "/api/chat, /api/chat/stream"),
    ("DocumentController", "/api/documents"),
    ("RateLimitFilter", "令牌桶 30 次/分"),
])

# 3 业务层
band(350, 110, "业务层", [
    ("ChatService", "检索 → 阈值 → 提示词 → 流式 → 引用"),
    ("文档接入流程", "解析 → 分块 → 入库"),
])

# 4 支撑层
band(490, 120, "支撑层", [
    ("Bm25Index", "中文二元组 · k1=1.2 b=0.75"),
    ("VectorStore", "内存 + JSON 落盘"),
    ("PromptBuilder", "上下文预算 + 编号溯源"),
    ("Parser / Chunker", "pdf/docx/txt · 400 字"),
])

# 5 外部
band(640, 100, "外部服务", [("DeepSeek API", "OpenAI 兼容 · deepseek-chat · SSE")])

down_arrow(W / 2, 190, 220, "HTTP / SSE")
down_arrow(W / 2, 320, 350)
down_arrow(W / 2, 460, 490)
down_arrow(W / 2, 610, 640, "生成")

d.text((px(30), px(775)), "说明：index.json 在启动时加载，重入库后 BM25 索引按版本号自动重建，无需重启服务。",
       font=font(12), fill=MUTED, anchor="la")

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print(f"已生成 {OUT} ({img.size[0]}x{img.size[1]})")
