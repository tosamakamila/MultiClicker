# -*- coding: utf-8 -*-
"""生成 MultiClicker 图标 icon.ico"""
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角深色背景
radius = 56
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=(22, 26, 38, 255))

# 主色渐变竖条(用多层圆角矩形模拟)
d.rounded_rectangle([0, S - 90, S - 1, S - 1], radius=radius,
                    fill=(99, 102, 241, 255))
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, outline=(42, 48, 69, 255), width=4)

# 鼠标指针(白色)
d.polygon([(56, 52), (56, 152), (88, 126), (108, 156), (122, 148), (102, 118),
           (142, 112)], fill=(226, 232, 240, 255))

# 底部三个点(代表多个点击位置)
for i, cx in enumerate((92, 128, 164)):
    cy = 196
    color = (52, 211, 153, 255) if i == 1 else (148, 163, 184, 255)
    d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=color)

# 连线
d.line([(92, 196), (128, 196), (164, 196)], fill=(99, 102, 241, 255), width=5)

img.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon.ico generated")
