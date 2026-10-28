"""批量判题（judge_many）契约测试。

批量是为配额窗口服务的：调用数按批缩小，但**绝不能**因此放行没判过的题。
这里钉住三件事：
1. 解析器只按 index 收结果，非法/重复 index 丢弃；
2. 批量结果里的 reject 如实转成拒绝；
3. 缺项一律回退单题判，单题判失败按 ERROR 处理（不放行）。
"""

from __future__ import annotations

import json

from app.config import Settings
from app.data.curriculum import KnowledgePoint
from app.services.question_generator import GeneratedQuestion
from app.services.question_verify import QuestionVerifier, _parse_judge_batch


def _point() -> KnowledgePoint:
    return KnowledgePoint(
        id="g1c-pinyin-initials",
        name="声母",
        subject="chinese",
        grade="grade1",
        unit_code="g1c-u1",
        unit_name="拼音",
        objective="准确认读 23 个声母",
        question_types=("choice", "judge"),
        difficulty_band=1,
        prerequisites=(),
    )


def _question(index: int) -> GeneratedQuestion:
    return GeneratedQuestion(
        qtype="choice",
        stem="第" + str(index) + "题：下面哪个是声母？",
        options={"A": "b", "B": "ɑ", "C": "o", "D": "e"},
        answer="A",
        analysis="b 是声母。",
        hint1="想一想声母表。",
        hint2="声母是发音时气流受阻的字母。",
        hint3="答案是 b。",
        difficulty=1,
        knowledge_point_id="g1c-pinyin-initials",
    )


class _StubResult:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubClient:
    """按顺序返回预设内容；记录调用次数。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def bind_session(self, session: object) -> None:
        del session

    async def complete(self, messages: object, **kwargs: object) -> _StubResult:
        del messages, kwargs
        self.calls += 1
        if not self._responses:
            return _StubResult("")
        return _StubResult(self._responses.pop(0))


def test_parse_batch_ignores_invalid_and_duplicate_indexes() -> None:
    raw = json.dumps(
        {
            "results": [
                {"index": 1, "verdict": "pass", "score": 90, "reason": "ok"},
                {"index": 1, "verdict": "reject", "score": 10, "reason": "dup"},
                {"index": 0, "verdict": "pass", "score": 90, "reason": "bad index"},
                {"index": 2, "verdict": "maybe", "score": 50, "reason": "bad verdict"},
            ]
        }
    )
    parsed = _parse_judge_batch(raw)
    assert list(parsed) == [1]
    assert parsed[1][0] == "pass"


def test_parse_batch_tolerates_fence_and_noise() -> None:
    raw = 'result:\n```json\n{"results": [{"index": 3, "verdict": "reject", "score": 20}]}\n```'
    parsed = _parse_judge_batch(raw)
    assert parsed[3][0] == "reject"


def test_parse_batch_tolerates_bare_array() -> None:
    """推理模型直接输出数组（无 results 包装）时也要能按 index 收结果。"""
    raw = json.dumps(
        [
            {"index": 1, "verdict": "pass", "score": 88, "reason": "合格"},
            {"index": 2, "verdict": "reject", "score": 30, "reason": "答案错误"},
        ]
    )
    parsed = _parse_judge_batch(raw)
    assert parsed[1][0] == "pass"
    assert parsed[2][0] == "reject"


async def test_judge_many_rejects_partial_batch_and_falls_back_all() -> None:
    # 批量只回第 1、3 题（第 2 题缺项）→ 题号集合不匹配，整批作废，
    # 三题全部回退单题判。绝不把某题结论套到另一题上。
    batch = json.dumps(
        {
            "results": [
                {"index": 1, "verdict": "pass", "score": 88, "reason": "合格"},
                {"index": 3, "verdict": "reject", "score": 30, "reason": "答案错误"},
            ]
        }
    )
    singles = [
        json.dumps({"verdict": "pass", "score": 80, "reason": "单题 1 合格"}),
        json.dumps({"verdict": "reject", "score": 25, "reason": "单题 2 不合格"}),
        json.dumps({"verdict": "reject", "score": 30, "reason": "单题 3 不合格"}),
    ]
    client = _StubClient([batch, *singles])
    verifier = QuestionVerifier(client, Settings())  # type: ignore[arg-type]

    outcomes = await verifier.judge_many([_question(1), _question(2), _question(3)], _point())

    assert [o[0] for o in outcomes] == [True, False, False]
    assert client.calls == 4, "一次批量 + 三次单题回退"


async def test_judge_many_rejects_zero_based_batch() -> None:
    """模型按 0 基返回时必须整批作废——否则第 2 题的结论会被套到第 1 题上。"""
    batch = json.dumps(
        {
            "results": [
                {"index": 0, "verdict": "reject", "score": 10, "reason": "对第 1 题"},
                {"index": 1, "verdict": "pass", "score": 90, "reason": "对第 2 题"},
            ]
        }
    )
    singles = [
        json.dumps({"verdict": "pass", "score": 90, "reason": "ok"}),
        json.dumps({"verdict": "pass", "score": 90, "reason": "ok"}),
    ]
    client = _StubClient([batch, *singles])
    verifier = QuestionVerifier(client, Settings())  # type: ignore[arg-type]

    outcomes = await verifier.judge_many([_question(1), _question(2)], _point())

    assert [o[0] for o in outcomes] == [True, True], "回退结果应来自单题判（全部合格）"
    assert client.calls == 3


async def test_judge_many_marks_missing_as_unavailable_when_fallback_fails() -> None:
    # 批量结果完全无法解析，且回退也失败 → 每题都必须 ERROR（judge_passed=None），不放行
    client = _StubClient(["not json", "", ""])
    verifier = QuestionVerifier(client, Settings())  # type: ignore[arg-type]

    outcomes = await verifier.judge_many([_question(1), _question(2)], _point())

    assert [o[0] for o in outcomes] == [None, None]


async def test_judge_many_short_circuits_when_disabled() -> None:
    """--no-judge：不调用模型，全部放行（批量化后必须同样生效）。"""
    client = _StubClient([])
    verifier = QuestionVerifier(client, Settings())  # type: ignore[arg-type]
    verifier.judge_enabled = False

    outcomes = await verifier.judge_many([_question(1), _question(2)], _point())

    assert [o[0] for o in outcomes] == [True, True]
    assert client.calls == 0
