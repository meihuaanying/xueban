"""编程题判题沙箱测试（M8 / T8.5，F-26）：恶意代码用例必须全部被拦截。"""

from __future__ import annotations

import os

from app.services import judge_service

CORRECT_CODE = """
def solve(values):
    return sum(values)

import sys
print(solve([int(item) for item in sys.stdin.read().split()]))
"""

WRONG_CODE = """
import sys
print(0)
"""


def test_correct_solution_accepted() -> None:
    outcome = judge_service.run_python(
        CORRECT_CODE,
        tests=[
            judge_service.TestCase(input="1 2 3", expected="6"),
            judge_service.TestCase(input="10", expected="10"),
        ],
    )
    assert outcome.verdict == "accepted"
    assert outcome.passed == 2
    assert outcome.feedback["boundary"]
    assert outcome.feedback["complexity"]
    assert outcome.feedback["style"]


def test_wrong_answer_reports_failing_case() -> None:
    outcome = judge_service.run_python(
        WRONG_CODE,
        tests=[judge_service.TestCase(input="1 2", expected="3")],
    )
    assert outcome.verdict == "wrong_answer"
    assert outcome.passed == 0
    assert outcome.results[0].status == "fail"
    assert outcome.results[0].expected == "3"


def test_infinite_loop_times_out() -> None:
    outcome = judge_service.run_python(
        "while True:\n    pass\n",
        tests=[judge_service.TestCase(input="", expected="")],
        timeout_seconds=0.5,
    )
    assert outcome.verdict == "timeout"
    assert outcome.results[0].status == "timeout"


def test_file_read_outside_sandbox_blocked() -> None:
    # 跨平台 CI：POSIX 用真实存在的系统文件，Windows 用 win.ini
    # （POSIX 下 Windows 风格路径会被 realpath 解析为沙箱内相对路径，无法触发越权拦截）
    outside = r"C:\Windows\win.ini" if os.name == "nt" else "/etc/passwd"
    code = f"""
with open(r"{outside}", "r") as handle:
    print(handle.read())
"""
    outcome = judge_service.run_python(
        code, tests=[judge_service.TestCase(input="", expected="")]
    )
    assert outcome.verdict in ("blocked", "runtime_error")
    assert outcome.results[0].passed is False
    assert "sandbox" in outcome.results[0].stderr or outcome.blocked_reason is not None


def test_network_access_blocked() -> None:
    code = """
import socket
socket.socket().connect(("example.com", 80))
print("connected")
"""
    outcome = judge_service.run_python(
        code, tests=[judge_service.TestCase(input="", expected="")]
    )
    assert outcome.verdict == "blocked"
    assert outcome.blocked_reason is not None


def test_dangerous_import_blocked() -> None:
    code = """
import os
print(os.listdir("/"))
"""
    outcome = judge_service.run_python(
        code, tests=[judge_service.TestCase(input="", expected="")]
    )
    assert outcome.verdict == "blocked"
    assert outcome.results[0].status == "forbidden"
    assert "judge sandbox" in outcome.results[0].stderr


def test_subprocess_call_blocked() -> None:
    code = """
import subprocess
print(subprocess.run(["cmd", "/c", "dir"], capture_output=True).stdout)
"""
    outcome = judge_service.run_python(
        code, tests=[judge_service.TestCase(input="", expected="")]
    )
    assert outcome.verdict == "blocked"


def test_oversized_code_rejected() -> None:
    outcome = judge_service.run_python(
        "x = 1\n" * 6000, tests=[judge_service.TestCase(input="", expected="")]
    )
    assert outcome.verdict == "rejected"
