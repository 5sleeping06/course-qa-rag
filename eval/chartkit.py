"""极简绘图工具（Pillow），供各实验脚本复用。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 2  # 2 倍分辨率

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\Deng.ttf",
]


def font(logical_size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, int(logical_size * S))
            except Exception:
                continue
    return ImageFont.load_default()


def px(v):
    return int(v * S)


def canvas(width, height):
    img = Image.new("RGB", (width * S, height * S), "white")
    return img, ImageDraw.Draw(img)


def nice_range(values, pad=0.22):
    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    span = hi - lo
    lo2 = lo - span * pad
    if lo >= 0:
        lo2 = max(0.0, lo2)   # 计数/吞吐/延迟不该出现负刻度
    return lo2, hi + span * pad


def panel(draw, box, title, xlabels, ys, fmt="{:.0f}", color=(47, 111, 237), bars=False):
    """box 为逻辑坐标 (x0,y0,x1,y1)。"""
    x0, y0, x1, y1 = box
    pad_l, pad_r, pad_t, pad_b = 92, 44, 64, 64
    px0, py0 = x0 + pad_l, y0 + pad_t
    px1, py1 = x1 - pad_r, y1 - pad_b

    draw.text((px((x0 + x1) / 2), px(y0 + 26)), title, font=font(25), fill=(28, 33, 45), anchor="mm")

    lo, hi = nice_range(ys)
    draw.line([(px(px0), px(py0)), (px(px0), px(py1)), (px(px1), px(py1))], fill=(96, 102, 118), width=px(2))

    for i in range(4):
        v = lo + (hi - lo) * i / 3
        y = py1 - (v - lo) / (hi - lo) * (py1 - py0)
        draw.line([(px(px0 - 6), px(y)), (px(px0), px(y))], fill=(96, 102, 118), width=px(2))
        draw.text((px(px0 - 14), px(y)), fmt.format(v), font=font(18), fill=(96, 102, 118), anchor="rm")

    n = len(ys)
    if bars:
        step = (px1 - px0) / n
        centers = [px0 + step * (i + 0.5) for i in range(n)]
    else:
        step = (px1 - px0) / max(n - 1, 1) if n > 1 else 0
        centers = [px0 + step * i for i in range(n)]

    pts = []
    for idx, (cx, yv) in enumerate(zip(centers, ys)):
        cy = py1 - (yv - lo) / (hi - lo) * (py1 - py0)
        pts.append((cx, cy))
        draw.text((px(cx), px(py1 + 14)), str(xlabels[idx]), font=font(20), fill=(58, 64, 80), anchor="ma")

    if bars:
        for (cx, cy), yv in zip(pts, ys):
            draw.rectangle([px(cx - step * 0.28), px(cy), px(cx + step * 0.28), px(py1)], fill=color)
            draw.text((px(cx), px(cy - 10)), fmt.format(yv), font=font(19), fill=(28, 33, 45), anchor="mb")
    else:
        draw.line([(px(a), px(b)) for a, b in pts], fill=color, width=px(3), joint="curve")
        for i, ((cx, cy), yv) in enumerate(zip(pts, ys)):
            draw.ellipse([px(cx - 7), px(cy - 7), px(cx + 7), px(cy + 7)], fill=color)
            label = fmt.format(yv)
            if cy - 28 < py0:
                draw.text((px(cx), px(cy + 18)), label, font=font(19), fill=(28, 33, 45), anchor="mt")
            elif i == 0:
                draw.text((px(cx + 14), px(cy - 10)), label, font=font(19), fill=(28, 33, 45), anchor="lb")
            elif i == len(pts) - 1:
                draw.text((px(cx - 14), px(cy - 10)), label, font=font(19), fill=(28, 33, 45), anchor="rb")
            else:
                draw.text((px(cx), px(cy - 16)), label, font=font(19), fill=(28, 33, 45), anchor="mb")
