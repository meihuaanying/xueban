"""TTS 供应商抽象：mock（生成可播放 WAV）与真实供应商占位（仅改环境变量切换）。"""

from __future__ import annotations

import io
import math
import struct
import wave
from typing import Protocol

from app.config import Settings


class TtsError(Exception):
    """语音合成失败。"""


class TtsProvider(Protocol):
    """语音合成接口：返回音频字节与 MIME 类型。"""

    name: str

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        """合成语音。"""
        ...


class MockTtsProvider:
    """占位实现：按文本长度生成可播放的静音 WAV（联调/测试用）。"""

    name = "mock"
    sample_rate = 16000

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        duration_seconds = min(max(len(text) / 6.0, 1.0), 120.0)
        frame_count = int(self.sample_rate * duration_seconds)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            frames = b"".join(
                struct.pack("<h", int(320 * math.sin(2 * math.pi * 220 * t / self.sample_rate)))
                for t in range(frame_count)
            )
            handle.writeframes(frames)
        return buffer.getvalue(), "audio/wav"


class VendorTtsProvider:
    """真实 TTS 供应商占位（CosyVoice/云厂商 API；Key 开通后实现调用）。"""

    name = "vendor"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        raise TtsError("TTS 供应商未接入：请配置 TTS_API_KEY 并实现 VendorTtsProvider")


def get_tts_provider(settings: Settings) -> TtsProvider:
    """按配置选择 TTS 供应商。"""
    if settings.tts_provider == "vendor":
        return VendorTtsProvider(settings.tts_api_key)
    return MockTtsProvider()
