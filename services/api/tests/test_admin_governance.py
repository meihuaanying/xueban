"""运营后台测试（M7 / T7.3~T7.4，F-44~F-47；含 RBAC 用例）。"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import httpx
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import (
    AlertRecord,
    Experiment,
    ExperimentAssignment,
    MasteryRecord,
    Plan,
    PlanKind,
    PlanTask,
    PracticeRecord,
    PracticeSource,
    Question,
    QuestionStatus,
    QuestionType,
    SubscriptionPlan,
    TaskStatus,
    User,
    UserRole,
)
from app.services import experiment_service, quality_service
from tests.conftest import auth_headers, next_phone
from tests.helpers import headers_of, register, register_user


def headers(token: str) -> dict[str, str]:
    """管理员鉴权头。"""
    return auth_headers(token)


async def _create_published_question(
    client: AsyncClient, token: str, *, stem: str, analysis: str | None
) -> dict[str, object]:
    """走完整审核流创建已上线题目（草稿→审核→上线）。"""
    created = await client.post(
        "/v1/admin/questions",
        json={
            "subject": "math",
            "stage": "junior",
            "qtype": "choice",
            "stem": stem,
            "options": {"A": "90", "B": "88"},
            "answer": "A",
            "analysis": analysis,
            "difficulty": 2,
            "source": "test",
        },
        headers=headers(token),
    )
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]
    latest = created.json()
    for target in ("review", "published"):
        response = await client.post(
            f"/v1/admin/questions/{question_id}/transition",
            json={"target": target},
            headers=headers(token),
        )
        assert response.status_code == 200, response.text
        latest = response.json()
    return latest


# --------------------------------- RBAC ---------------------------------


async def test_rbac_admin_apis_reject_student_and_parent(client: AsyncClient) -> None:
    """RBAC：题库/巡检/看板/实验/告警接口仅管理员可访问。"""
    student = await register(client)
    parent = await register(client, role="parent")
    endpoints: list[tuple[str, str, dict[str, object] | None]] = [
        ("GET", "/v1/admin/questions", None),
        ("GET", "/v1/admin/questions/coverage", None),
        ("GET", "/v1/admin/quality/reports", None),
        ("GET", "/v1/admin/metrics/overview", None),
        ("GET", "/v1/admin/experiments", None),
        (
            "POST",
            "/v1/admin/experiments",
            {"key": "rbac-x", "name": "越权实验", "variants": [{"name": "a"}, {"name": "b"}]},
        ),
        ("POST", "/v1/admin/quality/inspect", {"sample_size": 5}),
        ("POST", "/v1/admin/alerts/test", {"kind": "test", "payload": {}}),
    ]
    for role_payload in (student, parent):
        for method, path, body in endpoints:
            response = await client.request(
                method, path, json=body, headers=headers_of(role_payload)
            )
            assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
            assert response.json()["code"] == "PERMISSION_DENIED"

    # 管理员可访问探针
    ping = await client.get("/v1/admin/ping", headers=headers_of(student))
    assert ping.status_code == 403


async def test_rbac_admin_ping_allows_admin(client: AsyncClient, admin_token: str) -> None:
    """RBAC：管理员访问探针成功。"""
    response = await client.get("/v1/admin/ping", headers=auth_headers(admin_token))
    assert response.status_code == 200
    assert response.json()["ok"] == "true"


# ------------------------------- F-44 题库 -------------------------------


async def test_question_lifecycle_versions_and_coverage(
    client: AsyncClient, admin_token: str
) -> None:
    """F-44：三态审核流 + 解析修改留版本历史 + 覆盖率看板。"""
    question = await _create_published_question(
        client, admin_token, stem="计算 18 × 5 = ？", analysis="按乘法口诀计算。正确选项为 A。"
    )
    question_id = str(question["id"])
    assert question["status"] == "published"

    # 编辑解析 → 新版本
    updated = await client.patch(
        f"/v1/admin/questions/{question_id}",
        json={"analysis": "按乘法口诀计算，18×5=90。正确选项为 A。", "change_note": "补充算式"},
        headers=headers(admin_token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["analysis"].startswith("按乘法口诀计算，18×5=90")
    versions = await client.get(
        f"/v1/admin/questions/{question_id}/versions", headers=headers(admin_token)
    )
    assert versions.status_code == 200
    history = versions.json()
    assert len(history) >= 3  # 创建 + 审核 + 上线 + 编辑（至少 3 条，允许合并）
    assert {item["version"] for item in history} >= {1, 2}
    assert history[0]["snapshot"]["analysis"].startswith("按乘法口诀计算，18×5=90")

    # 覆盖率看板
    coverage = await client.get("/v1/admin/questions/coverage", headers=headers(admin_token))
    assert coverage.status_code == 200
    body = coverage.json()
    assert body["total"] >= 1
    assert body["with_analysis"] >= 1
    assert body["coverage_rate"] >= 0.95 or body["total"] == body["with_analysis"]
    assert body["published"] >= 1


async def test_question_transition_invalid_rejected(client: AsyncClient, admin_token: str) -> None:
    """F-44：不允许 draft 直接上线。"""
    created = await client.post(
        "/v1/admin/questions",
        json={"subject": "math", "stem": "题干", "answer": "A", "analysis": "解析"},
        headers=headers(admin_token),
    )
    question_id = created.json()["id"]
    response = await client.post(
        f"/v1/admin/questions/{question_id}/transition",
        json={"target": "published"},
        headers=headers(admin_token),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "QUESTION_TRANSITION_INVALID"


# ------------------------------- F-45 巡检 -------------------------------


async def test_inspection_flags_bad_analysis_and_sends_alert(
    client: AsyncClient,
    admin_token: str,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """F-45：抽样双通道校验；超阈值触发 webhook 告警（真实投递链路 + MockTransport）。"""
    await _create_published_question(client, admin_token, stem="好题 1", analysis="正确选项为 A。")
    await _create_published_question(client, admin_token, stem="坏题 1（缺解析）", analysis=None)
    await _create_published_question(
        client, admin_token, stem="坏题 2（解析不含答案）", analysis="随便写点内容。"
    )

    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0})

    async with sessionmaker() as session:
        report = await quality_service.run_inspection(
            session,
            sample_size=10,
            threshold=0.03,
            webhook_url="https://alert.example/webhook",
            transport=httpx.MockTransport(handler),
        )
        await session.commit()

    assert report.sample_size == 3
    assert report.flagged_count == 2
    assert report.wrong_rate > 0.03
    assert report.alerted is True
    assert captured and captured[0]["kind"] == "quality.wrong_rate"

    # 告警记录可查（管理员接口联调）
    alert_test = await client.post(
        "/v1/admin/alerts/test",
        json={"kind": "test", "payload": {"note": "联调"}},
        headers=headers(admin_token),
    )
    assert alert_test.status_code == 200
    assert alert_test.json()["status"] in ("skipped", "sent")  # 未配置 webhook 时 skipped

    reports = await client.get("/v1/admin/quality/reports", headers=headers(admin_token))
    assert reports.status_code == 200
    assert len(reports.json()) >= 1


async def test_inspection_report_saved_without_alert_when_threshold_not_exceeded(
    client: AsyncClient,
    admin_token: str,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """F-45：错题率未超阈值时不告警。"""
    await _create_published_question(client, admin_token, stem="好题 1", analysis="正确选项为 A。")
    await _create_published_question(client, admin_token, stem="好题 2", analysis="正确选项为 A。")
    async with sessionmaker() as session:
        report = await quality_service.run_inspection(session, sample_size=10, threshold=0.5)
        await session.commit()
    assert report.flagged_count == 0
    assert report.alerted is False


# ------------------------------- F-46 看板 -------------------------------


async def test_metrics_overview_traces_sql_aggregations(
    client: AsyncClient,
    admin_token: str,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """F-46：留存/完课率/续费率/掌握度提升口径可溯源。"""
    student = await register_user(client)
    other = await register_user(client)
    now = utcnow()

    async with sessionmaker() as session:
        # 队列：注册于 3 天前（D1 窗口 [now-8d, now-1d] 内）
        user = await session.get(User, uuid.UUID(student["id"]))
        assert user is not None
        user.created_at = now - timedelta(days=3)
        # 该用户在注册次日有活动 → D1 留存
        from app.models import AnalyticsEvent

        session.add(
            AnalyticsEvent(
                user_id=user.id,
                event_name="study.time",
                payload={"seconds": 600},
                occurred_at=now - timedelta(days=2),
                created_at=now - timedelta(days=2),
            )
        )
        # 另一个用户注册 3 天前但无活动 → 未留存
        other_user = await session.get(User, uuid.UUID(other["id"]))
        assert other_user is not None
        other_user.created_at = now - timedelta(days=3)

        # 完课率：1/2
        question_id = (await session.execute(select(Question.id).limit(1))).scalar_one_or_none()
        if question_id is None:
            question_id = uuid.uuid4()
            session.add(
                Question(
                    id=question_id,
                    subject="math",
                    stage="junior",
                    qtype=QuestionType.CHOICE,
                    stem="指标题",
                    options={"A": "1"},
                    answer="A",
                    analysis="解析",
                    difficulty=2,
                    source="test",
                    status=QuestionStatus.PUBLISHED,
                )
            )
            await session.flush()
        plan = Plan(
            user_id=user.id,
            kind=PlanKind.DAILY,
            title="今日任务",
            status="active",
            starts_on=now.date(),
        )
        session.add(plan)
        await session.flush()
        session.add(
            PlanTask(
                plan_id=plan.id,
                user_id=user.id,
                task_date=now.date(),
                title="任务 A",
                task_type="practice",
                status=TaskStatus.DONE,
            )
        )
        session.add(
            PlanTask(
                plan_id=plan.id,
                user_id=user.id,
                task_date=now.date(),
                title="任务 B",
                task_type="practice",
                status=TaskStatus.PENDING,
            )
        )
        # 续费率：1/2（注册流程可能已创建 free 订阅，这里直改为目标档位）
        from app.services import billing_service

        subscription = await billing_service.get_or_create_subscription(session, user.id)
        subscription.plan = SubscriptionPlan.PRO
        subscription.auto_renew = True
        other_subscription = await billing_service.get_or_create_subscription(
            session, other_user.id
        )
        other_subscription.plan = SubscriptionPlan.TRIAL
        other_subscription.auto_renew = False
        # 掌握度：近期 0.8 vs 更早 0.5（需要真实知识点，先建两个）
        from app.models import KnowledgePoint

        point_recent = KnowledgePoint(
            code=f"test.metric.recent.{uuid.uuid4().hex[:8]}",
            name="指标知识点A",
            subject="math",
            stage="junior",
        )
        point_older = KnowledgePoint(
            code=f"test.metric.older.{uuid.uuid4().hex[:8]}",
            name="指标知识点B",
            subject="math",
            stage="junior",
        )
        session.add_all([point_recent, point_older])
        await session.flush()
        session.add(
            MasteryRecord(
                user_id=user.id,
                knowledge_point_id=point_recent.id,
                mastery=0.8,
                updated_at=now - timedelta(days=1),
            )
        )
        session.add(
            MasteryRecord(
                user_id=other_user.id,
                knowledge_point_id=point_older.id,
                mastery=0.5,
                updated_at=now - timedelta(days=10),
            )
        )
        await session.commit()

    response = await client.get("/v1/admin/metrics/overview", headers=headers(admin_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["users_total"] >= 2
    assert body["retention_d1"] >= 0.3  # 队列含 2 人，其中 1 人留存（可能含其他用例用户）
    assert body["task_completion_rate_7d"] >= 0.4
    assert body["renewal_rate"] >= 0.4
    assert body["mastery_improvement"] > 0.2


# ------------------------------- F-47 实验 -------------------------------


async def test_experiment_assignment_is_sticky_and_report_significant(
    client: AsyncClient,
    admin_token: str,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """F-47：同用户恒定同组 + 实验报告含显著性检验。"""
    created = await client.post(
        "/v1/admin/experiments",
        json={
            "key": "prompt-v2",
            "name": "提示词 v2 实验",
            "variants": [{"name": "control", "weight": 1}, {"name": "v2", "weight": 1}],
            "metric": "accuracy",
        },
        headers=headers(admin_token),
    )
    assert created.status_code == 201, created.text
    experiment_id = created.json()["id"]

    async with sessionmaker() as session:
        probe = User(phone=next_phone(), role=UserRole.STUDENT, password_hash="x")
        session.add(probe)
        await session.commit()
    first = await client.get(
        f"/v1/admin/experiments/{experiment_id}/variant?user_id={probe.id}",
        headers=headers(admin_token),
    )
    second = await client.get(
        f"/v1/admin/experiments/{experiment_id}/variant?user_id={probe.id}",
        headers=headers(admin_token),
    )
    assert first.status_code == 200, first.text
    assert first.json()["variant"] == second.json()["variant"]

    # 构造结果数据：control 组全部成功、v2 组全部失败
    async with sessionmaker() as session:
        experiment = (
            await session.execute(select(Experiment).where(Experiment.key == "prompt-v2"))
        ).scalar_one()
        control_users: list[uuid.UUID] = []
        v2_users: list[uuid.UUID] = []
        attempts = 0
        while (len(control_users) < 5 or len(v2_users) < 5) and attempts < 80:
            attempts += 1
            user = User(phone=next_phone(), role=UserRole.STUDENT, password_hash="x")
            session.add(user)
            await session.flush()
            variant = await experiment_service.assign(
                session, experiment=experiment, user_id=user.id
            )
            (control_users if variant == "control" else v2_users).append(user.id)
        await session.commit()

    async with sessionmaker() as session:
        question_id = uuid.uuid4()
        session.add(
            Question(
                id=question_id,
                subject="math",
                stage="junior",
                qtype=QuestionType.CHOICE,
                stem="实验题",
                options={"A": "1"},
                answer="A",
                analysis="解析：正确选项为 A。",
                difficulty=2,
                source="test",
                status=QuestionStatus.PUBLISHED,
            )
        )
        await session.flush()
        for member in control_users:
            for _ in range(6):
                session.add(
                    PracticeRecord(
                        user_id=member,
                        question_id=question_id,
                        source=PracticeSource.PRACTICE,
                        is_correct=True,
                        user_answer="A",
                    )
                )
        for member in v2_users:
            for _ in range(6):
                session.add(
                    PracticeRecord(
                        user_id=member,
                        question_id=question_id,
                        source=PracticeSource.PRACTICE,
                        is_correct=False,
                        user_answer="B",
                    )
                )
        await session.commit()

    report = await client.get(
        f"/v1/admin/experiments/{experiment_id}/report", headers=headers(admin_token)
    )
    assert report.status_code == 200, report.text
    body = report.json()
    control = next(item for item in body["variants"] if item["name"] == "control")
    v2 = next(item for item in body["variants"] if item["name"] == "v2")
    assert control["participants"] >= 5 and v2["participants"] >= 5
    assert control["conversion_rate"] > v2["conversion_rate"]
    assert v2["significant"] is True
    assert v2["p_value"] is not None and v2["p_value"] < 0.05
    assert "control" in body["conclusion"]


async def test_experiment_duplicate_key_conflict(client: AsyncClient, admin_token: str) -> None:
    """F-47：实验 key 唯一。"""
    payload = {
        "key": "dup-key",
        "name": "重复实验",
        "variants": [{"name": "a"}, {"name": "b"}],
    }
    first = await client.post("/v1/admin/experiments", json=payload, headers=headers(admin_token))
    assert first.status_code == 201
    second = await client.post("/v1/admin/experiments", json=payload, headers=headers(admin_token))
    assert second.status_code == 409
    assert second.json()["code"] == "EXPERIMENT_KEY_EXISTS"


async def test_alert_record_skipped_without_webhook(
    client: AsyncClient, admin_token: str, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """T7.4：未配置 webhook 时告警记录为 skipped，且不影响主流程。"""
    response = await client.post(
        "/v1/admin/alerts/test",
        json={"kind": "test", "payload": {"ping": True}},
        headers=headers(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(AlertRecord))
        assert count and count >= 1


async def test_experiment_assignments_are_persisted(
    client: AsyncClient, admin_token: str, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """F-47：分组落库（复用查询路径）。"""
    created = await client.post(
        "/v1/admin/experiments",
        json={"key": "persist-key", "name": "落库实验", "variants": [{"name": "a"}, {"name": "b"}]},
        headers=headers(admin_token),
    )
    assert created.status_code == 201, created.text
    experiment_id = created.json()["id"]
    async with sessionmaker() as session:
        member = User(phone=next_phone(), role=UserRole.STUDENT, password_hash="x")
        session.add(member)
        await session.commit()
    response = await client.get(
        f"/v1/admin/experiments/{experiment_id}/variant?user_id={member.id}",
        headers=headers(admin_token),
    )
    assert response.status_code == 200, response.text
    async with sessionmaker() as session:
        rows = (
            (
                await session.execute(
                    select(ExperimentAssignment).where(ExperimentAssignment.user_id == member.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
