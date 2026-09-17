"""背诵助手（F-21）：ASR 转写与原文比对，输出错字标记与抽考点。"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

PUNCTUATION = "，。！？；：、“”‘’（）《》〈〉【】—…·,.!?;:\"'()<>[]{} \n\t"

MASK_CHAR = "＿"


@dataclass(slots=True)
class RecitationError:
    """错字/漏字/多字标记。"""

    position: int
    expected: str
    got: str
    kind: str


@dataclass(slots=True)
class RecitationResult:
    """背诵对照结果。"""

    accuracy: float
    total_chars: int
    errors: list[RecitationError] = field(default_factory=list)
    masked_preview: str = ""
    quiz_points: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    """去除标点与空白（保留汉字/字母/数字）。"""
    return "".join(char for char in text if char not in PUNCTUATION)


def check_recitation(reference: str, transcript: str) -> RecitationResult:
    """比对原文与转写：逐字对齐给出错字/漏字/多字标记。"""
    ref = _clean(reference)
    got = _clean(transcript)
    total = len(ref)
    if total == 0:
        return RecitationResult(accuracy=0.0, total_chars=0)

    matcher = difflib.SequenceMatcher(a=ref, b=got, autojunk=False)
    matches = sum(block.size for block in matcher.get_matching_blocks())
    accuracy = round(matches / total, 4)

    errors: list[RecitationError] = []
    masked: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            masked.extend(ref[i1:i2])
        elif tag == "replace":
            for offset in range(min(i2 - i1, j2 - j1)):
                errors.append(
                    RecitationError(
                        position=i1 + offset,
                        expected=ref[i1 + offset],
                        got=got[j1 + offset],
                        kind="wrong_char",
                    )
                )
                masked.append(MASK_CHAR)
            if i2 - i1 > j2 - j1:
                for offset in range(i1 + (j2 - j1), i2):
                    errors.append(
                        RecitationError(
                            position=offset, expected=ref[offset], got="", kind="missing"
                        )
                    )
                    masked.append(MASK_CHAR)
            if j2 - j1 > i2 - i1:
                for offset in range(j1 + (i2 - i1), j2):
                    errors.append(
                        RecitationError(position=i1, expected="", got=got[offset], kind="extra")
                    )
        elif tag == "delete":
            for offset in range(i1, i2):
                errors.append(
                    RecitationError(position=offset, expected=ref[offset], got="", kind="missing")
                )
                masked.append(MASK_CHAR)
        elif tag == "insert":
            errors.append(RecitationError(position=i1, expected="", got=got[j1:j2], kind="extra"))

    # 抽考点：优先抽错字所在短语（±4 字），最多 3 个
    quiz_points: list[str] = []
    for error in errors[:3]:
        start = max(0, error.position - 4)
        end = min(total, error.position + 5)
        fragment = ref[start:end]
        if fragment and fragment not in quiz_points:
            quiz_points.append(fragment)
    if not quiz_points and total > 0:
        quiz_points = [ref[: min(12, total)]]

    return RecitationResult(
        accuracy=accuracy,
        total_chars=total,
        errors=errors,
        masked_preview="".join(masked),
        quiz_points=quiz_points,
    )


def mask_reference(reference: str, *, ratio: float = 0.4) -> str:
    """遮挡自测：按比例遮蔽原文文字（保留标点，便于朗读断句）。"""
    if not reference:
        return reference
    step = max(int(1 / max(ratio, 0.01)), 1)
    counter = 0
    masked: list[str] = []
    for char in reference:
        if char in PUNCTUATION:
            masked.append(char)
            continue
        counter += 1
        masked.append(MASK_CHAR if counter % step == 0 else char)
    return "".join(masked)


__all__ = ["RecitationError", "RecitationResult", "check_recitation", "mask_reference"]
