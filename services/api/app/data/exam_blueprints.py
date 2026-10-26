"""地区考卷结构数据（广东 2026 高考/中考）。

用途：模考蓝图、内容对齐与前端说明页面的统一数据源。数据文件为
``app/data/exam_blueprints.json``，来源与置信度见
``docs/verification/GD_2026_ALIGNMENT.md``。

加载期做结构校验（坏数据不许流到前端）：
- 每个 exam 必须有唯一 id、名称、confidence ∈ {verified, partial}；
- 每个科目 score 必须是非负整数；
- 若声明 total_score：无选科规则时科目分值之和必须相等；有 3+1+2 选科规则时
  按「语数英 + 首选 1 门 + 再选 2 门」计算；
- 题组结构里的 count/per_score/scores 与 score 必须自洽。
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, NoReturn, cast

DATA_PATH = Path(__file__).parent / "exam_blueprints.json"
VALID_CONFIDENCE = frozenset({"verified", "partial"})


class ExamBlueprintError(ValueError):
    """考卷结构数据不合法。"""


def _fail(message: str) -> NoReturn:
    raise ExamBlueprintError(message)


def _as_dict(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{where}：必须是对象")
    return cast("dict[str, Any]", value)


def _as_list(value: object, where: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        _fail(f"{where}：必须是非空数组")
    return list(value)


def _as_int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{where}：必须是整数")
    return int(value)


def _score_of(exam_id: str, subject: dict[str, Any]) -> int:
    return _as_int(subject.get("score"), f"{exam_id}/{subject.get('subject')} 的 score")


def _check_structure(exam_id: str, subject: dict[str, Any]) -> None:
    raw_structure = subject.get("structure")
    if raw_structure is None:
        return
    total = 0
    for raw_part in _as_list(raw_structure, f"{exam_id}/{subject.get('subject')} 的 structure"):
        part = _as_dict(raw_part, f"{exam_id} 的 structure 项")
        part_score = _as_int(part.get("score"), f"{exam_id} 的 part score")
        per_score = part.get("per_score")
        count = part.get("count")
        if (
            isinstance(per_score, int)
            and isinstance(count, int)
            and per_score * count != part_score
        ):
            _fail(
                f"{exam_id}/{subject.get('subject')}：{part.get('part')} 的"
                " count×per_score 与 score 不一致"
            )
        scores = part.get("scores")
        if isinstance(scores, list):
            if not all(isinstance(item, int) and not isinstance(item, bool) for item in scores):
                _fail(f"{exam_id}/{subject.get('subject')}：scores 必须是整数数组")
            if sum(cast("list[int]", scores)) != part_score:
                _fail(f"{exam_id}/{subject.get('subject')}：scores 之和与 part score 不一致")
        total += part_score
    if total != _score_of(exam_id, subject):
        _fail(
            f"{exam_id}/{subject.get('subject')}：structure 合计 {total}"
            f" ≠ score {_score_of(exam_id, subject)}"
        )


def _check_selection(exam: dict[str, Any], exam_id: str, subjects: list[dict[str, Any]]) -> int:
    """按 3+1+2 选科规则返回应有的总分；无选科规则时返回 0（表示不适用）。"""
    raw_selection = exam.get("selection")
    if raw_selection is None:
        return 0
    selection = _as_dict(raw_selection, f"{exam_id} 的 selection")
    first = _as_dict(selection.get("first"), f"{exam_id} 的 selection.first")
    second = _as_dict(selection.get("second"), f"{exam_id} 的 selection.second")
    first_from = _as_list(first.get("from"), f"{exam_id} 的 selection.first.from")
    second_from = _as_list(second.get("from"), f"{exam_id} 的 selection.second.from")
    elective = {str(item) for item in first_from} | {str(item) for item in second_from}
    known = {str(item["subject"]) for item in subjects}
    if not elective <= known:
        _fail(f"{exam_id}：selection 引用了不存在的科目 {sorted(elective - known)}")
    first_choose = _as_int(first.get("choose"), f"{exam_id} 的 selection.first.choose")
    first_each = _as_int(first.get("score_each"), f"{exam_id} 的 selection.first.score_each")
    second_choose = _as_int(second.get("choose"), f"{exam_id} 的 selection.second.choose")
    second_each = _as_int(second.get("score_each"), f"{exam_id} 的 selection.second.score_each")
    base = sum(
        _score_of(exam_id, item) for item in subjects if str(item["subject"]) not in elective
    )
    return base + first_choose * first_each + second_choose * second_each


def _check_exam(raw_exam: object) -> None:
    exam = _as_dict(raw_exam, "exam")
    exam_id = exam.get("id")
    if not isinstance(exam_id, str) or not exam_id:
        _fail("exam 缺 id")
    if not isinstance(exam.get("name"), str) or not exam.get("name"):
        _fail(f"{exam_id}：缺 name")
    if exam.get("confidence") not in VALID_CONFIDENCE:
        _fail(f"{exam_id}：confidence 必须是 verified/partial")
    subjects: list[dict[str, Any]] = []
    for raw_subject in _as_list(exam.get("subjects"), f"{exam_id} 的 subjects"):
        subject = _as_dict(raw_subject, f"{exam_id} 的 subject 项")
        if not isinstance(subject.get("subject"), str):
            _fail(f"{exam_id}：subject 项缺 subject 字段")
        _score_of(exam_id, subject)
        _check_structure(exam_id, subject)
        subjects.append(subject)
    raw_total = exam.get("total_score")
    if raw_total is None:
        return
    total_score = _as_int(raw_total, f"{exam_id} 的 total_score")
    selection_total = _check_selection(exam, exam_id, subjects)
    expected = selection_total or sum(item["score"] for item in subjects)
    if expected != total_score:
        _fail(f"{exam_id}：计算总分 {expected} ≠ total_score {total_score}")


def _parse(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("region") != "guangdong":
        _fail("只支持广东（region=guangdong）")
    _as_int(raw.get("year"), "year")
    exams = _as_list(raw.get("exams"), "exams")
    seen: set[str] = set()
    for exam in exams:
        _check_exam(exam)
        exam_id = str(_as_dict(exam, "exam")["id"])
        if exam_id in seen:
            _fail(f"exam id 重复：{exam_id}")
        seen.add(exam_id)
    return raw


@cache
def load_blueprints() -> dict[str, Any]:
    """加载并缓存考卷结构（不可变使用，可直接返回给 API 层）。"""
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return _parse(_as_dict(data, "exam_blueprints.json"))


def get_exam(exam_id: str) -> dict[str, Any] | None:
    """按 id 取单场考试蓝图。"""
    for raw_exam in _as_list(load_blueprints().get("exams"), "exams"):
        exam = _as_dict(raw_exam, "exam")
        if exam.get("id") == exam_id:
            return exam
    return None


__all__ = ["ExamBlueprintError", "get_exam", "load_blueprints"]
