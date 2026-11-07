"""TTS 供应商抽象：mock 仅用于开发/测试，生产使用 Azure 语音合成。"""

from __future__ import annotations

import asyncio
import io
import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Protocol
from xml.sax.saxutils import escape

import httpx

from app.config import Settings

AZURE_TTS_ENDPOINT_TEMPLATE = "https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
AZURE_TTS_OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
AZURE_TTS_VOICE = "zh-CN-XiaoxiaoNeural"


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


class WindowsSapiTtsProvider:
    """Windows 本地离线配音（仅开发/测试）。

    没有云 TTS Key 时，§5.3 视频预生成仍然需要**真实人声**才能验收成片；
    Windows 自带的 SAPI 中文声音（Microsoft Huihui Desktop）足够完成本地演示。
    文本与输出路径都用 base64 传入 PowerShell，避免中文/引号/反斜杠的转义坑。
    """

    name = "windows"

    def __init__(self, voice: str = "Microsoft Huihui Desktop", *, rate: int = -1) -> None:
        self.voice = voice
        self.rate = rate

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        if not text.strip():
            raise TtsError("待合成文本为空")
        return await asyncio.to_thread(self._speak_sync, text)

    def _speak_sync(self, text: str) -> tuple[bytes, str]:
        # 文本、语音名、路径全部走参数传入：直接内插进 -Command 会踩 Windows
        # 命令行长度/转义坑（实测 WinError 786），也避免引号注入。
        script = (
            "param([string]$TextPath, [string]$OutPath, [string]$Voice, [int]$Rate)\n"
            "$text = Get-Content -Raw -Encoding UTF8 $TextPath\n"
            "Add-Type -AssemblyName System.Speech\n"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            "try { $s.SelectVoice($Voice) } catch { }\n"
            "$s.Rate = $Rate\n"
            "$s.SetOutputToWaveFile($OutPath)\n"
            "$s.Speak($text)\n"
            "$s.Dispose()\n"
        )
        with tempfile.TemporaryDirectory(prefix="xueban-sapi-") as tmp:
            workdir = Path(tmp)
            text_path = workdir / "narration.txt"
            output = workdir / "narration.wav"
            script_path = workdir / "sapi.ps1"
            text_path.write_text(text, encoding="utf-8")
            script_path.write_text(script, encoding="utf-8-sig")
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(script_path),
                        "-TextPath",
                        str(text_path),
                        "-OutPath",
                        str(output),
                        "-Voice",
                        self.voice,
                        "-Rate",
                        str(self.rate),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise TtsError(f"Windows 本地配音失败：{exc}") from exc
            if result.returncode != 0 or not output.exists():
                raise TtsError("Windows 本地配音失败：" + (result.stderr or "")[-500:])
            return output.read_bytes(), "audio/wav"


class AzureTtsProvider:
    """Azure 语音合成 REST（SSML 输入，返回 MP3）。

    生产环境需配置 TTS_API_KEY + TTS_REGION（或完整 TTS_ENDPOINT）。
    """

    name = "azure"

    def __init__(
        self,
        api_key: str,
        *,
        region: str = "",
        endpoint: str = "",
        voice: str = AZURE_TTS_VOICE,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.region = region
        self.endpoint = endpoint
        self.voice = voice
        self.timeout_seconds = timeout_seconds
        self._client = client

    def _url(self) -> str:
        if self.endpoint:
            return self.endpoint
        if not self.region:
            raise TtsError("未配置 TTS_REGION 或 TTS_ENDPOINT，无法调用 Azure 语音合成")
        return AZURE_TTS_ENDPOINT_TEMPLATE.format(region=self.region)

    def _ssml(self, text: str) -> str:
        voice = escape(self.voice, {'"': "&quot;", "'": "&apos;"})
        return (
            "<speak version='1.0' xml:lang='zh-CN'>"
            f"<voice name='{voice}'>"
            f"{escape(text)}"
            "</voice></speak>"
        )

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        if not self.api_key.strip():
            raise TtsError("未配置 TTS_API_KEY，无法调用 Azure 语音合成")
        if not text.strip():
            raise TtsError("待合成文本为空")
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": AZURE_TTS_OUTPUT_FORMAT,
            "User-Agent": "xueban-tts/1.0",
        }
        if self._client is not None:
            return await self._post(self._client, headers=headers, text=text)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            return await self._post(client, headers=headers, text=text)

    async def _post(
        self, client: httpx.AsyncClient, *, headers: dict[str, str], text: str
    ) -> tuple[bytes, str]:
        try:
            response = await client.post(
                self._url(), headers=headers, content=self._ssml(text)
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TtsError(f"Azure 语音合成返回 HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise TtsError("Azure 语音合成网络请求失败") from exc
        audio = response.content
        if not audio:
            raise TtsError("Azure 语音合成返回空音频")
        return audio, "audio/mpeg"


#: 兼容旧配置名（vendor）；实现已切换为 Azure 语音合成。
VendorTtsProvider = AzureTtsProvider


def get_tts_provider(settings: Settings) -> TtsProvider:
    """按配置选择 TTS 供应商；生产环境拒绝 mock。"""
    name = settings.tts_provider.strip().lower() or "auto"
    if name == "mock":
        if not settings.is_development:
            raise TtsError("生产环境禁止使用 mock TTS 供应商")
        return MockTtsProvider()
    if name == "windows":
        # 本地离线配音只是开发/演示通道；生产必须走云端供应商（启动校验也拦）。
        if not settings.is_development:
            raise TtsError("生产环境禁止使用 Windows 本地 TTS 供应商")
        return WindowsSapiTtsProvider(settings.tts_sapi_voice)
    if name in ("azure", "vendor", "auto"):
        if not settings.tts_api_key.strip():
            if name == "auto" and settings.is_development:
                return MockTtsProvider()
            raise TtsError("未配置 TTS_API_KEY，无法调用真实 TTS 供应商")
        if not settings.tts_region.strip() and not settings.tts_endpoint.strip():
            raise TtsError("未配置 TTS_REGION 或 TTS_ENDPOINT，无法调用 Azure 语音合成")
        return AzureTtsProvider(
            settings.tts_api_key,
            region=settings.tts_region,
            endpoint=settings.tts_endpoint,
            voice=settings.tts_voice,
            timeout_seconds=settings.tts_timeout_seconds,
        )
    raise TtsError(f"未知的 TTS 供应商：{name}")


__all__ = [
    "AZURE_TTS_ENDPOINT_TEMPLATE",
    "AZURE_TTS_OUTPUT_FORMAT",
    "AZURE_TTS_VOICE",
    "AzureTtsProvider",
    "MockTtsProvider",
    "TtsError",
    "TtsProvider",
    "VendorTtsProvider",
    "WindowsSapiTtsProvider",
    "get_tts_provider",
]
