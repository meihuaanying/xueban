"""LLM 结构化输出解析：容忍代码块与多余文字。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.errors import LlmError

_JSON_START = re.compile(r"[\[{]")


def _first_json_value(text: str, *, strict: bool = True) -> Any | None:
    """按每个 ``{`` / ``[`` 起点试解析，返回第一个完整 JSON 值。"""
    decoder = json.JSONDecoder(strict=strict)
    for match in _JSON_START.finditer(text):
        try:
            value, _ = decoder.raw_decode(text[match.start() :])
        except ValueError:
            continue
        if isinstance(value, (dict, list)):
            return value
    return None


#: JSON 合法转义之外的 ``\``（数学内容里常见 ``\frac`` / ``\sqrt``）。
_INVALID_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _repair_invalid_escapes(text: str) -> str:
    """把未转义的 LaTeX 反斜杠补成 ``\\\\``，让 json 能解析。"""
    return _INVALID_ESCAPE.sub(r"\\\\", text)


def parse_json_value(raw: str) -> Any | None:
    """从 LLM 输出中提取第一个 JSON 值（对象或数组），失败返回 None。

    依次尝试：代码围栏 → 严格解析 → 宽松解析（字符串内控制字符）→
    修复未转义的 LaTeX 反斜杠后重试。出题器返回数组，因此不能只认对象。
    """
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if fence is not None:
        text = fence.group(1)
    try:
        return json.loads(text)
    except ValueError:
        pass
    value = _first_json_value(text) or _first_json_value(text, strict=False)
    if value is not None:
        return value
    repaired = _repair_invalid_escapes(text)
    if repaired != text:
        return _first_json_value(repaired, strict=False)
    return None


def extract_json_object(raw: str, *, code: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON 对象；失败抛带明确错误码的 LlmError。"""
    payload = parse_json_value(raw)
    if payload is None:
        raise LlmError("模型结构化输出解析失败", code=code, status_code=502)
    if not isinstance(payload, dict):
        raise LlmError("模型结构化输出结构异常", code=code, status_code=502)
    return payload
