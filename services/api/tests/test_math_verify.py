"""SymPy 数学校验测试（T3.5/T3.7 共用能力）。"""

from __future__ import annotations

from app.services import math_verify


def test_equivalent_simple_expressions() -> None:
    assert math_verify.are_equivalent("2x+3", "3+2x")
    assert math_verify.are_equivalent("x - 1", "-1 + x")


def test_equivalent_polynomials() -> None:
    assert math_verify.are_equivalent("(x+1)^2", "x^2+2x+1")


def test_not_equivalent() -> None:
    assert math_verify.are_equivalent("2", "3") is False


def test_unparseable_falls_back_to_text() -> None:
    assert math_verify.are_equivalent("答案：甲", "答案：甲") is True
    assert math_verify.are_equivalent("答案：甲", "答案：乙") is False


def test_verify_contains_answer_latex() -> None:
    assert math_verify.verify_contains_answer("移项后得到 $x = 2$，所以答案是 2。", "2") is True


def test_verify_contains_answer_after_equals() -> None:
    assert math_verify.verify_contains_answer("计算得 x = 2。", "2") is True


def test_verify_rejects_wrong_answer() -> None:
    assert math_verify.verify_contains_answer("解得 x = 5。", "2") is False


def test_extract_expressions() -> None:
    expressions = math_verify.extract_expressions("由 $x+1$ 可得 x = 2。")
    assert "x+1" in expressions
    assert any(item.startswith("2") for item in expressions)


def test_parse_math_invalid() -> None:
    assert math_verify.parse_math("") is None
    assert math_verify.parse_math("不是数学") is None
