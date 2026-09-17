# CI 说明

GitHub Actions 只识别仓库根目录的 `.github/workflows/`，因此实际工作流文件位于
`../.github/workflows/ci.yml`，本目录仅作为占位与说明（与规格书 §4 目录结构对应）。

工作流包含五个作业：

| 作业 | 内容 |
|------|------|
| web | 共享包测试 + web 的 lint / typecheck / test / build |
| desktop | desktop 的 lint / typecheck / test / build（tauri 打包在 M5 加入） |
| mobile | mobile 的 lint / typecheck / test / build（EAS/APK 在 M6 加入） |
| api | ruff + mypy --strict + pytest |
| compose | `docker compose config -q` 校验编排文件 |
