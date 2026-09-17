"""复盘契约（F-27/F-29/F-30）。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class WeeklyReportResponse(BaseModel):
    """每周学情报告。"""

    week_start: date
    week_end: date
    report: dict[str, object]


class ShareResponse(BaseModel):
    """分享链接。"""

    token: str
    url_path: str
    expires_at: datetime


class SharedReportResponse(BaseModel):
    """免登录只读报告。"""

    report: dict[str, object]


class CalendarDayOut(BaseModel):
    """日历中的一天。"""

    day: date
    practice_count: int
    correct_count: int
    tasks_total: int
    tasks_done: int
    studied: bool


class CalendarResponse(BaseModel):
    """学习日历（打卡热力图 + 连续天数）。"""

    year: int
    month: int
    streak_days: int
    max_practice: int
    days: list[CalendarDayOut]


class SprintResponse(BaseModel):
    """考前冲刺包。"""

    exam_date: date
    remaining_days: int
    high_freq_mistakes: list[dict[str, object]]
    unmastered_knowledge_points: list[dict[str, object]]
    predicted_paper: list[dict[str, object]]
    generated_at: datetime
