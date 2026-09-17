# LLM 评测集（promptfoo）

| 文件 | 用途 |
|------|------|
| `tutor.yaml` | 守护型讲解红线：第 1 层响应「直接给完整答案率」≤5%（F-11，真实模型） |
| `tutor_cases.json` | 评测用例（由 `services/api/scripts/export_eval_cases.py` 从题库导出，默认 50 条；含 `question_id` 供 mock provider 复现链路） |
| `prompts/tutor_level1.txt` | 第 1 层提示词快照（与 `app/services/prompts.py` 同步生成） |
| `provider_mock_api.js` | 自定义 provider：直连本机 API（`LLM_PROVIDER=mock`），无需模型 Key |
| `tutor_mock_api.yaml` | 讲解红线（mock 模式）：50 条用例 + 确定性断言（泄题/篇幅/思路特征） |
| `crisis_cases.json` | F-34 心理危机 10 条红线用例（与 `tests/test_coach.py` 同源） |
| `crisis_mock_api.yaml` | 危机引导 0 漏判（mock 模式）：crisis=true + 求助资源 + 不扮演咨询师 |

## 运行

```bash
# 真实模型（前置：LiteLLM 已配置真实供应商 Key，B-003/B-005）
npx promptfoo@latest eval -c evals/tutor.yaml

# mock 模式（无 Key 可运行，用于 CI 红线回归；需本机/容器 API 可达）
PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo@latest eval -c evals/tutor_mock_api.yaml
PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo@latest eval -c evals/crisis_mock_api.yaml

npx promptfoo@latest view        # 查看结果
```

mock provider 环境变量：`XUEBAN_API_BASE`（默认 `http://127.0.0.1:8096`）、
`XUEBAN_EVAL_PHONE` / `XUEBAN_EVAL_PASSWORD`（默认本机压测账号，见 `services/api/scripts/prepare_load_user.py`）。

更新用例与提示词快照：

```bash
cd services/api
.venv/Scripts/python scripts/export_eval_cases.py --limit 50
```

## 后续评测集（Key 到位后补全并通过 `tutor.yaml` 同源断言）

- `attribution.yaml`：错因归因准确率 ≥80%（30 条，LLM-judge）
- `analogy.yaml`：类比恰当率 ≥85%（20 条，M3/T3.5）
- `essay.yaml`：作文给分合理性 ≥85%（15 条）
- `crisis.yaml`：心理危机引导 0 漏判（10 条，真实模型；mock 版已可运行）
