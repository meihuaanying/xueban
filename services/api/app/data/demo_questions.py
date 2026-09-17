"""演示题库生成器（M2·自建内容，无版权风险）。

数学：基于初中数学知识点批量生成（题干带 [知识点] 前缀，便于词面检索与校对）。
英语：60 组考研核心词 + 30 个语法点 + 20 条翻译，按模板组合成 ≥500 题。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.data.knowledge_graph import build_graph

MISTAKE_TAGS = ["concept", "computation", "method", "transfer", "reading"]


@dataclass(frozen=True, slots=True)
class WordEntry:
    """考研词汇条目。"""

    word: str
    gloss: str
    pos: str
    collocation: str  # 含 ___ 的例句


@dataclass(frozen=True, slots=True)
class GrammarItem:
    """语法条目。"""

    sentence: str  # 含 ___
    answer: str
    distractors: tuple[str, str, str]
    explanation: str


WORDS: list[WordEntry] = [
    WordEntry("abandon", "放弃；抛弃", "v.", "They had to ___ the plan due to lack of funds."),
    WordEntry("abstract", "抽象的；摘要", "adj.", "The professor gave an ___ explanation of the theory."),
    WordEntry("accelerate", "加速；促进", "v.", "New policies may ___ economic growth."),
    WordEntry("accommodate", "容纳；适应", "v.", "The hall can ___ up to 500 students."),
    WordEntry("accumulate", "积累；积聚", "v.", "Dust tends to ___ on the shelves."),
    WordEntry("acknowledge", "承认；致谢", "v.", "He refused to ___ his mistake."),
    WordEntry("adopt", "采用；收养", "v.", "The company decided to ___ a new strategy."),
    WordEntry("advocate", "提倡；拥护", "v.", "Many experts ___ reducing carbon emissions."),
    WordEntry("allocate", "分配；拨给", "v.", "The government will ___ more funds to education."),
    WordEntry("ambiguous", "模棱两可的", "adj.", "His answer was ___ and confused everyone."),
    WordEntry("analyze", "分析", "v.", "Scientists need to ___ the data carefully."),
    WordEntry("anticipate", "预料；期望", "v.", "We ___ a rise in demand next quarter."),
    WordEntry("apparent", "明显的；表面的", "adj.", "It soon became ___ that he was lying."),
    WordEntry("appreciate", "感激；欣赏", "v.", "I really ___ your help with the project."),
    WordEntry("approach", "接近；方法", "v.", "We need a new ___ to solving this problem."),
    WordEntry("assess", "评估；评定", "v.", "Teachers ___ students' progress every month."),
    WordEntry("assume", "假定；承担", "v.", "Let us ___ that the report is correct."),
    WordEntry("attribute", "归因于；属性", "v.", "She ___ her success to hard work."),
    WordEntry("available", "可获得的；有空的", "adj.", "The manager is not ___ right now."),
    WordEntry("aware", "意识到的", "adj.", "Students should be ___ of the deadline."),
    WordEntry("benefit", "益处；受益", "n.", "Regular exercise will ___ your health."),
    WordEntry("budget", "预算", "n.", "The project went over ___ last year."),
    WordEntry("capacity", "容量；能力", "n.", "The stadium has a ___ of 80,000 people."),
    WordEntry("challenge", "挑战；质疑", "n.", "Learning a language is a real ___."),
    WordEntry("commit", "承诺；犯（错）", "v.", "She decided to ___ herself to teaching."),
    WordEntry("comprehensive", "全面的；综合的", "adj.", "The book offers a ___ review of grammar."),
    WordEntry("concentrate", "集中；专注", "v.", "It is hard to ___ in a noisy room."),
    WordEntry("conduct", "进行；行为", "v.", "They will ___ a survey next week."),
    WordEntry("confirm", "确认；证实", "v.", "Please ___ your booking by email."),
    WordEntry("conflict", "冲突；矛盾", "n.", "There is a ___ between the two reports."),
    WordEntry("consequence", "结果；后果", "n.", "Every decision has its ___."),
    WordEntry("considerable", "相当大的", "adj.", "The project required ___ investment."),
    WordEntry("consistent", "一致的；始终如一的", "adj.", "His results are ___ with our theory."),
    WordEntry("contribute", "贡献；促成", "v.", "Many factors ___ to climate change."),
    WordEntry("convenient", "方便的", "adj.", "Online payment is very ___ for users."),
    WordEntry("crucial", "至关重要的", "adj.", "Timing is ___ to the success of the plan."),
    WordEntry("decline", "下降；婉拒", "v.", "Sales began to ___ last winter."),
    WordEntry("define", "定义；界定", "v.", "It is difficult to ___ happiness."),
    WordEntry("demonstrate", "证明；演示", "v.", "The experiment will ___ the principle."),
    WordEntry("derive", "源于；获得", "v.", "Many English words ___ from Latin."),
    WordEntry("distinguish", "区分；辨别", "v.", "Can you ___ the twins apart?"),
    WordEntry("dominate", "支配；主导", "v.", "One company tends to ___ the market."),
    WordEntry("efficient", "高效的", "adj.", "The new system is more ___ than the old one."),
    WordEntry("emerge", "出现；浮现", "v.", "New problems ___ during the discussion."),
    WordEntry("emphasize", "强调", "v.", "The teacher ___ the importance of practice."),
    WordEntry("enhance", "提高；增强", "v.", "Reading can ___ your vocabulary."),
    WordEntry("ensure", "确保", "v.", "Please ___ that the door is locked."),
    WordEntry("establish", "建立；确立", "v.", "The university was ___ in 1898."),
    WordEntry("evaluate", "评价；评估", "v.", "Managers ___ employees twice a year."),
    WordEntry("evident", "明显的", "adj.", "His talent was ___ from an early age."),
    WordEntry("evolve", "演变；进化", "v.", "Languages ___ slowly over centuries."),
    WordEntry("exceed", "超过；超越", "v.", "Do not ___ the speed limit."),
    WordEntry("expand", "扩大；扩展", "v.", "The company plans to ___ overseas."),
    WordEntry("facilitate", "促进；便利", "v.", "The new bridge will ___ traffic flow."),
    WordEntry("flexible", "灵活的；有弹性的", "adj.", "Our schedule is quite ___ this week."),
    WordEntry("fundamental", "基本的；根本的", "adj.", "Trust is ___ to any friendship."),
    WordEntry("generate", "产生；生成", "v.", "Solar panels ___ clean electricity."),
    WordEntry("guarantee", "保证；担保", "v.", "Hard work does not ___ success."),
    WordEntry("illustrate", "说明；举例说明", "v.", "The chart will ___ the trend clearly."),
    WordEntry("implement", "实施；执行", "v.", "The school will ___ the new rules in March."),
    WordEntry("impose", "强加；征收", "v.", "The city may ___ new taxes on cars."),
    WordEntry("indicate", "表明；指示", "v.", "The results ___ a clear improvement."),
    WordEntry("inevitable", "不可避免的", "adj.", "Some mistakes are ___ for beginners."),
    WordEntry("influence", "影响", "n.", "Parents have a great ___ on children."),
    WordEntry("initiate", "发起；开始", "v.", "They plan to ___ a new project."),
    WordEntry("innovative", "创新的", "adj.", "The company is known for ___ designs."),
    WordEntry("intense", "强烈的；紧张的", "adj.", "The training was ___ but rewarding."),
    WordEntry("interpret", "解释；口译", "v.", "How do you ___ this poem?"),
    WordEntry("investigate", "调查；研究", "v.", "Police will ___ the accident."),
    WordEntry("involve", "涉及；使参与", "v.", "The job will ___ a lot of travel."),
    WordEntry("isolate", "隔离；孤立", "v.", "Doctors had to ___ the patient."),
    WordEntry("justify", "证明…正当", "v.", "Nothing can ___ such behavior."),
    WordEntry("maintain", "维持；主张", "v.", "It is hard to ___ a healthy diet."),
    WordEntry("manipulate", "操纵；处理", "v.", "Do not let others ___ your emotions."),
    WordEntry("minimize", "使最小化", "v.", "We should ___ the risk of failure."),
    WordEntry("modify", "修改；调整", "v.", "You can ___ the plan if necessary."),
    WordEntry("negotiate", "谈判；协商", "v.", "The two sides will ___ a new contract."),
    WordEntry("obtain", "获得；得到", "v.", "You must ___ permission first."),
    WordEntry("occupy", "占据；占用", "v.", "Books ___ most of his desk."),
    WordEntry("participate", "参与；参加", "v.", "All students should ___ in the discussion."),
]

GRAMMAR: list[GrammarItem] = [
    GrammarItem("She ___ to school every day.", "goes", ("go", "going", "gone"), "一般现在时，第三人称单数用 goes。"),
    GrammarItem("They ___ football when it started to rain.", "were playing", ("played", "have played", "play"), "过去进行时表示过去某一时刻正在进行的动作。"),
    GrammarItem("The homework ___ by the students yesterday.", "was finished", ("finished", "has finished", "is finishing"), "一般过去时的被动语态：was/were + 过去分词。"),
    GrammarItem("He suggested that we ___ early.", "arrive", ("arrived", "will arrive", "arriving"), "suggest 后接虚拟语气，谓语用 should + 动词原形（should 可省略）。"),
    GrammarItem("I look forward to ___ from you soon.", "hearing", ("hear", "heard", "be heard"), "look forward to 中 to 为介词，后接动名词。"),
    GrammarItem("The man ___ is standing there is our teacher.", "who", ("which", "whose", "whom"), "先行词指人且在从句中作主语，用关系代词 who。"),
    GrammarItem("This is the book ___ cover is missing.", "whose", ("which", "who", "that"), "表示所属关系用 whose。"),
    GrammarItem("If I ___ you, I would accept the offer.", "were", ("am", "was", "be"), "虚拟语气中，条件句用 were 表示与现在事实相反。"),
    GrammarItem("By the time he arrived, the meeting ___.", "had ended", ("ended", "has ended", "ends"), "过去完成时表示“过去的过去”。"),
    GrammarItem("She is used to ___ up early.", "getting", ("get", "got", "gotten"), "be used to 中 to 是介词，后接动名词。"),
    GrammarItem("There ___ a lot of information in the report.", "is", ("are", "were", "be"), "there be 句型中主语为不可数名词，谓语用单数。"),
    GrammarItem("Neither the students nor the teacher ___ aware of it.", "was", ("were", "are", "be"), "neither...nor 遵循就近原则，谓语与 teacher 一致。"),
    GrammarItem("The room ___ cleaned every morning.", "is", ("are", "was being", "be"), "一般现在时被动语态主语为单数。"),
    GrammarItem("He asked me where I ___ from.", "came", ("come", "coming", "comes"), "宾语从句用陈述语序，时态与主句呼应，用过去式。"),
    GrammarItem("It is important that everyone ___ the rules.", "follows", ("follow", "followed", "following"), "主语从句中的陈述语气，主语 everyone 为单数。"),
    GrammarItem("We had better ___ now.", "leave", ("to leave", "leaving", "left"), "had better 后接动词原形。"),
    GrammarItem("The film is worth ___.", "watching", ("watch", "to watch", "watched"), "be worth doing 固定搭配。"),
    GrammarItem("Not until midnight ___ he finish his work.", "did", ("does", "do", "was"), "Not until 置于句首，主句用部分倒装。"),
    GrammarItem("The more you practice, ___ you will be.", "the better", ("better", "the best", "best"), "the more...the more 比较级结构。"),
    GrammarItem("She made me ___ the truth.", "tell", ("to tell", "telling", "told"), "make sb. do sth. 后接省略 to 的不定式。"),
    GrammarItem("This is the place ___ we first met.", "where", ("which", "that", "when"), "先行词为地点，从句中作状语，用关系副词 where。"),
    GrammarItem("The reason ___ he was late is unknown.", "why", ("which", "that", "when"), "先行词为 reason，从句中作原因状语，用 why。"),
    GrammarItem("Hardly ___ he arrived when the phone rang.", "had", ("has", "did", "was"), "hardly...when 结构中主句用过去完成时并倒装。"),
    GrammarItem("Either you or I ___ wrong.", "am", ("is", "are", "be"), "either...or 遵循就近原则，与 I 一致用 am。"),
    GrammarItem("She would rather ___ at home than go out.", "stay", ("stays", "staying", "stayed"), "would rather do...than do 结构用动词原形。"),
    GrammarItem("The project ___ next month.", "will be completed", ("completes", "will complete", "is completing"), "一般将来时的被动语态。"),
    GrammarItem("He kept ___ although he was tired.", "working", ("work", "to work", "worked"), "keep doing sth. 表示持续做某事。"),
    GrammarItem("It was in the library ___ I met him.", "that", ("where", "which", "when"), "强调句型 It is/was...that...。"),
    GrammarItem("Such books ___ I need are expensive.", "as", ("that", "which", "what"), "such...as 引导定语从句。"),
    GrammarItem("He is the only one of the students who ___ been to Beijing.", "has", ("have", "having", "had"), "先行词为 the only one，从句谓语用单数。"),
]

TRANSLATIONS: list[tuple[str, str]] = [
    ("学伴的目标是让学生独立做得对。", "The goal of XueBan is to help students solve problems independently."),
    ("坚持每天练习是提高成绩的关键。", "Practicing every day is the key to improving your grades."),
    ("我们应该重视基础知识的学习。", "We should attach importance to learning basic knowledge."),
    ("考试前做好复习计划非常重要。", "It is important to make a review plan before the exam."),
    ("这本书对提高写作能力很有帮助。", "This book is very helpful for improving writing skills."),
    ("他花了两个小时完成这篇作文。", "It took him two hours to finish the essay."),
    ("随着科技的发展，学习方式发生了改变。", "With the development of technology, ways of learning have changed."),
    ("多读书能帮助你扩大词汇量。", "Reading more can help you expand your vocabulary."),
    ("遇到问题时不要轻易放弃。", "Do not give up easily when you meet problems."),
    ("老师建议我们每天早上听英语。", "The teacher suggests that we listen to English every morning."),
    ("只有通过努力才能取得进步。", "Progress can only be made through hard work."),
    ("他对数学的兴趣始于初中。", "His interest in math began in junior high school."),
    ("我们需要找到更高效的学习方法。", "We need to find a more efficient way of learning."),
    ("这次考试的结果比他预期的要好。", "The result of the exam was better than he had expected."),
    ("家长应该鼓励孩子独立思考。", "Parents should encourage children to think independently."),
    ("时间管理对备考非常重要。", "Time management is very important for exam preparation."),
    ("我打算这个学期参加英语演讲比赛。", "I plan to take part in the English speech contest this term."),
    ("研究表明，睡眠不足会影响记忆力。", "Studies show that lack of sleep affects memory."),
    ("他不仅会做题，还能讲清思路。", "He can not only solve problems but also explain his ideas clearly."),
    ("让我们一起为梦想努力。", "Let us work hard for our dreams together."),
]


def _arithmetic(rng: random.Random) -> tuple[str, str, str]:
    """整数四则运算题。"""
    a, b = rng.randint(2, 99), rng.randint(2, 99)
    operator = rng.choice(["+", "-", "×"])
    if operator == "+":
        return f"{a} + {b}", str(a + b), "按照有理数加法法则，先确定符号再计算绝对值。"
    if operator == "-":
        if a < b:
            a, b = b, a
        return f"{a} - {b}", str(a - b), "减去一个数等于加上它的相反数。"
    a, b = rng.randint(2, 19), rng.randint(2, 19)
    return f"{a} × {b}", str(a * b), "按照乘法口诀与有理数乘法法则计算。" 


def _math_question(node_name: str, node_code: str, rng: random.Random, variant: int) -> dict[str, Any]:
    """按知识点类型构造一道题。"""
    difficulty = 2 + (variant % 3)
    if "方程组" in node_name:
        x, y = rng.randint(1, 9), rng.randint(1, 9)
        stem = f"解方程组：x + y = {x + y}，x - y = {x - y}，求 x。"
        answer = str(x)
        analysis = f"两式相加得 2x = {2 * x}，所以 x = {x}。"
        qtype = "fill"
    elif "方程" in node_name and "二次" in node_name:
        root = rng.randint(1, 9)
        stem = f"解一元二次方程：(x - {root})(x - {root}) = 0，求 x（取正根）。"
        answer = str(root)
        analysis = f"因式分解形式表明 x = {root} 是重根。"
        qtype = "fill"
    elif "方程" in node_name:
        a, x = rng.randint(2, 6), rng.randint(1, 9)
        b = rng.randint(1, 20)
        stem = f"解方程：{a}x + {b} = {a * x + b}，求 x。"
        answer = str(x)
        analysis = f"移项得 {a}x = {a * x}，两边同除以 {a}，x = {x}。"
        qtype = "fill"
    elif "函数" in node_name:
        a, b = rng.randint(1, 5), rng.randint(-9, 9)
        x0 = rng.randint(1, 6)
        stem = f"已知函数 f(x) = {a}x {'+' if b >= 0 else '-'} {abs(b)}，求 f({x0})。"
        answer = str(a * x0 + b)
        analysis = f"代入 x = {x0}，f({x0}) = {a}×{x0}{'+' if b >= 0 else '-'}{abs(b)} = {a * x0 + b}。"
        qtype = "fill"
    elif "勾股" in node_name or "直角" in node_name:
        triples = [(3, 4, 5), (5, 12, 13), (6, 8, 10), (8, 15, 17), (9, 12, 15)]
        leg_a, leg_b, hyp = rng.choice(triples)
        stem = f"直角三角形两条直角边分别为 {leg_a} 和 {leg_b}，求斜边长。"
        answer = str(hyp)
        analysis = f"由勾股定理，斜边² = {leg_a}² + {leg_b}² = {leg_a**2 + leg_b**2}，斜边 = {hyp}。"
        qtype = "fill"
    elif "分数" in node_name:
        denominator = rng.choice([5, 7, 8, 9, 11])
        numerator_a = rng.randint(1, denominator - 2)
        numerator_b = rng.randint(1, denominator - 1 - numerator_a)
        answer_num = numerator_a + numerator_b
        stem = f"计算：{numerator_a}/{denominator} + {numerator_b}/{denominator} = ?（结果用分数表示）"
        answer = f"{answer_num}/{denominator}"
        analysis = f"同分母分数相加，分母不变，分子相加得 {answer_num}/{denominator}。"
        qtype = "fill"
    elif "百分数" in node_name:
        number = rng.choice([40, 60, 80, 120, 200, 300])
        percent = rng.choice([15, 20, 25, 30, 40])
        stem = f"求 {number} 的 {percent}% 是多少。"
        answer = str(int(number * percent / 100))
        analysis = f"{number} × {percent}% = {number} × {percent / 100} = {int(number * percent / 100)}。"
        qtype = "fill"
    elif "平均数" in node_name or "统计" in node_name:
        values = [rng.randint(60, 100) for _ in range(4)]
        total = sum(values)
        while total % 4 != 0:
            values[-1] += 1
            total = sum(values)
        stem = f"求数据 {', '.join(map(str, values))} 的平均数。"
        answer = str(total // 4)
        analysis = f"平均数 = ({' + '.join(map(str, values))}) ÷ 4 = {total // 4}。"
        qtype = "fill"
    else:
        expression, answer, analysis = _arithmetic(rng)
        stem = f"计算：{expression} = ?"
        qtype = "fill"

    if variant % 2 == 0:
        correct = answer
        distractors: set[str] = set()
        while len(distractors) < 3:
            try:
                offset = rng.choice([-3, -2, -1, 1, 2, 3, 5])
                candidate = str(int(answer) + offset) if answer.lstrip("-").isdigit() else answer
                if candidate != correct:
                    distractors.add(candidate)
            except (TypeError, ValueError):
                break
        if len(distractors) == 3:
            keys = ["A", "B", "C", "D"]
            rng.shuffle(keys)
            options = {keys[0]: correct}
            for key, value in zip(keys[1:], sorted(distractors), strict=True):
                options[key] = value
            answer_letter = next(key for key, value in options.items() if value == correct)
            return {
                "subject": "math",
                "stage": "junior",
                "qtype": "choice",
                "stem": f"[{node_name}] {stem.rstrip('?')}？",
                "options": options,
                "answer": answer_letter,
                "analysis": f"{analysis} 正确选项为 {answer_letter}。",
                "difficulty": difficulty,
                "knowledge_points": [node_code],
                "mistake_tags": [MISTAKE_TAGS[variant % len(MISTAKE_TAGS)]],
                "source": "demo-template",
            }

    return {
        "subject": "math",
        "stage": "junior",
        "qtype": qtype,
        "stem": f"[{node_name}] {stem}",
        "options": None,
        "answer": answer,
        "analysis": analysis,
        "difficulty": difficulty,
        "knowledge_points": [node_code],
        "mistake_tags": [MISTAKE_TAGS[variant % len(MISTAKE_TAGS)]],
        "source": "demo-template",
    }


def generate_math_records(*, per_kp: int = 2, seed: int = 2026) -> list[dict[str, Any]]:
    """生成初中数学演示题（基础知识点 × per_kp）。"""
    nodes, _ = build_graph()
    base_nodes = [
        node
        for node in nodes
        if node.stage == "junior"
        and node.parent_code is not None
        and not node.code.endswith((".basic", ".apply"))
    ]
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    for node in base_nodes:
        for variant in range(per_kp):
            records.append(_math_question(node.name, node.code, rng, variant))
    return records


def _vocab_records(entry: WordEntry, node_code: str, rng: random.Random) -> list[dict[str, Any]]:
    """单个单词生成 5 道题。"""
    others = [item for item in WORDS if item.word != entry.word]
    distractors = rng.sample(others, 3)
    option_keys = ["A", "B", "C", "D"]

    def build(stem: str, correct: str, wrong: list[str], analysis: str, difficulty: int) -> dict[str, Any]:
        values = [correct] + wrong[:3]
        shuffled = values[:]
        rng.shuffle(shuffled)
        options = dict(zip(option_keys, shuffled, strict=True))
        answer = next(key for key, value in options.items() if value == correct)
        return {
            "subject": "english",
            "stage": "adult",
            "qtype": "choice",
            "stem": stem,
            "options": options,
            "answer": answer,
            "analysis": analysis,
            "difficulty": difficulty,
            "knowledge_points": [node_code],
            "mistake_tags": ["concept"],
            "source": "demo-template",
        }

    records = [
        build(
            f"选择与 {entry.word} 意思最接近的中文释义。",
            entry.gloss,
            [item.gloss for item in distractors],
            f"{entry.word}（{entry.pos}）意为“{entry.gloss}”。",
            2,
        ),
        build(
            f"“{entry.gloss}”对应的英文单词是？",
            entry.word,
            [item.word for item in distractors],
            f"“{entry.gloss}”对应 {entry.word}。",
            2,
        ),
        build(
            f"单词 {entry.word} 的词性是？",
            entry.pos,
            ["n.", "adj.", "adv."],
            f"{entry.word} 的词性为 {entry.pos}。",
            1,
        ),
        build(
            f"选择正确的拼写（释义：{entry.gloss}）。",
            entry.word,
            [_misspell(item.word, rng) for item in distractors],
            f"正确拼写为 {entry.word}。",
            3,
        ),
        build(
            entry.collocation,
            entry.word,
            [item.word for item in distractors],
            f"根据语境，应填入 {entry.word}（{entry.gloss}）。",
            3,
        ),
    ]
    return records


def _misspell(word: str, rng: random.Random) -> str:
    """生成拼写错误变体（交换相邻字母）。"""
    if len(word) < 4:
        return word + "e"
    position = rng.randint(1, len(word) - 2)
    return word[:position] + word[position + 1] + word[position] + word[position + 2 :]


def generate_english_records(*, seed: int = 2026) -> list[dict[str, Any]]:
    """生成考研英语演示题。"""
    nodes, _ = build_graph()
    base_nodes = [
        node
        for node in nodes
        if node.stage == "adult_en"
        and node.parent_code is not None
        and not node.code.endswith((".basic", ".apply"))
    ]
    vocab_nodes = [node for node in base_nodes if node.code.startswith("english.adult_en.c01")]
    grammar_nodes = [node for node in base_nodes if node.code.startswith("english.adult_en.c02")]
    translation_nodes = [node for node in base_nodes if node.code.startswith("english.adult_en.c05")]

    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    for index, entry in enumerate(WORDS):
        node = vocab_nodes[index % len(vocab_nodes)]
        records.extend(_vocab_records(entry, node.code, rng))

    for index, item in enumerate(GRAMMAR):
        node = grammar_nodes[index % len(grammar_nodes)]
        records.extend(_grammar_records(item, node.code, rng))

    for index, (chinese, english) in enumerate(TRANSLATIONS):
        node = translation_nodes[index % len(translation_nodes)]
        records.append(
            {
                "subject": "english",
                "stage": "adult",
                "qtype": "short_answer",
                "stem": f"[翻译] 将下面句子翻译成英文：{chinese}",
                "options": None,
                "answer": english,
                "analysis": f"参考译文：{english}。注意句子结构与时态的处理。",
                "difficulty": 3,
                "knowledge_points": [node.code],
                "mistake_tags": ["method"],
                "source": "demo-template",
            }
        )
    return records


def _grammar_records(item: GrammarItem, node_code: str, rng: random.Random) -> list[dict[str, Any]]:
    """单个语法点生成 4 道题。"""
    keys = ["A", "B", "C", "D"]
    values = [item.answer, *item.distractors]
    rng.shuffle(values)
    options = dict(zip(keys, values, strict=True))
    answer = next(key for key, value in options.items() if value == item.answer)

    correct_sentence = item.sentence.replace("___", item.answer)
    wrong_sentence = item.sentence.replace("___", item.distractors[0])

    return [
        {
            "subject": "english",
            "stage": "adult",
            "qtype": "choice",
            "stem": f"[语法] 选择最恰当的一项：{item.sentence}",
            "options": options,
            "answer": answer,
            "analysis": item.explanation,
            "difficulty": 3,
            "knowledge_points": [node_code],
            "mistake_tags": ["concept"],
            "source": "demo-template",
        },
        {
            "subject": "english",
            "stage": "adult",
            "qtype": "fill",
            "stem": f"[语法] 用括号中动词的适当形式填空：{item.sentence}",
            "options": None,
            "answer": item.answer,
            "analysis": item.explanation,
            "difficulty": 3,
            "knowledge_points": [node_code],
            "mistake_tags": ["concept"],
            "source": "demo-template",
        },
        {
            "subject": "english",
            "stage": "adult",
            "qtype": "choice",
            "stem": f"[语法] 判断下列句子语法是否正确：{correct_sentence}",
            "options": {"A": "正确", "B": "错误"},
            "answer": "A",
            "analysis": f"句子正确。{item.explanation}",
            "difficulty": 2,
            "knowledge_points": [node_code],
            "mistake_tags": ["reading"],
            "source": "demo-template",
        },
        {
            "subject": "english",
            "stage": "adult",
            "qtype": "choice",
            "stem": f"[语法] 判断下列句子语法是否正确：{wrong_sentence}",
            "options": {"A": "正确", "B": "错误"},
            "answer": "B",
            "analysis": f"句子有误，应改为 {correct_sentence}。{item.explanation}",
            "difficulty": 3,
            "knowledge_points": [node_code],
            "mistake_tags": ["reading"],
            "source": "demo-template",
        },
    ]


def generate_demo_records(*, math_per_kp: int = 7, seed: int = 2026) -> list[dict[str, Any]]:
    """生成完整演示题库（初中数学 ≥500 + 考研英语 ≥500）。"""
    return generate_math_records(per_kp=math_per_kp, seed=seed) + generate_english_records(seed=seed)
