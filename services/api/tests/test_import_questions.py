"""题库导入测试（T2.1）：校验、逐条报错、幂等、多格式。"""

from __future__ import annotations

import json

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import KnowledgePoint, MistakeTag, Question
from app.services.import_service import import_questions, load_records

VALID_ROWS: list[dict[str, object]] = [
    {
        "subject": "math",
        "stage": "junior",
        "qtype": "choice",
        "stem": "计算：2 + 3 = ?",
        "options": {"A": "4", "B": "5", "C": "6", "D": "7"},
        "answer": "B",
        "analysis": "2 + 3 = 5。",
        "difficulty": 1,
        "knowledge_points": ["math.test.t01"],
        "mistake_tags": ["computation"],
    },
    {
        "subject": "math",
        "stage": "junior",
        "qtype": "fill",
        "stem": "计算：10 - 4 = ?",
        "options": None,
        "answer": "6",
        "difficulty": 2,
        "knowledge_points": ["math.test.t02"],
    },
]


async def _seed_reference_data(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """插入测试用知识点与错因标签。"""
    async with sessionmaker() as session:
        session.add(KnowledgePoint(code="math.test.t01", name="测试知识点一", subject="math"))
        session.add(KnowledgePoint(code="math.test.t02", name="测试知识点二", subject="math"))
        session.add(MistakeTag(code="computation", name="计算失误", category="skill"))
        await session.commit()


async def test_import_valid_records(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await _seed_reference_data(sessionmaker)
    rows = [(index, dict(record)) for index, record in enumerate(VALID_ROWS, start=1)]
    async with sessionmaker() as session:
        report = await import_questions(session, rows)
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Question))
    assert report.ok
    assert report.imported == 2
    assert report.invalid == 0
    assert count == 2


async def test_import_invalid_rows_reported_without_interruption(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_reference_data(sessionmaker)
    bad_rows = [
        (3, {"subject": "math", "stem": "太短", "answer": "1"}),  # 题干过短
        (4, {**VALID_ROWS[0], "stem": "选择题缺少选项", "options": None}),  # 缺选项
        (5, {**VALID_ROWS[1], "stem": "知识点不存在", "knowledge_points": ["nope"]}),
        (6, {**VALID_ROWS[1], "stem": "难度越界", "difficulty": 9}),
    ]
    rows = [(1, dict(VALID_ROWS[0])), (2, dict(VALID_ROWS[1])), *bad_rows]
    async with sessionmaker() as session:
        report = await import_questions(session, rows)
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Question))
    assert report.imported == 2, "合法记录应照常入库"
    assert report.invalid == 4
    assert {issue.row for issue in report.issues} == {3, 4, 5, 6}
    assert count == 2


async def test_import_is_idempotent(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await _seed_reference_data(sessionmaker)
    rows = [(1, dict(VALID_ROWS[0]))]
    async with sessionmaker() as session:
        first = await import_questions(session, rows)
        await session.commit()
        second = await import_questions(session, rows)
        await session.commit()
    assert first.imported == 1
    assert second.imported == 0
    assert second.skipped == 1


async def test_validate_only_writes_nothing(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await _seed_reference_data(sessionmaker)
    rows = [(1, dict(VALID_ROWS[0])), (2, dict(VALID_ROWS[1]))]
    async with sessionmaker() as session:
        report = await import_questions(session, rows, validate_only=True)
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Question))
    assert report.ok
    assert report.imported == 2
    assert count == 0


async def test_analysis_filled_when_missing(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    await _seed_reference_data(sessionmaker)
    rows = [(1, dict(VALID_ROWS[1]))]
    async with sessionmaker() as session:
        await import_questions(session, rows)
        await session.commit()
        question = (await session.execute(select(Question))).scalar_one()
    assert question.analysis
    assert "6" in question.analysis


def test_load_records_json(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "q.json"
    path.write_text(json.dumps({"questions": VALID_ROWS}, ensure_ascii=False), encoding="utf-8")
    rows = load_records(path)
    assert len(rows) == 2
    assert rows[0][0] == 1


def test_load_records_csv(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "q.csv"
    path.write_text(
        "subject,stage,qtype,stem,options,answer,difficulty,knowledge_points,mistake_tags\n"
        'math,junior,choice,计算：1 + 1 = ?,A:1|B:2|C:3|D:4,B,1,math.test.t01,computation\n',
        encoding="utf-8",
    )
    rows = load_records(path)
    assert len(rows) == 1
    assert rows[0][0] == 2


def test_load_records_xlsx(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "q.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        ["subject", "qtype", "stem", "options", "answer", "difficulty", "knowledge_points"]
    )
    sheet.append(
        [
            "math",
            "choice",
            "计算：2×3 = ?",
            '{"A":"5","B":"6","C":"7","D":"8"}',
            "B",
            1,
            "math.test.t01",
        ]
    )
    workbook.save(path)
    rows = load_records(path)
    assert len(rows) == 1
    assert rows[0][1]["stem"] == "计算：2×3 = ?"


def test_load_records_unsupported(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "q.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(path)
