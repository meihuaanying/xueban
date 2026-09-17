"""生成品牌图标（安卓/iOS/商店素材），依赖 Pillow。

用法（services/api 虚拟环境）：
    .venv/Scripts/python scripts/make_icons.py

产物：
    apps/mobile/assets/icon.png           1024×1024 应用图标（不透明）
    apps/mobile/assets/adaptive-icon.png  1024×1024 自适应图标前景（透明底，含安全区）
    apps/mobile/assets/splash-icon.png    512×512   启动图图标
    apps/mobile/assets/favicon.png        48×48
    release-assets/icons/icon-512.png     商店图标 512×512
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
MOBILE_ASSETS = REPO_ROOT / "apps" / "mobile" / "assets"
STORE_ICONS = REPO_ROOT / "release-assets" / "icons"

PRIMARY_TOP = (51, 134, 255)  # #3386ff
PRIMARY_BOTTOM = (31, 102, 245)  # #1f66f5
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise SystemExit("未找到可用字体（尝试 msyhbd/msyh/DejaVuSans）")


def vertical_gradient(size: int) -> Image.Image:
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        ratio = y / max(size - 1, 1)
        color = tuple(
            round(PRIMARY_TOP[i] + (PRIMARY_BOTTOM[i] - PRIMARY_TOP[i]) * ratio) for i in range(3)
        )
        gradient.putpixel((0, y), color)
    return gradient.resize((size, size))


def centered_text(
    canvas: Image.Image, text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, ...]
) -> None:
    draw = ImageDraw.Draw(canvas)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((canvas.width - (right - left)) / 2 - left, (canvas.height - (bottom - top)) / 2 - top),
        text,
        font=font,
        fill=fill,
    )


def make_icon(size: int = 1024) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = vertical_gradient(size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=round(size * 0.22), fill=255
    )
    icon.paste(gradient, (0, 0), mask)
    centered_text(icon, "学", load_font(round(size * 0.56)), (255, 255, 255, 255))
    return icon


def make_adaptive_foreground(size: int = 1024) -> Image.Image:
    # 自适应图标前景安全区：中心 66% 内绘制
    foreground = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glyph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    centered_text(glyph, "学", load_font(round(size * 0.38)), (255, 255, 255, 255))
    foreground.alpha_composite(glyph)
    return foreground


def main() -> int:
    MOBILE_ASSETS.mkdir(parents=True, exist_ok=True)
    STORE_ICONS.mkdir(parents=True, exist_ok=True)

    icon = make_icon()
    icon.save(MOBILE_ASSETS / "icon.png")
    icon.resize((512, 512), Image.LANCZOS).save(STORE_ICONS / "icon-512.png")
    icon.resize((192, 192), Image.LANCZOS).save(STORE_ICONS / "icon-192.png")

    make_adaptive_foreground().save(MOBILE_ASSETS / "adaptive-icon.png")

    splash = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    centered_text(splash, "学", load_font(round(512 * 0.5)), (*PRIMARY_BOTTOM, 255))
    splash.save(MOBILE_ASSETS / "splash-icon.png")

    favicon = icon.resize((48, 48), Image.LANCZOS)
    favicon.save(MOBILE_ASSETS / "favicon.png")

    print("图标生成完成：", ", ".join(sorted(p.name for p in MOBILE_ASSETS.iterdir())))
    print("商店图标：", ", ".join(sorted(p.name for p in STORE_ICONS.iterdir())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
