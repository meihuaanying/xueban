"""§5.3 视频版讲解管线（P3，离线预生成）。

六阶段链（Math-To-Manim 思路，落地为可校验的结构化管线）：

    ① 意图      —— 学会做什么 / 常见错误 / 成功标准
    ② 前置知识图 —— 2~5 个必须先会的节点，有向无环
    ③ 教学序列   —— 3~4 幕，每幕一段可朗读台词
    ④ 数学导演   —— 逐幕场景描述（受限 DSL，不写代码）
    ⑤ 镜头语言   —— 平台确定性展开：元素入画顺序 + 每幕时长（TTS 音频决定）
    ⑥ 场景组装   —— 固定模板编译为 Manim 源码
    → Manim 渲染（失败把 stderr 摘要回喂④，≤3 次）→ ffmpeg 混流
    → MinIO 入库 → 元数据落 PG

为什么台词与画面要分开：语音时长决定画面停留，先有音频再有镜头，
才不会被固定的 wait 时长把口播截断。
"""

from __future__ import annotations

import logging
import mimetypes
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.data.curriculum import (
    KnowledgePoint as CurriculumPoint,
)
from app.data.curriculum import find_point, grade_name, stage_for_grade, subject_name
from app.errors import AppError, LlmError
from app.models import (
    ExplainerContent,
    ExplainerMode,
    ExplainerStatus,
)
from app.models import (
    KnowledgePoint as KnowledgePointModel,
)
from app.services import explainer_service
from app.services.llm_client import LlmClient
from app.services.llm_json import extract_json_object
from app.services.manim_toolchain import (
    ManimError,
    ManimToolchain,
    compile_scene,
)
from app.services.prompts import (
    VIDEO_DIRECTOR_SYSTEM_PROMPT,
    VIDEO_DIRECTOR_USER_TEMPLATE,
    VIDEO_INTENT_SYSTEM_PROMPT,
    VIDEO_INTENT_USER_TEMPLATE,
    VIDEO_PREREQ_SYSTEM_PROMPT,
    VIDEO_PREREQ_USER_TEMPLATE,
    VIDEO_REPAIR_SYSTEM_PROMPT,
    VIDEO_REPAIR_USER_TEMPLATE,
    VIDEO_SEQUENCE_SYSTEM_PROMPT,
    VIDEO_SEQUENCE_USER_TEMPLATE,
)
from app.services.safety_service import SafetyService
from app.services.tts import TtsProvider

logger = logging.getLogger("xueban.explainer.video")

#: 视频产物的对象键前缀；读取时换成预签名 URL。
VIDEO_KEY_PREFIX = "explainer/video"

_ELEMENT_KINDS = {"text", "bullet", "formula", "axes"}


class VideoPipelineError(AppError):
    """视频生成业务错误。"""

    status_code = 502
    code = "EXPLAINER_VIDEO_ERROR"


class VideoStorage(Protocol):
    """视频管线只需要「上传字节」这一件事（测试用替身）。"""

    async def upload_bytes(self, *, key: str, data: bytes, content_type: str) -> None: ...


class VideoToolchain(Protocol):
    """渲染工具链接口（测试用替身）。"""

    async def render_scene(self, source: str, *, workdir: Path) -> Path: ...

    async def mux_audio(
        self, *, video: Path, audios: list[Path], output: Path, workdir: Path
    ) -> Path: ...

    async def probe_duration(self, path: Path) -> float: ...


# ---------------------------------------------------------------- 结构校验


def _text(value: Any, field: str, *, limit: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise VideoPipelineError(f"场景字段 {field} 为空", code="EXPLAINER_VIDEO_SPEC_INVALID")
    return text[:limit]


def validate_intent(payload: dict[str, Any]) -> dict[str, str]:
    """① 意图：五个短句字段缺一不可。"""
    fields = ("learning_goal", "core_idea", "misconception", "success_check", "key_visual")
    return {name: _text(payload.get(name), name, limit=160) for name in fields}


def validate_prereq_graph(payload: dict[str, Any]) -> dict[str, Any]:
    """② 前置知识图：2~5 个节点，边只能指向已存在节点，entry 无入边。"""
    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 5:
        raise VideoPipelineError(
            "前置知识图需要 2~5 个节点", code="EXPLAINER_VIDEO_SPEC_INVALID"
        )
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise VideoPipelineError("节点必须是对象", code="EXPLAINER_VIDEO_SPEC_INVALID")
        node_id = _text(node.get("id") or f"p{index + 1}", "id", limit=12)
        if node_id in seen:
            raise VideoPipelineError(
                f"前置知识节点 id 重复：{node_id}", code="EXPLAINER_VIDEO_SPEC_INVALID"
            )
        seen.add(node_id)
        cleaned.append(
            {
                "id": node_id,
                "label": _text(node.get("label"), "label", limit=12),
                "why": _text(node.get("why"), "why", limit=60),
            }
        )
    edges: list[list[str]] = []
    for edge in payload.get("edges") or []:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            continue
        source, target = str(edge[0]), str(edge[1])
        if source in seen and target in seen and source != target:
            edges.append([source, target])
    entry = str(payload.get("entry") or "")
    if entry not in seen:
        targets = {target for _, target in edges}
        # 模型若把全部节点连成环，next() 无 default 会以 RuntimeError 形态炸掉
        # 整条生成；兜底取第一个节点，后续自愈循环仍可修复。
        entry = next(
            (node["id"] for node in cleaned if node["id"] not in targets),
            cleaned[0]["id"] if cleaned else "",
        )
    return {"nodes": cleaned, "edges": edges, "entry": entry}


def validate_sequence(payload: dict[str, Any], *, max_segments: int) -> list[dict[str, str]]:
    """③ 教学序列：2~max_segments 幕，每幕台词可朗读且长度可控。"""
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise VideoPipelineError("教学序列缺少 segments", code="EXPLAINER_VIDEO_SPEC_INVALID")
    cleaned: list[dict[str, str]] = []
    for index, segment in enumerate(segments[:max_segments], start=1):
        if not isinstance(segment, dict):
            raise VideoPipelineError("幕必须是对象", code="EXPLAINER_VIDEO_SPEC_INVALID")
        narration = _text(segment.get("narration"), "narration", limit=300)
        if len(narration) < 10:
            raise VideoPipelineError(
                f"第 {index} 幕台词过短，TTS 无法成句", code="EXPLAINER_VIDEO_SPEC_INVALID"
            )
        cleaned.append(
            {
                "name": _text(segment.get("name") or f"第{index}幕", "name", limit=16),
                "narration": narration,
                "visual_goal": _text(
                    segment.get("visual_goal"), "visual_goal", limit=120, required=False
                ),
            }
        )
    if len(cleaned) < 2:
        raise VideoPipelineError("教学序列至少需要 2 幕", code="EXPLAINER_VIDEO_SPEC_INVALID")
    return cleaned


def _numeric_pair(point: Any) -> tuple[float, float] | None:
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        return None
    x, y = point
    if isinstance(x, bool) or isinstance(y, bool):
        return None
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return float(x), float(y)


def _validate_element(element: Any) -> dict[str, Any]:
    if not isinstance(element, dict):
        raise VideoPipelineError("场景元素必须是对象", code="EXPLAINER_VIDEO_SPEC_INVALID")
    kind = str(element.get("kind") or "")
    if kind not in _ELEMENT_KINDS:
        raise VideoPipelineError(
            f"不支持的场景元素类型：{kind!r}", code="EXPLAINER_VIDEO_SPEC_INVALID"
        )
    if kind in {"text", "bullet"}:
        return {
            "kind": kind,
            "content": _text(element.get("content"), "content", limit=60),
        }
    if kind == "formula":
        latex = _text(element.get("latex"), "latex", limit=120)
        if latex.startswith("$$") and latex.endswith("$$"):
            latex = latex[2:-2]
        elif latex.startswith("$") and latex.endswith("$"):
            latex = latex[1:-1]
        if not latex:
            raise VideoPipelineError("公式为空", code="EXPLAINER_VIDEO_SPEC_INVALID")
        return {"kind": "formula", "latex": latex}
    x_range = element.get("x_range")
    y_range = element.get("y_range")
    points = element.get("points")
    if not isinstance(x_range, list) or len(x_range) != 3:
        raise VideoPipelineError("axes.x_range 必须是三个数", code="EXPLAINER_VIDEO_SPEC_INVALID")
    if not isinstance(y_range, list) or len(y_range) != 3:
        raise VideoPipelineError("axes.y_range 必须是三个数", code="EXPLAINER_VIDEO_SPEC_INVALID")
    if not isinstance(points, list) or not 2 <= len(points) <= 41:
        raise VideoPipelineError(
            "axes.points 需要 2~41 个坐标点", code="EXPLAINER_VIDEO_SPEC_INVALID"
        )
    coords = [pair for point in points if (pair := _numeric_pair(point)) is not None]
    if len(coords) != len(points):
        raise VideoPipelineError(
            "axes.points 含非数值坐标", code="EXPLAINER_VIDEO_SPEC_INVALID"
        )
    return {
        "kind": "axes",
        "x_range": [float(value) for value in x_range],
        "y_range": [float(value) for value in y_range],
        "points": [[x, y] for x, y in coords],
        "label": str(element.get("label") or "")[:20],
    }


def build_shots(
    segments: list[dict[str, str]],
    director: dict[str, Any],
    *,
    max_segments: int,
) -> list[dict[str, Any]]:
    """④⑤ 数学导演 → 镜头语言：校验并展开为逐幕镜头。

    导演输出必须与教学序列一一对应；数字对不上就要求模型重来，
    而不是静默截断导致后几幕没有台词或没有画面。
    """
    scenes = director.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != len(segments):
        raise VideoPipelineError(
            f"场景数量（{len(scenes) if isinstance(scenes, list) else 0}）"
            f"必须等于教学序列幕数（{len(segments)}）",
            code="EXPLAINER_VIDEO_SPEC_INVALID",
        )
    shots: list[dict[str, Any]] = []
    for index, (segment, scene) in enumerate(zip(segments, scenes, strict=True), start=1):
        if not isinstance(scene, dict):
            raise VideoPipelineError("scene 必须是对象", code="EXPLAINER_VIDEO_SPEC_INVALID")
        elements = scene.get("elements")
        if not isinstance(elements, list) or not 1 <= len(elements) <= 4:
            raise VideoPipelineError(
                f"第 {index} 幕需要 1~4 个元素", code="EXPLAINER_VIDEO_SPEC_INVALID"
            )
        layout = scene.get("layout") if scene.get("layout") in ("stack", "center") else "stack"
        shots.append(
            {
                "title": _text(
                    scene.get("headline") or segment["name"], "headline", limit=20
                ),
                "layout": layout,
                "elements": [_validate_element(element) for element in elements],
                "narration": segment["narration"],
            }
        )
    if len(shots) > max_segments:  # pragma: no cover - validate_sequence 已截断
        raise VideoPipelineError("镜头超过上限", code="EXPLAINER_VIDEO_SPEC_INVALID")
    return shots


# ---------------------------------------------------------------- LLM 各阶段


async def _json_stage(
    *,
    llm: LlmClient,
    settings: Settings,
    system: str,
    user: str,
    code: str,
    temperature: float = 0.4,
) -> dict[str, Any]:
    response = await llm.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=settings.content_generation_model,
        max_tokens=min(settings.content_max_tokens, settings.content_tokens_per_question * 4),
        temperature=temperature,
    )
    return extract_json_object(response.content, code=code)


def _point_context(point: CurriculumPoint) -> dict[str, str]:
    return {
        "subject_name": subject_name(point.subject),
        "grade_name": grade_name(point.grade),
        "point_name": point.name,
        "unit_name": point.unit_name,
        "objective": point.objective,
        "prerequisites": "、".join(point.prerequisites) or "无",
    }


async def _stage_intent(
    *, llm: LlmClient, point: CurriculumPoint, profile: str, settings: Settings
) -> dict[str, str]:
    payload = await _json_stage(
        llm=llm,
        settings=settings,
        system=VIDEO_INTENT_SYSTEM_PROMPT,
        user=VIDEO_INTENT_USER_TEMPLATE.format(**_point_context(point), profile=profile),
        code="EXPLAINER_VIDEO_INTENT_INVALID",
    )
    return validate_intent(payload)


async def _stage_prereq(
    *,
    llm: LlmClient,
    point: CurriculumPoint,
    intent: dict[str, str],
    settings: Settings,
) -> dict[str, Any]:
    intent_text = "；".join(f"{key}：{value}" for key, value in intent.items())
    payload = await _json_stage(
        llm=llm,
        settings=settings,
        system=VIDEO_PREREQ_SYSTEM_PROMPT,
        user=VIDEO_PREREQ_USER_TEMPLATE.format(
            **_point_context(point), intent=intent_text
        ),
        code="EXPLAINER_VIDEO_PREREQ_INVALID",
    )
    return validate_prereq_graph(payload)


async def _stage_sequence(
    *,
    llm: LlmClient,
    point: CurriculumPoint,
    intent: dict[str, str],
    prereq: dict[str, Any],
    settings: Settings,
) -> list[dict[str, str]]:
    prereq_text = "、".join(node["label"] for node in prereq["nodes"])
    payload = await _json_stage(
        llm=llm,
        settings=settings,
        system=VIDEO_SEQUENCE_SYSTEM_PROMPT,
        user=VIDEO_SEQUENCE_USER_TEMPLATE.format(
            **_point_context(point),
            misconception=intent["misconception"],
            core_idea=intent["core_idea"],
            prereq=prereq_text,
            max_segments=settings.explainer_video_max_segments,
            max_seconds=settings.explainer_video_max_seconds,
        ),
        code="EXPLAINER_VIDEO_SEQUENCE_INVALID",
    )
    return validate_sequence(payload, max_segments=settings.explainer_video_max_segments)


def _sequence_text(segments: list[dict[str, str]]) -> str:
    lines = []
    for index, segment in enumerate(segments, start=1):
        lines.append(
            f"第{index}幕·{segment['name']}\n"
            f"  台词：{segment['narration']}\n"
            f"  画面目标：{segment['visual_goal'] or '（未给出）'}"
        )
    return "\n".join(lines)


async def _stage_director(
    *,
    llm: LlmClient,
    point: CurriculumPoint,
    segments: list[dict[str, str]],
    settings: Settings,
) -> dict[str, Any]:
    payload = await _json_stage(
        llm=llm,
        settings=settings,
        system=VIDEO_DIRECTOR_SYSTEM_PROMPT,
        user=VIDEO_DIRECTOR_USER_TEMPLATE.format(
            **_point_context(point),
            segment_count=len(segments),
            sequence=_sequence_text(segments),
        ),
        code="EXPLAINER_VIDEO_DIRECTOR_INVALID",
    )
    return payload


async def _repair_director(
    *,
    llm: LlmClient,
    point: CurriculumPoint,
    director: dict[str, Any],
    error: str,
    settings: Settings,
) -> dict[str, Any]:
    """渲染失败自愈：把错误摘要回喂导演阶段，只修画面，不改台词。"""
    import json

    return await _json_stage(
        llm=llm,
        settings=settings,
        system=VIDEO_REPAIR_SYSTEM_PROMPT,
        user=VIDEO_REPAIR_USER_TEMPLATE.format(
            point_name=point.name,
            error=error[-3000:],
            director=json.dumps(director, ensure_ascii=False)[:12000],
        ),
        code="EXPLAINER_VIDEO_REPAIR_INVALID",
        temperature=0.1,
    )


# ---------------------------------------------------------------- 音频辅助


def _audio_path(workdir: Path, index: int, mime: str) -> Path:
    extension = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
    }.get(mime.split(";")[0].strip().lower())
    if extension is None:
        extension = mimetypes.guess_extension(mime) or ".bin"
    return workdir / f"narration-{index}{extension}"


async def _synthesize_narration(
    *,
    narrations: list[str],
    tts: TtsProvider,
    toolchain: VideoToolchain,
    workdir: Path,
) -> tuple[list[Path], list[float]]:
    """逐段配音并读出真实时长（镜头停留以它为准）。

    按教学序列的旁白**段落**合成，而不是按镜头：首次导演结构不合法时镜头
    还没建出来，修复重建的镜头与段一一对应，时长即可复用。
    """
    audio_paths: list[Path] = []
    durations: list[float] = []
    for index, narration in enumerate(narrations):
        audio, mime = await tts.synthesize(narration)
        if not audio:
            raise VideoPipelineError(
                f"第 {index + 1} 幕配音为空", code="EXPLAINER_VIDEO_TTS_EMPTY"
            )
        path = _audio_path(workdir, index, mime)
        path.write_bytes(audio)
        audio_paths.append(path)
        duration = await toolchain.probe_duration(path)
        duration = max(2.0, float(duration))
        durations.append(duration)
    return audio_paths, durations


# ---------------------------------------------------------------- 生成主流程


async def generate_video(
    session: AsyncSession,
    *,
    content_id: uuid.UUID,
    llm: LlmClient,
    settings: Settings,
    tts: TtsProvider,
    storage: VideoStorage,
    toolchain: VideoToolchain,
    safety: SafetyService | None = None,
    user_id: uuid.UUID | None = None,
    force: bool = False,
) -> ExplainerContent:
    """跑完 §5.3 六阶段 + 渲染自愈 + 配音混流 + 入库，失败标记 failed。

    视频是离线产物：失败不降级为图文（学生端请求未就绪的视频会回落互动讲解，
    见 ``explainer_service.request_explainer``），所以这里如实落 failed + error，
    便于预生成脚本续跑与人工排查。``force=True`` 时即使已有视频也重新生成；
    重生成失败会把该行标 failed（学生端回落互动讲解），但不会删除旧对象，
    修正后重跑同一命令即可覆盖。
    """
    found = await session.execute(
        select(ExplainerContent).where(ExplainerContent.id == content_id)
    )
    content = found.scalar_one()
    if content.mode is not ExplainerMode.VIDEO:
        raise VideoPipelineError(
            "交互讲解不能走视频管线", code="EXPLAINER_MODE_MISMATCH", status_code=500
        )
    if not force and content.status is ExplainerStatus.READY and content.video_key:
        return content  # 幂等

    record = await session.execute(
        select(KnowledgePointModel).where(KnowledgePointModel.id == content.knowledge_point_id)
    )
    kp = record.scalar_one()
    point = find_point(kp.code) or explainer_service.point_from_record(kp)

    content.status = ExplainerStatus.GENERATING
    content.attempts += 1
    stages: dict[str, Any] = {"version": "manim-v1", "repairs": []}

    try:
        profile = explainer_service._EMPTY_PROFILE
        if user_id is not None:
            profile = await explainer_service._student_profile(session, user_id, kp.id)
        intent = await _stage_intent(llm=llm, point=point, profile=profile, settings=settings)
        stages["intent"] = intent
        prereq = await _stage_prereq(llm=llm, point=point, intent=intent, settings=settings)
        stages["prereq_graph"] = prereq
        segments = await _stage_sequence(
            llm=llm, point=point, intent=intent, prereq=prereq, settings=settings
        )
        stages["sequence"] = segments
        director = await _stage_director(
            llm=llm, point=point, segments=segments, settings=settings
        )
        stages["director"] = director
        # 首次结构校验失败同样进自愈循环：此前直接 FAILED，浪费整条生成的
        # 前三阶段产出（实测 Top 100 里 4 条导演 JSON 失败全部要人工补跑）。
        spec_error = ""
        try:
            shots = build_shots(
                segments, director, max_segments=settings.explainer_video_max_segments
            )
        except VideoPipelineError as exc:
            spec_error = f"{exc.code or 'EXPLAINER_VIDEO_SPEC_INVALID'}：{exc.message}"
            shots = []
        stages["shots"] = shots
        content.script = dict(stages)

        if safety is not None:
            # 台词 + 画面文字 + 公式一起过安全闸：视频成片无法事后逐帧过滤，
            # 必须在上传对象存储之前拦住。
            visible = [shot["narration"] for shot in shots]
            for shot in shots:
                visible.append(str(shot.get("title") or ""))
                for element in shot.get("elements", []):
                    visible.append(str(element.get("content") or element.get("latex") or ""))
            decision = await safety.check_and_record(
                session,
                text="\n".join(visible),
                scene="explainer_video",
                user_id=user_id,
            )
            if not decision.allowed:
                raise VideoPipelineError(
                    "视频台词未通过内容安全检查",
                    code="EXPLAINER_VIDEO_CONTENT_BLOCKED",
                    status_code=422,
                )

        workdir = Path(tempfile.mkdtemp(prefix="xueban-video-"))
        key = ""
        data = b""
        duration = 0.0
        try:
            audio_paths, durations = await _synthesize_narration(
                narrations=[segment["narration"] for segment in segments],
                tts=tts,
                toolchain=toolchain,
                workdir=workdir,
            )
            # 首次结构失败时 shots 为空（等修复重建），此时先不写 duration
            for shot, duration in zip(shots, durations, strict=False):
                shot["duration"] = duration
            clip = await _render_with_repair(
                llm=llm,
                point=point,
                segments=segments,
                director=director,
                shots=shots,
                durations=durations,
                settings=settings,
                toolchain=toolchain,
                workdir=workdir,
                stages=stages,
                spec_error=spec_error,
            )
            final = workdir / "explainer.mp4"
            await toolchain.mux_audio(
                video=clip, audios=audio_paths, output=final, workdir=workdir
            )
            duration = await toolchain.probe_duration(final)
            data = final.read_bytes()
            if not data:
                raise VideoPipelineError("成片为空", code="EXPLAINER_VIDEO_EMPTY")
            key = f"{VIDEO_KEY_PREFIX}/{content.cache_key}.mp4"
            await storage.upload_bytes(key=key, data=data, content_type="video/mp4")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        content.video_key = key
        content.video_mime = "video/mp4"
        content.duration_seconds = round(duration)
        content.byte_size = len(data)
        content.html = None
        content.degraded = False
        content.status = ExplainerStatus.READY
        content.error = None
        content.script = dict(stages)
        return content
    except (LlmError, AppError) as exc:
        content.status = ExplainerStatus.FAILED
        content.error = f"{exc.code or type(exc).__name__}：{exc.message}"
        content.script = dict(stages)
        logger.warning("视频讲解生成失败：%s", content.error)
        return content
    except Exception as exc:
        content.status = ExplainerStatus.FAILED
        # 学生可见的 error 只留异常类型：str(exc) 可能带 stderr 尾部/临时路径，
        # 完整诊断已在日志与 stages.repairs（仅管理员可见口径）里。
        content.error = f"{type(exc).__name__}（内部错误，详见服务日志）"
        content.script = dict(stages)
        logger.exception("视频讲解生成异常")
        return content


def student_script(script: dict[str, Any] | None) -> dict[str, Any] | None:
    """学生端脚本视图：剥掉自愈细节（stderr 尾部/TeX 日志片段）。

    完整 repairs 仅留在落库 script 与服务日志里，供管理员排障；
    `script` 为 None 或缺键时原样返回（交互讲解路径不经过这里）。
    """
    if script is None or "repairs" not in script:
        return script
    return {key: value for key, value in script.items() if key != "repairs"}


async def _render_with_repair(
    *,
    llm: LlmClient,
    point: CurriculumPoint,
    segments: list[dict[str, str]],
    director: dict[str, Any],
    shots: list[dict[str, Any]],
    durations: list[float],
    settings: Settings,
    toolchain: VideoToolchain,
    workdir: Path,
    stages: dict[str, Any],
    spec_error: str = "",
) -> Path:
    """⑥ 场景组装 + 渲染自愈：最多 ``manim_max_attempts`` 次。

    ``spec_error`` 非空表示组卷前的首次结构校验已失败（shots 为空）：
    第一轮直接走导演修复，不浪费一次注定失败的渲染。
    """
    max_attempts = max(1, settings.manim_max_attempts)
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        if spec_error:
            # 导演修完仍不合规：不再浪费一次渲染，直接把结构错误回喂下一轮。
            last_error = spec_error
        else:
            source = compile_scene(shots, font=settings.manim_font)
            try:
                return await toolchain.render_scene(source, workdir=workdir)
            except ManimError as exc:
                last_error = exc.detail or str(exc)
        # 头部是 TeX 首错行（自愈提示的入口），尾部是 traceback；两边都留。
        stages["repairs"].append({"attempt": attempt, "error": last_error[:3000]})
        logger.warning(
            "视频生成失败（第 %s/%s 次）：%s", attempt, max_attempts, last_error[:300]
        )
        if attempt >= max_attempts:
            break
        director = await _repair_director(
            llm=llm, point=point, director=director, error=last_error, settings=settings
        )
        stages["director"] = director
        spec_error = ""
        try:
            shots = build_shots(
                segments, director, max_segments=settings.explainer_video_max_segments
            )
        except VideoPipelineError as exc:
            spec_error = f"{exc.code or 'EXPLAINER_VIDEO_SPEC_INVALID'}：{exc.message}"
            continue
        if len(shots) != len(durations):
            # 旁白按段预合成，镜头数必须与段数一致；不一致回喂下一轮修复，
            # 否则 strict zip 会以 ValueError 炸出无诊断信息的失败。
            spec_error = (
                "EXPLAINER_VIDEO_SPEC_INVALID："
                f"修复后镜头数 {len(shots)} 与旁白段数 {len(durations)} 不一致"
            )
            continue
        for shot, duration in zip(shots, durations, strict=True):
            shot["duration"] = duration
        stages["shots"] = shots
    raise VideoPipelineError(
        f"视频渲染 {max_attempts} 次仍失败", code="EXPLAINER_VIDEO_RENDER_FAILED"
    )


async def reserve_video_content(
    session: AsyncSession,
    *,
    point: CurriculumPoint,
    settings: Settings,
) -> ExplainerContent:
    """给预生成脚本占一行视频缓存（幂等）。"""
    stage = stage_for_grade(point.grade)
    kp_id = await explainer_service.ensure_knowledge_point(
        session, point, stage=stage, sort_order=point.difficulty_band
    )
    return await explainer_service.reserve_content(
        session,
        point_code=point.id,
        kp_id=kp_id,
        stage=stage,
        title=point.name,
        mode=ExplainerMode.VIDEO,
        settings=settings,
    )


def build_toolchain(settings: Settings) -> ManimToolchain:
    """生产工具链工厂（预生成脚本/worker 共用）。"""
    return ManimToolchain(settings)


__all__ = [
    "VIDEO_KEY_PREFIX",
    "VideoPipelineError",
    "build_shots",
    "build_toolchain",
    "generate_video",
    "reserve_video_content",
    "validate_intent",
    "validate_prereq_graph",
    "validate_sequence",
]
