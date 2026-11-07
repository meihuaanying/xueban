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
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

import sympy

from app.config import Settings
from app.data.curriculum import KnowledgePoint, stage_for_grade
from app.data.curriculum import grade_name as _grade_name
from app.data.curriculum import subject_name as _subject_name
from app.services.llm_client import LlmClient
from app.services.math_verify import is_pure_math, parse_math, strip_latex
from app.services.prompts import (
    CONTENT_JUDGE_BATCH_USER_TEMPLATE,
    CONTENT_JUDGE_QUESTION_BLOCK,
    CONTENT_JUDGE_USER_TEMPLATE,
    content_judge_system_prompt,
)
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
        # rejected 已经包含 judge 不可用（judge_errors）的题，不能再减一次
        return (self.total - self.rejected) / self.total if self.total else 0.0


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
    """选择题/多选题/连线题：答案必须指向存在的选项，且选项值不得重复。"""
    if question.qtype not in {"choice", "match", "multi_choice"}:
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


_MULTI_LETTER = re.compile(r"[A-Z]")


def _check_multi_choice_answer(question: GeneratedQuestion) -> str | None:
    """多选题专项规则：≥2 个字母、全部指向存在的选项、按字母顺序存储。"""
    if question.qtype != "multi_choice":
        return None
    if not question.options:
        return "多选题缺少选项"
    letters = sorted(set(_MULTI_LETTER.findall(question.answer.upper())))
    if len(letters) < 2:
        return "多选题答案至少包含两个选项字母"
    option_keys = {key.upper() for key in question.options}
    missing = [letter for letter in letters if letter not in option_keys]
    if missing:
        return f"答案字母不在选项范围内：{''.join(missing)}"
    canonical = "".join(letters)
    if canonical != "".join(_MULTI_LETTER.findall(question.answer.upper())):
        return "多选题答案必须按字母顺序存储（如 \"AC\"），否则判分与展示会乱序"
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
    elif question.qtype == "multi_choice":
        letters = set(_MULTI_LETTER.findall(question.answer.upper()))
        target = "；".join(
            value for key, value in (question.options or {}).items()
            if key.upper() in letters
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


def normalize_math_number(value: sympy.Expr) -> sympy.Expr:
    """把 sympy 数值归一：整数值的浮点尾巴砍掉（``14.0000000000000`` → ``14``）。

    只在**确实是整数**时收成 ``Integer``，非整数一律保持原值（``14.5`` 绝不能被
    收成 ``14``）。

    要说清楚这个函数的**实际**作用，避免后人重复我的误判：它**不是**为了救
    「整数 11 vs 浮点 11.0000000000000」——实测 sympy 的 ``simplify`` 会走
    ``.equals()`` 的容差判断，本来就判相等。归一真正换来的是两件事：

    1. **错误消息可读**：不再把 ``11.0000000000000`` 印进「与标准答案不一致」里
       干扰排障（这才是线上真正被看到的那条消息）；
    2. **比较走精确路径时不受浮点表示影响**（:func:`numbers_agree` 的补充分支）。

    历史上真正的数学拒收主因不是浮点尾巴，而是题干带 LaTeX 定界符与中文前缀
    （``混合运算：$3 + 5 + 4 =$``），已由 ``36e3c14`` 的 ``strip_latex`` +
    ``_MATH_SEGMENT`` 修掉，实测通过率 60.7% → 71.0%。
    """
    if getattr(value, "is_number", False) and value.is_integer:
        return sympy.Integer(int(value))
    return value


def exact_fraction(value: sympy.Expr) -> Fraction | None:
    """把 sympy 数值转成精确分数；不是数值（含符号变量）返回 None。

    用于**精确比较**，刻意不用浮点容差：``Fraction`` 表示的是精确有理数，
    所以 ``1/3`` 与 ``0.333`` 判不等——这是我们要的口径。一年级题库全是整数与
    有限小数，两边都能精确表示，用容差反而会放过「该是 1/3 却写成 0.33」的错答案。
    """
    if not getattr(value, "is_number", False):
        return None
    if value.is_Rational:
        # Integer / Rational：p、q 就是精确分子分母
        return Fraction(int(value.p), int(value.q))
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return Fraction(number)


def numbers_agree(expected: sympy.Expr, answer: sympy.Expr) -> bool:
    """判断两个 sympy 数值是否相等。

    **以 ``simplify`` 为主判**，精确分数只作补充（仅能把"不等"翻成"等"）。

    这个顺序是实测定的，不是偏好：``simplify`` 内部会走 ``.equals()`` 的容差判断，
    所以 ``1/3`` 与 ``1/3``（evalf 出来是 ``0.333...``，精确二进制分数是
    ``6004799503160661/18014398509481984``）本来就判相等；反过来把
    :func:`exact_fraction` 当主判会把这种"同一分数的两种写法"误拒成不等。
    而 ``1/3`` 与 ``0.333`` 两边都不对，``simplify`` 判不等、精确分数也判不等，
    照样拒——精确口径并没有被牺牲。
    """
    try:
        if bool(sympy.simplify(expected - answer) == 0):
            return True
    except (TypeError, ValueError):
        pass
    # 补充：两边都能精确表示成有理数且完全相同（例如 Float(2.5) 与 Rational(5,2)）
    left_fraction = exact_fraction(expected)
    right_fraction = exact_fraction(answer)
    return left_fraction is not None and right_fraction is not None and (
        left_fraction == right_fraction
    )


# 数学题里哪些题型走「规则 + SymPy 硬对拍」：这些题型的标准答案是可计算数值/单个字母。
# 多选（AC）与解答题（含步骤文字）的答案不是数值表达式，硬对拍会 100% 误拒，
# 必须交给 judge 通道；此前多选全部被 SymPy 规则误杀，题库 0 道多选。
_MATH_NUMERIC_QTYPES = frozenset({"choice", "fill", "judge", "match", "oral", "pick_hanzi"})


def _check_math_answer(question: GeneratedQuestion) -> str | None:
    """数学题：用 SymPy 求值题干算式，与标准答案对拍。

    求值**等号左侧**而不是比较等号两侧，是因为中文题面里右侧常常是"？"（答案留空）
    或与答案重复；从左侧算更可靠，也能同时覆盖 "12 + 7 = 19" 这种右侧已给值
    的写法。

    比较前两侧都过 :func:`normalize_math_number`（整数值的浮点尾巴先砍掉），
    再交给 :func:`numbers_agree`：``simplify`` 主判 + 精确分数补充。
    """
    stem = _normalize_math_text(question.stem)
    # 含字母的等式（方程/公式/带单位情境）不是数值对拍能判的：
    # 「x²-3x+2=0 的解是？」「长 5m 宽 3m，面积 = ？」的左侧不是纯数字算式，
    # 任何「左侧求值 vs 答案」的比较都会误拒。统一交给 judge 通道。
    # 宁可放行给 LLM 复核，也不能把整类初高中方程题拒之门外。
    if "=" in stem:
        raw_left = strip_latex(stem.rpartition("=")[0])
        if re.search(r"[A-Za-z]", raw_left):
            return None
    left = _math_left_side(stem)
    if left is not None:
        expr = parse_math(left)
        # 含逗号的表达式会被 SymPy 解析成 tuple（如「1,2」），没有 evalf；
        # 这类题交给 judge，不能让规则通道直接抛异常把整个知识点判失败。
        if isinstance(expr, sympy.Expr):
            try:
                expected = normalize_math_number(expr.evalf())
                # 含变量的等式（方程/恒等式/函数）不是数值对拍能判的：
                # 「x²-3x+2=0 的解是？」的左侧是符号表达式，交给 judge 通道。
                # 只有纯数值算式才走 SymPy 硬对拍。
                if not getattr(expected, "is_number", False):
                    return None
                answer_expr = parse_math(question.answer)
                if not isinstance(answer_expr, sympy.Expr):
                    return f"标准答案 {question.answer} 不是可计算的数学表达式"
                if not numbers_agree(expected, normalize_math_number(answer_expr)):
                    # 消息里必须带上标准答案本身：只说"不一致"而看不出答案是多少，
                    # 这条消息在线上等于没用（2026-10 排障时就卡在这里）。
                    return (
                        f"题干算式 {left} 的结果是 {expected}，"
                        f"标准答案是 {question.answer}，两者不一致"
                    )
            except (TypeError, ValueError, ZeroDivisionError):
                return "题干算式无法求值"
        elif expr is None:
            return f"题干算式 {left} 无法解析"
        # expr 是 tuple 等非 Expr（如「1,2」）：规则通道不做硬对拍，交给 judge。

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
    # 题干长度上限按学段放宽：小学 300 字（要能朗读），初高中允许情境题/阅读材料。
    stage = stage_for_grade(point.grade)
    max_stem = 300 if stage == "primary" else 900
    if stage == "primary" and ("reading" in point.id or "阅读" in point.unit_name):
        # 阅读理解题干本身就含短文（实测 350~400 字），按普通题 300 字会全量误拒。
        max_stem = 600
    if len(question.stem) > max_stem:
        return f"题干过长（{len(question.stem)} > {max_stem}）"
    for name in ("analysis", "hint1", "hint2", "hint3"):
        if not getattr(question, name).strip():
            return f"{name} 为空"

    reasons = (
        _check_options_unique(question),
        _check_multi_choice_answer(question),
        _check_judge_answer_format(question),
        _check_hints_not_leaking(question),
    )
    for reason in reasons:
        if reason:
            return reason

    if point.subject == _MATH_SUBJECT and question.qtype in _MATH_NUMERIC_QTYPES:
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


def _parse_judge_batch(raw: str) -> dict[int, tuple[str, int, str]]:
    """解析批量 judge 结果；容忍 ```json 包裹、多余文字与裸数组输出。

    只按 index 收结果；index 非法或重复一律丢弃（该题位由调用方回退单题判）。
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    brace, bracket = text.find("{"), text.find("[")
    if brace < 0 and bracket < 0:
        return {}
    if brace >= 0 and (bracket < 0 or brace < bracket):
        start, end = brace, text.rfind("}")
    else:
        start, end = bracket, text.rfind("]")
    if end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    # 推理模型常把结果直接输出成 JSON 数组而不是 {"results": [...]}
    results = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        return {}
    parsed: dict[int, tuple[str, int, str]] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index", 0))
        except (TypeError, ValueError):
            continue
        if index < 1 or index in parsed:
            continue
        verdict = str(item.get("verdict", "")).strip().lower()
        if verdict not in {"pass", "reject"}:
            continue
        try:
            score = int(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        parsed[index] = (verdict, score, str(item.get("reason", "")).strip())
    return parsed


def _error_detail(exc: BaseException) -> str:
    """异常的可读标识：类型名 + 业务错误码（LlmError.code 是限流/上游故障的判据）。"""
    code = getattr(exc, "code", None)
    return f"{type(exc).__name__}:{code}" if code else type(exc).__name__


class QuestionVerifier:
    """规则 + LLM judge 双通道验证。"""

    def __init__(self, client: LlmClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        # --no-judge 排障开关：False 时规则通道照跑、judge 一律放行且不发请求。
        # 必须覆盖单题与批量两条路径，否则批量化后该开关会失效、继续烧配额。
        self.judge_enabled = True

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
            {
                "role": "system",
                "content": content_judge_system_prompt(stage_for_grade(point.grade)),
            },
            {
                "role": "user",
                "content": CONTENT_JUDGE_USER_TEMPLATE.format(
                    point_name=point.name,
                    grade_name=_grade_name(point.grade),
                    subject_name=_subject_name(point.subject),
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

    # ------------------------------------------------------------ 批量 judge

    def _question_block(self, index: int, question: GeneratedQuestion) -> str:
        options_block = (
            "\n".join(f"{key}. {value}" for key, value in (question.options or {}).items())
            or "（无选项）"
        )
        return CONTENT_JUDGE_QUESTION_BLOCK.format(
            index=index,
            qtype=question.qtype,
            stem=question.stem,
            options=options_block,
            answer=question.answer,
            analysis=question.analysis,
            hint1=question.hint1,
            hint2=question.hint2,
            hint3=question.hint3,
        )

    async def judge_many(
        self, questions: list[GeneratedQuestion], point: KnowledgePoint
    ) -> list[JudgeOutcome]:
        """一次判多题（控配额）；解析失败的题位回退逐题 judge。

        批量判题的收益是调用次数按批缩小（配额窗口下这是决定性差异），
        代价是个别模型的数组输出可能缺项——缺项一律回退单题判，绝不默认放行。
        """
        if not questions:
            return []
        if not self.judge_enabled:
            return [(True, 100, "judge 已按 --no-judge 跳过")] * len(questions)
        self._client.bind_session(f"{self._settings.llm_session_prefix}-judge-{point.id}")
        blocks = "\n\n".join(
            self._question_block(index, question)
            for index, question in enumerate(questions, start=1)
        )
        messages = [
            {
                "role": "system",
                "content": content_judge_system_prompt(stage_for_grade(point.grade))
                + "\n本次需要一次判多题，请严格按题号输出结果数组，不要合并或省略。",
            },
            {
                "role": "user",
                "content": CONTENT_JUDGE_BATCH_USER_TEMPLATE.format(
                    point_name=point.name,
                    grade_name=_grade_name(point.grade),
                    subject_name=_subject_name(point.subject),
                    objective=point.objective,
                    count=len(questions),
                    questions=blocks,
                ),
            },
        ]
        result = await self._client.complete(
            messages,
            model=self._settings.content_judge_model,
            temperature=0.1,
            # judge 是推理模型，reasoning 会吃掉大量 token；按题量算的预算
            # 经常在 JSON 收尾前截断，导致整批解析失败、5 倍单题回退。
            # 直接用完整输出预算，实际消耗仍由回答长度决定。
            max_tokens=self._settings.content_max_tokens,
            name=f"content.judge.batch.{point.subject}",
        )
        parsed = _parse_judge_batch(result.content)
        expected = set(range(1, len(questions) + 1))
        if set(parsed) != expected:
            # 题号集合不严格匹配（缺项/多余/0 基错位）时整批作废，全部回退单题判。
            # 接受「部分匹配」会把某题的结论静默套到另一题上，宁可多花调用。
            logger.warning(
                "批量 judge 题号不匹配（期望 %s，收到 %s；原始输出前 160 字：%r），整批回退单题判",
                sorted(expected),
                sorted(parsed),
                result.content[:160],
            )
            outcomes = []
            for question in questions:
                try:
                    outcomes.append(await self.judge(question, point))
                except Exception as exc:
                    logger.warning("回退单题 judge 失败：%s", exc)
                    outcomes.append(
                        (None, None, f"judge 调用失败：{_error_detail(exc)}")
                    )
            return outcomes
        outcomes = []
        for index in range(1, len(questions) + 1):
            verdict, score, reason = parsed[index]
            passed_item = verdict == "pass" and score >= JUDGE_SCORE_THRESHOLD
            outcomes.append((passed_item, score, reason))
        return outcomes

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

        if point.subject == _MATH_SUBJECT and question.qtype in _MATH_NUMERIC_QTYPES:
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
                reason=f"judge 调用失败：{_error_detail(exc)}",
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
        """批量验证；返回 (通过, [(未通过题, 结果)], 统计)。

        流程：规则通道逐题先跑（纯本地、零成本）；规则通过的题再按
        ``content_judge_batch_size`` 分批做 LLM judge——数学客观题按既有口径
        只走规则+SymPy；多选/解答题答案不是数值表达式，同样进 judge。
        """
        report = VerificationReport(total=len(questions))
        passed: list[GeneratedQuestion] = []
        rejected: list[tuple[GeneratedQuestion, VerificationResult]] = []

        rule_failed: dict[int, VerificationResult] = {}
        judge_targets: list[int] = []
        for index, question in enumerate(questions):
            reason = rule_verify(question, point)
            if reason is not None:
                report.rejected += 1
                rule_failed[index] = VerificationResult(
                    verdict=Verdict.REJECT,
                    rule_passed=False,
                    judge_passed=None,
                    score=None,
                    reason="规则不通过：" + reason,
                )
                continue
            report.rule_passed += 1
            if point.subject != _MATH_SUBJECT or question.qtype not in _MATH_NUMERIC_QTYPES:
                judge_targets.append(index)
            else:
                # 数学客观题按既有口径只走规则 + SymPy；judge 跳过如实计数
                report.judge_skipped += 1
                passed.append(question)

        judge_results: dict[int, JudgeOutcome] = {}
        batch_size = max(1, int(self._settings.content_judge_batch_size))
        for start in range(0, len(judge_targets), batch_size):
            chunk = judge_targets[start : start + batch_size]
            try:
                outcomes = await self.judge_many([questions[i] for i in chunk], point)
            except Exception as exc:
                logger.warning("批量 judge 调用失败（%s 题）：%s", len(chunk), exc)
                outcomes = [(None, None, "judge 调用失败：" + _error_detail(exc))] * len(chunk)
            for index, outcome in zip(chunk, outcomes, strict=True):
                judge_results[index] = outcome

        for index, question in enumerate(questions):
            failed = rule_failed.get(index)
            if failed is not None:
                rejected.append((question, failed))
                continue
            if index not in judge_results:
                # 数学题：规则 + SymPy 已过，按既有口径直接通过
                passed.append(question)
                continue
            judge_passed, score, judge_reason = judge_results[index]
            if judge_passed is True:
                report.judge_passed += 1
                passed.append(question)
                continue
            if judge_passed is None:
                report.judge_skipped += 1
                report.judge_errors += 1
                report.rejected += 1
                rejected.append(
                    (
                        question,
                        VerificationResult(
                            verdict=Verdict.ERROR,
                            rule_passed=True,
                            judge_passed=None,
                            score=score,
                            reason="judge 不可用：" + (judge_reason or ""),
                        ),
                    )
                )
                continue
            report.rejected += 1
            rejected.append(
                (
                    question,
                    VerificationResult(
                        verdict=Verdict.REJECT,
                        rule_passed=True,
                        judge_passed=False,
                        score=score,
                        reason=judge_reason or "judge 判定不合格",
                    ),
                )
            )

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
