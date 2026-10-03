"""题目自动验证（P1 / §6.2 第三段）。

按学科走两条通道，这是 REBUILD §6.2 的明确要求：

- **数学**：规则 + SymPy 双保险。用 `math_verify.are_equivalent` 把题干里的表达式
  与标准答案对拍；口算题必须能解析成算式并算出答案；选择/判断题检查选项唯一性。
  数学题不需要 LLM judge——算术事实可以用符号计算验证，用模型"看一眼"反而不可靠。
- **语文 / 英语**：规则通道（选项唯一性、答案在选项内、答案不得出现在题干里、
  提示层级不得泄底）+ LLM judge 通道（语义正确性、适龄性、答案唯一性）。
  规则挡不住"汉字写错了但结构合法""英文单词拼错但格式正确"，所以必须双通道。

任一通道判定 reject 就整题淘汰，不做"部分通过"。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum

import sympy

from app.config import Settings
from app.data.curriculum import KnowledgePoint
from app.services.llm_client import LlmClient
from app.services.math_verify import is_pure_math, parse_math, strip_latex
from app.services.prompts import CONTENT_JUDGE_SYSTEM_PROMPT, CONTENT_JUDGE_USER_TEMPLATE
from app.services.question_generator import GeneratedQuestion

logger = logging.getLogger("xueban.content.verify")


class Verdict(StrEnum):
    """单题验证结论。"""

    PASS = "pass"
    REJECT = "reject"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """一道题的验证结论与依据。"""

    verdict: Verdict
    rule_passed: bool
    judge_passed: bool | None
    score: int | None
    reason: str

    @property
    def accepted(self) -> bool:
        return self.verdict is Verdict.PASS


@dataclass(slots=True)
class VerificationReport:
    """一批题的验证统计。"""

    total: int = 0
    rule_passed: int = 0
    judge_passed: int = 0
    judge_skipped: int = 0
    rejected: int = 0
    judge_errors: int = 0

    @property
    def rule_pass_rate(self) -> float:
        return self.rule_passed / self.total if self.total else 0.0

    @property
    def final_accept_rate(self) -> float:
        return (self.total - self.rejected - self.judge_errors) / self.total if self.total else 0.0


# judge 的通过门槛：低于此分视为不合格（judge 同时要给出 verdict）
JUDGE_SCORE_THRESHOLD = 60

_CHINESE_TRUE = frozenset({"对", "正确", "√", "T", "true", "是", "对的"})
_CHINESE_FALSE = frozenset({"错", "错误", "×", "F", "false", "否", "不对"})

_MATH_SUBJECT = "math"

# judge 结论：(是否通过, 评分, 说明)；评分为 None 表示 judge 不可用
JudgeOutcome = tuple[bool | None, int | None, str]


def _answer_appears_in_stem(stem: str, answer: str) -> bool:
    """答案是否被直接写进题干（守护型讲解红线）。

    只拦「把答案原样摆出来」的模式（如「答案是 14」「正确答案：声母 b」），
    而不是任何子串出现——题干本身常需提到该知识点（如 hint 里的
    「声母表第一个是 b」），那属于正常引导，拦掉会误杀大量好题。
    """
    cleaned = answer.strip()
    if len(cleaned) < 2:
        return False
    escaped = re.escape(cleaned)
    patterns = (
        rf"答案(?:是|为)?\s*[：:]?\s*{escaped}",
        rf"正确答案\s*[：:]\s*{escaped}",
        rf"(?:应该|该)选\s*{escaped}",
        rf"正确选项(?:是|为)\s*{escaped}",
        rf"就是{escaped}",
        rf"^[\s。．.]*{escaped}[\s。．.]*$",
    )
    return any(re.search(pattern, stem) for pattern in patterns)


def _option_key(answer: str) -> str:
    return answer.strip().upper()


def _check_options_unique(question: GeneratedQuestion) -> str | None:
    """选择题/连线题：答案必须指向存在的选项，且选项值不得重复。"""
    if question.qtype not in {"choice", "match"}:
        return None
    if not question.options:
        return "选择题缺少选项"
    values = [value.strip() for value in question.options.values()]
    if len(set(values)) != len(values):
        return "选项内容重复，无法唯一作答"
    if question.qtype == "choice":
        if _answer_appears_in_stem(question.stem, next(
            (v for k, v in question.options.items() if k.upper() == _option_key(question.answer)),
            "",
        )):
            return "题干中出现了正确选项内容，等于直接给答案"
        if _option_key(question.answer) not in {key.upper() for key in question.options}:
            return "答案不在选项范围内"
    return None


def _check_judge_answer_format(question: GeneratedQuestion) -> str | None:
    """判断题答案必须是「对/错」这类明确表述。"""
    if question.qtype != "judge":
        return None
    answer = question.answer.strip()
    if answer in _CHINESE_TRUE or answer in _CHINESE_FALSE:
        return None
    return "判断题答案必须是「对」或「错」"


def _check_hints_not_leaking(question: GeneratedQuestion) -> str | None:
    """三层提示红线：第 1、2 层不得包含最终答案。"""
    if question.qtype == "choice":
        target = next(
            (value for key, value in (question.options or {}).items()
             if key.upper() == _option_key(question.answer)),
            None,
        )
    else:
        target = question.answer
    if not target:
        return None
    for level, text in ((1, question.hint1), (2, question.hint2)):
        if _answer_appears_in_stem(text, target):
            return f"第 {level} 层提示泄露了最终答案"
    return None


def _normalize_math_text(text: str) -> str:
    """把全角标点归一化成半角，让 SymPy 能吃下中文题面。"""
    table = str.maketrans(
        {
            "＋": "+",
            "－": "-",
            "×": "*",
            "÷": "/",
            "＝": "=",
            "？": "?",
            "．": ".",
            "（": "(",
            "）": ")",
        }
    )
    return text.translate(table)


#: 题干里可能夹着中文叙述（「混合运算：3 + 5 + 4」），求值前要先抽出纯算式段。
_MATH_SEGMENT = re.compile(r"[\d][\d\s+\-*/().^]*[\d)]|\d")


def _math_left_side(stem: str) -> str | None:
    """取出题干里最后一个等号的左侧算式（"9 + 5 = ？" → "9 + 5"）。"""
    if "=" not in stem:
        return None
    left, _, _ = stem.rpartition("=")
    # 剥掉 $ 定界符：出题 prompt 要求用 $...$，SymPy 吃不下（见 math_verify.strip_latex）。
    left = strip_latex(left).strip()
    if not left or not re.search(r"\d", left):
        return None
    if is_pure_math(left):
        return left
    # 左侧混着中文叙述时取最长的一段纯算式
    segment = max(_MATH_SEGMENT.findall(left), key=len, default="")
    return segment.strip() or None


def _check_math_answer(question: GeneratedQuestion) -> str | None:
    """数学题：用 SymPy 求值题干算式，与标准答案对拍。

    求值**等号左侧**而不是比较等号两侧，是因为中文题面里右侧常常是"？"（答案留空）
    或与答案重复；从左侧算更可靠，也能同时覆盖 "12 + 7 = 19" 这种右侧已给值
    的写法。
    """
    stem = _normalize_math_text(question.stem)
    left = _math_left_side(stem)
    if left is not None:
        expr = parse_math(left)
        if expr is not None:
            try:
                expected = expr.evalf()
                answer_expr = parse_math(question.answer)
                if answer_expr is None:
                    return f"标准答案 {question.answer} 不是可计算的数学表达式"
                if not bool(sympy.simplify(expected - answer_expr) == 0):
                    return f"题干算式 {left} 的结果是 {expected}，与标准答案不一致"
            except (TypeError, ValueError, ZeroDivisionError):
                return "题干算式无法求值"
        else:
            return f"题干算式 {left} 无法解析"

    if (
        question.qtype == "oral"
        and parse_math(stem.replace("?", "").strip()) is None
        and len(re.findall(r"-?\d+(?:\.\d+)?", stem)) < 2
    ):
        return "口算题无法识别算式"
    return None


def rule_verify(question: GeneratedQuestion, point: KnowledgePoint) -> str | None:
    """规则通道；返回 None 表示通过，否则返回拒绝理由。"""
    if not question.stem.strip():
        return "题干为空"
    if len(question.stem) > 300:
        return "题干过长，不适合低年级朗读"
    for name in ("analysis", "hint1", "hint2", "hint3"):
        if not getattr(question, name).strip():
            return f"{name} 为空"

    reasons = (
        _check_options_unique(question),
        _check_judge_answer_format(question),
        _check_hints_not_leaking(question),
    )
    for reason in reasons:
        if reason:
            return reason

    if point.subject == _MATH_SUBJECT:
        return _check_math_answer(question)
    return None


def _parse_judge_payload(raw: str) -> tuple[str, int, str] | None:
    """解析 judge 返回的 JSON，容忍 ```json 包裹。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    verdict = str(payload.get("verdict", "")).strip().lower()
    try:
        score = int(payload.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    reason = str(payload.get("reason", "")).strip()
    if verdict not in {"pass", "reject"}:
        return None
    return verdict, score, reason


class QuestionVerifier:
    """规则 + LLM judge 双通道验证。"""

    def __init__(self, client: LlmClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def judge(
        self, question: GeneratedQuestion, point: KnowledgePoint
    ) -> JudgeOutcome:
        """LLM judge 通道；judge 不可用时返回 (None, None, 原因)。"""
        self._client.bind_session(f"{self._settings.llm_session_prefix}-judge-{point.id}")
        options_block = (
            "\n".join(f"{key}. {value}" for key, value in (question.options or {}).items())
            or "（无选项）"
        )
        messages = [
            {"role": "system", "content": CONTENT_JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": CONTENT_JUDGE_USER_TEMPLATE.format(
                    point_name=point.name,
                    grade_name={"grade1": "一年级", "grade2": "二年级"}.get(
                        point.grade, point.grade
                    ),
                    subject_name={"math": "数学", "chinese": "语文", "english": "英语"}.get(
                        point.subject, point.subject
                    ),
                    objective=point.objective,
                    qtype=question.qtype,
                    stem=question.stem,
                    options=options_block,
                    answer=question.answer,
                    analysis=question.analysis,
                    hint1=question.hint1,
                    hint2=question.hint2,
                    hint3=question.hint3,
                ),
            },
        ]
        result = await self._client.complete(
            messages,
            model=self._settings.content_judge_model,
            temperature=0.1,
            # judge 一次只判一题，输出很短；但推理模型仍要先花 reasoning 预算，
            # 给太少会拿到空正文，所以至少按单题预留下限。
            max_tokens=max(
                self._settings.content_tokens_per_question * 2,
                self._settings.content_max_tokens // 8,
            ),
            name=f"content.judge.{point.subject}",
        )
        parsed = _parse_judge_payload(result.content)
        if parsed is None:
            return None, None, "judge 输出无法解析"
        verdict, score, reason = parsed
        return verdict == "pass" and score >= JUDGE_SCORE_THRESHOLD, score, reason

    async def verify_one(
        self, question: GeneratedQuestion, point: KnowledgePoint
    ) -> VerificationResult:
        """单题验证：规则必过；非数学题额外要求 judge 通过。"""
        reason = rule_verify(question, point)
        if reason is not None:
            return VerificationResult(
                verdict=Verdict.REJECT,
                rule_passed=False,
                judge_passed=None,
                score=None,
                reason=f"规则不通过：{reason}",
            )

        if point.subject == _MATH_SUBJECT:
            return VerificationResult(
                verdict=Verdict.PASS,
                rule_passed=True,
                judge_passed=None,
                score=None,
                reason="规则 + SymPy 对拍通过",
            )

        try:
            passed, score, judge_reason = await self.judge(question, point)
        except Exception as exc:
            logger.warning("judge 调用失败 %s：%s", question.stem[:20], exc)
            return VerificationResult(
                verdict=Verdict.ERROR,
                rule_passed=True,
                judge_passed=None,
                score=None,
                reason=f"judge 调用失败：{type(exc).__name__}",
            )

        if passed is None:
            return VerificationResult(
                verdict=Verdict.ERROR,
                rule_passed=True,
                judge_passed=None,
                score=score,
                reason=f"judge 不可用：{judge_reason}",
            )

        return VerificationResult(
            verdict=Verdict.PASS if passed else Verdict.REJECT,
            rule_passed=True,
            judge_passed=passed,
            score=score,
            reason=judge_reason or ("judge 通过" if passed else "judge 判定不合格"),
        )

    async def verify_all(
        self, questions: list[GeneratedQuestion], point: KnowledgePoint
    ) -> tuple[
        list[GeneratedQuestion],
        list[tuple[GeneratedQuestion, VerificationResult]],
        VerificationReport,
    ]:
        """批量验证；返回 (通过, [(未通过题, 结果)], 统计)。"""
        report = VerificationReport(total=len(questions))
        passed: list[GeneratedQuestion] = []
        rejected: list[tuple[GeneratedQuestion, VerificationResult]] = []

        for question in questions:
            result = await self.verify_one(question, point)
            if result.rule_passed:
                report.rule_passed += 1
            if result.judge_passed is True:
                report.judge_passed += 1
            elif result.judge_passed is None:
                report.judge_skipped += 1
            if result.verdict is Verdict.ERROR:
                report.judge_errors += 1
            if result.accepted:
                passed.append(question)
            else:
                report.rejected += 1
                rejected.append((question, result))

        return passed, rejected, report


def verify_question_locally(
    question: GeneratedQuestion, point: KnowledgePoint
) -> VerificationResult:
    """只跑规则通道（供单测与不需要 judge 的场景使用）。"""
    reason = rule_verify(question, point)
    if reason is None:
        return VerificationResult(
            verdict=Verdict.PASS,
            rule_passed=True,
            judge_passed=None,
            score=None,
            reason="规则通道通过",
        )
    return VerificationResult(
        verdict=Verdict.REJECT,
        rule_passed=False,
        judge_passed=None,
        score=None,
        reason=f"规则不通过：{reason}",
    )


__all__ = [
    "JUDGE_SCORE_THRESHOLD",
    "QuestionVerifier",
    "Verdict",
    "VerificationReport",
    "VerificationResult",
    "rule_verify",
    "verify_question_locally",
]
