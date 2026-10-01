"""课程知识点树加载器（P1 / §6.1）。

数据形态：`app/data/curriculum/*.json`，学科一份，结构为
`schema_version → subject → stages[] → units[] → knowledge_points[]`。

与既有 `app/data/knowledge_graph.py` 的关系：后者服务「章节 → 基础知识点 →
基础巩固/综合应用」的自动展开图谱（stage 用 elementary/junior/senior 等学段名），
本模块服务 P1 一二年级语数英的**人教版大纲**目录，用显式 `grade` 字段，两者互不覆盖。

本模块只做「加载 + 结构校验」，不做业务判断；校验失败一律抛
`CurriculumError`，保证坏数据不会流到题库管线与前端（§8 约束 8：内容必须先过校验）。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

CURRICULUM_DIR = Path(__file__).parent

SUBJECT_FILES: dict[str, str] = {
    "chinese": "chinese.json",
    "math": "math.json",
    "english": "english.json",
}

VALID_DIFFICULTY_BANDS = frozenset({1, 2, 3})


class CurriculumError(ValueError):
    """课程数据不合法（结构错误 / 关系断裂 / 字段缺失）。"""


@dataclass(frozen=True, slots=True)
class KnowledgePoint:
    """一个可出题、可挂讲解的最小知识点。"""

    id: str
    name: str
    subject: str
    grade: str
    unit_code: str
    unit_name: str
    objective: str
    question_types: tuple[str, ...]
    difficulty_band: int
    prerequisites: tuple[str, ...]

    @property
    def code(self) -> str:
        """与 KnowledgePoint.code 对齐的稳定编码。"""
        return self.id


@dataclass(frozen=True, slots=True)
class Unit:
    """教材单元。"""

    code: str
    name: str
    subject: str
    grade: str


@dataclass(frozen=True, slots=True)
class Curriculum:
    """单学科的完整课程树。"""

    subject: str
    subject_name: str
    standard: str
    points: tuple[KnowledgePoint, ...]
    units: tuple[Unit, ...]

    def by_id(self, point_id: str) -> KnowledgePoint | None:
        return next((p for p in self.points if p.id == point_id), None)

    def by_grade(self, grade: str) -> tuple[KnowledgePoint, ...]:
        return tuple(p for p in self.points if p.grade == grade)

    def by_subject_and_grade(self, subject: str, grade: str) -> tuple[KnowledgePoint, ...]:
        return tuple(p for p in self.points if p.subject == subject and p.grade == grade)

    def __iter__(self) -> Iterator[KnowledgePoint]:
        return iter(self.points)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CurriculumError(message)


def _require_str(value: Any, where: str) -> str:
    """要求是非空字符串，否则抛出带定位信息的错误。

    单独抽出来是为了让 mypy --strict 能把 JSON 的 Any 收窄成 str，
    避免每个调用点都要写 isinstance 判断。
    """
    if not isinstance(value, str) or not value.strip():
        raise CurriculumError(where)
    return value


def _as_str_list(value: Any, where: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{where}：question_types/prerequisites 必须是数组")
    _require(
        all(isinstance(item, str) and item.strip() for item in value),
        f"{where}：数组元素必须是非空字符串",
    )
    return tuple(value)


def _parse_subject(path: Path) -> Curriculum:
    raw = json.loads(path.read_text(encoding="utf-8"))
    subject = _require_str(raw.get("subject"), f"{path.name}：缺少 subject")
    _require(subject in SUBJECT_FILES, f"{path.name}：未知学科 {subject}")

    points: list[KnowledgePoint] = []
    units: list[Unit] = []
    seen_ids: dict[str, str] = {}

    for stage in raw.get("stages", []):
        grade = _require_str(stage.get("grade"), f"{path.name}：stage 缺少 grade")
        for unit in stage.get("units", []):
            unit_code = _require_str(
                unit.get("code"), f"{path.name}：{grade} 下的单元缺少 code/name"
            )
            unit_name = _require_str(
                unit.get("name"), f"{path.name}：{grade} 下的单元缺少 code/name"
            )
            units.append(Unit(unit_code, unit_name, subject, grade))
            for kp in unit.get("knowledge_points", []):
                point_id = _require_str(
                    kp.get("id"), f"{path.name}：{unit_code} 下存在没有 id 的知识点"
                )
                _require(
                    point_id not in seen_ids,
                    f"{path.name}：知识点 id 重复 {point_id}"
                    f"（已出现于 {seen_ids.get(point_id)}）",
                )
                seen_ids[point_id] = unit_code
                band = kp.get("difficulty_band")
                _require(
                    isinstance(band, int) and band in VALID_DIFFICULTY_BANDS,
                    f"{path.name}：{point_id} 的 difficulty_band 非法：{band}",
                )
                objective = _require_str(
                    kp.get("objective"), f"{path.name}：{point_id} 缺少 objective"
                )
                name = _require_str(kp.get("name"), f"{path.name}：{point_id} 缺少 name")
                points.append(
                    KnowledgePoint(
                        id=point_id,
                        name=name,
                        subject=subject,
                        grade=grade,
                        unit_code=unit_code,
                        unit_name=unit_name,
                        objective=objective,
                        question_types=_as_str_list(
                            kp.get("question_types", []), f"{point_id}.question_types"
                        ),
                        difficulty_band=band,
                        prerequisites=_as_str_list(
                            kp.get("prerequisites", []), f"{point_id}.prerequisites"
                        ),
                    )
                )

    curriculum = Curriculum(
        subject=subject,
        subject_name=raw.get("subject_name", subject),
        standard=raw.get("curriculum_standard", ""),
        points=tuple(points),
        units=tuple(units),
    )
    _validate_prerequisites(curriculum, path.name)
    return curriculum


def _validate_prerequisites(curriculum: Curriculum, source: str) -> None:
    """前置关系校验：不得悬空、不得自指、不得成环。"""
    ids = {p.id for p in curriculum.points}
    graph: dict[str, tuple[str, ...]] = {}
    for point in curriculum.points:
        for prereq in point.prerequisites:
            _require(prereq in ids, f"{source}：{point.id} 的前置 {prereq} 不存在")
            _require(prereq != point.id, f"{source}：{point.id} 不能以自身为前置")
            graph.setdefault(point.id, ())
        graph[point.id] = point.prerequisites

    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str, trail: tuple[str, ...]) -> None:
        if node in done:
            return
        _require(node not in visiting, f"{source}：前置关系成环 {' → '.join((*trail, node))}")
        visiting.add(node)
        for nxt in graph.get(node, ()):
            visit(nxt, (*trail, node))
        visiting.discard(node)
        done.add(node)

    for point in curriculum.points:
        visit(point.id, ())


@cache
def _load(subject: str) -> Curriculum:
    filename = SUBJECT_FILES.get(subject)
    if filename is None:
        raise CurriculumError(f"未知学科：{subject}")
    return _parse_subject(CURRICULUM_DIR / filename)


def get_curriculum(subject: str) -> Curriculum:
    """加载并缓存单学科课程树（结果不可变，可安全共享）。"""
    return _load(subject)


def all_curricula() -> tuple[Curriculum, ...]:
    """按 SUBJECT_FILES 顺序加载全部学科。"""
    return tuple(_load(subject) for subject in SUBJECT_FILES)


def iter_all_points() -> Iterator[KnowledgePoint]:
    """按学科顺序遍历全部知识点。"""
    for curriculum in all_curricula():
        yield from curriculum.points


def topological_order(curriculum: Curriculum) -> tuple[str, ...]:
    """先修顺序（前置在前），便于按顺序出题、逐步解锁。"""
    ordered: list[str] = []
    state: dict[str, int] = {}

    def visit(node_id: str) -> None:
        if state.get(node_id) == 2:
            return
        point = curriculum.by_id(node_id)
        if point is None or state.get(node_id) == 1:
            return
        state[node_id] = 1
        for prereq in point.prerequisites:
            visit(prereq)
        state[node_id] = 2
        ordered.append(node_id)

    for point in curriculum.points:
        visit(point.id)
    return tuple(ordered)
