"""结构化输出解析的容错测试（队列实测问题的回归）。"""

from __future__ import annotations

import pytest

from app.errors import LlmError
from app.services.llm_json import extract_json_object, parse_json_value


def test_extract_json_object_uses_first_of_two_objects() -> None:
    """模型连发两个对象时，贪婪截取会报 Extra data；应取第一个完整对象。"""
    raw = '结果如下：{"a": 1, "list": [1, 2]}\n{"b": 2}'
    assert extract_json_object(raw, code="TEST_CODE") == {"a": 1, "list": [1, 2]}


def test_extract_json_object_handles_nested_code_fence() -> None:
    raw = '```json\n{"a": {"b": 2}, "c": [1, 2]}\n```\n以上是结果'
    assert extract_json_object(raw, code="TEST_CODE") == {
        "a": {"b": 2},
        "c": [1, 2],
    }


def test_extract_json_object_repairs_unescaped_latex() -> None:
    """数学题里的 ``\\sqrt`` 未按 JSON 转义时也要能解析。"""
    raw = r'{"latex": "\sqrt{3} + \alpha"}'
    assert extract_json_object(raw, code="TEST_CODE") == {
        "latex": r"\sqrt{3} + \alpha"
    }


def test_extract_json_object_tolerates_control_characters() -> None:
    """模型把真实换行写进字符串时（非严格 JSON），宽松解析应接受。"""
    raw = '{"text": "第一行\n第二行"}'
    assert extract_json_object(raw, code="TEST_CODE") == {
        "text": "第一行\n第二行"
    }


def test_parse_json_value_repairs_latex_in_array() -> None:
    r"""出题器返回数组时也要走同样的宽松解析（\sqrt 未转义）。"""
    raw = r'[{"stem": "求 \sqrt{3} 的近似值", "answer": "\sqrt{3}"}]'
    parsed = parse_json_value(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["answer"] == r"\sqrt{3}"


def test_parse_json_value_returns_none_for_truncated_output() -> None:
    assert parse_json_value('{"questions": [{"stem": "未写完') is None


def test_extract_json_object_reports_code_on_garbage() -> None:
    with pytest.raises(LlmError) as excinfo:
        extract_json_object("完全不是 JSON", code="TEST_CODE")
    assert excinfo.value.code == "TEST_CODE"
