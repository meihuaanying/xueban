"""题库内容管线测试（P1 / §6.2）。

全部用 `httpx.MockTransport` 喂假响应，**不发起真实网络请求**（§8 约束 4：
生产路径零 mock，测试层才用 mock）。覆盖：

- 出题器：JSON 解析、```json 包裹、非法结构重问、字段缺失淘汰、难度夹取；
- 验证器：数学 SymPy 对拍、选项唯一性、答案不得出现在题干、三层提示红线；
- 去重器：阈值 0.95 的实际行为、精确指纹粗筛、跨批次种子拦截；
- 编排器：断点续跑（达标即跳过）、难度标定、入库与 5% 人审标记。
"""

from __future__ import annotations

import json
import random
import types
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.data.curriculum import KnowledgePoint, get_curriculum
from app.models import KnowledgePoint as KnowledgePointModel
from app.models import Question as QuestionModel
from app.models import QuestionKnowledgePoint, QuestionStatus, QuestionType
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.question_dedupe import (
    DEDUP_THRESHOLD,
    QuestionDeduplicator,
    fingerprint,
)
from app.services.question_generator import (
    ALLOWED_QTYPES,
    GeneratedQuestion,
    QuestionGenerator,
)
from app.services.question_pipeline import (
    ELEMENTARY_STAGE,
    HUMAN_REVIEW_RATE,
    PIPELINE_SOURCE,
    QuestionPipeline,
    _subject_of,
)
from app.services.question_verify import (
    JUDGE_SCORE_THRESHOLD,
    QuestionVerifier,
    Verdict,
    rule_verify,
    verify_question_locally,
)

# ---------------------------------------------------------------- 夹具


class FakeLangfuse:
    def start_observation(self, **kwargs: Any) -> Any:
        observation = types.SimpleNamespace(end=lambda: None, kwargs=kwargs)
        return observation

    def create_event(self, **kwargs: Any) -> None:
        del kwargs

    def flush(self) -> int:
        return 1


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "litellm_base_url": "http://llm.test",
        "litellm_master_key": "sk-test",
        "llm_max_retries": 1,
        "llm_retry_backoff_seconds": 0.0,
        "llm_rate_limit_retries": 0,
        "llm_rate_limit_backoff_seconds": 0.0,
        "embedding_provider": "lexical",
        "langfuse_public_key": "",
        "langfuse_secret_key": "",
    }
    base.update(overrides)
    return Settings(**base)


def make_client(handler: Any, **overrides: Any) -> LlmClient:
    settings = make_settings(**overrides)
    observability = ObservabilityService(settings, client=FakeLangfuse())
    return LlmClient(settings, observability, transport=httpx.MockTransport(handler))


def chat_body(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "x",
            "model": "kimi-k3",
            "choices": [{"message": {"content": content}}],
            "usage": {"total_tokens": 10},
        },
    )


def json_handler(payload: Any) -> Any:
    """永远返回同一份 JSON 的 handler。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return chat_body(json.dumps(payload, ensure_ascii=False))

    return handler


MATH_POINT = KnowledgePoint(
    id="g1m-add-within-20-carry",
    name="20 以内进位加法",
    subject="math",
    grade="grade1",
    unit_code="g1m-u2",
    unit_name="20 以内的进位加法与退位减法",
    objective="掌握凑十法",
    question_types=("choice", "oral", "fill"),
    difficulty_band=2,
    prerequisites=("g1m-add-within-10",),
)

CHINESE_POINT = KnowledgePoint(
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


def question_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "qtype": "choice",
        # 题干刻意不含答案内容，否则泄露检查会在题干这一步就命中，
        # 测不到第 1/2 层提示的检查。
        "stem": "下面哪个是声母？",
        "options": {"A": "b", "B": "a", "C": "p", "D": "d"},
        "answer": "A",
        "analysis": "b 是声母，书写时 ascender 在左。",
        "hint1": "想一想 23 个声母里第一个是什么。",
        "hint2": "声母表第一个是 b，读作「玻」。",
        "hint3": "完整解答：b 是声母，读作「玻」，写法是 b。",
        "difficulty": 3,
    }
    payload.update(overrides)
    return payload


def make_question(**overrides: Any) -> GeneratedQuestion:
    payload = question_payload(**overrides)
    return GeneratedQuestion(
        qtype=payload["qtype"],
        stem=payload["stem"],
        options=payload.get("options"),
        answer=payload["answer"],
        analysis=payload["analysis"],
        hint1=payload["hint1"],
        hint2=payload["hint2"],
        hint3=payload["hint3"],
        difficulty=payload["difficulty"],
        knowledge_point_id=CHINESE_POINT.id,
    )


# ---------------------------------------------------------------- 出题器


def test_allowed_qtypes_match_model_enum() -> None:
    """出题器允许的题型必须都能落进 QuestionType，否则入库会炸。"""
    assert {member.value for member in QuestionType} >= ALLOWED_QTYPES


async def test_generator_binds_session_per_point() -> None:
    """出题会话要按知识点绑定，同一知识点重试才能命中网关提示缓存。"""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["x-opencode-session"])
        return chat_body(json.dumps({"questions": [question_payload()]}))

    client = make_client(handler)
    await QuestionGenerator(client, make_settings()).generate(CHINESE_POINT, count=1)
    assert seen[0].endswith("-gen-g1c-pinyin-initials")


async def test_generator_returns_coerced_questions() -> None:
    client = make_client(json_handler({"questions": [question_payload()]}))
    generator = QuestionGenerator(client, make_settings())
    questions, report = await generator.generate(CHINESE_POINT, count=1)
    assert len(questions) == 1
    assert report.produced == 1
    assert questions[0].qtype == "choice"
    assert questions[0].knowledge_point_id == CHINESE_POINT.id


async def test_generator_handles_fenced_json() -> None:
    body = (
        "```json\n"
        + json.dumps({"questions": [question_payload()]}, ensure_ascii=False)
        + "\n```"
    )
    client = make_client(lambda request: chat_body(body))
    questions, _ = await QuestionGenerator(client, make_settings()).generate(
        CHINESE_POINT, count=1
    )
    assert len(questions) == 1


async def test_generator_accepts_bare_list() -> None:
    client = make_client(json_handler([question_payload()]))
    questions, _ = await QuestionGenerator(client, make_settings()).generate(
        CHINESE_POINT, count=1
    )
    assert len(questions) == 1


async def test_generator_retries_on_invalid_structure() -> None:
    """JSON 不合法时应重问，而不是直接失败。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return chat_body("这不是 JSON")
        return chat_body(json.dumps({"questions": [question_payload()]}, ensure_ascii=False))

    client = make_client(handler)
    questions, report = await QuestionGenerator(client, make_settings()).generate(
        CHINESE_POINT, count=1
    )
    assert calls["n"] == 2
    assert len(questions) == 1
    assert report.rejected_structure >= 1


async def test_generator_drops_incomplete_items() -> None:
    """缺 hint 的题必须淘汰（§6.2 要求每题带三层提示）。"""
    broken = question_payload()
    del broken["hint2"]
    client = make_client(json_handler({"questions": [broken, question_payload()]}))
    questions, report = await QuestionGenerator(client, make_settings()).generate(
        CHINESE_POINT, count=5, max_rounds=1
    )
    assert len(questions) == 1
    assert report.rejected_structure >= 1


async def test_generator_clamps_difficulty() -> None:
    client = make_client(
        json_handler(
            {
                "questions": [
                    question_payload(difficulty=99),
                    question_payload(difficulty=-5),
                ]
            }
        )
    )
    questions, _ = await QuestionGenerator(client, make_settings()).generate(
        CHINESE_POINT, count=2
    )
    assert sorted(q.difficulty for q in questions) == [1, 5]


async def test_generator_stops_at_requested_count() -> None:
    client = make_client(json_handler({"questions": [question_payload()] * 20}))
    questions, _ = await QuestionGenerator(client, make_settings()).generate(
        CHINESE_POINT, count=3
    )
    assert len(questions) == 3


async def test_generator_uses_generation_model() -> None:
    """出题必须走 content_generation_model，不是默认模型。"""
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return chat_body(json.dumps({"questions": [question_payload()]}))

    client = make_client(
        handler, llm_default_model="unused-model", content_generation_model="kimi-k3"
    )
    await QuestionGenerator(client, make_settings(llm_default_model="unused-model")).generate(
        CHINESE_POINT, count=1
    )
    assert seen[0]["model"] == "kimi-k3"


# ---------------------------------------------------------------- 规则通道


def test_rule_verify_rejects_empty_stem() -> None:
    assert rule_verify(make_question(stem="  "), CHINESE_POINT) is not None


def test_rule_verify_rejects_missing_hint() -> None:
    assert rule_verify(make_question(hint1=""), CHINESE_POINT) is not None


def test_rule_verify_rejects_long_stem() -> None:
    assert rule_verify(make_question(stem="字" * 301), CHINESE_POINT) is not None


def test_rule_verify_rejects_duplicate_options() -> None:
    question = make_question(options={"A": "b", "B": "a", "C": "b", "D": "d"})
    assert "重复" in (rule_verify(question, CHINESE_POINT) or "")


def test_rule_verify_rejects_answer_not_in_options() -> None:
    assert rule_verify(make_question(answer="Z"), CHINESE_POINT) is not None


def test_rule_verify_rejects_stem_leaking_answer() -> None:
    """题干里直接把答案摆出来 = 直接给答案（守护型红线）。"""
    question = make_question(
        stem="下面哪个是声母？答案是声母 b。",
        options={"A": "声母 b", "B": "声母 p", "C": "韵母 ɑ", "D": "韵母 o"},
        answer="A",
    )
    reason = rule_verify(question, CHINESE_POINT)
    assert reason is not None


def test_leak_check_allows_incidental_mention() -> None:
    """正常引导里提到与答案相关的字样不算泄露，不能误杀好题。"""
    question = make_question(
        hint2="声母表第一个是 b，读作「玻」，你从声母 b 里挑一个。",
        options={"A": "声母 b", "B": "声母 p", "C": "韵母 ɑ", "D": "韵母 o"},
    )
    assert rule_verify(question, CHINESE_POINT) is None


def test_single_character_answers_are_exempt_from_leak_check() -> None:
    """已知限制：单字答案（b / 对 / 7）做泄露模式检测会大量误报。

    题干本身常需要提到该字（"下面哪个是声母 b？"），因此对长度 < 2 的答案
    跳过模式检查，改由 LLM judge 通道兜底。这里把这个行为显式钉住，
    避免后人误以为单字答案也受模式检查保护。
    """
    question = make_question(stem="下面哪个是声母 b？", answer="A")
    assert rule_verify(question, CHINESE_POINT) is None


def test_rule_verify_requires_judge_answer_format() -> None:
    question = make_question(qtype="judge", options=None, answer="也许")
    assert rule_verify(question, CHINESE_POINT) is not None


def test_rule_verify_accepts_chinese_judge_answers() -> None:
    for word in ("对", "错"):
        question = make_question(qtype="judge", options=None, answer=word)
        assert rule_verify(question, CHINESE_POINT) is None


def test_rule_verify_rejects_hint1_leaking_answer() -> None:
    """第 1 层提示不得泄露最终答案（§8 约束 1）。"""
    question = make_question(
        hint1="想一想就可以了，正确答案就是声母 b 这个说法。",
        options={"A": "声母 b", "B": "声母 p", "C": "韵母 ɑ", "D": "韵母 o"},
    )
    reason = rule_verify(question, CHINESE_POINT)
    assert reason is not None and "第 1 层" in reason


def test_rule_verify_rejects_hint2_leaking_answer() -> None:
    question = make_question(
        hint2="正确选项是声母 b 这一个，读作玻。",
        options={"A": "声母 b", "B": "声母 p", "C": "韵母 ɑ", "D": "韵母 o"},
    )
    reason = rule_verify(question, CHINESE_POINT)
    assert reason is not None and "第 2 层" in reason


def test_rule_verify_allows_hint3_to_contain_answer() -> None:
    """第 3 层是完整解答，必须允许给答案。"""
    assert rule_verify(make_question(hint3="答案：b"), CHINESE_POINT) is None


def test_rule_verify_accepts_good_choice() -> None:
    assert rule_verify(make_question(), CHINESE_POINT) is None


def test_math_rule_rejects_wrong_arithmetic() -> None:
    """数学题：题干算式的结果与标准答案不一致必须拒（SymPy 对拍）。"""
    correct = make_question(
        qtype="fill",
        stem="9 + 5 = ？",
        options=None,
        answer="14",
        knowledge_point_id=MATH_POINT.id,
    )
    assert rule_verify(correct, MATH_POINT) is None

    wrong = make_question(
        qtype="fill",
        stem="9 + 5 = ？",
        options=None,
        answer="15",
        knowledge_point_id=MATH_POINT.id,
    )
    assert rule_verify(wrong, MATH_POINT) is not None


def test_math_rule_rejects_equal_stem_with_wrong_answer() -> None:
    question = make_question(
        qtype="fill",
        stem="计算：12 + 7 = 19",
        options=None,
        answer="20",
        knowledge_point_id=MATH_POINT.id,
    )
    assert rule_verify(question, MATH_POINT) is not None


def test_math_rule_rejects_unparseable_oral() -> None:
    question = make_question(
        qtype="oral",
        stem="口算：几加几？",
        options=None,
        answer="5",
        knowledge_point_id=MATH_POINT.id,
    )
    assert rule_verify(question, MATH_POINT) is not None


def test_verify_question_locally_helper() -> None:
    result = verify_question_locally(make_question(), CHINESE_POINT)
    assert result.verdict is Verdict.PASS
    assert result.accepted


def test_verify_question_locally_rejects() -> None:
    result = verify_question_locally(make_question(stem=""), CHINESE_POINT)
    assert result.verdict is Verdict.REJECT
    assert not result.accepted


# ---------------------------------------------------------------- LLM judge


def judge_handler(verdict: str, score: int, reason: str = "ok") -> Any:
    payload = {"verdict": verdict, "score": score, "reason": reason}

    def handler(request: httpx.Request) -> httpx.Response:
        return chat_body(json.dumps(payload, ensure_ascii=False))

    return handler


async def test_judge_pass_for_chinese() -> None:
    client = make_client(judge_handler("pass", 90))
    result = await QuestionVerifier(client, make_settings()).verify_one(
        make_question(), CHINESE_POINT
    )
    assert result.verdict is Verdict.PASS
    assert result.judge_passed is True
    assert result.score == 90


async def test_judge_reject_low_score() -> None:
    client = make_client(judge_handler("pass", JUDGE_SCORE_THRESHOLD - 1))
    result = await QuestionVerifier(client, make_settings()).verify_one(
        make_question(), CHINESE_POINT
    )
    assert result.verdict is Verdict.REJECT


async def test_judge_reject_verdict() -> None:
    client = make_client(judge_handler("reject", 95, "答案错了"))
    result = await QuestionVerifier(client, make_settings()).verify_one(
        make_question(), CHINESE_POINT
    )
    assert result.verdict is Verdict.REJECT


async def test_judge_unparseable_is_error_not_reject() -> None:
    """judge 挂掉不等于题目有问题，必须区分 ERROR 与 REJECT。"""
    client = make_client(lambda request: chat_body("judge 说不上来"))
    result = await QuestionVerifier(client, make_settings()).verify_one(
        make_question(), CHINESE_POINT
    )
    assert result.verdict is Verdict.ERROR
    assert not result.accepted


async def test_math_skips_judge_entirely() -> None:
    """数学题不走 LLM judge：算术用符号计算验证更可靠。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return chat_body("不应该被调用")

    question = make_question(
        qtype="fill",
        stem="9 + 5 = ？",
        options=None,
        answer="15",
        knowledge_point_id=MATH_POINT.id,
    )
    result = await QuestionVerifier(make_client(handler), make_settings()).verify_one(
        question, MATH_POINT
    )
    assert result.verdict is Verdict.REJECT
    assert calls["n"] == 0


async def test_judge_uses_judge_model() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return chat_body(json.dumps({"verdict": "pass", "score": 90, "reason": "ok"}))

    settings = make_settings(llm_default_model="unused", content_judge_model="deepseek-v4-flash")
    client = make_client(
        handler, llm_default_model="unused", content_judge_model="deepseek-v4-flash"
    )
    await QuestionVerifier(client, settings).verify_one(make_question(), CHINESE_POINT)
    assert seen[0]["model"] == "deepseek-v4-flash"


async def test_verify_all_reports_rates() -> None:
    client = make_client(judge_handler("pass", 90))
    questions = [make_question(stem=f"题目 {index}") for index in range(3)]
    questions.append(make_question(stem=""))
    passed, rejected, report = await QuestionVerifier(client, make_settings()).verify_all(
        questions, CHINESE_POINT
    )
    assert len(passed) == 3
    assert len(rejected) == 1
    assert report.total == 4
    assert report.rejected == 1
    assert report.rule_pass_rate == 0.75


# ---------------------------------------------------------------- 去重


def test_fingerprint_normalizes_punctuation_and_width() -> None:
    assert fingerprint("9 + 5 = ？") == fingerprint("9+5=?")
    assert fingerprint("ＡＢＣ") == fingerprint("abc")


async def test_dedupe_removes_exact_fingerprint_duplicates() -> None:
    questions = [make_question(stem="甲乙丙"), make_question(stem="甲 乙，丙")]
    result = await QuestionDeduplicator(make_settings()).dedupe(questions)
    assert len(result.kept) == 1
    assert result.removed_count == 1


async def test_dedupe_removes_near_duplicates() -> None:
    questions = [
        make_question(stem="小明有 8 个苹果，又买来 5 个，小明现在有多少个苹果？"),
        make_question(stem="小明有8个苹果，又买来5个，小明现在有多少个苹果"),
        make_question(stem="钟面上分针指向 6 时，时针指向哪里？"),
    ]
    result = await QuestionDeduplicator(make_settings()).dedupe(questions)
    assert len(result.kept) == 2
    assert result.removed_count == 1
    assert result.removal_rate == pytest.approx(1 / 3)


async def test_dedupe_keeps_distinct_questions() -> None:
    questions = [
        make_question(stem="下面哪个是声母 b？"),
        make_question(stem="下面哪个是韵母 a？"),
        make_question(stem="「日」的笔顺是先横后竖吗？"),
    ]
    result = await QuestionDeduplicator(make_settings()).dedupe(questions)
    assert len(result.kept) == 3
    assert result.removal_rate == 0.0


async def test_dedupe_uses_seed_to_block_cross_batch_repeats() -> None:
    """断点续跑时，已入库题的种子必须能拦住新生成的重复题。"""
    settings = make_settings()
    provider = QuestionDeduplicator(settings)
    seed = make_question(stem="小明有 8 个苹果，又买来 5 个，小明现在有多少个苹果？")
    [seed_vector] = await provider._provider.embed([seed.stem])
    fresh = make_question(stem="小明有8个苹果，又买来5个，小明现在有多少个苹果")
    result = await provider.dedupe([fresh], seed_vectors=[seed_vector], seed_fingerprints=[])
    assert len(result.kept) == 0
    assert result.removed_count == 1


async def test_dedupe_threshold_is_configurable_and_default_is_095() -> None:
    assert DEDUP_THRESHOLD == 0.95
    strict = QuestionDeduplicator(make_settings(), threshold=0.1)
    questions = [
        make_question(stem="下面哪个是声母 b？"),
        make_question(stem="下面哪个是韵母 a？"),
    ]
    result = await strict.dedupe(questions)
    assert result.removed_count == 1


async def test_dedupe_empty_input() -> None:
    result = await QuestionDeduplicator(make_settings()).dedupe([])
    assert result.kept == []
    assert result.removal_rate == 0.0


# ---------------------------------------------------------------- 编排器


def test_subject_of_point_id() -> None:
    assert _subject_of("g1m-add-within-10") == "math"
    assert _subject_of("g2c-hanzi-basic") == "chinese"
    assert _subject_of("g1e-letter-a-g") == "english"
    assert _subject_of("weird") == "unknown"


def test_pipeline_uses_isolated_elementary_stage() -> None:
    """小学内容必须与存量 elementary（初中）题库隔离。"""
    assert ELEMENTARY_STAGE == "grade1_2"


def test_pipeline_review_rate_is_five_percent() -> None:
    assert HUMAN_REVIEW_RATE == 0.05
    assert PIPELINE_SOURCE == "llm-pipeline-v1"


def test_pipeline_calibrates_difficulty_around_band() -> None:
    pipeline = QuestionPipeline(
        make_client(lambda request: chat_body("{}")), make_settings(), rng=random.Random(0)
    )
    band1 = pipeline._calibrate_difficulty(
        make_question(difficulty=3), MATH_POINT.__class__(
            id="x", name="n", subject="math", grade="grade1", unit_code="u", unit_name="u",
            objective="o", question_types=("oral",), difficulty_band=1, prerequisites=(),
        )
    )
    band3 = pipeline._calibrate_difficulty(
        make_question(difficulty=3), MATH_POINT.__class__(
            id="y", name="n", subject="math", grade="grade1", unit_code="u", unit_name="u",
            objective="o", question_types=("oral",), difficulty_band=3, prerequisites=(),
        )
    )
    assert 1 <= band1 <= 5 and 1 <= band3 <= 5
    assert band1 < band3


async def test_pipeline_skips_point_already_at_target(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """断点续跑：已达标知识点不再调用 LLM。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return chat_body(json.dumps({"questions": [question_payload()]}))

    async with sessionmaker() as session:
        pipeline = QuestionPipeline(
            make_client(handler), make_settings(), request_interval_seconds=0
        )
        kp_id = await pipeline._ensure_knowledge_point(session, CHINESE_POINT, 0)
        for index in range(2):
            record = QuestionModel(
                subject="chinese",
                stage=ELEMENTARY_STAGE,
                qtype=QuestionType.CHOICE,
                stem=f"预置题目 {index}",
                answer="A",
                status=QuestionStatus.PUBLISHED,
            )
            session.add(record)
            await session.flush()
            session.add(QuestionKnowledgePoint(question_id=record.id, knowledge_point_id=kp_id))
        await session.commit()

        outcome = await pipeline.process_point(session, CHINESE_POINT, target=2)
        assert outcome.skipped is True
        assert calls["n"] == 0


async def test_pipeline_inserts_published_questions(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """端到端：生成 → 验证 → 去重 → 入库，并打上 pipeline 来源标记。"""
    # 题干必须彼此真正不同：词面向量对"只差一个数字"的题干会判重复，
    # 那正是去重要拦住的行为，用它当夹具只会测到去重而不是入库。
    stems = [
        "下面哪一个是单韵母？",
        "「妈」字的左边偏旁是什么？",
        "「b」属于声母还是韵母？",
        "「ɑ」这个音属于哪一类韵母？",
        "「m」读的时候气流要从哪里出来？",
        "拼读「dɑ」的时候先读哪个音？",
    ]
    # 选项也要随题干变化：题干相近而选项相同，词面向量仍会判重复。
    options = [
        {"A": "单韵母", "B": "声母", "C": "整体认读音节", "D": "复韵母"},
        {"A": "女字旁", "B": "木字旁", "C": "三点水", "D": "单人旁"},
        {"A": "声母", "B": "韵母", "C": "音节", "D": "汉字"},
        {"A": "单韵母", "B": "复韵母", "C": "鼻韵母", "D": "声母"},
        {"A": "鼻子出气", "B": "嘴里送气", "C": "喉咙摩擦", "D": "舌头不动"},
        {"A": "先读声母", "B": "先读韵母", "C": "同时读出", "D": "从后往前读"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.content.decode("utf-8")
        if '"stem"' in payload or "questions" in payload:
            if "verdict" in payload or "质检" in payload:
                return chat_body(json.dumps({"verdict": "pass", "score": 90, "reason": "ok"}))
            return chat_body(
                json.dumps(
                    {
                        "questions": [
                            question_payload(stem=stem, options=option, answer="A")
                            for stem, option in zip(stems, options, strict=True)
                        ]
                    },
                    ensure_ascii=False,
                )
            )
        return chat_body(json.dumps({"verdict": "pass", "score": 90, "reason": "ok"}))

    settings = make_settings(content_batch_size=3)
    pipeline = QuestionPipeline(
        make_client(handler), settings, request_interval_seconds=0, rng=random.Random(7)
    )
    async with sessionmaker() as session:
        outcome = await pipeline.process_point(session, CHINESE_POINT, target=6)
        # 6 道题同属「拼音」知识点，词面高度重合，lexical 会判掉一部分近重复。
        # 这里不假设"全部入库"——那是 bge-m3 的能力；只断言账目自洽：
        # 入库 + 去重 == 验证通过，且至少入库 1 道。
        assert outcome.generated >= len(stems)
        assert outcome.inserted + outcome.deduped_away == outcome.verified
        assert outcome.inserted >= 1
        assert outcome.verified == len(stems), "规则 + judge 都应放行这批题"
        assert outcome.for_review == pytest.approx(outcome.inserted * HUMAN_REVIEW_RATE, abs=1)

        rows = (
            await session.execute(
                select(QuestionModel).where(QuestionModel.source == PIPELINE_SOURCE)
            )
        ).scalars().all()
        assert len(rows) == outcome.inserted
        for row in rows:
            assert row.stage == ELEMENTARY_STAGE
            assert row.status in (QuestionStatus.REVIEW, QuestionStatus.PUBLISHED)
            assert "第1层·思路提示" in (row.analysis or "")
            assert "第3层·完整解答" in (row.analysis or "")

        kp = (
            await session.execute(
                select(KnowledgePointModel).where(
                    KnowledgePointModel.code == CHINESE_POINT.id
                )
            )
        ).scalar_one()
        assert kp.stage == ELEMENTARY_STAGE
        linked = await session.scalar(
            select(func.count())
            .select_from(QuestionKnowledgePoint)
            .where(QuestionKnowledgePoint.knowledge_point_id == kp.id)
        )
        assert linked == outcome.inserted


async def test_pipeline_deduplicates_against_existing(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """已有相似题时，新生成的重复题必须被去重挡掉。"""
    shared = "下面哪个是声母 b？这是全批共有的题干。"

    def handler(request: httpx.Request) -> httpx.Response:
        text = request.content.decode("utf-8")
        if "verdict" in text or "质检" in text:
            return chat_body(json.dumps({"verdict": "pass", "score": 90, "reason": "ok"}))
        return chat_body(
            json.dumps(
                {
                    "questions": [
                        question_payload(
                            stem=shared,
                            options={"A": "甲", "B": "乙", "C": "丙", "D": "丁"},
                        )
                        for _ in range(5)
                    ]
                },
                ensure_ascii=False,
            )
        )

    pipeline = QuestionPipeline(
        make_client(handler), make_settings(), request_interval_seconds=0, rng=random.Random(1)
    )
    async with sessionmaker() as session:
        outcome = await pipeline.process_point(session, CHINESE_POINT, target=4)
        assert outcome.deduped_away >= 3
        assert outcome.inserted == 1


async def test_pipeline_report_rates() -> None:
    """统计字段要能支撑简报：生成量/验证通过率/去重剔除率/学科汇总。"""
    from app.services.question_pipeline import PipelineReport, PointOutcome

    report = PipelineReport(
        outcomes=[
            PointOutcome(
                point_id="g1m-a",
                generated=40,
                verified=32,
                deduped_away=6,
                inserted=26,
                for_review=1,
            ),
            PointOutcome(
                point_id="g1c-b",
                generated=30,
                verified=30,
                deduped_away=0,
                inserted=30,
                for_review=2,
            ),
        ]
    )
    assert report.total_generated == 70
    assert report.total_verified == 62
    assert report.verify_pass_rate == pytest.approx(62 / 70)
    assert report.dedupe_removal_rate == pytest.approx(6 / 68)
    assert report.by_subject()["math"]["inserted"] == 26


def test_curriculum_points_are_usable_by_pipeline() -> None:
    """课程树里真实存在的知识点要能被管线直接消费。"""
    curriculum = get_curriculum("math")
    point = curriculum.by_id("g1m-add-within-20-carry")
    assert point is not None
    assert point.subject == "math"
    assert point.question_types
    assert point.objective


