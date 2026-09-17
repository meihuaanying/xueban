"""LLM 结构化输出解析：容忍代码块与多余文字。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.errors import LlmError


def extract_json_object(raw: str, *, code: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON 对象；失败抛带明确错误码的 LlmError。"""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence is not None:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace is not None:
            text = brace.group(0)
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise LlmError("模型结构化输出解析失败", code=code, status_code=502) from exc
    if not isinstance(payload, dict):
        raise LlmError("模型结构化输出结构异常", code=code, status_code=502)
    return payload
