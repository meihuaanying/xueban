"""arq 定时任务（F-06 路径重排、F-16 微课生成）：`arq app.worker.WorkerSettings`。"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.config import settings


async def regenerate_paths(ctx: dict[str, object]) -> str:
    """为所有有学情数据的用户重排学习路径（每日 03:00）。"""
    from app.db import create_engine, create_sessionmaker
    from app.services import planner_service

    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    try:
        count = await planner_service.regenerate_all_paths(sessionmaker)
    finally:
        await engine.dispose()
    return f"regenerated={count}"


async def generate_micro_lesson(ctx: dict[str, object], lesson_id: str) -> str:
    """异步生成微课讲解稿与音频（F-16）。"""
    from app.db import create_engine, create_sessionmaker
    from app.services.lesson_service import generate_micro_lesson as run_generation
    from app.services.llm_client import LlmClient
    from app.services.observability import ObservabilityService
    from app.services.storage_service import StorageService
    from app.services.tts import get_tts_provider

    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    observability = ObservabilityService(settings)
    llm = LlmClient(settings, observability)
    try:
        async with sessionmaker() as session:
            lesson = await run_generation(
                session,
                lesson_id=uuid.UUID(lesson_id),
                llm=llm,
                tts=get_tts_provider(settings),
                storage=StorageService(settings),
            )
            await session.commit()
            return lesson.status.value
    finally:
        await llm.aclose()
        observability.flush()
        await engine.dispose()


async def generate_weekly_reports(ctx: dict[str, object]) -> str:
    """为近两周活跃用户生成每周学情报告（每周日 22:00，F-27）。"""
    from app.db import create_engine, create_sessionmaker
    from app.services import report_service

    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    try:
        count = await report_service.generate_weekly_reports_all(sessionmaker)
    finally:
        await engine.dispose()
    return f"reports={count}"


async def inspect_quality(ctx: dict[str, object]) -> str:
    """每日 AI 质量巡检（F-45）：抽样校验并触发告警。"""
    from app.db import create_engine, create_sessionmaker
    from app.services import quality_service

    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    try:
        count = await quality_service.run_daily_inspection(sessionmaker)
    finally:
        await engine.dispose()
    return f"inspected={count}"


class WorkerSettings:
    """arq worker 配置。"""

    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(settings.redis_url)
    functions: ClassVar[list[Any]] = [
        regenerate_paths,
        generate_micro_lesson,
        generate_weekly_reports,
        inspect_quality,
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(regenerate_paths, hour=3, minute=0),
        cron(generate_weekly_reports, weekday=6, hour=22, minute=0),
        # F-45 每日质量巡检（03:30 抽样，超阈值 webhook 告警）
        cron(inspect_quality, hour=3, minute=30),
    ]
