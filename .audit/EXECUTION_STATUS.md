# EXECUTION STATUS

最后更新: 2026-10-24T12:19:14+08:00

## 任务状态

| ID | 状态 | 验证命令 | 验证结果 | 阻塞原因 |
|----|------|----------|----------|----------|
| T-001 | validated | cd services/api && pytest tests/test_parents.py tests/test_auth.py tests/test_auth_extra.py | pass | - |
| T-002 | blocked | cd services/api && pytest tests/test_judge.py tests/test_grading.py | - | STOP：修复指令与当前代码结构语义冲突。指令 2 要求在 `del _xueban_install_guard` 之后追加 `import runpy as _r; _r.run_path("user_solution.py", run_name="__main__")`，但此时导入守卫已安装且 BLOCKED_MODULES 含 importlib（judge_service.py:29），runpy 顶层 `import importlib.machinery` 被守卫拦截。已在仓库外临时目录以 Python 3.12.10 实证：`python -I -S solution.py` 抛 `ImportError: judge sandbox: module 'importlib' is not allowed`，用户代码不执行；test_judge.py:31 `test_correct_solution_accepted` 等 accepted 路径用例必然失败。规避手段（守卫前预导入 runpy / 为 runpy 内部导入放行 importlib / 从黑名单移除 importlib）均无规格授权，按硬约束不得自行决策，故未修改任何代码 |
| T-003 | validated | cd services/api && pytest tests/test_guardian.py tests/test_parents.py | pass | - |
| T-004 | validated | cd services/api && pytest | pass | - |
| T-005 | validated | cd services/api && pytest tests/test_admin_governance.py | pass | - |
| T-006 | validated | pnpm --filter @xueban/desktop test && pnpm --filter @xueban/desktop typecheck; pnpm --filter @xueban/mobile test && pnpm --filter @xueban/mobile typecheck | pass | - |
| T-007 | validated | cd services/api && pytest tests/test_safety.py | pass | - |
| T-008 | validated | cd services/api && pytest tests/test_coach.py | pass | - |
| T-009 | validated | cd services/api && pytest tests/test_sync.py | pass | - |
| T-010 | validated | cd services/api && pytest tests/test_auth.py tests/test_auth_extra.py | pass | - |
| T-011 | validated | cd services/api && pytest tests/test_library_cards.py | pass | - |
| T-012 | validated | cd services/api && ruff check . && pytest tests/test_auth.py | pass | - |
| T-013 | validated | cd services/api && mypy --strict app && pytest | pass | - |
| T-014 | validated | pnpm --filter @xueban/core test | pass | - |
| T-015 | validated | pnpm --filter @xueban/desktop test && pnpm --filter @xueban/desktop typecheck | pass | - |
| T-016 | blocked | pnpm --filter @xueban/desktop build && pnpm test:e2e:desktop | fail | build 通过；E2E 28 passed / 1 flaky / 2 failed，exit 1。两条失败（guardian.spec.ts:89 与 :119）根因与 CSP 无关：两用例经 API 绑定孩子时仍用 T-001 改造前的请求体（`{child_phone}`，无 `sms_code`），绑定返回 422 后 `expect(bind.ok()).toBe(true)` 失败。`apps/desktop/e2e/guardian.spec.ts` 不在任何任务的 allowed_files/allowed_extra_paths 内，按硬约束不得修改；CSP 修改本身无法回退（指令明确「不得回退为 null」）。CSP 对 E2E 无影响（E2E 跑 vite preview 浏览器，不读 tauri.conf.json；讲解页相关 28 项用例全部通过） |

## 当前游标
- 当前层级: 完成
- 当前任务: -
