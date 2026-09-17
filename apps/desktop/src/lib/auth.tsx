/** 登录态上下文：注册/登录/注销、用户信息与路由守卫。 */

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
import { clearTokens, loadTokens, saveTokens } from "./token-store";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: UserProfile | null;
  login: (phone: string, password: string) => Promise<void>;
  register: (phone: string, password: string, nickname?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<UserProfile | null>(null);

  const bootstrap = useCallback(async () => {
    const tokens = await loadTokens();
    if (!tokens) {
      setAccessToken(null);
      setStatus("anonymous");
      return;
    }
    setAccessToken(tokens.accessToken);
    try {
      const profile = await api.me();
      setUser(profile);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clearTokens();
      }
      setAccessToken(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const applyTokens = useCallback(async (pair: TokenPair) => {
    setAccessToken(pair.access_token);
    await saveTokens(pair);
    const profile = await api.me();
    setUser(profile);
    setStatus("authenticated");
  }, []);

  const login = useCallback(
    async (phone: string, password: string) => {
      const pair = await api.login({ phone, password });
      await applyTokens(pair);
    },
    [applyTokens],
  );

  const register = useCallback(
    async (phone: string, password: string, nickname?: string) => {
      const pair = await api.register({ phone, password, nickname });
      await applyTokens(pair);
    },
    [applyTokens],
  );

  const logout = useCallback(async () => {
    const tokens = await loadTokens();
    if (tokens?.refreshToken) {
      try {
        await api.logout(tokens.refreshToken);
      } catch {
        // 注销失败不影响本地退出
      }
    }
    await clearTokens();
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const refreshUser = useCallback(async () => {
    const profile = await api.me();
    setUser(profile);
  }, []);

  const value = useMemo(
    () => ({ status, user, login, register, logout, refreshUser }),
    [status, user, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return context;
}
