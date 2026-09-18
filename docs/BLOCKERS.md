# BLOCKERS（阻塞与替代验证记录）

> 依据规格书 §0.4：标准不可达时记录原因与替代方案，不允许静默降级。

## 当前阻塞项

### B-001 GitHub Actions 未实跑（M0）

- **状态**：✅ 已闭环（2026-09-18）
- **闭环证据**：远端 `https://github.com/meihuaanying/xueban` 已创建；首次全绿 run `35287350732`（main，8 作业全过：API / Web / Desktop×3 / Desktop E2E / Mobile / Mobile APK+Maestro / Compose）。期间修复了 9 类 CI 问题（跨平台服务容器、AppImage 图标、pytest 导入路径、被 .gitignore 遗漏的 `app/data` 源码、Maestro 驱动/ANR/键盘/网络等），并补齐证据日志入库。
- **说明**：`v0.1.0` 标签已推送，Release 工作流随出三平台安装包（见 B-008/B-009）。

### B-002 三端界面截图缺失（M0）

- **状态**：✅ 已闭环（2026-09-15，M4）
- **闭环证据**：Playwright E2E 自动截图写入 `docs/verification/assets/`：`m4-01-home.png`（首页）、`m4-02-primary-button.png`（主色按钮）、`m4-03-register.png`（注册页）、`m4-04-app-trial.png`（试用状态）；见 `docs/verification/M4_2026-09-15.md` §1。
- **说明**：Web 端视觉证据已补齐；桌面端与移动端页面级截图随 M5/M6 的 E2E 各自补充（不影响 M0 视觉一致结论：设计 tokens 同源）。

### B-003 外部模型/短信/支付 Key 待人工开通（M1）

- **状态**：进行中（不影响里程碑推进）
- **原因**：DeepSeek/通义/智谱/硅基流动 API Key、短信与支付商户需人工办理（规格书 §0.8）。
- **替代验证**：LLM 客户端以 MockTransport 单测覆盖重试/降级/错误映射；实测 LiteLLM fallback 链已触发并返回明确错误；Langfuse trace 实测连通；短信为 mock 提供商（开发环境返回 debug_code）；支付为 mock 收银台。
- **闭环动作**：开通后在 `.env` 填入密钥，重跑 `services/api/scripts/verify_langfuse_trace.py`（应出现真实模型响应）与 promptfoo 评测（M3 起）。

### B-004 语义检索评测待真实 bge-m3（M2）

- **状态**：进行中（不阻塞 M3）
- **原因**：T2.4 的 recall@5 需语义向量；硅基流动 Key 未开通（B-003），当前以 mock 词面向量完成流水线验证（recall@5=100%，题目带知识点前缀）。
- **替代验证**：真实供应商接口（bge-m3 / bge-reranker-v2-m3）已实现并有 HTTP 契约测试；检索/重排抽象切换仅改环境变量。
- **闭环动作**：`SILICONFLOW_API_KEY` 开通后设置 `EMBEDDING_PROVIDER=siliconflow RERANK_PROVIDER=siliconflow`，重跑 `scripts/eval_retrieval.py` 并回填真实语义召回指标。

### B-005 promptfoo 红线评测待真实模型 Key（M3 / T3.4）

- **状态**：进行中（阻塞 M3 出口门禁中的 promptfoo 项，不阻塞其余开发）
- **原因**：F-11 红线指标（50 条「首次响应直接给完整答案率」≤5%）需真实 LLM 输出评测；DeepSeek Key 未开通（B-003）。
- **替代验证**：三层提示状态机的跳层/回退/耗尽约束、第 1 层「禁给答案」提示词口径、SSE 流式链路、求助层级落库均已由 20 个自动化用例覆盖；评测配置（`evals/tutor.yaml`：答案泄露 not-contains + llm-rubric + 篇幅断言）与 50 条用例（题库导出）已就绪。
- **闭环动作**：Key 开通后执行 `npx promptfoo@latest eval -c evals/tutor.yaml`，报告存入 `docs/verification/` 并复核 ≤5% 阈值。

### B-006 FSRS 参考实现逐值对齐（M3 / F-19）

- **状态**：进行中（T10 评测阶段收口）
- **原因**：T3.6 采用「stability 驱动间隔」的 FSRS 简化移植（公式与系数已在代码与测试中固化），与 fsrs4anki 原版参数的逐值对齐需要参考实现数据集。
- **替代验证**：评分 1–4 的间隔表、状态迁移（learning/relearning/review）、lapses 与难度截断均由 16 个确定性单测锁定（误差为 0 于当前公式）。
- **闭环动作**：T10 引入 fsrs4anki 参考调度数据集，跑逐值对照并通过后再移除本条目。

### B-009 本机无 Android SDK / 模拟器 / Maestro（M6 / T6.8）

- **状态**：✅ 已闭环（2026-09-18，CI 实跑）
- **闭环证据**：CI `mobile-apk` 作业实跑通过（run `35287350732`）：`expo prebuild` + `gradlew assembleRelease` 构建 release APK（体积门禁 ≤80MB 通过，产物 `xueban-android-apk`）+ Android 30 模拟器（headless，`hide_error_dialogs`/硬件键盘/adb reverse）+ Maestro 两条核心旅程全绿（注册→诊断→规划→打卡；练习→错题→重练）。
- **顺带修复**：E2E 暴露「移动端练习填空题无法作答」的真实缺陷——已补 `TextField` 支持（`apps/mobile/src/screens/practice.tsx`），并由流程覆盖。
- **遗留**：暗色设备截图（B-014）与冷启动/体积实测数值待随模拟器产物回填；APK 冷启动可在后续工作中用 emulator 计时补充。

### B-010 移动端原生公式渲染未接入（M6 / T6.3）

- **状态**：进行中（M8 前补齐）
- **原因**：`react-native-math-view` 等原生 KaTeX 方案需要 `expo prebuild` 生成原生工程（本机无 Android SDK，见 B-009）。
- **替代验证**：`src/components/math-text.tsx` 对 `$...$`/`$$...$$` 分段渲染（行内/块级样式），组件测试覆盖公式片段可读性。
- **闭环动作**：prebuild 环境可用后安装原生公式渲染库并补充视觉快照；与 B-009 同步闭环。

### B-014 移动端暗色未做设备端视觉快照（M9 / T9.3）

- **状态**：进行中（随机型验证一并收口）
- **原因**：nativewind 暗色依赖设备外观与原生渲染，本机无模拟器/真机（B-009），无法产出设备截图。
- **替代验证**：`userInterfaceStyle: automatic` 已开启、`palette.cjs` 同时定义明暗语义色；官网与桌面暗色已有 E2E + axe 证据。
- **闭环动作**：CI 模拟器（B-009 的 mobile-apk 作业）就绪后补暗色截图与 Maestro 断言。

### B-015 pnpm audit 2 处 high：image-size（metro 构建链，无修复版本）（M10 / T10.3）

- **状态**：跟踪上游（不阻塞 M10；仅构建期依赖）
- **原因**：`image-size@1.x`（经 react-native → metro 引入）存在 GHSA-5p2g-fcmc-qvqq（2 high），上游暂无修复版本；强制 override 至 2.x 会导致 `expo export` 崩溃。
- **替代验证**：`pnpm audit --prod --registry=https://registry.npmjs.org/` 实测仅剩该 2 处；运行时产物不含该依赖（不进入 Web/桌面/API 产物）；已加 `glob/postcss/uuid` overrides 修复其余 5 处高危。
- **闭环动作**：跟踪 metro 升级至支持 image-size 2.x 后移除本条；每月安全扫描复核。

### B-016 trufflehog 镜像 Docker Hub 不可达（M10 / T10.3）

- **状态**：✅ 已闭环（2026-09-17）
- **原原因**：本机 `registry-1.docker.io` 不可达，无法拉取 trufflesecurity/trufflehog。
- **闭环证据**：改由 **ghcr.io/trufflesecurity/trufflehog:latest** 拉取成功，实测扫描 9713 chunks / 96.3 MB，`verified_secrets=0, unverified_secrets=0`（`docs/verification/M10_2026-09-16_trufflehog.jsonl`、`..._trufflehog.log`）。
- **说明**：此前以 `detect-secrets`（0 findings）作为替代验证已同步留存。

### B-017 k6 核心 API 压测 p95 未达 ≤300ms（本机共享 CPU 环境）（M10 / T10.2）

- **状态**：进行中（错误率门禁已达标；p95 门禁待生产硬件复测）
- **实测（5 分钟 200 VU，生产式拓扑 api×4 副本×4 worker + Caddy 轮询）**：905.6 rps、272,222 请求、**错误率 0.00%**（✓ ≤0.1%）、checks 100%；**p95=605ms（✗ ≤300ms）**、p90=479ms、p99=922ms。
- **已完成的优化（均已落入代码/配置）**：中间件由 BaseHTTPMiddleware 改为纯 ASGI（单请求 CPU 降约 30%）；连接池可配置 + `max_connections=200`；关闭 pool_pre_ping；Caddy 轮询负载均衡；纯 Linux 容器运行时（与生产一致）。
- **根因分析**：应用为 CPU 密集（实测约 11ms CPU/请求，源于 SQLAlchemy asyncpg/greenlet 协议栈 + 纯 Python 事件循环回调），本机为 16 逻辑核笔记本，且 k6 压测器 + PostgreSQL + Caddy + 13 个开发容器共驻同一台机器；扩容至 16 worker 后吞吐不再上升（900 rps 量级为当前共享 CPU 上限），属**环境算力受限**而非功能缺陷；LLM 流式首 token p95=18.16ms（mock，✓ ≤3s）证明异步链路无阻塞缺陷。
- **替代验证**：`infra/k6/core_api.js` + `infra/docker/docker-compose.loadtest.yml` 可一键复现；证据 `docs/verification/M10_2026-09-16_k6-core.log`、`..._k6-core-summary.json`。
- **闭环动作**：T11.1 生产栈部署到独立 VPS（建议 ≥16 vCPU 专用核）后原样复跑本脚本回填 p95；未达标前 T11.6 FINAL 中该项标注「待 VPS 复测」。

### B-012 真实 OCR 引擎（PaddleOCR/Pix2Text）未接入（M8 / T8.1）

- **状态**：进行中（接口与降级路径已就绪）
- **原因**：`services/ocr` 仍为占位服务（501）；真实 PaddleOCR + Pix2Text 引擎体积大、需独立镜像与模型权重，未在本机安装。
- **替代验证**：API 侧 OCR 客户端契约测试（MockTransport 断言请求/响应映射）、拍照搜题红线（响应不含答案）、手写步骤定位（数值零容忍）、失败即降级提示（读文件/网络/进程均在判题沙箱拦截，见 `test_ocr_flow.py` 9 例）。
- **闭环动作**：替换 `services/ocr` 为 PaddleOCR 镜像后设置 `OCR_PROVIDER=service`，用 10 张预置样本记录识别准确率与召回率，并把降级比例写入验证文档。

### B-013 口语评测供应商未接入（M8 / F-25）

- **状态**：进行中（mock 供应商契约完整）
- **原因**：音素级评测需第三方 API（如讯飞/腾讯云）与密钥。
- **替代验证**：`speaking_service`（mock）返回发音/流利度/完整度三维分数与纠错词列表，API 契约测试覆盖语速带与错误词；客户端展示结构已就绪。
- **闭环动作**：开通供应商后设置 `SPEAKING_PROVIDER` 并实现适配器；补一条真实样本回归用例。

### B-011 F-45 质量巡检的 LLM judge 通道待模型 Key（M7 / F-45）

- **状态**：进行中（不阻塞 M7 出口门禁）
- **原因**：F-45 要求「SymPy + judge 双通道」；当前 judge 通道为规则判定（解析必须引用正确答案），LLM 语义抽检需真实模型 Key（B-003）。
- **替代验证**：抽样→双通道校验→错题率→阈值告警的完整链路已由 2 个用例覆盖（含 webhook 投递 MockTransport 断言、未超阈值不告警）；每日 03:30 arq 定时任务已注册。
- **闭环动作**：Key 到位后接入 LLM judge 并重跑巡检用例与 promptfoo 全量评测（与 B-003/B-005 同批收口）。

### B-008 macOS/Linux 安装包与 Windows MSI 无法在本机产出（M5 / T5.8）

- **状态**：✅ 已闭环（2026-09-18，CI 实跑）
- **闭环证据**：CI desktop 矩阵实跑通过（run `35287350732` 产出可选产物；`v0.1.0` Release 工作流产出稳定资产：`XueBan-Setup-x64.exe`（NSIS）/ `XueBan-universal.dmg`（macOS 通用包）/ `XueBan-x86_64.AppImage` + `XueBan-amd64.deb`，附 SHA256SUMS）。本机 NSIS 冒烟与 24 条桌面 E2E 证据见 `M5_2026-09-16.md` 与 CI `desktop-e2e` 作业。
- **说明**：Windows 仍以 NSIS 交付（MSI/WiX 非必须）；mac/Linux 安装冒烟在对应 runner 构建成功，安装交互冒烟建议随正式分发抽查。

### B-007 本机 Lighthouse 退出码受 chrome-launcher 清理竞态影响（M4，仅本机环境）

- **状态**：✅ 已规避（不阻塞 M4；CI Linux 无此问题）
- **原因**：Windows 下 chrome-launcher 在审计完成后删除临时 profile 时偶发 `EPERM`（审计与断言结果本身正常，仅进程退出码受影响）；与 Edge/Chromium 均复现，属 launcher 在 Windows 的清理时序问题。
- **替代验证/规避**：本机改为「外部启动 Edge（`--remote-debugging-port=9222`）+ `lhci autorun --collect.settings.port=9222`」接入，不创建临时 profile，3 次运行与四项断言确定性通过（`docs/verification/M4_2026-09-15.logs.txt` §4）；另以 FCP≤1ms 负向对照证明断言机制生效。
- **闭环动作**：CI（ubuntu-latest）按规格书原命令 `lhci autorun` 执行，由 LHCI 自管浏览器；若未来 CI 也出现，升级 `@lhci/cli`/`chrome-launcher` 复验后删除本条。
