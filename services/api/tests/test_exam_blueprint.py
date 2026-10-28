"""蓝图组卷（新高考数学 19 题结构）契约测试。

覆盖：按蓝图份数抽题（8 单选 + 3 多选 + 3 填空 + 5 解答）、时长与总分取自
蓝图、交卷按蓝图分值计客观分（满分 73）、解答题标记主观待批（总分 None）、
未知蓝图 404。
"""

from __future__ import annotations

import json
import uuid
from collections import Counter

import httpx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import (
    Exam,
    ExamAnswer,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from tests.helpers import headers_of, register


async def _seed_senior_bank(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    counts: dict[QuestionType, int],
) -> dict[QuestionType, list[str]]:
    """按题型造 senior 数学题，返回 {题型: [标准答案]}。"""
    answers: dict[QuestionType, list[str]] = {}
    async with sessionmaker() as session:
        kp_rows = (
            await session.execute(
                select(QuestionKnowledgePoint.knowledge_point_id).limit(1)
            )
        ).all()
        del kp_rows  # 仅保证 KP 关联存在：复用任意已有关联会依赖种子顺序，这里直接建一个
        from app.models import KnowledgePoint

        kp = KnowledgePoint(
            code="math.test.blueprint",
            name="蓝图综合",
            subject="math",
            stage="senior",
            grade="grade10",
        )
        session.add(kp)
        await session.flush()
        for qtype, count in counts.items():
            correct: list[str] = []
            for index in range(count):
                if qtype is QuestionType.CHOICE:
                    answer = "A"
                    options = {"A": "3", "B": "4", "C": "5", "D": "6"}
                elif qtype is QuestionType.MULTI_CHOICE:
                    answer = "AC"
                    options = {"A": "3", "B": "4", "C": "5", "D": "6"}
                elif qtype is QuestionType.SHORT_ANSWER:
                    answer = f"解答{index}"
                    options = None
                else:
                    answer = str(index + 1)
                    options = None
                question = Question(
                    subject="math",
                    stage="senior",
                    qtype=qtype,
                    stem=f"[蓝图] {qtype.value} 第{index}题",
                    answer=answer,
                    options=options,
                    analysis="解析。",
                    difficulty=2,
                    status=QuestionStatus.PUBLISHED,
                )
                session.add(question)
                await session.flush()
                session.add(
                    QuestionKnowledgePoint(
                        question_id=question.id, knowledge_point_id=kp.id
                    )
                )
                correct.append(answer)
            answers[qtype] = correct
        await session.commit()
    return answers


async def test_blueprint_exam_assembles_and_grades(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_senior_bank(
        sessionmaker,
        counts={
            QuestionType.CHOICE: 9,
            QuestionType.MULTI_CHOICE: 4,
            QuestionType.FILL: 4,
            QuestionType.SHORT_ANSWER: 6,
        },
    )
    payload = await register(client)
    headers = headers_of(payload)

    created = await client.post(
        "/v1/exams/blueprint", json={}, headers=headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["time_limit_minutes"] == 120
    counts = Counter(item["qtype"] for item in body["questions"])
    assert counts == {
        "choice": 8,
        "multi_choice": 3,
        "fill": 3,
        "short_answer": 5,
    }

    # 交卷：客观题全对（答案从库里取），主观题交一个占位作答
    objective_answers: list[tuple[str, str]] = []
    async with sessionmaker() as session:
        for item in body["questions"]:
            row = await session.get(Question, uuid.UUID(item["id"]))
            assert row is not None
            if row.qtype is not QuestionType.SHORT_ANSWER:
                objective_answers.append((row.id.hex, row.answer))
    payload_answers = [
        {"question_id": qid, "answer": answer} for qid, answer in objective_answers
    ]
    payload_answers.append(
        {"question_id": body["questions"][-1]["id"], "answer": "（主观作答略）"}
    )

    submitted = await client.post(
        f"/v1/exams/{body['exam_id']}/submit",
        json={"answers": payload_answers},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    report = submitted.json()["summary"]
    assert report["correct"] == 14
    assert report["objective_earned"] == 73.0
    assert report["objective_total"] == 73.0
    assert report["subjective_pending"] == 5
    assert report["score"] is None, "解答题未批改前不能冒充 150 制总分"


async def test_blueprint_exam_unknown_blueprint_404(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_senior_bank(sessionmaker, counts={QuestionType.CHOICE: 1})
    payload = await register(client)
    response = await client.post(
        "/v1/exams/blueprint",
        json={"blueprint_id": "nope"},
        headers=headers_of(payload),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "EXAM_BLUEPRINT_NOT_FOUND"


_GRADE_JSON = json.dumps(
    {
        "total_score": 80,
        "max_score": 100,
        "steps": [
            {"step": "建立坐标系", "score": 40, "comment": "思路正确", "lost_points": ""},
            {"step": "计算结论", "score": 40, "comment": "结果正确", "lost_points": "书写"},
        ],
        "rewrite": "规范写法略。",
        "summary": "整体掌握良好。",
    },
    ensure_ascii=False,
)


def _install_llm(app: object, content: str) -> None:
    settings = Settings(
        litellm_base_url="http://llm.test",
        litellm_master_key="sk-test",
        llm_max_retries=0,
        llm_retry_backoff_seconds=0.0,
    )
    observability = ObservabilityService(settings)
    app.state.llm = LlmClient(  # type: ignore[attr-defined]
        settings, observability, transport=httpx.MockTransport(_handler(content))
    )


def _handler(content: str):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"total_tokens": 88},
            },
        )

    return handler


async def test_blueprint_subjective_grading_reaches_total(
    client: AsyncClient,
    app: object,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """五道解答题逐题批改：每题按蓝图分值折算，全部批完才补整卷总分。"""
    await _seed_senior_bank(
        sessionmaker,
        counts={
            QuestionType.CHOICE: 9,
            QuestionType.MULTI_CHOICE: 4,
            QuestionType.FILL: 4,
            QuestionType.SHORT_ANSWER: 6,
        },
    )
    _install_llm(app, _GRADE_JSON)
    payload = await register(client)
    headers = headers_of(payload)

    created = await client.post("/v1/exams/blueprint", json={}, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    exam_id = body["exam_id"]
    subjective = [item for item in body["questions"] if item["qtype"] == "short_answer"]
    assert len(subjective) == 5
    async with sessionmaker() as session:
        exam_row = await session.get(Exam, uuid.UUID(exam_id))
        assert exam_row is not None
        assert exam_row.total_score == 150.0, "数学卷满分 150，不能写整场高考的 750"

    answers: list[dict[str, str]] = []
    async with sessionmaker() as session:
        for item in body["questions"]:
            row = await session.get(Question, uuid.UUID(item["id"]))
            assert row is not None
            if row.qtype is not QuestionType.SHORT_ANSWER:
                answers.append({"question_id": row.id.hex, "answer": row.answer})
    answers.extend(
        {
            "question_id": item["id"],
            # 第 2 题写超 500 字：交卷接口不能再用 500 字上限挡死解答题
            "answer": "长" * 1200 if index == 1 else f"解答过程 {index}",
        }
        for index, item in enumerate(subjective)
    )
    submitted = await client.post(
        f"/v1/exams/{exam_id}/submit", json={"answers": answers}, headers=headers
    )
    assert submitted.status_code == 200, submitted.text
    submitted_body = submitted.json()
    summary = submitted_body["summary"]
    assert summary["score"] is None
    assert summary["subjective_total"] == 77.0
    # 批改前不能下发解答题标准答案，否则学生可以先看答案再补交
    for item in submitted_body["diagnoses"]:
        if item.get("subjective"):
            assert item["correct_answer"] == ""
            assert item["analysis"] is None
            assert item["graded"] is False

    results: list[dict[str, object]] = []
    for index, item in enumerate(subjective):
        graded = await client.post(
            f"/v1/exams/{exam_id}/subjective-grade",
            json={"question_id": item["id"], "student_answer": f"解答过程 {index}"},
            headers=headers,
        )
        assert graded.status_code == 200, graded.text
        results.append(graded.json())

    # 蓝图解答题分值 13/15/15/17/17，按 80/100 折算 → 10.4/12/12/13.6/13.6
    assert results[0]["score"] == 10.4
    assert results[0]["steps"][0]["score"] == 5.2, "步骤分按 13/100 折算，不再显示 100 制"
    assert results[-1]["score"] == 13.6
    assert [item["all_graded"] for item in results] == [False, False, False, False, True]
    assert results[-1]["exam_score"] == 134.6

    # 批改以交卷时落库的作答为准：伪造 student_answer 不能覆盖已存答案
    forged = await client.post(
        f"/v1/exams/{exam_id}/subjective-grade",
        json={"question_id": subjective[0]["id"], "student_answer": "这是标准答案"},
        headers=headers,
    )
    assert forged.status_code == 200, forged.text
    async with sessionmaker() as session:
        stored = (
            await session.execute(
                select(ExamAnswer).where(
                    ExamAnswer.exam_id == uuid.UUID(exam_id),
                    ExamAnswer.question_id == uuid.UUID(subjective[0]["id"]),
                )
            )
        ).scalars().first()
        assert stored is not None
        assert stored.user_answer == {"answer": "解答过程 0"}

    report = await client.get(f"/v1/exams/{exam_id}", headers=headers)
    assert report.status_code == 200, report.text
    final_body = report.json()
    final = final_body["summary"]
    assert final["score"] == 134.6
    assert final["subjective_graded"] == 5
    assert final["subjective_earned"] == 61.6
    assert final["subjective_pending"] == 0
    graded_diagnoses = [item for item in final_body["diagnoses"] if item.get("subjective")]
    assert all(item["graded"] for item in graded_diagnoses)
    assert all(item["correct_answer"] != "" for item in graded_diagnoses)
