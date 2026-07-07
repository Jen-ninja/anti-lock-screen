# -*- coding: utf-8 -*-
"""生成 exe 图标 app.ico（绿色圆角方块 + 白色电源符号）。"""
from PIL import Image, ImageDraw

ACCENT = "#46c585"


def make_app_icon(size=256):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([size * 0.05, size * 0.05, size * 0.95, size * 0.95],
                        radius=int(size * 0.22), fill=ACCENT)
    box = [size * 0.24, size * 0.22, size * 0.76, size * 0.76]
    w = max(2, int(size * 0.085))
    d.arc(box, 135, 360, fill="white", width=w)
    d.arc(box, 0, 45, fill="white", width=w)
    d.line([size / 2, size * 0.25, size / 2, size * 0.52], fill="white", width=w)
    return im


if __name__ == "__main__":
    make_app_icon(256).save(
        "app.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("app.ico saved")
