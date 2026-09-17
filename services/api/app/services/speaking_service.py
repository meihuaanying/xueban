"""英语口语评测（F-25）：供应商抽象（mock 先行），输出三维分数与音素级纠错。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SPEAKING_PROVIDER_MOCK = "mock"

_WORD = re.compile(r"[a-zA-Z']+")

# 常见易错音素提示（mock 用；真实供应商返回音素级结果）
PRONUNCIATION_HINTS: dict[str, str] = {
    "th": "/θ/ 舌尖轻触上齿，注意不要读成 /s/",
    "r": "/r/ 卷舌不要颤音，避免读成 /l/",
    "l": "/l/ 舌尖抵上齿龈，注意词尾清晰",
    "v": "/v/ 上齿轻触下唇，避免读成 /w/",
    "w": "/w/ 双唇收圆，避免读成 /v/",
    "ed": "-ed 结尾注意 /t/ /d/ /ɪd/ 三种读法",
    "s": "词尾 -s 注意 /s/ /z/ /ɪz/ 三种读法",
}


@dataclass(slots=True)
class PronunciationError:
    """纠错词。"""

    word: str
    expected: str
    pronunciation: str


@dataclass(slots=True)
class SpeakingResult:
    """口语评测三维结果。"""

    provider: str
    pronunciation: float
    fluency: float
    completeness: float
    errors: list[PronunciationError] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)


def _words(text: str) -> list[str]:
    return [word.lower() for word in _WORD.findall(text)]


def grade_speaking(
    *, reference: str, transcript: str, duration_seconds: float | None = None
) -> SpeakingResult:
    """评分（mock 供应商）：发音=词匹配率，流利度=语速带，完整度=覆盖率。"""
    ref_words = _words(reference)
    got_words = _words(transcript)
    ref_set = set(ref_words)
    matched = sum(1 for word in got_words if word in ref_set)
    coverage = round(min(matched / len(ref_set), 1.0) if ref_set else 0.0, 4)

    # 逐词对齐，定位读错/漏读
    errors: list[PronunciationError] = []
    got_pool = list(got_words)
    for word in ref_words:
        if word in got_pool:
            got_pool.remove(word)
            continue
        hint = next(
            (message for key, message in PRONUNCIATION_HINTS.items() if word.endswith(key)),
            "注意重音位置与元音长度",
        )
        errors.append(PronunciationError(word=word, expected="准确发音", pronunciation=hint))

    pronunciation = round(max(coverage - 0.02 * len(errors), 0.0), 4)
    if duration_seconds and duration_seconds > 0:
        words_per_second = len(got_words) / duration_seconds
        if 1.2 <= words_per_second <= 3.2:
            fluency = 0.95
            notes = {"fluency": "语速自然，接近日常对话节奏"}
        elif words_per_second < 1.2:
            fluency = 0.7
            notes = {"fluency": "语速偏慢：先求准确，再用跟读练习提升连贯度"}
        else:
            fluency = 0.65
            notes = {"fluency": "语速偏快：注意停顿与句子重音，避免吞音"}
    else:
        fluency = 0.8
        notes = {"fluency": "未提供时长，按文本完整度估算；建议录音时保持匀速"}

    return SpeakingResult(
        provider=SPEAKING_PROVIDER_MOCK,
        pronunciation=pronunciation,
        fluency=round(fluency, 4),
        completeness=coverage,
        errors=errors[:10],
        notes=notes,
    )


__all__ = ["PronunciationError", "SpeakingResult", "grade_speaking"]
