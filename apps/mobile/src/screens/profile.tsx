/** 我的 Tab（T6.7）：账号、订阅、行为画像、通知、拍照搜题与语音入口。 */

import { useCallback, useEffect, useState } from "react";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import * as Notifications from "expo-notifications";
import { Text, View } from "react-native";

import { Badge, Card, ErrorBlock, PrimaryButton, Screen } from "../components/ui";
import { ApiError, api, type BehaviorProfile, type SubscriptionState } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { LearnStackParamList } from "../navigation";

const PLAN_LABEL: Record<string, string> = { free: "免费版", trial: "试用中", pro: "专业版" };

export function ProfileScreen() {
  const { user, logout } = useAuth();
  const navigation = useNavigation<NativeStackNavigationProp<LearnStackParamList>>();
  const [subscription, setSubscription] = useState<SubscriptionState | null>(null);
  const [behavior, setBehavior] = useState<BehaviorProfile | null>(null);
  const [notifyEnabled, setNotifyEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [sub, profile] = await Promise.all([api.subscription(), api.behavior().catch(() => null)]);
      setSubscription(sub);
      setBehavior(profile);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载账号数据失败。");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function enableTrial() {
    setBusy(true);
    try {
      setSubscription(await api.startTrial());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "试用开通失败。");
    } finally {
      setBusy(false);
    }
  }

  async function toggleNotify() {
    try {
      const permission = await Notifications.requestPermissionsAsync();
      const granted = permission.granted ?? permission.status === "granted";
      setNotifyEnabled(granted);
      if (granted) {
        await Notifications.scheduleNotificationAsync({
          content: { title: "学伴复习提醒", body: "今天还有复习卡片没完成，去练习页看看吧。" },
          trigger: { type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL, seconds: 5 },
        });
      }
    } catch {
      setError("当前环境不支持本地通知（模拟器/Expo Go 受限）。");
    }
  }

  return (
    <Screen title="我的" hint="账号与订阅状态来自 API；推送通知为本机能力。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Card testID="profile-account">
        <Text className="font-semibold text-foreground">{user?.nickname ?? "学生账号"}</Text>
        <Text className="mt-1 text-sm text-muted">{user?.phone}</Text>
        <View className="mt-2 flex-row gap-2">
          <Badge label={user?.is_k12 ? "K12 保护" : "普通账号"} tone={user?.is_k12 ? "warning" : "default"} />
          <Badge label={user?.role === "parent" ? "家长" : "学生"} />
        </View>
      </Card>

      <Card testID="profile-subscription">
        <Text className="font-semibold text-foreground">订阅状态</Text>
        <Text className="mt-1 text-sm text-muted">
          当前套餐：{subscription ? (PLAN_LABEL[subscription.plan] ?? subscription.plan) : "—"}
        </Text>
        <Text className="text-sm text-muted">到期时间：{subscription?.expires_at ?? "—"}</Text>
        {subscription && subscription.plan === "free" && !subscription.trial_used ? (
          <View className="mt-2">
            <PrimaryButton label="开通 7 天试用" disabled={busy} onPress={() => void enableTrial()} testID="start-trial" />
          </View>
        ) : null}
      </Card>

      <Card testID="profile-behavior">
        <Text className="font-semibold text-foreground">行为画像</Text>
        <Text className="mt-1 text-sm text-muted">{behavior?.learning_style_label ?? "数据积累中"}</Text>
      </Card>

      <Card testID="profile-tools">
        <Text className="font-semibold text-foreground">学习工具</Text>
        <View className="mt-2 gap-2">
          <PrimaryButton label="拍照搜题（OCR mock 降级）" variant="outline" onPress={() => navigation.navigate("Camera")} />
          <PrimaryButton label="语音助手（录音上传）" variant="outline" onPress={() => navigation.navigate("Voice")} />
        </View>
      </Card>

      <Card testID="profile-notify">
        <Text className="font-semibold text-foreground">通知</Text>
        <Text className="mt-1 text-sm text-muted">
          复习到期与每日任务提醒：{notifyEnabled ? "已开启" : "未开启"}
        </Text>
        <View className="mt-2">
          <PrimaryButton
            label={notifyEnabled ? "重新安排提醒" : "开启通知"}
            variant="outline"
            onPress={() => void toggleNotify()}
            testID="toggle-notify"
          />
        </View>
      </Card>

      <Card>
        <Text className="text-sm text-muted">学伴移动端 v0.1.0（Expo SDK 53）</Text>
        <View className="mt-2">
          <PrimaryButton label="退出登录" variant="outline" onPress={() => void logout()} testID="logout" />
        </View>
      </Card>
    </Screen>
  );
}

/** 拍照搜题（T6.5）：选图/拍照 → MinIO 直传 → mock OCR → 引导练习（降级路径）。 */
export function CameraScreen() {
  const [status, setStatus] = useState<"idle" | "uploading" | "recognized">("idle");
  const [ocrText, setOcrText] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function pick(fromCamera: boolean) {
    setError(null);
    try {
      const permission = fromCamera
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        setError("未获得相机/相册权限，已降级为手动输入。");
        setOcrText("请手动输入题目文本");
        setStatus("recognized");
        return;
      }
      const result = fromCamera
        ? await ImagePicker.launchCameraAsync({ quality: 0.6 })
        : await ImagePicker.launchImageLibraryAsync({ quality: 0.6 });
      if (result.canceled || !result.assets[0]) return;

      setStatus("uploading");
      const asset = result.assets[0];
      const size = asset.fileSize ?? 1024;
      const presign = await api.presignUpload({
        filename: asset.fileName ?? "photo.jpg",
        content_type: asset.mimeType ?? "image/jpeg",
        size_bytes: size,
      });
      const form = new FormData();
      Object.entries(presign.fields).forEach(([key, value]) => form.append(key, value));
      form.append("file", {
        uri: asset.uri,
        name: asset.fileName ?? "photo.jpg",
        type: asset.mimeType ?? "image/jpeg",
      } as unknown as Blob);
      await fetch(presign.url, { method: "POST", body: form });

      // OCR 服务在 M8 接入；当前走 mock 识别降级路径
      setOcrText("（mock OCR）识别到：计算 18 × 5 = ？请选择正确答案。");
      setStatus("recognized");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "上传识别失败，已降级为手动输入。");
      setOcrText("请手动输入题目文本");
      setStatus("recognized");
    }
  }

  return (
    <Screen title="拍照搜题" hint="拍照/选图 → 上传 → 识别（M8 接入真实 OCR，当前为 mock 降级路径）。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}
      <Card testID="camera-card">
        <View className="gap-2">
          <PrimaryButton label="拍照" disabled={status === "uploading"} onPress={() => void pick(true)} testID="take-photo" />
          <PrimaryButton
            label="从相册选择"
            variant="outline"
            disabled={status === "uploading"}
            onPress={() => void pick(false)}
            testID="pick-photo"
          />
        </View>
        {status === "uploading" ? <Text className="mt-3 text-sm text-muted">上传并识别中…</Text> : null}
        {status === "recognized" ? (
          <View className="mt-3" testID="ocr-result">
            <Text className="text-sm font-medium text-foreground">识别结果</Text>
            <Text className="mt-1 text-sm text-muted">{ocrText}</Text>
          </View>
        ) : null}
      </Card>
    </Screen>
  );
}

/** 语音助手（T6.6）：录音 → 上传 → 识别结果（ASR 在 M8 接入，当前 mock）。 */
export function VoiceScreen() {
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function toggleRecording() {
    if (recording) {
      setRecording(false);
      setTranscript("（mock ASR）请帮我讲解一下一元二次方程的求根公式。");
      return;
    }
    setError(null);
    try {
      const permission = await import("expo-av").then((module) =>
        module.Audio.requestPermissionsAsync(),
      );
      if (!permission.granted) {
        setError("未获得麦克风权限，请到系统设置开启。");
        return;
      }
      setRecording(true);
    } catch {
      setError("当前环境不支持录音（模拟器/Expo Go 受限）。");
    }
  }

  return (
    <Screen title="语音助手" hint="录音 → 上传 → 识别（真实 ASR 供应商在 M8 接入，当前 mock 结果）。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}
      <Card testID="voice-card">
        <PrimaryButton
          label={recording ? "停止录音并识别" : "开始录音"}
          onPress={() => void toggleRecording()}
          testID="toggle-recording"
        />
        {transcript ? (
          <View className="mt-3" testID="voice-transcript">
            <Text className="text-sm font-medium text-foreground">识别结果</Text>
            <Text className="mt-1 text-sm text-muted">{transcript}</Text>
          </View>
        ) : null}
      </Card>
    </Screen>
  );
}
