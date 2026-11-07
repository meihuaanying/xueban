"""复习卡导出 Anki（吸收 DeepTutor「闪卡导出到 Anki」）。

FSRS 复习卡是学伴自己的调度；导出只把题面/答案交给 Anki 的调度体系，
两边互不干扰。格式用 Anki 文本导入头（#separator/#html/#deck/#tags column），
LaTeX 的 ``$...$`` 转成 ``\\(...\\)`` 以便 Anki 的 MathJax 渲染。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ANKI_HEADER_LINES = ("#separator:tab", "#html:true", "#deck:学伴::复习", "#tags column:3")
ANKI_MEDIA_TYPE = "text/plain;charset=utf-8"
ANKI_FILENAME = "xueban-review-anki.txt"

_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_RE = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)")
_TAG_UNSAFE_RE = re.compile(r"[\s\"']+")

QTYPE_LABELS = {
    "choice": "单选",
    "multi_choice": "多选",
    "fill": "填空",
    "judge": "判断",
    "match": "连线",
    "pick_hanzi": "点选识字",
}


@dataclass(slots=True)
class AnkiCard:
    """一张导出卡片：题面、答案面与 Anki 标签。"""

    front: str
    back: str
    tags: list[str]


def to_mathjax(text: str) -> str:
    """把题库常见的 $...$ / $$...$$ 定界符转成 Anki 认的 MathJax 定界符。

    只有定界符成对出现时才转换；题库文本可能截断或混入普通金额符号，
    单边 $ 原样保留比错误改写更安全。
    """
    if text.count("$$") % 2 != 0:
        display = text
    else:
        display = _DISPLAY_RE.sub(lambda m: r"\[" + m.group(1) + r"\]", text)
    if display.count("$") % 2 != 0:
        return display
    return _INLINE_RE.sub(lambda m: r"\(" + m.group(1) + r"\)", display)


def _cell(text: str) -> str:
    """TSV 单元格转义：换行转 <br>，制表符转空格（#html:true 下 <br> 生效）。"""
    return to_mathjax(text).replace("\r\n", "\n").replace("\n", "<br>").replace("\t", "    ")


def sanitize_tag(name: str) -> str:
    """Anki 标签不允许空白与引号；统一压成下划线。"""
    cleaned = _TAG_UNSAFE_RE.sub("_", name.strip())
    return cleaned.strip("_") or "未命名"


def card_front(stem: str, options: dict[str, str] | None) -> str:
    """题面 = 题干 +（选择题的）选项行。"""
    parts = [stem.strip()]
    for key, value in (options or {}).items():
        parts.append(f"{key}. {value}")
    return "\n".join(parts)


def card_back(answer: str, analysis: str | None) -> str:
    """答案面 = 正确答案 +（可能有题干引用的）解析。"""
    parts = [f"答案：{answer.strip()}"]
    if analysis and analysis.strip():
        parts.append(f"解析：{analysis.strip()}")
    return "\n".join(parts)


def build_anki_txt(cards: list[AnkiCard]) -> str:
    """渲染 Anki 文本导入文件；cards 为空时只有表头（Anki 可空导入）。"""
    lines = list(ANKI_HEADER_LINES)
    for card in cards:
        tags = " ".join(sanitize_tag(tag) for tag in card.tags) or "未命名"
        lines.append(f"{_cell(card.front)}\t{_cell(card.back)}\t{tags}")
    return "\n".join(lines) + "\n"
