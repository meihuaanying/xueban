"""英语口语评测（F-25）：供应商抽象，输出三维分数与音素级纠错。

mock 仅用于开发/测试；生产环境必须配置 azure（Azure Pronunciation Assessment）。
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import Settings, get_settings

SPEAKING_PROVIDER_MOCK = "mock"
SPEAKING_PROVIDER_AZURE = "azure"
SPEAKING_PROVIDER_AUTO = "auto"

AZURE_ENDPOINT_TEMPLATE = (
    "https://{region}.stt.speech.microsoft.com/speech/recognition/"
    "conversation/cognitiveservices/v1"
)

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


class SpeakingConfigurationError(RuntimeError):
    """供应商未配置或配置不足以发起真实评测。"""


class SpeakingAudioRequired(ValueError):
    """真实供应商必须收到可评测的音频。"""


class SpeakingProviderError(RuntimeError):
    """供应商调用失败或返回无法解析的结果。"""


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


class SpeakingProvider(Protocol):
    """口语评测供应商接口。"""

    name: str

    async def assess(
        self,
        *,
        reference: str,
        transcript: str,
        audio: bytes | None,
        content_type: str,
        duration_seconds: float | None = None,
    ) -> SpeakingResult:
        """对一段跟读音频（或文本）给出三维评分。"""
        ...


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


class MockSpeakingProvider:
    """本地确定性评分；只能在 development/testing 使用。"""

    name = SPEAKING_PROVIDER_MOCK

    async def assess(
        self,
        *,
        reference: str,
        transcript: str,
        audio: bytes | None,
        content_type: str,
        duration_seconds: float | None = None,
    ) -> SpeakingResult:
        del audio, content_type
        return grade_speaking(
            reference=reference, transcript=transcript, duration_seconds=duration_seconds
        )


def _score(value: Any, dimension: str) -> float:
    try:
        number = float(value) / 100.0
    except (TypeError, ValueError) as exc:
        raise SpeakingProviderError(f"Azure 返回缺少{dimension}分数") from exc
    return round(max(0.0, min(1.0, number)), 4)


def _hint_for_word(word: str) -> str:
    normalized = word.lower()
    return next(
        (message for key, message in PRONUNCIATION_HINTS.items() if normalized.endswith(key)),
        "注意重音位置与元音长度",
    )


def _fluency_comment(score: float) -> str:
    if score >= 0.8:
        return "语速与停顿自然"
    if score >= 0.6:
        return "整体可听，注意断句与重音"
    return "停顿或连贯性偏弱，建议放慢速度逐句跟读"


def _azure_to_result(payload: dict[str, Any]) -> SpeakingResult:
    status = str(payload.get("RecognitionStatus") or "")
    best = (payload.get("NBest") or [{}])[0]
    assessment = best.get("PronunciationAssessment") if isinstance(best, dict) else None
    if status != "Success" or not isinstance(assessment, dict):
        raise SpeakingProviderError(f"Azure 识别失败：{status or '无评测结果'}")

    pronunciation = _score(assessment.get("AccuracyScore"), "发音")
    fluency = _score(assessment.get("FluencyScore"), "流利度")
    completeness = _score(assessment.get("CompletenessScore"), "完整度")

    errors: list[PronunciationError] = []
    words = best.get("Words") if isinstance(best, dict) else None
    for item in words if isinstance(words, list) else []:
        if not isinstance(item, dict):
            continue
        detail = item.get("PronunciationAssessment")
        if not isinstance(detail, dict):
            continue
        error_type = str(detail.get("ErrorType") or "None")
        if error_type == "None":
            continue
        word = str(item.get("Word") or "").strip() or "?"
        expected = "读出该词" if error_type == "Omission" else "准确发音"
        errors.append(
            PronunciationError(word=word, expected=expected, pronunciation=_hint_for_word(word))
        )

    return SpeakingResult(
        provider=SPEAKING_PROVIDER_AZURE,
        pronunciation=pronunciation,
        fluency=fluency,
        completeness=completeness,
        errors=errors[:10],
        notes={
            "fluency": _fluency_comment(fluency),
            "recognition_status": status,
        },
    )


class AzureSpeakingProvider:
    """Azure Pronunciation Assessment（REST，detailed 结果含单词/音素级错误）。"""

    name = SPEAKING_PROVIDER_AZURE

    def __init__(
        self,
        *,
        api_key: str,
        region: str,
        endpoint: str = "",
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint or AZURE_ENDPOINT_TEMPLATE.format(region=region)
        self._timeout = timeout_seconds
        self._client = client

    async def assess(
        self,
        *,
        reference: str,
        transcript: str,
        audio: bytes | None,
        content_type: str,
        duration_seconds: float | None = None,
    ) -> SpeakingResult:
        del transcript, duration_seconds
        if not audio:
            raise SpeakingAudioRequired("Azure 口语评测需要上传跟读音频（audio_base64）")
        assessment = {
            "ReferenceText": reference,
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
            "EnableMiscue": True,
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": content_type,
            "Pronunciation-Assessment": base64.b64encode(
                json.dumps(assessment, ensure_ascii=False).encode("utf-8")
            ).decode("ascii"),
        }
        params = {"language": "en-US", "format": "detailed"}
        if self._client is not None:
            return await self._post(self._client, params=params, headers=headers, audio=audio)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await self._post(client, params=params, headers=headers, audio=audio)

    async def _post(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, str],
        headers: dict[str, str],
        audio: bytes,
    ) -> SpeakingResult:
        try:
            response = await client.post(
                self._endpoint, params=params, headers=headers, content=audio
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SpeakingProviderError(
                f"Azure 口语评测返回 HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SpeakingProviderError("Azure 口语评测网络请求失败") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise SpeakingProviderError("Azure 口语评测返回了非 JSON 内容") from exc
        if not isinstance(payload, dict):
            raise SpeakingProviderError("Azure 口语评测返回结构异常")
        return _azure_to_result(payload)


def decode_audio_base64(value: str) -> bytes:
    """解码原生 Base64 或 data URL；空音频交给供应商按配置报错。"""
    payload = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    try:
        audio = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SpeakingAudioRequired("audio_base64 不是合法的 Base64 音频") from exc
    if not audio:
        raise SpeakingAudioRequired("audio_base64 解码后为空")
    return audio


def get_speaking_provider(settings: Settings | None = None) -> SpeakingProvider:
    """按配置选择供应商；生产环境拒绝 mock。"""
    current = settings or get_settings()
    name = current.speaking_provider.strip().lower() or SPEAKING_PROVIDER_AUTO
    if name == SPEAKING_PROVIDER_MOCK:
        if not current.is_development:
            raise SpeakingConfigurationError("生产环境禁止使用 mock 口语评测供应商")
        return MockSpeakingProvider()
    if name in (SPEAKING_PROVIDER_AZURE, SPEAKING_PROVIDER_AUTO):
        if not current.speaking_api_key.strip():
            if name == SPEAKING_PROVIDER_AUTO and current.is_development:
                return MockSpeakingProvider()
            raise SpeakingConfigurationError("未配置 SPEAKING_API_KEY，无法调用真实口语评测")
        if not current.speaking_region.strip() and not current.speaking_endpoint.strip():
            raise SpeakingConfigurationError("未配置 SPEAKING_REGION 或 SPEAKING_ENDPOINT")
        return AzureSpeakingProvider(
            api_key=current.speaking_api_key,
            region=current.speaking_region,
            endpoint=current.speaking_endpoint,
            timeout_seconds=current.speaking_timeout_seconds,
        )
    raise SpeakingConfigurationError(f"未知的口语评测供应商：{name}")


async def assess_speaking(
    *,
    reference: str,
    transcript: str,
    duration_seconds: float | None = None,
    audio_base64: str | None = None,
    audio_content_type: str = "audio/wav; codecs=audio=pcm; samplerate=16000",
    settings: Settings | None = None,
) -> SpeakingResult:
    """统一入口：选供应商、解码音频并评测（供路由与测试复用）。"""
    provider = get_speaking_provider(settings)
    audio = decode_audio_base64(audio_base64) if audio_base64 else None
    return await provider.assess(
        reference=reference,
        transcript=transcript,
        audio=audio,
        content_type=audio_content_type,
        duration_seconds=duration_seconds,
    )


__all__ = [
    "SPEAKING_PROVIDER_AZURE",
    "SPEAKING_PROVIDER_MOCK",
    "AzureSpeakingProvider",
    "MockSpeakingProvider",
    "PronunciationError",
    "SpeakingAudioRequired",
    "SpeakingConfigurationError",
    "SpeakingProvider",
    "SpeakingProviderError",
    "SpeakingResult",
    "assess_speaking",
    "decode_audio_base64",
    "get_speaking_provider",
    "grade_speaking",
]
