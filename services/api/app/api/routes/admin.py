"""运营后台路由（F-44~F-47 / T7.4，全部要求管理员角色）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_roles
from app.models import User, UserRole
from app.schemas import (
    AdminQuestionCreateRequest,
    AdminQuestionListResponse,
    AdminQuestionOut,
    AdminQuestionUpdateRequest,
    AlertRecordOut,
    AlertTestRequest,
    CoverageResponse,
    ExperimentCreateRequest,
    ExperimentOut,
    ExperimentReportResponse,
    InspectionReportOut,
    InspectionRunRequest,
    MetricsOverviewResponse,
    QuestionTransitionRequest,
    QuestionVersionOut,
)
from app.services import (
    admin_service,
    alert_service,
    experiment_service,
    metrics_service,
    quality_service,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/ping", summary="管理员权限探针")
async def admin_ping(user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, str]:
    """仅管理员可访问（用于 RBAC 验收）。"""
    return {"ok": "true", "admin_id": str(user.id)}


# ------------------------------- F-44 题库管理 -------------------------------


@router.get(
    "/questions", response_model=AdminQuestionListResponse, summary="题库列表（F-44）"
)
async def list_questions(
    status: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AdminQuestionListResponse:
    """分页检索（支持状态/学科/学段/关键词）。"""
    total, items = await admin_service.list_questions(
        session,
        status=status,
        subject=subject,
        stage=stage,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return AdminQuestionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AdminQuestionOut.model_validate(item) for item in items],
    )


@router.get(
    "/questions/coverage", response_model=CoverageResponse, summary="题库覆盖率看板（F-44）"
)
async def question_coverage(
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> CoverageResponse:
    """解析覆盖率与状态/学科分布。"""
    return CoverageResponse.model_validate(await admin_service.coverage(session))


@router.post(
    "/questions",
    response_model=AdminQuestionOut,
    status_code=201,
    summary="新建题目（F-44：草稿）",
)
async def create_question(
    payload: AdminQuestionCreateRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AdminQuestionOut:
    """创建草稿题目并落初始版本。"""
    question = await admin_service.create_question(
        session,
        editor=admin,
        subject=payload.subject,
        stage=payload.stage,
        qtype=payload.qtype,
        stem=payload.stem,
        options=payload.options,
        answer=payload.answer,
        analysis=payload.analysis,
        difficulty=payload.difficulty,
        source=payload.source,
    )
    await session.commit()
    return AdminQuestionOut.model_validate(question)


@router.patch(
    "/questions/{question_id}", response_model=AdminQuestionOut, summary="编辑题目（F-44）"
)
async def update_question(
    question_id: uuid.UUID,
    payload: AdminQuestionUpdateRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AdminQuestionOut:
    """编辑内容/解析；变化时写入版本历史。"""
    changes = payload.model_dump(exclude={"change_note"}, exclude_none=True)
    question = await admin_service.update_question(
        session,
        editor=admin,
        question_id=question_id,
        changes=changes,
        change_note=payload.change_note,
    )
    await session.commit()
    return AdminQuestionOut.model_validate(question)


@router.post(
    "/questions/{question_id}/transition",
    response_model=AdminQuestionOut,
    summary="审核流流转（F-44：草稿→审核→上线）",
)
async def transition_question(
    question_id: uuid.UUID,
    payload: QuestionTransitionRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AdminQuestionOut:
    """流转并记录版本。"""
    question = await admin_service.transition(
        session, editor=admin, question_id=question_id, target=payload.target, note=payload.note
    )
    await session.commit()
    return AdminQuestionOut.model_validate(question)


@router.get(
    "/questions/{question_id}/versions",
    response_model=list[QuestionVersionOut],
    summary="解析版本历史（F-44）",
)
async def question_versions(
    question_id: uuid.UUID,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> list[QuestionVersionOut]:
    """倒序版本历史。"""
    versions = await admin_service.list_versions(session, question_id=question_id)
    return [QuestionVersionOut.model_validate(item) for item in versions]


# ------------------------------- F-45 质量巡检 -------------------------------


@router.post(
    "/quality/inspect", response_model=InspectionReportOut, summary="执行质量巡检（F-45）"
)
async def run_inspection(
    payload: InspectionRunRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> InspectionReportOut:
    """抽样校验（SymPy + 规则双通道）；超阈值自动 webhook 告警。"""
    report = await quality_service.run_inspection(
        session, sample_size=payload.sample_size, threshold=payload.threshold
    )
    await session.commit()
    return InspectionReportOut.model_validate(report)


@router.get(
    "/quality/reports",
    response_model=list[InspectionReportOut],
    summary="巡检报告列表（F-45）",
)
async def list_inspections(
    limit: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> list[InspectionReportOut]:
    """最近巡检记录。"""
    reports = await quality_service.list_reports(session, limit=limit)
    return [InspectionReportOut.model_validate(item) for item in reports]


# ------------------------------- F-46 数据看板 -------------------------------


@router.get(
    "/metrics/overview", response_model=MetricsOverviewResponse, summary="学情数据看板（F-46）"
)
async def metrics_overview(
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> MetricsOverviewResponse:
    """留存/完课率/续费率/掌握度提升。"""
    return MetricsOverviewResponse.model_validate(await metrics_service.overview(session))


# ------------------------------- F-47 A/B 实验 -------------------------------


@router.get(
    "/experiments", response_model=list[ExperimentOut], summary="实验列表（F-47）"
)
async def list_experiments(
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> list[ExperimentOut]:
    """全部实验。"""
    experiments = await experiment_service.list_experiments(session)
    return [ExperimentOut.model_validate(item) for item in experiments]


@router.post(
    "/experiments", response_model=ExperimentOut, status_code=201, summary="创建实验（F-47）"
)
async def create_experiment(
    payload: ExperimentCreateRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> ExperimentOut:
    """创建分组实验。"""
    experiment = await experiment_service.create_experiment(
        session,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        variants=[variant.model_dump() for variant in payload.variants],
        metric=payload.metric,
    )
    await session.commit()
    return ExperimentOut.model_validate(experiment)


@router.get(
    "/experiments/{experiment_id}/variant",
    summary="获取用户分组（F-47：同用户恒定同组）",
)
async def get_variant(
    experiment_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """幂等分组（重复请求返回同组）。"""
    experiment = await experiment_service.get_experiment(session, experiment_id=experiment_id)
    variant = await experiment_service.assign(session, experiment=experiment, user_id=user_id)
    await session.commit()
    return {"experiment": experiment.key, "variant": variant}


@router.get(
    "/experiments/{experiment_id}/report",
    response_model=ExperimentReportResponse,
    summary="实验报告（F-47：含显著性检验）",
)
async def experiment_report(
    experiment_id: uuid.UUID,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> ExperimentReportResponse:
    """分组指标 + 两比例 z 检验。"""
    experiment = await experiment_service.get_experiment(session, experiment_id=experiment_id)
    data = await experiment_service.report(session, experiment=experiment)
    return ExperimentReportResponse.model_validate(data)


# ------------------------------- T7.4 告警联调 -------------------------------


@router.post(
    "/alerts/test", response_model=AlertRecordOut, summary="告警联调（T7.4：webhook）"
)
async def test_alert(
    payload: AlertTestRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AlertRecordOut:
    """发送测试告警（未配置 webhook 时记录 skipped）。"""
    record = await alert_service.send_alert(session, kind=payload.kind, payload=payload.payload)
    await session.commit()
    return AlertRecordOut.model_validate(record)
