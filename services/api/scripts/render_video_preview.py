"""Manim 成片冒烟：不碰数据库/LLM/TTS，用固定镜头渲染一支真实视频。

用途：部署新机器后验证 §5.3 的「场景组装 → 渲染 → ffmpeg」链路是否真的能出片；
LLM/TTS/入库的契约由 `tests/test_explainer_video.py` 覆盖。

用法（services/api 目录）：
    .venv/Scripts/python scripts/render_video_preview.py
    .venv/Scripts/python scripts/render_video_preview.py --out ./preview.mp4
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.services.manim_toolchain import ManimToolchain, compile_scene

SHOTS = [
    {
        "title": "集合与元素",
        "layout": "stack",
        "duration": 7.0,
        "elements": [
            {"kind": "text", "content": "把确定的整体叫作集合"},
            {"kind": "bullet", "content": "集合里的对象叫元素"},
            {"kind": "formula", "latex": r"a \in A"},
        ],
    },
    {
        "title": "二次函数的形状",
        "layout": "center",
        "duration": 8.0,
        "elements": [
            {
                "kind": "axes",
                "x_range": [-3, 3, 1],
                "y_range": [-1, 6, 1],
                "points": [[-3, 9], [-2, 4], [-1, 1], [0, 0], [1, 1], [2, 4], [3, 9]],
                "label": "y = x^2",
            },
            {"kind": "formula", "latex": r"y=x^2"},
        ],
    },
]


async def run(args: argparse.Namespace) -> int:
    toolchain = ManimToolchain(settings)
    missing = toolchain.availability()
    if missing is not None:
        print(f"[fail] 视频工具链不完整：{missing}", file=sys.stderr)
        return 1
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xueban-preview-") as tmp:
        workdir = Path(tmp)
        source = compile_scene(SHOTS, font=settings.manim_font)
        scene_file = workdir / "scene.py"
        scene_file.write_text(source, encoding="utf-8")
        print(f"[info] 场景源码：{scene_file}（临时目录，渲染后清理）")
        video = await toolchain.render_scene(source, workdir=workdir)
        # 冒烟片不带配音，直接复制成片；混流链路由单元测试与正式管线覆盖。
        output.write_bytes(video.read_bytes())
        duration = await toolchain.probe_duration(output)
    print(f"[ok] {output}  {duration:.1f}s  {output.stat().st_size // 1024}KB")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manim 成片冒烟")
    parser.add_argument("--out", default="video-preview.mp4", help="输出文件路径")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
