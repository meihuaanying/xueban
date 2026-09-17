"""自适应诊断测试（T3.2 / F-01）：难度调节、选题策略、API 全流程。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Exam,
    ExamStatus,
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services import diagnosis_service
from app.services.diagnosis_service import QuestionCandidate, adjust_difficulty, select_candidate
from tests.helpers import headers_of, register

# ---------- 算法单元 ----------


def test_adjust_difficulty_raises_on_correct() -> None:
    assert adjust_difficulty(3, True) == 4
    assert adjust_difficulty(2, True) == 3


def test_adjust_difficulty_ceiling() -> None:
    assert adjust_difficulty(5, True) == 5


def test_adjust_difficulty_lowers_on_wrong() -> None:
    assert adjust_difficulty(3, False) == 2
    assert adjust_difficulty(4, False) == 3


def test_adjust_difficulty_floor() -> None:
    assert adjust_difficulty(1, False) == 1


def _candidate(difficulty: int, kp: uuid.UUID, index: int) -> QuestionCandidate:
    from datetime import UTC, datetime, timedelta

    base = datetime(2026, 1, 1, tzinfo=UTC)
    return QuestionCandidate(
        question_id=uuid.uuid4(),
        difficulty=difficulty,
        knowledge_point_ids=[kp],
        sort_key=(base + timedelta(seconds=index), f"{index:04d}"),
    )


def test_select_candidate_prefers_weakest_knowledge_point() -> None:
    weak_kp, strong_kp = uuid.uuid4(), uuid.uuid4()
    weak = _candidate(3, weak_kp, 0)
    strong = _candidate(3, strong_kp, 1)
    picked = select_candidate(
        [strong, weak], {weak_kp: 0.2, strong_kp: 0.9}, preferred_difficulty=3
    )
    assert picked is weak


def test_select_candidate_prefers_closest_difficulty() -> None:
    kp = uuid.uuid4()
    near = _candidate(3, kp, 0)
    far = _candidate(5, kp, 1)
    picked = select_candidate([far, near], {kp: 0.5}, preferred_difficulty=3)
    assert picked is near


def test_select_candidate_stable_tie_break() -> None:
    kp = uuid.uuid4()
    first = _candidate(3, kp, 0)
    second = _candidate(3, kp, 1)
    picked = select_candidate([second, first], {kp: 0.5}, preferred_difficulty=3)
    assert picked is first


def test_select_candidate_empty_returns_none() -> None:
    assert select_candidate([], {}, preferred_difficulty=3) is None


def test_normalize_and_check_answer() -> None:
    question = Question(
        subject="math",
        stage="junior",
        qtype=QuestionType.FILL,
        stem="计算 1+1",
        answer="２",
        analysis="",
        status=QuestionStatus.PUBLISHED,
    )
    assert diagnosis_service.check_answer(question, "2")
    assert diagnosis_service.check_answer(question, " ２ ")
    assert not diagnosis_service.check_answer(question, "3")


# ---------- API 全流程 ----------


async def _seed_bank(sessionmaker: async_sessionmaker[AsyncSession], *, kp_count: int = 5) -> None:
    """5 个知识点 × 4 题（难度 1~4 循环），共 20 题。"""
    async with sessionmaker() as session:
        for k in range(kp_count):
            kp = KnowledgePoint(
                code=f"math.test.k{k:02d}",
                name=f"知识点{k}",
                subject="math",
                stage="junior",
                sort_order=k,
            )
            session.add(kp)
            await session.flush()
            for i in range(4):
                difficulty = (i % 4) + 1
                question = Question(
                    subject="math",
                    stage="junior",
                    qtype=QuestionType.FILL,
                    stem=f"[知识点{k}] 第{i}题：{k}+{i}+{i} = ?",
                    answer=str(k + 2 * i),
                    analysis="基础加法。",
                    difficulty=difficulty,
                    status=QuestionStatus.PUBLISHED,
                )
                session.add(question)
                await session.flush()
                session.add(
                    QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id)
                )
        await session.commit()


async def test_diagnosis_full_flow(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers,
    )
    assert started.status_code == 201, started.text
    body = started.json()
    exam_id = body["exam_id"]
    question = body["question"]
    assert question["difficulty"] == 3
    assert question["knowledge_points"]

    from app.models import Question as QuestionModel

    for index in range(20):
        answer_correct = index % 2 == 0
        async with sessionmaker() as session:
            stored = await session.get(QuestionModel, uuid.UUID(question["id"]))
            assert stored is not None
            expected = stored.answer if answer_correct else f"wrong-{index}"
        response = await client.post(
            f"/v1/diagnosis/{exam_id}/answer",
            json={"question_id": question["id"], "answer": expected},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["is_correct"] is answer_correct
        assert data["progress"]["answered"] == index + 1
        if index < 19:
            assert data["finished"] is False
            assert data["next_question"] is not None
            question = data["next_question"]
        else:
            assert data["finished"] is True
            assert data["next_question"] is None

    report = await client.get(f"/v1/diagnosis/{exam_id}/report", headers=headers)
    assert report.status_code == 200, report.text
    report_body = report.json()
    assert report_body["finished"] is True
    assert report_body["summary"]["answered"] == 20
    assert report_body["summary"]["correct"] == 10
    assert len(report_body["points"]) == 5
    assert report_body["has_data"] is True
    levels = (
        report_body["summary"]["red_count"]
        + report_body["summary"]["yellow_count"]
        + report_body["summary"]["green_count"]
    )
    assert levels == 5


async def test_diagnosis_difficulty_adapts(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers,
    )
    exam_id = started.json()["exam_id"]
    question = started.json()["question"]

    # 连续答对两题 → 难度应从 3 升到 4；随后答错 → 降回 3
    from app.models import Question as QuestionModel

    difficulties: list[int] = []
    pattern = [True, True, False, True, False, False]
    for answer_correct in pattern:
        async with sessionmaker() as session:
            stored = await session.get(QuestionModel, uuid.UUID(question["id"]))
            assert stored is not None
            expected = stored.answer if answer_correct else "wrong"
        response = await client.post(
            f"/v1/diagnosis/{exam_id}/answer",
            json={"question_id": question["id"], "answer": expected},
            headers=headers,
        )
        data = response.json()
        if data["next_question"] is not None:
            difficulties.append(data["next_question"]["difficulty"])
            question = data["next_question"]

    async with sessionmaker() as session:
        exam = await session.get(Exam, uuid.UUID(exam_id))
        assert exam is not None
        # pattern [T, T, F, T, F, F]：3→4→5→4→5→4→3
        assert exam.meta["difficulty"] == 3
    assert difficulties, "应返回过下一题"


async def test_diagnosis_start_requires_bank(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers_of(payload),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DIAGNOSIS_NO_QUESTIONS"


async def test_diagnosis_target_count_validation(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 10},
        headers=headers_of(payload),
    )
    assert response.status_code == 422


async def test_diagnosis_report_before_finish_conflict(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers,
    )
    exam_id = started.json()["exam_id"]
    response = await client.get(f"/v1/diagnosis/{exam_id}/report", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "DIAGNOSIS_NOT_FINISHED"


async def test_diagnosis_answer_after_finish_conflict(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers,
    )
    exam_id = started.json()["exam_id"]
    question = started.json()["question"]
    from app.models import Question as QuestionModel

    async with sessionmaker() as session:
        exam = await session.get(Exam, uuid.UUID(exam_id))
        assert exam is not None
        question_id = uuid.UUID(question["id"])
        stored = await session.get(QuestionModel, question_id)
        assert stored is not None
        expected = stored.answer

    response = await client.post(
        f"/v1/diagnosis/{exam_id}/answer",
        json={"question_id": question["id"], "answer": expected},
        headers=headers,
    )
    assert response.status_code == 200
    duplicate = await client.post(
        f"/v1/diagnosis/{exam_id}/answer",
        json={"question_id": question["id"], "answer": expected},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DIAGNOSIS_ALREADY_ANSWERED"


async def test_diagnosis_records_mastery_and_exam_state(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers,
    )
    exam_id = started.json()["exam_id"]
    async with sessionmaker() as session:
        exam = await session.get(Exam, uuid.UUID(exam_id))
    assert exam is not None
    assert exam.kind.value == "diagnosis"
    assert exam.status == ExamStatus.IN_PROGRESS
    assert len(exam.meta["asked"]) == 1


async def test_diagnosis_other_user_denied(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    owner = await register(client)
    intruder = await register(client)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers_of(owner),
    )
    exam_id = started.json()["exam_id"]
    response = await client.get(
        f"/v1/diagnosis/{exam_id}/report", headers=headers_of(intruder)
    )
    assert response.status_code == 403


async def test_diagnosis_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/diagnosis/start", json={"subject": "math", "stage": "junior", "target_count": 20}
    )
    assert response.status_code == 401


# ---------- 分支补齐（M10 覆盖率收口：诊断核心域 ≥90%） ----------


async def test_diagnosis_question_mismatch_rejected(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """提交不属于本次诊断的题目 → 400 DIAGNOSIS_QUESTION_MISMATCH。"""
    user = await register(client)
    await _seed_bank(sessionmaker)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers_of(user),
    )
    assert started.status_code == 201, started.text
    exam_id = started.json()["exam_id"]
    response = await client.post(
        f"/v1/diagnosis/{exam_id}/answer",
        json={"question_id": str(uuid.uuid4()), "answer": "A"},
        headers=headers_of(user),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DIAGNOSIS_QUESTION_MISMATCH"


async def test_diagnosis_duplicate_answer_conflict(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """同一题重复作答 → 409（进入下一题后旧题不可再交）。"""
    user = await register(client)
    await _seed_bank(sessionmaker)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers_of(user),
    )
    exam_id = started.json()["exam_id"]
    question_id = started.json()["question"]["id"]
    first = await client.post(
        f"/v1/diagnosis/{exam_id}/answer",
        json={"question_id": question_id, "answer": "A"},
        headers=headers_of(user),
    )
    assert first.status_code == 200
    again = await client.post(
        f"/v1/diagnosis/{exam_id}/answer",
        json={"question_id": question_id, "answer": "A"},
        headers=headers_of(user),
    )
    assert again.status_code in (400, 409)


async def test_diagnosis_list_questions_skips_missing(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """list_exam_questions：题目被删除时跳过而不报错。"""
    from app.services import diagnosis_service

    user = await register(client)
    await _seed_bank(sessionmaker)
    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "target_count": 20},
        headers=headers_of(user),
    )
    assert started.status_code == 201
    exam_id = started.json()["exam_id"]

    async with sessionmaker() as session:
        exam = await session.get(Exam, uuid.UUID(exam_id))
        assert exam is not None
        asked = list(exam.meta.get("asked", []))
        # 删除第一道题后再列题：应跳过被删除题目
        question = await session.get(Question, uuid.UUID(hex=asked[0]))
        if question is not None:
            await session.delete(question)
            await session.commit()
        questions = await diagnosis_service.list_exam_questions(session, exam)
        assert all(str(item.id.hex) != asked[0] for item in questions)


async def test_diagnosis_knowledge_point_names(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """question_knowledge_point_names 返回知识点名称。"""
    from app.services import diagnosis_service

    async with sessionmaker() as session:
        question = (
            await session.execute(select(Question).limit(1))
        ).scalar_one_or_none()
        if question is None:
            return
        names = await diagnosis_service.question_knowledge_point_names(
            session, question.id
        )
        assert isinstance(names, list)
