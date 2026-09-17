/** 多端同步（T9.1 / F-39）：轮询版本号，变化时通知页面刷新。 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Badge } from "@xueban/ui";

import { api, type SyncState } from "@/lib/api";

const POLL_INTERVAL_MS = 5_000;

interface SyncContextValue {
  version: string | null;
  state: SyncState | null;
  /** 手动触发一次同步检查（页面操作后调用） */
  refresh: () => Promise<void>;
}

const SyncContext = createContext<SyncContextValue>({
  version: null,
  state: null,
  refresh: async () => undefined,
});

export function useSync(): SyncContextValue {
  return useContext(SyncContext);
}

export function SyncProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SyncState | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const next = await api.syncState();
      if (mounted.current) setState(next);
    } catch {
      // 同步失败不打断使用（下一次轮询重试）
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => {
      mounted.current = false;
      clearInterval(timer);
    };
  }, [refresh]);

  const value = useMemo(
    () => ({ version: state?.version ?? null, state, refresh }),
    [state, refresh],
  );
  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

/** 顶栏同步指示器。 */
export function SyncIndicator() {
  const { state } = useSync();
  if (!state) return null;
  return (
    <span className="flex items-center gap-2 text-xs text-muted-foreground" data-testid="sync-indicator">
      <Badge variant="outline">已同步</Badge>
      <span>
        今日 {state.summary.completed_today}/{state.summary.total_today} · 连续 {state.summary.streak_days} 天
      </span>
    </span>
  );
}
