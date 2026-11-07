# DeepTutor 评估与吸收记录 · 2026-11-07

- 触发来源：用户提供的抖音视频（「还上个🥚学。#学术ai工具」，作者西兰花费算力，
  2026-10-26 发布，https://v.douyin.com/smOxa5lWwz8/）。
- 视频所指项目：**HKUDS/DeepTutor**（港大数据智能实验室，Apache-2.0，
  https://github.com/HKUDS/DeepTutor ，arXiv:2604.26962）。
- 结论：**定位不同，不整体照搬；吸收 2 项已落地、3 项进 backlog、其余明确不吸收**。

## 1. 定位对比

| 维度 | DeepTutor | 学伴（xueban） |
|---|---|---|
| 目标用户 | 成人自学/科研（"还上个大学"） | K12 小学/初中/高中生 |
| 内容来源 | 任意上传资料/RAG/联网/论文库 | 固定人教版课程树（907 点）+ 审核过的题库 |
| 解题哲学 | Solve 模式给完整解法、多智能体 | 守护型三层提示，**不直接给答案**（README 红线） |
| 调度/成本 | agent 循环按轮计费（评论区："token 消耗量非常恐怖"） | 固定管线：生成→验证→judge→入库，成本可控 |
| 合规 | 面向成人，无未成年人专门控制 | 时长管控/内容过滤/家长留痕/AI 标识/生产 mock 禁用 |

DeepTutor 的能力全景（来自其 README_CN）：Chat/Quiz/Research/Visualize/Solve/Mastery
Path/Reading 多模式工作区、Book 活书、知识库多引擎 RAG（LlamaIndex/GraphRAG/LightRAG…）、
`kb eval`（Recall@k/Precision@k/MRR/nDCG@k）、可审计三层记忆（L1/L2/L3 + Memory Graph）、
Partners/IM 渠道、EduHub 技能社区、Anki 导出、Readiness 就绪度矩阵。

## 2. 已吸收（本次落地）

### 2.1 检索评测指标对齐 `kb eval`

- **动机**：我们只有 recall@5（query 命中率）一个数，无法定位「检索变差是召回掉了
  还是排序掉了」。DeepTutor 的 `kb eval` 报四件套且全部是排序纯函数，直接吸收。
- **落地**：`services/api/scripts/retrieval_metrics.py`（precision@k / recall@k /
  hit@k / MRR@k / nDCG@k，二元相关、无模型裁判）+ `eval_retrieval.py` 输出五项指标。
- **门禁不变**：T2.4 的「recall@5 ≥ 90%」即现在的 `hit_rate@5`，退出码语义原样保留。
- 测试：`tests/test_retrieval_metrics.py`（3 项纯函数单测）。

### 2.2 复习卡导出 Anki

- **动机**：DeepTutor 的「闪卡导出到 Anki」对自学型用户是刚需；学伴已有 FSRS 卡，
  但学生换了工具生态就带不走复习内容。
- **落地**：
  - 后端 `GET /v1/review/export.anki`（`app/services/anki_export.py` +
    `app/api/routes/review.py`）：导出当前用户全部未暂停的**客观题**复习卡，
    Anki 文本导入格式（`#separator:tab` / `#html:true` / `#deck:学伴::复习` /
    `#tags column:3`），`$...$` → `\(…\)` 以便 Anki 的 MathJax 渲染，标签含题型与知识点。
  - 桌面端复盘页「导出 Anki 复习卡」按钮（`anki-export-button.tsx` +
    `lib/anki-export.ts`，带鉴权下载、错误转学生视角文案）。
- **红线**：复习调度仍以学伴 FSRS 为准，导出不包含任何调度状态——两套调度互不干扰。

## 3. 进 backlog（有增量价值，未排期）

| 项 | 来源 | 学伴落点 |
|---|---|---|
| 大纲先审后生成（outline-first） | Book：章节大纲先确认再生成 | Explainer/视频管线：脚本先出大纲给（家长/学生）确认，再渲染——直接降幻觉与 token 浪费；与进行中的视频管线同一条线，等其合入后排期 |
| 可审计学习者记忆 L1/L2/L3 | Memory + Memory Graph | 家长端画像的「可解释、可编辑」版：把掌握度/行为的依据链暴露给家长，替代黑盒雷达图 |
| Readiness 就绪度矩阵 | Settings → 运行状态 | 运维页/`/healthz` 扩展：列出各外部依赖（LLM/ embedding/TTS/口语/Manim）的可用性与阻断项 |

## 4. 明确不吸收（与红线/定位冲突）

| 项 | 理由 |
|---|---|
| Solve 直给完整解法、Little Tutor 旁路讲解 | 违反守护型红线：任何「给答案类」功能必须走三层提示（README 全程硬约束 1） |
| Research 深度研究（联网搜索+论文库） | K12 内容过滤红线；未成年人不该由 agent 自由联网取材 |
| Partners / IM 渠道 / 多 agent 调度 | 成本不可控（评论区的 token 吞吐即前车之鉴），且增加未成年人接触面 |
| 任意资料→Book/活书全套 | 学伴的价值主张是「人教版对齐 + 审核过的题库」，任意生成内容绕开了内容安全管线；如未来做「我的资料」，必须复用题库管线的验证/judge 链 |
| 多语言 UI、OAuth 登录、多主题外观 | 与当前交付目标无关 |

## 5. 验证

| 项 | 结果 |
|---|---|
| `tests/test_retrieval_metrics.py` | 3 passed |
| `tests/test_review_anki_export.py` | 3 passed（含跨用户隔离、暂停/主观题排除、MathJax 转换） |
| 桌面 `anki-export.test.ts` | 4 passed（全量 226 passed） |
| 后端全量 pytest | 见 `PROGRESS_2026-11-07.md` |

## 6. 来源

- 视频页：https://v.douyin.com/smOxa5lWwz8/ （评论区「大家都在搜：deeptutor」定位到项目）
- 仓库与中文 README：https://github.com/HKUDS/DeepTutor （assets/README/README_CN.md，经 gh api 获取）
