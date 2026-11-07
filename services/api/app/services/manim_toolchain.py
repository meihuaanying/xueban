"""§5.3 视频版工具链：受限场景 DSL → Manim 源码 → 渲染 → 混流。

设计约束（为什么不是「让模型直接写 Manim 代码」）：

1. **可校验**。模型只产出 JSON 场景描述（文字/公式/步骤/坐标点），
   编译器再用固定模板生成 Manim 源码。任何越界字段在编译前就被拒绝，
   不会把任意 Python 代码带进渲染进程。
2. **可自愈**。渲染失败时把 stderr 摘要回喂「数学导演」阶段要求改场景描述，
   而不是让模型在代码层反复试错。
3. **可测试**。编译器是纯函数，单测不需要安装 Manim；真实渲染只走
   :class:`ManimToolchain`，测试里用替身。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import Settings


class ManimError(Exception):
    """渲染/混流失败。``detail`` 会回喂给导演阶段做自愈修复。"""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


#: 固定配色（深底浅字，高中/成人主题）。不交给模型选色，避免低对比度成片。
_COLORS = {
    "background": "#0E1116",
    "headline": "#F2F5FA",
    "text": "#D7DEEA",
    "formula": "#8CD3FF",
    "axis": "#5A6476",
    "muted": "#8A94A6",
}


def _tex_log_detail(workdir: Path) -> str:
    """提取 Manim TeX 日志里的首错行。

    stderr 尾部往往只有 Python traceback，真正的原因（``! Undefined control
    sequence`` / 缺宏包 / 非法 Unicode）在 ``media/Tex/*.log`` 里。把这几行放进
    自愈提示，导演才知道改哪个公式，而不是盲改场景。
    """
    log_dir = workdir / "media" / "Tex"
    if not log_dir.is_dir():
        return ""
    logs = sorted(
        log_dir.glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    if not logs:
        return ""
    try:
        lines = logs[0].read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    picked: list[str] = []
    for index, line in enumerate(lines):
        if line.startswith("!"):
            picked.extend(item.strip() for item in lines[index : index + 4])
            if len(picked) >= 8:
                break
    return "\n".join(picked)[:1200]


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _range(value: Any, default: list[float]) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return default
    return [_num(item) for item in value]


def _latex(raw: str) -> str:
    """去掉模型常见的 ``$...$`` 包裹；MathTex 只接受裸公式。"""
    text = raw.strip()
    if text.startswith("$$") and text.endswith("$$") and len(text) > 4:
        text = text[2:-2]
    elif text.startswith("$") and text.endswith("$") and len(text) > 2:
        text = text[1:-1]
    return text


def _element_lines(element: dict[str, Any], index: int) -> tuple[list[str], str | None]:
    """编译单个元素。返回 (代码行, 变量名)；变量名 None 表示没有可播放对象。"""
    kind = element.get("kind")
    if kind == "text":
        return (
            [
                f"e{index} = Text({element.get('content', '')!r}, font=FONT, "
                f"font_size=30, color='{_COLORS['text']}', line_spacing=0.6)"
            ],
            f"e{index}",
        )
    if kind == "bullet":
        content = f"• {element.get('content', '')}"
        return (
            [
                f"e{index} = Text({content!r}, font=FONT, font_size=28, "
                f"color='{_COLORS['text']}', line_spacing=0.6)"
            ],
            f"e{index}",
        )
    if kind == "formula":
        latex = _latex(str(element.get("latex", "")))
        return (
            [
                f"e{index} = MathTex({latex!r}, font_size=44, "
                f"color='{_COLORS['formula']}')"
            ],
            f"e{index}",
        )
    if kind == "axes":
        x_range = _range(element.get("x_range"), [-3.0, 3.0, 1.0])
        y_range = _range(element.get("y_range"), [-3.0, 3.0, 1.0])
        points = element.get("points") or []
        coords = [
            (float(point[0]), float(point[1]))
            for point in points
            if isinstance(point, (list, tuple))
            and len(point) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in point)
        ]
        if len(coords) < 2:
            raise ManimError("axes 元素至少需要 2 个坐标点")
        lines = [
            f"ax{index} = Axes(x_range={x_range!r}, y_range={y_range!r}, "
            "x_length=5.6, y_length=3.6, tips=False, "
            f"axis_config={{'color': '{_COLORS['axis']}', 'stroke_width': 2}})",
            f"curve{index} = VMobject().set_points_smoothly(["
            + ", ".join(f"ax{index}.c2p({x}, {y})" for x, y in coords)
            + f"]).set_stroke(color='{_COLORS['formula']}', width=4)",
        ]
        label = str(element.get("label") or "").strip()
        if label:
            lines.append(
                f"lab{index} = Text({label!r}, font=FONT, font_size=20, "
                f"color='{_COLORS['muted']}').next_to(ax{index}, UP, buff=0.1)"
            )
            lines.append(f"e{index} = VGroup(ax{index}, curve{index}, lab{index})")
        else:
            lines.append(f"e{index} = VGroup(ax{index}, curve{index})")
        return lines, f"e{index}"
    raise ManimError(f"不支持的场景元素类型：{kind!r}")


def compile_scene(shots: list[dict[str, Any]], *, font: str) -> str:
    """把已校验的镜头列表编译成单文件 Manim 场景源码（确定性，无模型参与）。"""
    if not shots:
        raise ManimError("镜头列表为空，拒绝生成空视频")
    body: list[str] = []
    for shot_index, shot in enumerate(shots):
        # 注释行不做 repr：标题里的换行会把 `import os` 拼回方法体缩进，
        # 打破「模型文本永不成为代码」的不变量，因此先折叠全部空白。
        title = " ".join(str(shot.get("title") or "").split())
        layout = shot.get("layout") if shot.get("layout") in ("stack", "center") else "stack"
        duration = max(2.0, _num(shot.get("duration"), 8.0))
        wait_seconds = max(0.8, duration - 2.4)
        elements = shot.get("elements") or []
        names: list[str] = []

        body.append(f"        # --- 第 {shot_index + 1} 幕：{title} ---")
        body.append(
            f"        head{shot_index} = Text({title!r}, font=FONT, font_size=38, "
            f"color='{_COLORS['headline']}')"
        )
        names.append(f"head{shot_index}")
        for element_index, element in enumerate(elements):
            if not isinstance(element, dict):
                raise ManimError("场景元素必须是对象")
            lines, name = _element_lines(element, shot_index * 100 + element_index)
            body.extend("        " + line for line in lines)
            if name is not None:
                names.append(name)
        body.append(
            f"        group{shot_index} = VGroup({', '.join(names)}).arrange("
            "DOWN, aligned_edge=LEFT, buff=0.35)"
        )
        body.append(
            f"        if group{shot_index}.width > 11.0:\n"
            f"            group{shot_index}.scale_to_fit_width(11.0)\n"
            f"        if group{shot_index}.height > 5.8:\n"
            f"            group{shot_index}.scale_to_fit_height(5.8)"
        )
        if layout == "center":
            body.append(f"        group{shot_index}.move_to(ORIGIN)")
        else:
            body.append(f"        group{shot_index}.to_edge(LEFT, buff=0.9).shift(UP * 0.2)")
        body.append(
            f"        self.play(Write(head{shot_index}), "
            f"FadeIn(VGroup({', '.join(names[1:]) or 'VGroup()'}), shift=UP * 0.2), "
            "run_time=1.8)"
        )
        body.append(f"        self.wait({wait_seconds:.2f})")
        body.append(f"        self.play(FadeOut(group{shot_index}), run_time=0.6)")

    return (
        "# -*- coding: utf-8 -*-\n"
        "# 本文件由学伴 §5.3 场景编译器生成，请勿手改。\n"
        "from manim import *\n\n"
        f"FONT = {font!r}\n\n"
        "class XuebanExplainer(Scene):\n"
        "    def construct(self):\n"
        f"        self.camera.background_color = '{_COLORS['background']}'\n"
        "        watermark = Text('学伴 · AI 生成讲解', font=FONT, font_size=14, "
        f"color='{_COLORS['muted']}')\n"
        "        watermark.to_corner(DR, buff=0.25)\n"
        "        self.add(watermark)\n"
        + "\n".join(body)
        + "\n"
    )


def _find_manim_python(settings: Settings) -> Path | None:
    env_override = os.environ.get("MANIM_PYTHON", "").strip()
    candidates = [
        Path(settings.manim_python) if settings.manim_python.strip() else None,
        Path(env_override) if env_override else None,
        Path(__file__).resolve().parents[2] / ".venv-manim/Scripts/python.exe",
        Path(__file__).resolve().parents[2] / ".venv-manim/bin/python",
        Path(__file__).resolve().parents[2] / ".venv/Scripts/python.exe",
        Path(__file__).resolve().parents[2] / ".venv/bin/python",
    ]
    return next((path for path in candidates if path is not None and path.exists()), None)


def _find_latex() -> Path | None:
    launcher = shutil.which("latex")
    if launcher:
        return Path(launcher)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        for name in ("latex.exe", "latex"):
            candidate = Path(local_app_data) / "Programs/MiKTeX/miktex/bin/x64" / name
            if candidate.exists():
                return candidate
    return None


def _find_ffmpeg() -> Path | None:
    launcher = shutil.which("ffmpeg")
    return Path(launcher) if launcher else None


class ManimToolchain:
    """真实渲染工具链（Manim + LaTeX + ffmpeg）。同步子进程放线程池执行。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def availability(self) -> str | None:
        """返回缺失项说明；全部就绪时返回 None。"""
        missing: list[str] = []
        if _find_manim_python(self.settings) is None:
            missing.append("manim 解释器（.venv-manim）")
        if _find_latex() is None:
            missing.append("LaTeX（MiKTeX）")
        if _find_ffmpeg() is None:
            missing.append("ffmpeg")
        return "、".join(missing) or None

    async def render_scene(self, source: str, *, workdir: Path) -> Path:
        if self.availability() is not None:
            raise ManimError(f"视频工具链不完整：{self.availability()}")
        return await asyncio.to_thread(self._render_sync, source, workdir)

    def _render_sync(self, source: str, workdir: Path) -> Path:
        python = _find_manim_python(self.settings)
        latex = _find_latex()
        assert python is not None and latex is not None  # availability() 已校验
        scene_file = workdir / "scene.py"
        scene_file.write_text(source, encoding="utf-8")
        env = dict(os.environ)
        env["PATH"] = str(latex.parent) + os.pathsep + env.get("PATH", "")
        # 缺宏包时直接失败，而不是在无人值守的预生成里挂起等交互安装
        env["MIKTEX_AUTOINSTALL"] = "0"
        env["MIKTEX_ENABLEINSTALLER"] = "0"
        command = [
            str(python),
            "-m",
            "manim",
            "render",
            f"-q{self.settings.manim_quality}",
            "--disable_caching",
            "-o",
            "xueban-explainer.mp4",
            str(scene_file),
            "XuebanExplainer",
        ]
        try:
            result = subprocess.run(
                command,
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.settings.manim_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ManimError("Manim 渲染超时", detail=str(exc)[:2000]) from exc
        movies = list(workdir.glob("media/videos/**/xueban-explainer.mp4"))
        if result.returncode != 0 or not movies:
            tail = "\n".join((result.stderr or result.stdout or "").strip().splitlines()[-25:])
            tex_error = _tex_log_detail(workdir)
            detail = f"TeX 报错：\n{tex_error}\n---\n{tail}" if tex_error else tail
            raise ManimError("Manim 渲染失败", detail=detail[-4000:])
        return movies[0]

    async def mux_audio(
        self, *, video: Path, audios: list[Path], output: Path, workdir: Path
    ) -> Path:
        return await asyncio.to_thread(self._mux_sync, video, audios, output, workdir)

    def _mux_sync(
        self, video: Path, audios: list[Path], output: Path, workdir: Path
    ) -> Path:
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            raise ManimError("未找到 ffmpeg，无法合成配音")
        if not audios:
            shutil.copyfile(video, output)
            return output
        narration = workdir / "narration.m4a"
        if len(audios) == 1:
            source_args = ["-i", str(audios[0])]
        else:
            listing = workdir / "audio-list.txt"
            listing.write_text(
                "".join(
                    "file '" + audio.as_posix().replace("'", "'\\''") + "'\n"
                    for audio in audios
                ),
                encoding="utf-8",
            )
            source_args = ["-f", "concat", "-safe", "0", "-i", str(listing)]
        self._run_ffmpeg(
            ffmpeg,
            [*source_args, "-y", "-c:a", "aac", "-b:a", "128k", str(narration)],
        )
        self._run_ffmpeg(
            ffmpeg,
            [
                "-y",
                "-i",
                str(video),
                "-i",
                str(narration),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-shortest",
                str(output),
            ],
        )
        return output

    @staticmethod
    def _run_ffmpeg(ffmpeg: Path, args: list[str]) -> None:
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-loglevel", "error", *args],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise ManimError("ffmpeg 处理失败", detail=(result.stderr or "")[-2000:])

    async def probe_duration(self, path: Path) -> float:
        return await asyncio.to_thread(self._probe_sync, path)

    @staticmethod
    def _probe_sync(path: Path) -> float:
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            raise ManimError("未找到 ffmpeg，无法读取媒体时长")
        ffprobe = shutil.which("ffprobe")
        probe = Path(ffprobe) if ffprobe else ffmpeg.with_name("ffprobe.exe")
        try:
            result = subprocess.run(
                [
                    str(probe),
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return max(0.0, float((result.stdout or "0").strip() or 0))
        except (OSError, ValueError) as exc:
            raise ManimError("读取媒体时长失败", detail=str(exc)) from exc


async def render_preview(
    *,
    shots: list[dict[str, Any]],
    font: str,
    settings: Settings,
    output_dir: Path,
) -> Path:
    """不依赖数据库/对象存储的渲染冒烟：给定镜头直接出片（供脚本与人工验证）。"""
    toolchain = ManimToolchain(settings)
    with tempfile.TemporaryDirectory(prefix="xueban-video-") as tmp:
        workdir = Path(tmp)
        source = compile_scene(shots, font=font)
        video = await toolchain.render_scene(source, workdir=workdir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / "preview.mp4"
        shutil.copyfile(video, output)
        return output


__all__ = [
    "ManimError",
    "ManimToolchain",
    "compile_scene",
    "render_preview",
]
