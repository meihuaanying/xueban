# 学伴（XueBan）合规清单（T11 交付件）

> 依据：规格书 §8「合规提示」与 §10「非功能需求」。
> 说明：以下分「代码侧已具备」与「人工办理」两类；人工事项逐项列出责任与闭环证据位置，实际办理由业务方执行。

## 1. 生成式 AI 合规

### 1.1 生成式 AI 服务备案 / 算法备案咨询（人工）

- [ ] 确认模型来源：当前通过自建 LiteLLM 网关接入第三方已备案大模型（DeepSeek / 通义 / 智谱），保留供应商备案材料与合同。
- [ ] 按《生成式人工智能服务管理暂行办法》完成**服务备案评估**；面向公众提供生成式功能的，按规定完成算法备案或安全评估。
- [ ] 留存安全评估报告、内容审核机制说明、应急处置流程（可引用本仓库：`docs/OPS.md` 故障处置、`app/services/safety_service.py` 内容安全）。
- 责任人：`__________`（业务方）｜预计完成：`__________`

### 1.2 内容安全（代码侧已具备，厂商接入为人工）

- [x] 内容安全服务抽象 `safety_service`（`SAFETY_PROVIDER=mock|yidun`，失败降级本地词表，不阻塞主流程）。
- [x] 未成年人账号默认最严过滤档（`is_k12` 标记 + 过滤策略）。
- [x] 对话留痕：`chat_messages` 全量落库，家长端可查（F-44）。
- [ ] 接入真实内容安全厂商（网易易盾/数美）：填写 `YIDUN_SECRET_ID/KEY`，切 `SAFETY_PROVIDER=yidun`，用 20 条样本回归。

### 1.3 心理安全红线（代码侧已具备）

- [x] F-34 规则层危机识别 + 固定求助话术 + 专业热线资源（`coach_service`）；10 条红线用例 0 漏判（`tests/test_coach.py`、`evals/crisis_mock_api.yaml`）。
- [x] 明确不扮演心理咨询师（话术含免责声明）。
- [ ] 按运营地区复核危机求助资源清单（热线号码/平台）并每年更新。

## 2. 个人信息保护（PIPL / 儿童个人信息规范）

| 要求 | 现状 | 证据/位置 |
| --- | --- | --- |
| 隐私政策公示 | ✅ 官网 `/privacy`（更新日期 2026-09-15），随包附件 `release-assets/privacy-policy.md` | `apps/web/src/app/privacy/page.tsx` |
| 未成年人保护声明 | ✅ 官网 `/minor-protection`，随包附件 | `apps/web/src/app/minor-protection/page.tsx` |
| 监护人同意 | ✅ 注册/订阅/敏感功能需监护人同意（文案与流程） | 注册页、`docs/verification/M4/M7` |
| 数据最小化 | ✅ 仅手机号+学习数据；权限最小化（相机/麦克风/网络） | `release-assets/store-listing.md` §5 |
| 敏感字段加密存储 | ✅ 密码 bcrypt 单向哈希；日志脱敏（access 日志不含手机号/正文） | `app/services/security.py`、`app/middleware.py` |
| 数据删除权 | ✅ 注销接口 `POST /v1/auth/account/delete`（匿名化+停用+吊销令牌）；物理删除脚本 `scripts/purge_deleted_accounts.py`（默认 30 天，`--dry-run` 演练） | `tests/test_account_deletion.py`（4 例） |
| 数据保留期限 | ✅ 对话记录保留 12 个月（可配置清理周期）；学情数据长期保留；注销后 30 天物理删除 | `docs/OPS.md` §2、purge 脚本 |
| 数据境内存储 | ✅ 生产部署于境内服务器；跨境外传前依法评估并单独告知 | `docs/DEPLOY.md` §1 |
| 个人信息主体权利 | ✅ 查询/更正（账号与画像页）、删除（错题/文档/注销）、撤回同意（设置） | 各端功能 + 注销接口 |

## 3. 知识产权与资质（人工）

- [ ] 软件著作权登记（材料与提示见 `release-assets/compliance-checklist.md` §1）。
- [ ] 域名 ICP 备案并展示备案号（官网页脚）。
- [x] 题库版权纪律：仅使用自建/开放授权题目，禁止爬取，后台记录每题来源（`import_service` 来源字段）。
- [ ] 商标注册评估（“学伴”/图形商标，第 9/41/42 类建议）。

## 4. 支付与消费者权益（如上线付费）

- [ ] 微信支付/支付宝商户号与协议（当前 `PAYMENT_PROVIDER=mock`）。
- [x] 订阅状态机与退订/到期逻辑（`billing_service`，mock 收银台）。
- [x] 未成年人默认关闭自动续费入口；价格页明示（`/pricing`）。
- [ ] 各安卓商店虚拟商品分成政策核对（安卓渠道内购规则）。

## 5. 安全与审计

- [x] 漏洞扫描：pip-audit / pnpm audit / detect-secrets / trufflehog / ZAP baseline（0 High）——证据 `docs/verification/M10_2026-09-16*`。
- [x] 访问控制：JWT（access 15min / refresh 30d 轮换）、角色 RBAC、越权用例（家长不可看他人孩子数据）。
- [x] 管理员操作审计：`audit_logs` 表（关键操作留痕）。
- [ ] 每月安全扫描例行化（`docs/OPS.md` §6 已列命令）。

## 6. 交付物索引

| 文档 | 用途 |
| --- | --- |
| `docs/DEPLOY.md` | 部署手册（含安全基线与容量） |
| `docs/OPS.md` | 运维手册（备份/注销清理/模型切换/成本） |
| `docs/RELEASE.md` | 发布手册（桌面/安卓/EAS/回滚） |
| `release-assets/` | 上架材料（图标/文案/隐私政策/合规办理清单） |
| `docs/verification/FINAL.md` | 最终验收清单与证据链接 |

## 7. 风险登记（合规视角）

| 风险 | 触发信号 | 预案 |
| --- | --- | --- |
| 生成式 AI 备案未完成 | 监管问询/商店审核要求 | 按 §1.1 咨询代理机构；模型侧保留供应商备案材料 |
| 未成年人充值纠纷 | 客诉/退款 | 默认关闭自动续费；冷静期退款流程；监护人确认记录 |
| 内容安全漏拦截 | 用户举报 | 厂商服务切换 + 本地词表兜底 + 24h 复核承诺 |
| 数据删除未按期执行 | 演练发现 purge 未跑 | cron 值守 + restore_drill 同类演练纳入月度 |
