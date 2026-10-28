"""Manim 渲染环境自检（P3 §5.3 视频管线前置）。

用法（在 services/api 下）：
    .venv/Scripts/python scripts/check_manim.py

检查项：
1. Manim 专用解释器：MANIM_PYTHON 环境变量，或 .venv-manim / .venv；
2. LaTeX：PATH 中的 latex，或 MiKTeX 默认安装目录；
3. ffmpeg：PATH 中的 ffmpeg；
4. 真实渲染一个 Text + MathTex 场景（480p），产物存在即通过。

任何必需项缺失都返回退出码 1，并打印对应安装命令。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
MIXTEX_BIN = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/MiKTeX/miktex/bin/x64"

SCENE = '''
from manim import DOWN, MathTex, Scene, Text, VGroup, Write


class XuebanManimSmoke(Scene):
    def construct(self):
        title = Text("学伴 · Manim 环境自检", font="Microsoft YaHei")
        formula = MathTex(r"f(x)=x^2+2x+1=(x+1)^2")
        group = VGroup(title, formula).arrange(DOWN, buff=0.6)
        self.play(Write(group), run_time=0.8)
        self.wait(0.2)
'''


def find_manim_python() -> Path | None:
    override = os.environ.get("MANIM_PYTHON", "").strip()
    candidates = [
        Path(override) if override else None,
        API_DIR / ".venv-manim/Scripts/python.exe",
        API_DIR / ".venv-manim/bin/python",
        API_DIR / ".venv/Scripts/python.exe",
        API_DIR / ".venv/bin/python",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return None


def find_latex() -> Path | None:
    launcher = shutil.which("latex")
    if launcher:
        return Path(launcher)
    for name in ("latex.exe", "latex"):
        candidate = MIXTEX_BIN / name
        if candidate.exists():
            return candidate
    return None


def find_ffmpeg() -> Path | None:
    launcher = shutil.which("ffmpeg")
    return Path(launcher) if launcher else None


def ensure_manim(python: Path) -> str | None:
    result = subprocess.run(
        [str(python), "-m", "manim", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0]


def render_smoke(python: Path, latex: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="xueban-manim-") as tmp:
        workdir = Path(tmp)
        scene = workdir / "smoke_scene.py"
        scene.write_text(SCENE, encoding="utf-8")
        env = dict(os.environ)
        env["PATH"] = str(latex.parent) + os.pathsep + env.get("PATH", "")
        result = subprocess.run(
            [
                str(python),
                "-m",
                "manim",
                "render",
                "-ql",
                "--disable_caching",
                "-o",
                "smoke.mp4",
                str(scene),
                "XuebanManimSmoke",
            ],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        movies = list(workdir.glob("media/videos/**/smoke.mp4"))
        if result.returncode == 0 and movies:
            return True, str(movies[0])
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        return False, "\n".join(tail)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manim/LaTeX 渲染环境自检")
    parser.add_argument("--skip-render", action="store_true", help="只查依赖，不实际渲染")
    args = parser.parse_args()

    python = find_manim_python()
    latex = find_latex()
    ffmpeg = find_ffmpeg()

    failures: list[str] = []
    if python is None:
        failures.append(
            "未找到 Manim 解释器；安装：\n"
            "  cd services/api\n"
            "  .venv/Scripts/python -m venv .venv-manim\n"
            "  ./.venv-manim/Scripts/python -m pip install --no-cache-dir manim"
        )
    else:
        version = ensure_manim(python)
        if version is None:
            failures.append(f"{python} 里没有可用的 manim（python -m manim --version 失败）")
        else:
            print(f"[ok] Manim: {version} ({python})")

    if latex is None:
        failures.append(
            "未找到 LaTeX；Windows 安装：\n"
            "  winget install --id MiKTeX.MiKTeX -e\n"
            "  miktex packages install preview standalone amsmath amsfonts dvisvgm"
        )
    else:
        print(f"[ok] LaTeX: {latex}")

    if ffmpeg is None:
        failures.append("未找到 ffmpeg；Windows：winget install Gyan.FFmpeg")
    else:
        print(f"[ok] ffmpeg: {ffmpeg}")

    if failures:
        for item in failures:
            print(f"[fail] {item}", file=sys.stderr)
        return 1

    if args.skip_render:
        return 0
    assert python is not None and latex is not None
    ok, detail = render_smoke(python, latex)
    if not ok:
        print("[fail] Manim 渲染失败：\n" + detail, file=sys.stderr)
        return 1
    print(f"[ok] 渲染成功：{detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
