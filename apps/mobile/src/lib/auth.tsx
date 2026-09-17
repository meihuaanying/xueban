/** 登录态：SecureStore 持久化（T6.1），无 SecureStore 环境回退内存。 */

import * as SecureStore from "expo-secure-store";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api, setAccessToken, type TokenPair, type UserProfile } from "./api";

const ACCESS_KEY = "xueban.mobile.access_token";
const REFRESH_KEY = "xueban.mobile.refresh_token";

async function saveTokens(pair: TokenPair): Promise<void> {
  try {
    await SecureStore.setItemAsync(ACCESS_KEY, pair.access_token);
    await SecureStore.setItemAsync(REFRESH_KEY, pair.refresh_token);
  } catch {
    // 测试/Web 环境无 SecureStore
  }
}

async function loadTokens(): Promise<{ accessToken: string; refreshToken: string } | null> {
  try {
    const accessToken = await SecureStore.getItemAsync(ACCESS_KEY);
    if (!accessToken) return null;
    const refreshToken = (await SecureStore.getItemAsync(REFRESH_KEY)) ?? "";
    return { accessToken, refreshToken };
  } catch {
    return null;
  }
}

async function clearTokens(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(ACCESS_KEY);
    await SecureStore.deleteItemAsync(REFRESH_KEY);
  } catch {
    // 忽略
  }
}

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: UserProfile | null;
  login: (phone: string, password: string) => Promise<void>;
  register: (phone: string, password: string, nickname?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tokens = await loadTokens();
      if (!tokens) {
        if (!cancelled) setStatus("anonymous");
        return;
      }
      setAccessToken(tokens.accessToken);
      try {
        const profile = await api.me();
        if (!cancelled) {
          setUser(profile);
          setStatus("authenticated");
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) await clearTokens();
        setAccessToken(null);
        if (!cancelled) setStatus("anonymous");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const apply = useCallback(async (pair: TokenPair) => {
    setAccessToken(pair.access_token);
    await saveTokens(pair);
    setUser(await api.me());
    setStatus("authenticated");
  }, []);

  const login = useCallback(
    async (phone: string, password: string) => {
      await apply(await api.login({ phone, password }));
    },
    [apply],
  );

  const register = useCallback(
    async (phone: string, password: string, nickname?: string) => {
      await apply(await api.register({ phone, password, nickname }));
    },
    [apply],
  );

  const logout = useCallback(async () => {
    await clearTokens();
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return context;
}
