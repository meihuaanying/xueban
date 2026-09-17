/** 离线兜底队列（T9.2）：弱网/断网时缓存作答，恢复后自动补齐（幂等重放不重复）。 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Network from "expo-network";

import { api } from "./api";

const STORAGE_KEY = "xueban.mobile.offline_answers";

export interface PendingAnswer {
  client_event_id: string;
  question_id: string;
  answer: string;
  source: "practice" | "repractice" | "variant";
  queued_at: string;
}

type StorageLike = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
};

const defaultStorage: StorageLike = {
  getItem: (key) => AsyncStorage.getItem(key),
  setItem: (key, value) => AsyncStorage.setItem(key, value),
};

let storage: StorageLike = defaultStorage;

/** 测试注入存储实现。 */
export function __setStorageForTests(next: StorageLike | null): void {
  storage = next ?? defaultStorage;
}

export function newEventId(): string {
  return `off-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function loadQueue(): Promise<PendingAnswer[]> {
  try {
    const raw = await storage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as PendingAnswer[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function saveQueue(queue: PendingAnswer[]): Promise<void> {
  try {
    await storage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch {
    // 存储失败不影响主流程
  }
}

export async function enqueueAnswer(answer: Omit<PendingAnswer, "queued_at">): Promise<void> {
  const queue = await loadQueue();
  if (queue.some((item) => item.client_event_id === answer.client_event_id)) return;
  queue.push({ ...answer, queued_at: new Date().toISOString() });
  await saveQueue(queue);
}

export async function isOnline(): Promise<boolean> {
  try {
    const state = await Network.getNetworkStateAsync();
    return Boolean(state.isConnected) && state.isInternetReachable !== false;
  } catch {
    return true; // 无法判断时按在线处理，交给请求失败回退
  }
}

export interface FlushResult {
  sent: number;
  remaining: number;
}

/** 补齐离线队列：逐条提交（幂等键去重），失败保留待下次。 */
export async function flushQueue(): Promise<FlushResult> {
  const queue = await loadQueue();
  if (queue.length === 0) return { sent: 0, remaining: 0 };
  if (!(await isOnline())) return { sent: 0, remaining: queue.length };

  const remaining: PendingAnswer[] = [];
  let sent = 0;
  for (const item of queue) {
    try {
      await api.answerPractice({
        question_id: item.question_id,
        answer: item.answer,
        source: item.source,
        client_event_id: item.client_event_id,
      });
      sent += 1;
    } catch {
      remaining.push(item);
    }
  }
  await saveQueue(remaining);
  return { sent, remaining: remaining.length };
}

/** 网络恢复监听：接入应用启动与前台切换。 */
export async function flushOnReconnect(): Promise<FlushResult> {
  return flushQueue();
}
