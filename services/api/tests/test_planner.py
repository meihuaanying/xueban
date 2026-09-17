"""规划引擎测试（T3.3 / F-06~F-10）：纯函数 + API 全流程。"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import (
    Exam,
    ExamAnswer,
    ExamKind,
    ExamStatus,
    KnowledgeEdge,
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    User,
)
from app.services import planner_service, practice_service
from app.services.planner_service import (
    CountdownPhase,
    PathPoint,
    build_countdown_plan,
    build_learning_path,
    compress_remaining,
    compute_streak,
    elapsed_ratio,
    should_backtrack,
    should_compress,
)
from tests.helpers import headers_of, register

# ---------- 路径纯函数 ----------


def _point(name: str, mastery: float, point_id: uuid.UUID | None = None) -> PathPoint:
    return PathPoint(id=point_id or uuid.uuid4(), name=name, mastery=mastery)


def test_build_learning_path_prerequisites_first() -> None:
    prereq = _point("前置概念", 0.2)
    dependent = _point("后续概念", 0.3)
    phases = build_learning_path(
        weak_points=[dependent],
        prerequisites={dependent.id: [prereq]},
        strong_points=[],
    )
    assert [phase.name for phase in phases] == ["foundation", "current"]
    flat = planner_service.flatten_phases(phases)
    assert [point.name for point in flat] == ["前置概念", "后续概念"]


def test_build_learning_path_strong_prereq_not_in_foundation() -> None:
    prereq = _point("已掌握前置", 0.9)
    dependent = _point("薄弱点", 0.2)
    phases = build_learning_path(
        weak_points=[dependent], prerequisites={dependent.id: [prereq]}, strong_points=[]
    )
    assert [phase.name for phase in phases] == ["current"]


def test_build_learning_path_advanced_phase() -> None:
    weak = _point("薄弱", 0.2)
    medium = _point("接近掌握", 0.7)
    phases = build_learning_path(weak_points=[weak], prerequisites={}, strong_points=[medium])
    assert [phase.name for phase in phases] == ["current", "advanced"]


def test_build_learning_path_empty() -> None:
    assert build_learning_path(weak_points=[], prerequisites={}, strong_points=[]) == []


def test_build_learning_path_dedupes() -> None:
    same_prereq = _point("重复前置", 0.1)
    weak_a, weak_b = _point("A", 0.2), _point("B", 0.3)
    phases = build_learning_path(
        weak_points=[weak_a, weak_b],
        prerequisites={weak_a.id: [same_prereq], weak_b.id: [same_prereq]},
        strong_points=[],
    )
    foundation = phases[0]
    assert [point.id for point in foundation.knowledge_points] == [same_prereq.id]


# ---------- 打卡连续天数 ----------


def test_streak_cross_midnight_boundary() -> None:
    """23:59 完成、00:01 查看：连续天数应保留为 1。"""
    day = date(2026, 9, 15)
    assert compute_streak({day}, today=day + timedelta(days=1)) == 1


def test_streak_counts_consecutive_days() -> None:
    today = date(2026, 9, 15)
    dates = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert compute_streak(dates, today=today) == 3


def test_streak_gap_breaks() -> None:
    today = date(2026, 9, 15)
    dates = {today, today - timedelta(days=2)}
    assert compute_streak(dates, today=today) == 1


def test_streak_empty() -> None:
    assert compute_streak(set(), today=date(2026, 9, 15)) == 0


# ---------- 考期倒排 ----------


def test_countdown_phases_sum_to_total() -> None:
    today = date(2026, 9, 15)
    plan = build_countdown_plan(today=today, exam_date=today + timedelta(days=60))
    assert [phase.name for phase in plan.phases] == ["foundation", "strengthen", "sprint"]
    assert sum(phase.days for phase in plan.phases) == 60
    assert plan.phases[0].start == today
    assert plan.phases[-1].end == today + timedelta(days=59)


def test_countdown_warns_when_less_than_seven_days() -> None:
    today = date(2026, 9, 15)
    plan = build_countdown_plan(today=today, exam_date=today + timedelta(days=5))
    assert len(plan.phases) == 1
    assert plan.phases[0].name == "sprint"
    assert plan.warning is not None
    assert "不足 7 天" in plan.warning


def test_countdown_invalid_date_raises() -> None:
    today = date(2026, 9, 15)
    try:
        build_countdown_plan(today=today, exam_date=today)
        raised = False
    except Exception:
        raised = True
    assert raised is True


def test_should_compress_branches() -> None:
    assert should_compress(progress_ratio=0.2, elapsed_ratio=0.5) is True
    assert should_compress(progress_ratio=0.5, elapsed_ratio=0.5) is False
    # 边界：落后恰好 20% 不压缩
    assert should_compress(progress_ratio=0.3, elapsed_ratio=0.5) is False


def test_elapsed_ratio() -> None:
    assert elapsed_ratio(total_days=60, remaining_days=60) == 0.0
    assert elapsed_ratio(total_days=60, remaining_days=30) == 0.5
    assert elapsed_ratio(total_days=0, remaining_days=0) == 1.0


def test_compress_remaining_shortens_middle() -> None:
    today = date(2026, 9, 15)
    plan = build_countdown_plan(today=today, exam_date=today + timedelta(days=50))
    compressed = compress_remaining(plan.phases)
    assert len(compressed) == 3
    assert compressed[-2].days < plan.phases[-2].days
    assert compressed[-1].days > plan.phases[-1].days
    assert sum(phase.days for phase in compressed) == 50
    assert compressed[-1].end == plan.phases[-1].end


def test_compress_single_phase_noop() -> None:
    single = [CountdownPhase("sprint", "冲刺", date(2026, 9, 15), date(2026, 9, 18), 4, "f")]
    assert compress_remaining(single) == single


# ---------- 前置回溯与动态难度 ----------


def test_should_backtrack_three_consecutive_wrong() -> None:
    assert should_backtrack([True, False, False, False]) is True


def test_should_backtrack_needs_three() -> None:
    assert should_backtrack([False, False]) is False


def test_should_backtrack_resets_with_correct() -> None:
    assert should_backtrack([False, False, True]) is False


def test_dynamic_difficulty_up() -> None:
    assert practice_service.choose_next_difficulty(3, 0.9) == 4
    assert practice_service.choose_next_difficulty(3, 0.85) == 4  # 阈值边界


def test_dynamic_difficulty_down() -> None:
    assert practice_service.choose_next_difficulty(3, 0.4) == 2
    assert practice_service.choose_next_difficulty(3, 0.5) == 2  # 阈值边界


def test_dynamic_difficulty_keep() -> None:
    assert practice_service.choose_next_difficulty(3, 0.7) == 3


def test_dynamic_difficulty_clamps() -> None:
    assert practice_service.choose_next_difficulty(5, 1.0) == 5
    assert practice_service.choose_next_difficulty(1, 0.0) == 1


def test_accuracy_of() -> None:
    assert practice_service.accuracy_of([]) == 1.0
    assert practice_service.accuracy_of([True, False, True, True]) == 0.75


# ---------- arq 定时任务 ----------


def test_worker_settings_has_daily_cron() -> None:
    from app.worker import WorkerSettings, inspect_quality, regenerate_paths

    assert regenerate_paths in WorkerSettings.functions
    assert inspect_quality in WorkerSettings.functions
    # 路径重排（每日 03:00）+ 周报（每周日 22:00）+ 质量巡检（每日 03:30，F-45）
    assert len(WorkerSettings.cron_jobs) == 3


# ---------- API ----------


async def _seed_prerequisite_chain(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    """前置 A → 薄弱 B（带一两道题）。"""
    async with sessionmaker() as session:
        prereq = KnowledgePoint(
            code="math.test.p01", name="前置知识A", subject="math", sort_order=1
        )
        weak = KnowledgePoint(
            code="math.test.p02", name="薄弱知识B", subject="math", sort_order=2
        )
        session.add_all([prereq, weak])
        await session.flush()
        session.add(KnowledgeEdge(from_id=prereq.id, to_id=weak.id))
        for index, kp in enumerate((prereq, weak)):
            question = Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem=f"[{kp.name}] 第{index}题",
                answer="1",
                analysis="略。",
                status=QuestionStatus.PUBLISHED,
            )
            session.add(question)
            await session.flush()
            session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
        await session.commit()
        return prereq.id, weak.id


async def _seed_basic_knowledge_points(
    sessionmaker: async_sessionmaker[AsyncSession], *, count: int = 4
) -> None:
    """播种基础知识点（无学情数据时的兜底路径依赖）。"""
    async with sessionmaker() as session:
        for index in range(count):
            session.add(
                KnowledgePoint(
                    code=f"math.test.base{index:02d}",
                    name=f"基础知识点{index}",
                    subject="math",
                    sort_order=index,
                )
            )
        await session.commit()


async def test_path_api_generates_fallback_without_data(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_basic_knowledge_points(sessionmaker)
    payload = await register(client)
    response = await client.get("/v1/plan/path", headers=headers_of(payload))
    assert response.status_code == 200
    body = response.json()
    assert body["has_path"] is True
    assert body["phases"]


async def test_path_api_with_weak_point(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    from app.services import mastery_service

    prereq_id, weak_id = await _seed_prerequisite_chain(sessionmaker)
    payload = await register(client)
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=weak_id, correct=False
        )
        await session.commit()
    response = await client.get("/v1/plan/path", headers=headers_of(payload))
    body = response.json()
    names = [phase["name"] for phase in body["phases"]]
    assert "foundation" in names and "current" in names
    foundation = next(phase for phase in body["phases"] if phase["name"] == "foundation")
    current = next(phase for phase in body["phases"] if phase["name"] == "current")
    assert any(point["name"] == "前置知识A" for point in foundation["knowledge_points"])
    assert any(point["name"] == "薄弱知识B" for point in current["knowledge_points"])
    assert prereq_id


async def test_path_regenerate_archives_previous(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    from app.models import Plan, PlanKind

    payload = await register(client)
    headers = headers_of(payload)
    first = await client.get("/v1/plan/path", headers=headers)
    second = await client.post("/v1/plan/path/regenerate", headers=headers)
    assert second.status_code == 201
    assert second.json()["plan_id"] != first.json()["plan_id"]
    async with sessionmaker() as session:
        plans = (
            await session.execute(
                select(Plan).where(
                    Plan.kind == PlanKind.PATH, Plan.user_id.is_not(None)
                )
            )
        ).scalars().all()
    statuses = sorted(plan.status for plan in plans)
    assert statuses.count("active") == 1
    assert "archived" in statuses


async def test_today_tasks_and_streak(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_basic_knowledge_points(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    today = await client.get("/v1/plan/today", headers=headers)
    assert today.status_code == 200, today.text
    body = today.json()
    assert 3 <= len(body["tasks"]) <= 5
    assert body["all_completed"] is False

    again = await client.get("/v1/plan/today", headers=headers)
    assert [task["id"] for task in again.json()["tasks"]] == [task["id"] for task in body["tasks"]]

    last = None
    for task in body["tasks"]:
        done = await client.post(f"/v1/plan/tasks/{task['id']}/complete", headers=headers)
        assert done.status_code == 200, done.text
        last = done.json()
    assert last is not None
    assert last["today"]["all_completed"] is True
    assert last["today"]["streak_days"] == 1

    # 幂等：重复完成不报错且状态不变
    repeat = await client.post(
        f"/v1/plan/tasks/{body['tasks'][0]['id']}/complete", headers=headers
    )
    assert repeat.status_code == 200
    assert repeat.json()["today"]["all_completed"] is True


async def test_today_task_complete_other_user_denied(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_basic_knowledge_points(sessionmaker)
    owner = await register(client)
    intruder = await register(client)
    today = await client.get("/v1/plan/today", headers=headers_of(owner))
    task_id = today.json()["tasks"][0]["id"]
    response = await client.post(
        f"/v1/plan/tasks/{task_id}/complete", headers=headers_of(intruder)
    )
    assert response.status_code == 404


async def test_exam_countdown_api(client: AsyncClient) -> None:
    payload = await register(client)
    exam_date = (utcnow().date() + timedelta(days=90)).isoformat()
    response = await client.post(
        "/v1/plan/exam-countdown",
        json={"exam_date": exam_date, "target_score": 600, "progress_ratio": 1.0},
        headers=headers_of(payload),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert [phase["name"] for phase in body["phases"]] == ["foundation", "strengthen", "sprint"]
    assert body["warning"] is None
    assert body["compressed"] is False


async def test_exam_countdown_warning_and_validation(client: AsyncClient) -> None:
    payload = await register(client)
    headers = headers_of(payload)
    soon = (utcnow().date() + timedelta(days=3)).isoformat()
    response = await client.post(
        "/v1/plan/exam-countdown", json={"exam_date": soon}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["warning"]

    past = (utcnow().date() - timedelta(days=1)).isoformat()
    invalid = await client.post(
        "/v1/plan/exam-countdown", json={"exam_date": past}, headers=headers
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "PLAN_INVALID_EXAM_DATE"


async def test_backtrack_api_triggers_after_three_wrong(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    prereq_id, weak_id = await _seed_prerequisite_chain(sessionmaker)
    payload = await register(client)
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        question = (
            await session.execute(
                select(Question)
                .join(QuestionKnowledgePoint, QuestionKnowledgePoint.question_id == Question.id)
                .where(QuestionKnowledgePoint.knowledge_point_id == weak_id)
            )
        ).scalar_one()
        exam = Exam(
            user_id=user.id,
            kind=ExamKind.MOCK,
            title="测试测评",
            status=ExamStatus.SUBMITTED,
        )
        session.add(exam)
        await session.flush()
        for _ in range(3):
            session.add(
                ExamAnswer(exam_id=exam.id, question_id=question.id, is_correct=False, score=0.0)
            )
        await session.commit()

    response = await client.post(
        "/v1/plan/backtrack",
        json={"knowledge_point_id": str(weak_id)},
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backtrack"] is True
    assert "前置知识A" in body["prerequisites"]
    assert prereq_id


async def test_backtrack_api_no_trigger_with_two_wrong(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    _, weak_id = await _seed_prerequisite_chain(sessionmaker)
    payload = await register(client)
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        question = (
            await session.execute(
                select(Question)
                .join(QuestionKnowledgePoint, QuestionKnowledgePoint.question_id == Question.id)
                .where(QuestionKnowledgePoint.knowledge_point_id == weak_id)
            )
        ).scalar_one()
        exam = Exam(
            user_id=user.id, kind=ExamKind.MOCK, title="测试测评", status=ExamStatus.SUBMITTED
        )
        session.add(exam)
        await session.flush()
        for _ in range(2):
            session.add(
                ExamAnswer(exam_id=exam.id, question_id=question.id, is_correct=False, score=0.0)
            )
        await session.commit()
    response = await client.post(
        "/v1/plan/backtrack",
        json={"knowledge_point_id": str(weak_id)},
        headers=headers_of(payload),
    )
    assert response.status_code == 200
    assert response.json()["backtrack"] is False


async def test_plan_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/plan/path")).status_code == 401
    assert (await client.get("/v1/plan/today")).status_code == 401
