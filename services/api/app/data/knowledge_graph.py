"""知识点体系数据（M2）：数学（小学/初中/高中/考研公共数学）+ 考研英语。

图结构由「章节 → 基础知识点 → 基础巩固/综合应用」自动展开生成，边仅从先序指向后序，
天然无环；仍由 validate_graph 做拓扑排序校验兜底。
"""

from __future__ import annotations

from dataclasses import dataclass

STAGE_CHAPTERS: dict[str, list[tuple[str, str]]] = {
    "elementary": [
        ("整数与小数认识", "整数的认识|小数的认识|数位与计数单位|近似数"),
        ("整数四则运算", "加法与减法|乘法与除法|四则混合运算|运算定律"),
        ("分数与百分数", "分数的意义|分数加减法|分数乘除法|百分数"),
        ("式与方程", "用字母表示数|简易方程|等式的性质"),
        ("图形与几何", "平面图形认识|周长|面积|立体图形与体积"),
        ("统计与概率", "统计表与统计图|平均数|可能性"),
        ("典型应用题", "行程问题|工程问题|浓度问题|比例问题"),
    ],
    "junior": [
        ("有理数", "正数与负数|数轴|相反数|绝对值|有理数大小比较"),
        ("有理数运算", "有理数加减法|有理数乘除法|有理数乘方|混合运算|科学记数法"),
        ("整式", "单项式与多项式|整式加减|去括号与合并同类项"),
        ("一元一次方程", "方程的概念|等式的性质|解一元一次方程|实际问题建模|行程问题"),
        ("几何图形初步", "直线射线与线段|角的度量|余角与补角|相交线|平行线的判定|平行线的性质"),
        ("实数", "平方根|立方根|实数的概念|实数的运算"),
        ("平面直角坐标系", "点的坐标|坐标变换|坐标与图形"),
        ("二元一次方程组", "代入消元法|加减消元法|方程组的应用"),
        ("不等式与不等式组", "不等式的性质|一元一次不等式|一元一次不等式组|不等式的应用"),
        ("整式的乘法与因式分解", "幂的运算|单项式与多项式乘法|乘法公式|提公因式分解|公式法分解"),
        ("分式", "分式的概念|分式的基本性质|分式的运算|分式方程"),
        ("三角形", "三角形的边角关系|全等三角形判定|等腰三角形|直角三角形|勾股定理"),
        ("轴对称", "轴对称的性质|线段的垂直平分线|等腰三角形的性质"),
        ("二次根式", "二次根式的概念|二次根式的运算"),
        ("一元二次方程", "一元二次方程的概念|配方法|公式法|因式分解法|根与系数的关系|一元二次方程的应用"),
        ("二次函数", "二次函数的图像与性质|顶点式|二次函数的最值|二次函数与方程"),
        ("旋转与圆", "旋转的性质|圆心角与弧|垂径定理|切线的性质|圆内接多边形"),
        ("概率与统计", "数据的集中趋势|方差|随机事件|概率计算"),
        ("相似", "相似三角形的判定|相似三角形的性质|位似"),
        ("锐角三角函数", "正弦余弦与正切|解直角三角形|仰角与俯角"),
    ],
    "senior": [
        ("集合与常用逻辑", "集合的运算|充分必要条件|量词"),
        ("函数", "函数的概念|函数的单调性|函数的奇偶性|指数函数|对数函数|幂函数"),
        ("三角函数", "弧度制|三角恒等变换|三角函数的图像与性质|解三角形"),
        ("数列", "等差数列|等比数列|数列求和"),
        ("平面向量", "向量的运算|向量的数量积|向量的应用"),
        ("立体几何", "空间点线面关系|平行与垂直的判定|空间向量|表面积与体积"),
        ("解析几何", "直线方程|圆的方程|椭圆|双曲线|抛物线"),
        ("导数", "导数的概念|导数的运算|单调性与极值|导数的应用"),
        ("概率与统计", "排列组合|二项式定理|条件概率|随机变量的分布"),
        ("不等式选讲", "基本不等式|线性规划"),
    ],
    "adult": [
        ("高等数学·极限", "极限的概念|极限的计算|无穷小的比较|函数的连续性"),
        ("高等数学·导数", "导数的定义|求导法则|高阶导数|微分中值定理"),
        ("高等数学·积分", "不定积分|定积分|反常积分|定积分的应用"),
        ("高等数学·多元函数", "偏导数|全微分|二重积分|多元函数极值"),
        ("高等数学·级数", "数项级数|幂级数|傅里叶级数"),
        ("线性代数", "行列式|矩阵运算|向量组的线性相关性|特征值与特征向量|二次型"),
        ("概率论与数理统计", "随机事件|一维随机变量|数字特征|大数定律|参数估计"),
    ],
    "adult_en": [
        ("考研词汇", "核心词汇辨析|近义词辨析|词根词缀|固定搭配"),
        ("考研语法", "时态语态|非谓语动词|虚拟语气|定语从句|状语从句"),
        ("完形填空", "逻辑衔接|词义复现|语境推断"),
        ("阅读理解", "主旨大意|细节理解|推理判断|词义猜测"),
        ("翻译", "长难句拆分|英译汉技巧|汉译英技巧"),
        ("写作", "应用文写作|图表作文|议论文写作"),
    ],
}

# 跨章节衔接边（数学主线）：(前置 stage, 章节序号) -> (后继 stage, 章节序号)，序号从 1 起
CROSS_CHAPTER_EDGES: list[tuple[tuple[str, int], tuple[str, int]]] = [
    (("elementary", 2), ("junior", 1)),  # 整数四则运算 → 有理数
    (("elementary", 3), ("junior", 6)),  # 分数与百分数 → 实数
    (("junior", 15), ("senior", 2)),  # 一元二次方程 → 函数
    (("junior", 16), ("senior", 8)),  # 二次函数 → 导数
    (("junior", 19), ("senior", 7)),  # 相似 → 解析几何
    (("senior", 8), ("adult", 2)),  # 导数 → 高等数学·导数
    (("senior", 6), ("adult", 4)),  # 立体几何 → 多元函数
    (("senior", 7), ("adult", 6)),  # 解析几何 → 线性代数
]


@dataclass(frozen=True, slots=True)
class GraphNode:
    """知识点节点。"""

    code: str
    name: str
    subject: str
    stage: str
    parent_code: str | None


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """前置依赖边：from 是 to 的前置。"""

    from_code: str
    to_code: str


def _chapter_code(subject: str, stage: str, index: int) -> str:
    return f"{subject}.{stage}.c{index:02d}"


def build_graph() -> tuple[list[GraphNode], list[GraphEdge]]:
    """展开生成知识点与依赖边（顺序即拓扑序）。"""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for stage, chapters in STAGE_CHAPTERS.items():
        subject = "english" if stage.endswith("_en") else "math"
        previous_applied: str | None = None
        for chapter_index, (chapter_name, topics_text) in enumerate(chapters, start=1):
            chapter_code = _chapter_code(subject, stage, chapter_index)
            nodes.append(GraphNode(chapter_code, chapter_name, subject, stage, None))
            if previous_applied is not None:
                edges.append(GraphEdge(previous_applied, chapter_code))
            topics = [item.strip() for item in topics_text.split("|") if item.strip()]
            for topic_index, topic in enumerate(topics, start=1):
                base_code = f"{chapter_code}.t{topic_index:02d}"
                basic_code = f"{base_code}.basic"
                applied_code = f"{base_code}.apply"
                nodes.append(GraphNode(base_code, topic, subject, stage, chapter_code))
                nodes.append(GraphNode(basic_code, f"{topic}·基础巩固", subject, stage, base_code))
                nodes.append(GraphNode(applied_code, f"{topic}·综合应用", subject, stage, base_code))
                edges.append(GraphEdge(chapter_code, base_code))
                edges.append(GraphEdge(base_code, basic_code))
                edges.append(GraphEdge(base_code, applied_code))
                if previous_applied is not None:
                    edges.append(GraphEdge(previous_applied, base_code))
                previous_applied = applied_code

    for (from_stage, from_index), (to_stage, to_index) in CROSS_CHAPTER_EDGES:
        from_subject = "english" if from_stage.endswith("_en") else "math"
        to_subject = "english" if to_stage.endswith("_en") else "math"
        edges.append(
            GraphEdge(
                _chapter_code(from_subject, from_stage, from_index),
                _chapter_code(to_subject, to_stage, to_index),
            )
        )
    return nodes, edges


def topological_order(nodes: list[GraphNode], edges: list[GraphEdge]) -> list[str]:
    """Kahn 拓扑排序；存在环时抛 ValueError。"""
    indegree = {node.code: 0 for node in nodes}
    adjacency: dict[str, list[str]] = {node.code: [] for node in nodes}
    for edge in edges:
        if edge.from_code not in indegree or edge.to_code not in indegree:
            raise ValueError(f"边引用了不存在的知识点：{edge.from_code} -> {edge.to_code}")
        adjacency[edge.from_code].append(edge.to_code)
        indegree[edge.to_code] += 1
    queue = [code for code, degree in indegree.items() if degree == 0]
    order: list[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for successor in adjacency[current]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
    if len(order) != len(nodes):
        raise ValueError("知识点前置依赖图中存在环")
    return order
