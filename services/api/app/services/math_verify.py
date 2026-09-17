"""数学解答机器校验（SymPy）：等价性抽检与文本表达式提取。"""

from __future__ import annotations

import re
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMATIONS = (*standard_transformations, implicit_multiplication_application)

# 从文本中提取候选数学表达式的保守模式：
#  - $...$ 行内公式
#  - "= <表达式>"（等号后的结果）
_INLINE_MATH = re.compile(r"\$([^$]{1,120})\$")
_AFTER_EQUALS = re.compile(r"=\s*([0-9a-zA-Z\\^_{}()+\-*/.,\s]{1,60})")
_BARE_NUMBERS = re.compile(r"-?\d+(?:\.\d+)?")


_MATH_CHARS = re.compile(r"^[\d\s+\-*/().^_,a-zA-Z{}]+$")


def parse_math(text: str) -> Any | None:
    """尝试把文本解析为 SymPy 表达式；失败返回 None。"""
    cleaned = text.strip().replace("^", "**").replace("\\", "")
    if not cleaned or not _MATH_CHARS.match(cleaned):
        return None
    try:
        return parse_expr(cleaned, transformations=TRANSFORMATIONS, evaluate=True)
    except (sympy.SympifyError, SyntaxError, TypeError, ValueError, ZeroDivisionError):
        return None


def are_equivalent(left: str, right: str) -> bool:
    """两段数学文本是否等价；不可解析时退化为归一化字符串比较。"""
    expr_left = parse_math(left)
    expr_right = parse_math(right)
    if expr_left is None or expr_right is None:
        return _normalize_text(left) == _normalize_text(right)
    try:
        return bool(sympy.simplify(expr_left - expr_right) == 0)
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def extract_expressions(text: str) -> list[str]:
    """提取文本中的候选数学表达式（$...$、等号后的结果；兜底裸数字）。"""
    candidates: list[str] = [match.strip() for match in _INLINE_MATH.findall(text)]
    for match in _AFTER_EQUALS.findall(text):
        fragment = match.strip().rstrip("。,.，；;")
        if fragment:
            candidates.append(fragment)
    if not candidates:
        candidates.extend(_BARE_NUMBERS.findall(text))
    return [item for item in candidates if item]


def verify_contains_answer(solution_text: str, answer: str) -> bool:
    """校验解答文本中是否出现与标准答案等价的结果（SymPy 抽检）。"""
    expected = parse_math(answer)
    if expected is None:
        return _normalize_text(answer) in _normalize_text(solution_text)
    for candidate in extract_expressions(solution_text):
        parsed = parse_math(candidate)
        if parsed is None:
            continue
        try:
            if sympy.simplify(parsed - expected) == 0:
                return True
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    return False


def _normalize_text(value: str) -> str:
    """文本归一化（去空白、全角转半角、大小写统一）。"""
    translation = str.maketrans("０１２３４５６７８９（）．，", "0123456789().,")
    return re.sub(r"\s+", "", value.translate(translation).lower())
