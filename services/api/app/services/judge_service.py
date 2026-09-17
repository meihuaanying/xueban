"""编程题判题沙箱（F-26）：隔离执行 + 资源/超时限制 + 评审式反馈。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

DEFAULT_TIMEOUT_SECONDS = 3.0
MAX_MEMORY_BYTES = 256 * 1024 * 1024
MAX_CODE_BYTES = 20_000

BLOCKED_MODULES = {
    "os",
    "subprocess",
    "socket",
    "ctypes",
    "multiprocessing",
    "shutil",
    "urllib",
    "http",
    "requests",
    "ftplib",
    "smtplib",
    "pathlib",
    "importlib",
    "pickle",
    "marshal",
    "webbrowser",
    "signal",
    "pty",
    "resource",
}

# 沙箱前置代码：安装审计钩子（禁文件越权/网络/进程）与导入白名单
SANDBOX_PREAMBLE = """
import os as _os
import sys as _sys

_ALLOWED_ROOTS = tuple(
    _os.path.realpath(root)
    for root in {{_sys.base_prefix, _sys.prefix, _os.getcwd()}}
    if root
)
_BLOCKED_MODULES = {blocked!r}
_REAL_IMPORT = __import__


def _guarded_import(name, *args, **kwargs):
    root = str(name).split(".")[0]
    if root in _BLOCKED_MODULES:
        raise ImportError("judge sandbox: module %r is not allowed" % root)
    return _REAL_IMPORT(name, *args, **kwargs)


def _audit(event, args):
    if event in ("open", "io.open"):
        path = args[0] if args else ""
        try:
            real = _os.path.realpath(_os.fspath(path))
        except Exception:
            real = ""
        if not real.startswith(_ALLOWED_ROOTS):
            raise RuntimeError("judge sandbox: file access denied (%s)" % event)
    elif event.startswith("socket.") or event in (
        "os.system",
        "os.exec",
        "os.spawn",
        "subprocess.Popen",
        "ctypes.dlopen",
        "ctypes.dlsym",
        "shutil.copyfile",
        "shutil.rmtree",
        "os.remove",
        "os.rename",
    ):
        raise RuntimeError("judge sandbox: operation denied (%s)" % event)


_sys.addaudithook(_audit)
__builtins__.__import__ = _guarded_import
"""

FORBIDDEN_MARKERS = (
    "socket.",
    "subprocess",
    "os.system",
    "ctypes",
    "shutil.rmtree",
    "__import__('os')",
)


@dataclass(slots=True)
class TestCase:
    """单条测试用例。"""

    input: str = ""
    expected: str = ""


@dataclass(slots=True)
class TestResult:
    """单条用例结果。"""

    index: int
    passed: bool
    status: str
    stdout: str = ""
    expected: str = ""
    stderr: str = ""
    runtime_ms: int = 0


@dataclass(slots=True)
class JudgeOutcome:
    """判题结论。"""

    verdict: str
    passed: int
    total: int
    results: list[TestResult] = field(default_factory=list)
    feedback: dict[str, list[str]] = field(default_factory=dict)
    blocked_reason: str | None = None


def _limit_resources() -> None:  # pragma: no cover - 仅在 POSIX 子进程中执行
    """子进程资源限制（POSIX；Windows 无 resource 模块，统一 getattr 探测）。"""
    import resource

    setrlimit = getattr(resource, "setrlimit", None)
    if setrlimit is None:
        return
    rlimit_as = getattr(resource, "RLIMIT_AS", None)
    rlimit_cpu = getattr(resource, "RLIMIT_CPU", None)
    rlimit_nproc = getattr(resource, "RLIMIT_NPROC", None)
    if rlimit_as is not None:
        setrlimit(rlimit_as, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
    if rlimit_cpu is not None:
        setrlimit(rlimit_cpu, (2, 2))
    if rlimit_nproc is not None:
        setrlimit(rlimit_nproc, (0, 0))


def _static_scan(code: str) -> str | None:
    """静态扫描明显越权调用（快速失败，避免进入子进程）。"""
    for marker in FORBIDDEN_MARKERS:
        if marker in code:
            return f"代码包含沙箱禁止的调用：{marker}"
    return None


def _build_feedback(code: str, results: list[TestResult], verdict: str) -> dict[str, list[str]]:
    """评审式反馈：边界条件 / 复杂度 / 风格。"""
    boundary: list[str] = []
    complexity: list[str] = []
    style: list[str] = []

    if verdict == "wrong_answer":
        boundary.append("部分用例未通过：检查空输入、单元素、重复元素或极值（0/负数/最大值）边界。")
    if "input(" in code:
        boundary.append("代码依赖交互式输入；判题环境通过标准输入一次性提供数据，请确认读取方式。")
    if code.count("for ") + code.count("while ") >= 2 and "sorted(" not in code:
        complexity.append(
            "存在多层循环：若数据规模较大，考虑排序 + 双指针或哈希表优化到 O(n log n) 以内。"
        )
    if "sorted(" in code or "set(" in code:
        style.append("使用了 Python 内置数据结构，复杂度意识良好。")
    if "def " not in code:
        style.append("建议将核心逻辑封装为函数，便于测试与复用。")
    if "#" not in code:
        style.append("建议补充关键步骤注释，说明变量含义与边界处理。")
    if len(code.splitlines()) > 40:
        style.append("代码较长：可拆分函数、减少嵌套层级，提升可读性。")
    if not boundary:
        boundary.append("边界条件覆盖良好：包含对空输入/极端值的处理（如未特殊处理，建议补充）。")
    if not complexity:
        complexity.append("未检测到明显高复杂度结构；请结合题目数据规模评估是否满足时限。")
    if not style:
        style.append("风格检查通过：命名与结构清晰。")
    return {"boundary": boundary, "complexity": complexity, "style": style}


def run_python(
    code: str,
    *,
    tests: list[TestCase],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    workdir: str | None = None,
) -> JudgeOutcome:
    """在受限子进程中执行 Python 代码并逐用例比对输出。"""
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return JudgeOutcome(
            verdict="rejected",
            passed=0,
            total=len(tests),
            blocked_reason="代码超过大小限制",
            feedback=_build_feedback(code, [], "rejected"),
        )
    blocked = _static_scan(code)
    if blocked is not None:
        return JudgeOutcome(
            verdict="blocked",
            passed=0,
            total=len(tests),
            blocked_reason=blocked,
            feedback=_build_feedback(code, [], "blocked"),
        )

    sandbox_dir = workdir or tempfile.mkdtemp(prefix="judge-")
    owned = workdir is None
    try:
        script = os.path.join(sandbox_dir, "solution.py")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(SANDBOX_PREAMBLE.format(blocked=sorted(BLOCKED_MODULES)))
            handle.write("\n")
            handle.write(code)

        results: list[TestResult] = []
        passed = 0
        verdict = "accepted"
        for index, case in enumerate(tests):
            started = os.times().elapsed
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", "-S", script],
                    input=case.input,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=sandbox_dir,
                    env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
                    check=False,
                    preexec_fn=_limit_resources if os.name == "posix" else None,
                )
            except subprocess.TimeoutExpired:
                results.append(
                    TestResult(
                        index=index,
                        passed=False,
                        status="timeout",
                        expected=case.expected,
                        runtime_ms=int(timeout_seconds * 1000),
                    )
                )
                verdict = "timeout"
                continue
            runtime_ms = int((os.times().elapsed - started) * 1000)
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            ok = completed.returncode == 0 and stdout == case.expected.strip()
            status = "passed" if ok else "fail"
            if completed.returncode != 0:
                status = "forbidden" if "judge sandbox" in stderr else "runtime_error"
                if verdict == "accepted":
                    verdict = "runtime_error" if status == "runtime_error" else "blocked"
            elif not ok and verdict == "accepted":
                verdict = "wrong_answer"
            if ok:
                passed += 1
            results.append(
                TestResult(
                    index=index,
                    passed=ok,
                    status=status,
                    stdout=stdout[:500],
                    expected=case.expected.strip()[:500],
                    stderr=stderr[:500],
                    runtime_ms=runtime_ms,
                )
            )

        return JudgeOutcome(
            verdict=verdict,
            passed=passed,
            total=len(tests),
            results=results,
            feedback=_build_feedback(code, results, verdict),
        )
    finally:
        if owned:
            shutil.rmtree(sandbox_dir, ignore_errors=True)


__all__ = ["JudgeOutcome", "TestCase", "TestResult", "run_python"]
