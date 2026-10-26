"""全学段年级口径一致性（2026-10 内容扩展）。

这组用例是「小初高内容做完」的结构性底线：年级 → 学段只有一份权威映射
（``STAGE_FOR_GRADE``），课程树里每个知识点都必须落在 12 个合法年级内，
且每学科在**其应覆盖的年级**都有可出题的内容（物理八年级起、化学九年级起、
其余选考科目七年级起）。全是纯函数断言，不依赖数据库。
"""

from __future__ import annotations

from collections import Counter

from app.data.curriculum import (
    GRADE_NAMES,
    STAGE_FOR_GRADE,
    VALID_STAGES,
    all_curricula,
    grades_for_stage,
)

STAGES = ("primary", "junior", "senior")
EXPECTED_GRADES = {f"grade{i}" for i in range(1, 13)}

#: 每学科必须覆盖的年级（广东口径：语数英小学起；物理八年级起、化学九年级起）。
SUBJECT_GRADES: dict[str, set[str]] = {
    "chinese": EXPECTED_GRADES,
    "math": EXPECTED_GRADES,
    "english": EXPECTED_GRADES,
    "physics": {f"grade{i}" for i in range(8, 13)},
    "chemistry": {f"grade{i}" for i in range(9, 13)},
    "biology": {f"grade{i}" for i in (7, 8, 10, 11, 12)},
    "history": {f"grade{i}" for i in range(7, 13)},
    # 广东地理在八年级结课（学业水平考试），九年级不开课
    "geography": {f"grade{i}" for i in (7, 8, 10, 11, 12)},
    "politics": {f"grade{i}" for i in range(7, 13)},
}


def test_grade_names_and_stage_mapping_cover_same_keys() -> None:
    """两个映射的键集合必须完全一致，且学段取值只有 primary/junior/senior。"""
    assert set(GRADE_NAMES) == set(STAGE_FOR_GRADE)
    assert set(STAGE_FOR_GRADE.values()) == VALID_STAGES
    assert set(STAGES) == VALID_STAGES
    assert set(GRADE_NAMES) == EXPECTED_GRADES


def test_grades_for_stage_partitions_all_grades() -> None:
    """三个学段返回的年级并集 == GRADE_NAMES 键集合，且互相不重复。"""
    collected = [grade for stage in STAGES for grade in grades_for_stage(stage)]
    assert len(collected) == len(set(collected)), "同一个年级不能出现在多个学段"
    assert set(collected) == set(GRADE_NAMES)
    # grades_for_stage 按升序返回；拼接后应等于 grade1..grade12 的声明顺序
    assert collected == list(GRADE_NAMES)


def test_every_curriculum_point_has_known_grade() -> None:
    """三科课程树里的所有知识点，其 grade 都必须在 GRADE_NAMES 内。"""
    unknown: list[str] = []
    for curriculum in all_curricula():
        for point in curriculum.points:
            if point.grade not in GRADE_NAMES:
                unknown.append(f"{curriculum.subject}:{point.id}={point.grade}")
    assert not unknown, f"存在未知年级：{unknown}"


def test_every_subject_has_points_in_expected_grades() -> None:
    """每学科在其应覆盖的年级里知识点数量都必须大于 0。"""
    counts: Counter[tuple[str, str]] = Counter(
        (curriculum.subject, point.grade)
        for curriculum in all_curricula()
        for point in curriculum.points
    )
    subjects = [curriculum.subject for curriculum in all_curricula()]
    assert set(subjects) == set(SUBJECT_GRADES), "学科注册与预期清单不一致"
    empty = [
        f"{subject}/{grade}"
        for subject in subjects
        for grade in sorted(SUBJECT_GRADES[subject])
        if counts[(subject, grade)] <= 0
    ]
    assert not empty, f"以下学科/年级没有知识点：{empty}"
