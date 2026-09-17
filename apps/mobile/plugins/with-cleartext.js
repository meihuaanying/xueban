/**
 * 本地 config plugin：仅在显式设置 EXPO_PUBLIC_ALLOW_CLEARTEXT=true 时，
 * 向主 AndroidManifest 注入 android:usesCleartextTraffic="true"。
 *
 * 用途：CI 的 Maestro 联调（模拟器经 http://10.0.2.2:8000 访问本机 API）。
 * 生产构建（HTTPS）默认不开启，避免削弱 TLS 策略。
 */
// Expo config plugin 以 CommonJS 加载（Node 运行时），此处 require 为规范用法
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { withAndroidManifest } = require("@expo/config-plugins");

module.exports = function withCleartext(config) {
  if (process.env.EXPO_PUBLIC_ALLOW_CLEARTEXT !== "true") {
    return config;
  }
  return withAndroidManifest(config, (result) => {
    const application = result.modResults.manifest.application?.[0];
    if (application) {
      application.$["android:usesCleartextTraffic"] = "true";
    }
    return result;
  });
};
