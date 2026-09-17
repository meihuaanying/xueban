# 应用商店截图获取指引（B-009 待补）

> 当前状态：⬜ 未采集（本机无 Android SDK/模拟器/真机与 Maestro）。
> 目标：每商店 3~8 张手机截图（1080×1920 或同比例竖屏），内容与 `../store-listing.md` §7 顺序一致。

## 1. 采集环境（二选一）

### A. 本地模拟器（有 Android SDK 时）

```bash
cd apps/mobile
npx expo start                                  # 另开终端
maestro test maestro/01-register-diagnosis-plan.yaml   # 自动走通核心旅程
# 在关键页面使用模拟器截图（adb exec-out screencap -p > shots/01.png）
adb shell screencap -p /sdcard/01.png && adb pull /sdcard/01.png screenshots/01-diagnosis.png
```

### B. CI 模拟器（B-009 的 `mobile-apk` 作业扩展）

在 `.github/workflows/ci.yml` 的 `mobile-apk` 作业中，Maestro 流程后追加：

```yaml
- name: 采集商店截图
  uses: reactivecircus/android-emulator-runner@v2
  with:
    api-level: 34
    script: |
      maestro test apps/mobile/maestro/01-register-diagnosis-plan.yaml
      adb exec-out screencap -p > apps/mobile/screenshots/01-diag.png
      # ……按页面顺序继续截图并上传 artifact
```

## 2. 截图清单（按顺序）

| # | 页面 | 要点 | 文件名 |
| --- | --- | --- | --- |
| 1 | 学情诊断结果 | 雷达图/薄弱点，隐藏个人信息 | `01-diagnosis.png` |
| 2 | 每日任务卡 | 任务拆解与打卡 | `02-daily-plan.png` |
| 3 | 分层讲解 | 第 1 层「思路提示」（体现不直接给答案） | `03-tutor-level1.png` |
| 4 | 错题本 | 五类错因分组 | `04-mistakes.png` |
| 5 | 周报/家长看板 | 学习趋势 | `05-weekly-report.png` |
| 6 | 暗色模式 | 任一核心页暗色 | `06-dark.png` |

采集后放入本目录并在 `../README.md` 材料表勾选。

## 3. 合规注意

- 截图中不得出现真实未成年人姓名/手机号/头像；演示账号使用测试数据。
- 不得出现「全网第一」「保过」等违规宣传词。
- 华为/OPPO 要求截图不得含其他渠道水印。
