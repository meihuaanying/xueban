#!/usr/bin/env bash
# Maestro CI 运行脚本（GitHub Actions android-emulator-runner 调用）
# - 启动本机 API（mock LLM）并用 adb reverse 映射到模拟器 127.0.0.1:8000
# - 失败时抓取截图 / logcat / API 日志，供上传诊断
set -uo pipefail

ARTIFACTS="/tmp/maestro-artifacts"
mkdir -p "$ARTIFACTS"

# 退出时清理后台进程，避免 detach 的 API/工具进程阻止 job 结束
cleanup() {
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "maestro" 2>/dev/null || true
}
trap cleanup EXIT

echo "== 安装 Maestro =="
curl -Ls https://get.maestro.mobile.dev | bash
export PATH="$PATH:$HOME/.maestro/bin"
maestro --version

echo "== 启动 API（mock LLM） =="
(cd services/api && LLM_PROVIDER=mock setsid nohup python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &)
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/healthz > /dev/null; then
    echo "API 就绪"
    break
  fi
  sleep 2
done

echo "== 等待设备并配置 =="
adb wait-for-device
adb reverse tcp:8000 tcp:8000
adb shell settings put global hide_error_dialogs 1
adb shell settings put secure anr_show_background 0
# 已连接硬件键盘时不弹出软键盘，避免遮挡表单（Maestro 用 adb 输入文本）
adb shell settings put secure show_ime_with_hard_keyboard 0
adb install -r apps/mobile/android/app/build/outputs/apk/release/app-release.apk

PHONE="139$(date +%N | head -c 8)"
echo "测试手机号: $PHONE"

capture() {
  local tag="$1"
  adb exec-out screencap -p > "$ARTIFACTS/fail-$tag.png" 2>/dev/null || true
  adb logcat -d -t 1200 > "$ARTIFACTS/logcat-$tag.txt" 2>/dev/null || true
  tail -200 /tmp/api.log > "$ARTIFACTS/api-$tag.log" 2>/dev/null || true
}

status=0
timeout 1500 maestro test apps/mobile/maestro/01-register-diagnosis-plan.yaml -e PHONE="$PHONE" || status=$?
if [ "$status" -ne 0 ]; then
  echo "流程 01 失败（exit=$status），抓取诊断产物"
  capture 01
  exit "$status"
fi

timeout 1200 maestro test apps/mobile/maestro/02-practice-mistake-loop.yaml -e PHONE="$PHONE" || status=$?
if [ "$status" -ne 0 ]; then
  echo "流程 02 失败（exit=$status），抓取诊断产物"
  capture 02
  exit "$status"
fi

echo "Maestro 两条核心旅程全部通过"
