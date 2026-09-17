"""陪练四件套（F-32~F-35）：情景口语、面试模拟、学习陪伴、文书辅助。

F-34 红线：心理危机表述必须触发「引导专业求助」话术，规则层高召回（0 漏判），
LLM 仅用于正常对话与润色，危机话术不经过模型生成。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CRISIS_TERMS: tuple[str, ...] = (
    "自杀",
    "自尽",
    "轻生",
    "想死",
    "不想活",
    "不活了",
    "去死",
    "死了算了",
    "结束生命",
    "结束自己",
    "离开这个世界",
    "跳楼",
    "跳下去",
    "跳河",
    "割腕",
    "自残",
    "遗书",
    "安眠药",
    "上吊",
    "烧炭",
)

HOPELESSNESS_TERMS: tuple[str, ...] = (
    "活着没意思",
    "没有意义",
    "毫无意义",
    "撑不下去",
    "熬不下去",
    "活着好累",
    "绝望",
    "生无可恋",
    "没人需要我",
    "消失就好了",
)

CRISIS_RESOURCES: tuple[str, ...] = (
    "全国 24 小时心理援助热线：12356",
    "北京心理危机研究与干预中心：010-82951332（24 小时）",
    "教育部华中师范大学心理援助热线：4009-678-320（24 小时）",
)

CRISIS_REPLY = (
    "我很在意你现在的感受，也很感谢你愿意说出来。你现在承受的痛苦是真实且重要的，"
    "但它需要专业的、马上就到的支持——请立刻告诉身边的家长、老师或可信任的成年人，"
    "并拨打下面的 24 小时心理援助热线，让受过专业训练的人陪你度过这段时间。\n\n"
    "如果你正处在危险中或有伤害自己的冲动，请马上拨打 120 或 110，或立即前往最近的医院急诊。"
    "我会一直在这里，但请把「立刻联系专业帮助」放在第一位。"
)

GUIDANCE_TAIL = "\n\n（我不会以心理咨询师的身份提供治疗；我可以陪你一起联系家长/老师与专业热线。）"

ROLEPLAY_SCENES: dict[str, dict[str, object]] = {
    "restaurant": {
        "title": "餐厅点餐",
        "opening": "Hi! Welcome to Sunny Cafe. What would you like to order today?",
        "focus": ["点餐句式", "礼貌请求", "口味表达"],
    },
    "airport": {
        "title": "机场问路",
        "opening": (
            "Excuse me, you look a bit lost. Are you looking for a gate or the baggage claim?"
        ),
        "focus": ["问路句式", "方向介词", "确认信息"],
    },
    "hotel": {
        "title": "酒店入住",
        "opening": "Good evening! Welcome to Lakeside Hotel. Do you have a reservation with us?",
        "focus": ["预订信息", "房型需求", "时间表达"],
    },
    "campus": {
        "title": "校园交友",
        "opening": "Hey! I think we're in the same English class. What's your name?",
        "focus": ["自我介绍", "兴趣爱好", "约定句式"],
    },
    "shopping": {
        "title": "购物退换",
        "opening": "Hello! How can I help you today? Is there a problem with your purchase?",
        "focus": ["投诉表达", "退换条件", "协商语气"],
    },
}

# 常见中式英语纠错（mock 规则库；真实场景由 LLM 输出）
COMMON_MISTAKES: tuple[tuple[str, str, str], ...] = (
    ("I very like", "I really like", "very 不能直接修饰动词，用 really 或 like ... very much"),
    ("open the light", "turn on the light", "开灯固定搭配是 turn on"),
    ("I have 18 years old", "I am 18 years old", "年龄用 be 动词表达"),
    ("discuss about", "discuss", "discuss 是及物动词，不加 about"),
    ("How to say", "How do you say", "疑问句需要完整主谓结构"),
    ("I will go to there", "I will go there", "there 是副词，前面不加 to"),
)

FILLERS = ("um", "uh", "you know", "like,")


@dataclass(slots=True)
class Correction:
    """纠错标注。"""

    original: str
    suggestion: str
    note: str


@dataclass(slots=True)
class CoachReply:
    """陪练一轮回复。"""

    scene: str
    reply: str
    corrections: list[Correction] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)
    crisis: bool = False
    crisis_resources: list[str] = field(default_factory=list)


def detect_crisis(text: str) -> bool:
    """规则层危机识别（高召回）：明确危机词或无望表达任一命中即触发。"""
    normalized = text.replace(" ", "")
    if any(term in normalized for term in CRISIS_TERMS):
        return True
    return any(term in normalized for term in HOPELESSNESS_TERMS)


def crisis_reply() -> CoachReply:
    """危机安全话术（不经过 LLM 生成）。"""
    return CoachReply(
        scene="companion",
        reply=CRISIS_REPLY + GUIDANCE_TAIL,
        corrections=[],
        followups=["现在可以告诉我，你身边有没有可以马上联系的家长或老师？"],
        crisis=True,
        crisis_resources=list(CRISIS_RESOURCES),
    )


def roleplay_reply(*, scene: str, message: str, turn: int) -> CoachReply:
    """情景口语陪练（mock 教师角色）：纠错 + 同场景追问。"""
    scene_spec = ROLEPLAY_SCENES.get(scene) or ROLEPLAY_SCENES["restaurant"]
    corrections = [
        Correction(original=wrong, suggestion=right, note=note)
        for wrong, right, note in COMMON_MISTAKES
        if wrong.lower() in message.lower()
    ]
    focus = "、".join(str(item) for item in list(scene_spec["focus"]))  # type: ignore[call-overload]
    if corrections:
        lead = f"Good try! 我注意到一处表达可以更地道：{corrections[0].suggestion}。"
    else:
        lead = "Nice, that sounds natural!"
    followups = [
        f"试着用完整句子再说一次（本场景重点：{focus}）。",
        "Can you ask me a question in this scene?",
    ]
    reply = (
        f"{lead}（第 {turn} 轮 · 场景：{scene_spec['title']}）"
        f"继续用英语回应我吧，例如：{scene_spec['opening']}"
        if turn > 1
        else f"{lead} 我们先从开场开始：{scene_spec['opening']}"
    )
    return CoachReply(
        scene=str(scene),
        reply=reply,
        corrections=corrections,
        followups=followups,
    )


def interview_feedback(*, message: str, question: str) -> CoachReply:
    """面试/复试模拟：内容/逻辑/表达三维反馈（规则评分，mock 先行）。"""
    length = len(message)
    structure_markers = ["首先", "其次", "最后", "第一", "第二", "总结", "因此"]
    structure_score = sum(1 for marker in structure_markers if marker in message)
    filler_count = sum(message.lower().count(filler) for filler in FILLERS)

    content = "内容较充实" if length >= 80 else "内容偏短：建议补充具体事例与数据"
    logic = (
        "逻辑清晰（使用了分点/总结结构）"
        if structure_score >= 2
        else "逻辑可加强：尝试「观点 → 例子 → 小结」三段式"
    )
    expression = (
        "表达流畅"
        if filler_count == 0
        else f"口头禅偏多（约 {filler_count} 处），可用停顿替代 filler"
    )
    reply = (
        f"针对问题「{question}」的三维反馈：\n"
        f"· 内容：{content}\n· 逻辑：{logic}\n· 表达：{expression}\n\n"
        "追问：请用 30 秒说明你在这个经历中的具体贡献。"
    )
    return CoachReply(
        scene="interview",
        reply=reply,
        corrections=[],
        followups=["如果面试官追问「失败经历」，你会怎么组织回答？"],
    )


def companion_reply(*, message: str) -> CoachReply:
    """学习陪伴：先共情、再具体行动建议（非心理咨询）。"""
    if detect_crisis(message):
        return crisis_reply()
    action = "把今天的目标缩小到一件事：先完成 10 分钟练习，再决定要不要继续。"
    if "厌学" in message or "不想学" in message:
        action = "先做「最小启动」：打开练习页完成 1 道最简单题，恢复成就感后再加量。"
    elif "焦虑" in message or "紧张" in message:
        action = (
            "试试 4-6 呼吸（吸气 4 秒、呼气 6 秒，做 5 轮），再写下最担心的那件事和对应的一步行动。"
        )
    reply = (
        "我听到你的感受了，这很正常：学习压力大时，情绪先于效率出问题，"
        "我们先照顾情绪，再谈计划。\n\n"
        f"可以马上做的一件事：{action}\n"
        "如果这种状态持续两周以上并影响睡眠/食欲，请告诉家长或老师，寻求线下专业支持。"
    )
    return CoachReply(
        scene="companion",
        reply=reply,
        corrections=[],
        followups=["今天最让你卡住的是哪一件小事？我们一起把它拆小。"],
    )


WRITING_ISSUE_RULES: tuple[tuple[str, str, str], ...] = (
    (r"非常非常|特别特别", "重复强调", "删去重复副词，用一个更精确的形容词"),
    (r"我觉得|我认为", "主观冗余", "简历/自荐信中减少「我认为」，直接陈述事实与结果"),
    (r"等等|什么的", "口语化", "替换为具体列举，避免含糊"),
    (r"负责了|参与了", "弱动词", "使用强动词 + 量化结果（如「主导…，使…提升 20%」）"),
    (r"[\u4e00-\u9fff]{40,}", "长句", "拆成 2 句，每句一个观点，便于阅读"),
)


def writing_assist(*, text: str, kind: str, goal: str | None) -> CoachReply:
    """文书辅助：只改表达不代写观点（输出建议与批注）。"""
    annotations = [
        Correction(original=pattern, suggestion=label, note=advice)
        for pattern, label, advice in WRITING_ISSUE_RULES
        if re.search(pattern, text)
    ]
    suggestions = [f"{item.suggestion}：{item.note}" for item in annotations] or [
        "结构清晰：建议进一步量化成果（数字/比例/影响范围）。",
        "表达准确：保留你的个人观点，仅调整句式与衔接。",
    ]
    reply = "以下是修改建议与批注（不代写内容）：\n" + "\n".join(
        f"· {item}" for item in suggestions
    )
    return CoachReply(
        scene=f"writing:{kind}",
        reply=reply,
        corrections=annotations,
        followups=["需要我针对某一段给出更具体的句式改写示例吗？"],
    )


__all__ = [
    "CRISIS_RESOURCES",
    "ROLEPLAY_SCENES",
    "CoachReply",
    "Correction",
    "companion_reply",
    "crisis_reply",
    "detect_crisis",
    "interview_feedback",
    "roleplay_reply",
    "writing_assist",
]
