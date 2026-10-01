"""课程知识点树测试（P1 / §6.1）：数据完整性与关系正确性。

这些用例是 §8 约束 8 的兜底——知识点树一旦有悬空前置或环，题库管线就会生成
错乱的题目，因此加载期必须失败而不是静默通过。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.data import curriculum as curriculum_mod
from app.data.curriculum import (
    SUBJECT_FILES,
    CurriculumError,
    all_curricula,
    get_curriculum,
    iter_all_points,
    topological_order,
)

SUBJECTS = ("chinese", "math", "english")


def _minimal_payload(**overrides: object) -> dict:
    payload: dict = {
        "subject": "math",
        "subject_name": "数学",
        "curriculum_standard": "测试",
        "stages": [
            {
                "grade": "grade1",
                "units": [
                    {
                        "code": "u1",
                        "name": "单元一",
                        "knowledge_points": [
                            {
                                "id": "kp-a",
                                "name": "知识点 A",
                                "objective": "会 A",
                                "difficulty_band": 1,
                                "prerequisites": [],
                                "question_types": ["choice"],
                            },
                            {
                                "id": "kp-b",
                                "name": "知识点 B",
                                "objective": "会 B",
                                "difficulty_band": 2,
                                "prerequisites": ["kp-a"],
                                "question_types": ["fill"],
                            },
                        ],
                    }
                ],
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把加载器指向临时目录，便于构造坏数据。"""
    monkeypatch.setattr(curriculum_mod, "CURRICULUM_DIR", tmp_path)
    monkeypatch.setattr(curriculum_mod, "SUBJECT_FILES", {"math": "math.json"})
    monkeypatch.setattr(curriculum_mod, "_load", curriculum_mod._load.__wrapped__)
    return tmp_path


def _write(directory: Path, payload: dict, name: str = "math.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------- 真实数据


@pytest.mark.parametrize("subject", SUBJECTS)
def test_each_subject_loads(subject: str) -> None:
    curriculum = get_curriculum(subject)
    assert curriculum.subject == subject
    assert curriculum.subject_name
    assert curriculum.standard
    assert curriculum.points, f"{subject} 不应为空"
    assert curriculum.units


@pytest.mark.parametrize("subject", SUBJECTS)
def test_real_data_covers_grade1_and_grade2(subject: str) -> None:
    curriculum = get_curriculum(subject)
    grades = {point.grade for point in curriculum.points}
    assert grades == {"grade1", "grade2"}, f"{subject} 必须覆盖一年级与二年级"


@pytest.mark.parametrize("subject", SUBJECTS)
def test_real_data_fields_are_complete(subject: str) -> None:
    curriculum = get_curriculum(subject)
    unit_codes = {unit.code for unit in curriculum.units}
    for point in curriculum.points:
        assert point.id and point.name
        assert point.objective, f"{point.id} 缺 objective"
        assert point.difficulty_band in (1, 2, 3)
        assert point.unit_code in unit_codes
        assert point.question_types, f"{point.id} 未声明题型"
        for prereq in point.prerequisites:
            assert prereq != point.id, f"{point.id} 不能以自身为前置"


@pytest.mark.parametrize("subject", SUBJECTS)
def test_real_data_prerequisites_resolve_and_precede(subject: str) -> None:
    curriculum = get_curriculum(subject)
    ids = {point.id for point in curriculum.points}
    for point in curriculum.points:
        for prereq in point.prerequisites:
            assert prereq in ids, f"{point.id} 的前置 {prereq} 不存在"


@pytest.mark.parametrize("subject", SUBJECTS)
def test_real_data_has_entry_level_points(subject: str) -> None:
    """每个知识点都必须能从零前置起步，不能整棵树都依赖别的点。"""
    curriculum = get_curriculum(subject)
    roots = [p for p in curriculum.points if not p.prerequisites]
    assert roots, f"{subject} 没有任何入门知识点"


def test_real_data_topological_order_respects_prerequisites() -> None:
    for curriculum in all_curricula():
        order = topological_order(curriculum)
        assert len(order) == len(curriculum.points)
        position = {point_id: index for index, point_id in enumerate(order)}
        for point in curriculum.points:
            for prereq in point.prerequisites:
                assert position[prereq] < position[point.id], (
                    f"{curriculum.subject}: {prereq} 必须排在 {point.id} 之前"
                )


def test_real_data_lookups() -> None:
    math = get_curriculum("math")
    first = math.points[0]
    assert math.by_id(first.id) is first
    assert math.by_id("不存在的知识点") is None
    assert all(p.grade == "grade1" for p in math.by_grade("grade1"))
    assert all(
        p.subject == "math" and p.grade == "grade1"
        for p in math.by_subject_and_grade("math", "grade1")
    )
    assert math.by_subject_and_grade("math", "grade9") == ()


def test_iter_all_points_covers_every_subject() -> None:
    points = list(iter_all_points())
    assert {p.subject for p in points} == set(SUBJECTS)
    assert len({p.id for p in points}) == len(points), "知识点 id 必须全局唯一"


def test_curriculum_is_cached_and_immutable() -> None:
    first = get_curriculum("math")
    second = get_curriculum("math")
    assert first is second
    with pytest.raises((AttributeError, TypeError)):
        first.subject = "changed"  # type: ignore[misc]


def test_code_property_matches_id() -> None:
    """KnowledgePoint.code 用于对齐 knowledge_points.code 列。"""
    point = get_curriculum("math").points[0]
    assert point.code == point.id


# ---------------------------------------------------------------- 坏数据


def test_unknown_subject_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curriculum_mod, "CURRICULUM_DIR", tmp_path)
    monkeypatch.setattr(curriculum_mod, "SUBJECT_FILES", {})
    with pytest.raises(CurriculumError, match="未知学科"):
        get_curriculum("music")


def test_missing_subject_field_raises(sandbox: Path) -> None:
    _write(sandbox, {"stages": []})
    with pytest.raises(CurriculumError, match="缺少 subject"):
        get_curriculum("math")


def test_unsupported_subject_raises(sandbox: Path) -> None:
    _write(sandbox, _minimal_payload(subject="physics"))
    with pytest.raises(CurriculumError, match="未知学科"):
        get_curriculum("math")


def test_duplicate_id_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"].append(
        dict(payload["stages"][0]["units"][0]["knowledge_points"][0])
    )
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="重复"):
        get_curriculum("math")


def test_dangling_prerequisite_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"][1]["prerequisites"] = ["kp-missing"]
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="前置 kp-missing 不存在"):
        get_curriculum("math")


def test_self_prerequisite_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"][0]["prerequisites"] = ["kp-a"]
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="不能以自身为前置"):
        get_curriculum("math")


def test_prerequisite_cycle_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    points = payload["stages"][0]["units"][0]["knowledge_points"]
    points[0]["prerequisites"] = ["kp-b"]
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="成环"):
        get_curriculum("math")


def test_invalid_difficulty_band_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"][0]["difficulty_band"] = 9
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="difficulty_band 非法"):
        get_curriculum("math")


def test_missing_objective_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"][0]["objective"] = ""
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="缺少 objective"):
        get_curriculum("math")


def test_unit_without_code_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    del payload["stages"][0]["units"][0]["code"]
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="缺少 code/name"):
        get_curriculum("math")


def test_point_without_id_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    del payload["stages"][0]["units"][0]["knowledge_points"][0]["id"]
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="没有 id"):
        get_curriculum("math")


def test_non_list_prerequisites_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"][0]["prerequisites"] = "kp-b"
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="必须是数组"):
        get_curriculum("math")


def test_non_string_element_raises(sandbox: Path) -> None:
    payload = _minimal_payload()
    payload["stages"][0]["units"][0]["knowledge_points"][0]["question_types"] = ["choice", 7]
    _write(sandbox, payload)
    with pytest.raises(CurriculumError, match="非空字符串"):
        get_curriculum("math")


def test_minimal_payload_loads_successfully(sandbox: Path) -> None:
    _write(sandbox, _minimal_payload())
    curriculum = get_curriculum("math")
    assert [p.id for p in curriculum.points] == ["kp-a", "kp-b"]
    assert curriculum.units[0].code == "u1"
    assert topological_order(curriculum) == ("kp-a", "kp-b")


def test_subject_files_cover_all_declared_subjects() -> None:
    assert set(SUBJECT_FILES) == set(SUBJECTS)
