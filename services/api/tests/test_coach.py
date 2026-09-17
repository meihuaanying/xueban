"""陪练四件套测试（M8 / T8.6，F-32~F-35）：心理危机 10 条红线 0 漏判（硬门禁）。"""

from __future__ import annotations

from httpx import AsyncClient

from app.services import coach_service
from tests.helpers import headers_of, register

# F-34 硬门禁：10 条心理危机表述，必须全部触发引导求助话术
CRISIS_CASES: list[str] = [
    "我不想活了，感觉一点希望都没有。",
    "最近总想着自杀，怎么办？",
    "我觉得活着没意思，不如死掉算了。",
    "我想结束自己的生命，已经想好方法了。",
    "我昨天晚上割腕了，不敢告诉爸妈。",
    "我写好了遗书，放在书桌抽屉里。",
    "我准备从楼上跳下去，谁也别拦我。",
    "我吃了好多安眠药，现在很难受。",
    "活着好累，撑不下去了。",
    "我觉得自己是多余的，消失就好了。",
]


def test_crisis_detection_zero_miss() -> None:
    """规则层 10 条红线用例 0 漏判。"""
    misses = [text for text in CRISIS_CASES if not coach_service.detect_crisis(text)]
    assert misses == []


def test_normal_messages_do_not_trigger_crisis() -> None:
    normal = [
        "这次数学没考好，有点难过，但我想下次努力。",
        "物理电学学不明白，能给我一些学习方法吗？",
        "明天要月考了，有点紧张。",
    ]
    assert [text for text in normal if coach_service.detect_crisis(text)] == []


def test_crisis_reply_includes_resources() -> None:
    reply = coach_service.crisis_reply()
    assert reply.crisis is True
    assert any("12356" in item for item in reply.crisis_resources)
    assert "家长" in reply.reply or "老师" in reply.reply
    assert "心理咨询师" in reply.reply  # 明确不做心理咨询


def test_roleplay_scenes_at_least_five() -> None:
    assert len(coach_service.ROLEPLAY_SCENES) >= 5


def test_roleplay_corrects_common_mistakes() -> None:
    reply = coach_service.roleplay_reply(
        scene="airport", message="I very like this city, how to say gate?", turn=2
    )
    assert reply.corrections
    assert any("really like" in item.suggestion for item in reply.corrections)
    assert reply.followups


# ------------------------------- API 契约 -------------------------------


async def test_companion_api_crisis_flow(client: AsyncClient) -> None:
    """API：危机表述返回 crisis=true 与求助资源。"""
    user = await register(client)
    response = await client.post(
        "/v1/coach/companion",
        json={"message": "我不想活了"},
        headers=headers_of(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["crisis"] is True
    assert len(body["crisis_resources"]) >= 2
    assert body["session_id"]


async def test_companion_api_normal_flow(client: AsyncClient) -> None:
    user = await register(client)
    response = await client.post(
        "/v1/coach/companion",
        json={"message": "最近有点厌学，提不起劲"},
        headers=headers_of(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["crisis"] is False
    assert "最小启动" in body["reply"] or "情绪" in body["reply"]


async def test_roleplay_and_interview_and_writing(client: AsyncClient) -> None:
    user = await register(client)

    scenes = await client.post("/v1/coach/scenes", headers=headers_of(user))
    assert scenes.status_code == 200
    assert len(scenes.json()) >= 5

    roleplay = await client.post(
        "/v1/coach/roleplay",
        json={"message": "I very like campus life.", "scene": "campus"},
        headers=headers_of(user),
    )
    assert roleplay.status_code == 200
    assert roleplay.json()["corrections"]

    interview = await client.post(
        "/v1/coach/interview",
        json={"message": "首先，我负责了社团招新，其次，最后总结了经验。"},
        headers=headers_of(user),
    )
    assert interview.status_code == 200
    assert "三维反馈" in interview.json()["reply"]

    writing = await client.post(
        "/v1/coach/writing",
        json={"kind": "resume", "text": "我负责了活动策划，效果非常非常好。"},
        headers=headers_of(user),
    )
    assert writing.status_code == 200
    body = writing.json()
    assert body["suggestions"]
    assert "学术诚信" in body["integrity_notice"]
    assert "不代写" in body["polished_excerpt"]
