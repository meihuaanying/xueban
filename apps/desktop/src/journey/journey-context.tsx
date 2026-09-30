/**
 * 旅程状态机运行时（REBUILD §7 P0）：阶段推进 + 学段主题联动。
 * 状态持久化到 localStorage，刷新后回到上次所在阶段。
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  GRADE_BANDS,
  STAGES,
  canEnter,
  defaultJourneyState,
  nextStage as computeNext,
  stagePath,
  type GradeBand,
  type JourneyStage,
  type JourneyState,
} from "./stages";

const STATE_KEY = "xueban.journey";
const THEME_KEY = "xueban.theme";
const MODE_KEY = "xueban.mode";
const BAND_KEY = "xueban.gradeBand";

export type ThemeName = "focus" | "kids";

interface JourneyContextValue {
  state: JourneyState;
  stage: JourneyStage;
  theme: ThemeName;
  mode: "light" | "dark";
  band: GradeBand | null;
  setBand: (band: GradeBand) => void;
  goTo: (stage: JourneyStage) => void;
  advance: () => JourneyStage;
  mark: (patch: Partial<JourneyState>) => void;
  setTheme: (theme: ThemeName) => void;
  setMode: (mode: "light" | "dark") => void;
  canEnter: (stage: JourneyStage) => boolean;
  pathOf: (stage: JourneyStage) => string;
}

const JourneyContext = createContext<JourneyContextValue | null>(null);

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? ({ ...fallback, ...(JSON.parse(raw) as object) } as T) : fallback;
  } catch {
    return fallback;
  }
}

function readString(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeString(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* 隐私模式下 localStorage 不可用，降级为内存态 */
  }
}

/** 把主题与深浅模式写到 <html>，供 CSS 皮肤块消费 */
function applySkin(theme: ThemeName, mode: "light" | "dark"): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.dataset.mode = mode;
  root.classList.toggle("dark", mode === "dark");
}

export function JourneyProvider({
  children,
  initial,
}: {
  children: ReactNode;
  initial?: Partial<JourneyState>;
}) {
  const [state, setState] = useState<JourneyState>(() =>
    defaultJourneyState({ ...readJson<Partial<JourneyState>>(STATE_KEY, {}), ...initial }),
  );
  const [band, setBandState] = useState<GradeBand | null>(() => {
    const raw = readString(BAND_KEY);
    return raw && raw in GRADE_BANDS ? (raw as GradeBand) : null;
  });
  const [theme, setThemeState] = useState<ThemeName>(() => {
    const raw = readString(THEME_KEY);
    return raw === "kids" ? "kids" : "focus";
  });
  const [mode, setModeState] = useState<"light" | "dark">(() => {
    const raw = readString(MODE_KEY);
    return raw === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    applySkin(theme, mode);
  }, [mode, theme]);

  useEffect(() => {
    writeString(STATE_KEY, JSON.stringify(state));
  }, [state]);

  const goTo = useCallback((stage: JourneyStage) => {
    setState((prev) => (canEnter(stage, prev) ? { ...prev, stage } : prev));
  }, []);

  const mark = useCallback((patch: Partial<JourneyState>) => {
    setState((prev) => ({ ...prev, ...patch }));
  }, []);

  const advance = useCallback((): JourneyStage => {
    let target: JourneyStage = "today";
    setState((prev) => {
      target = computeNext(prev);
      return { ...prev, stage: target };
    });
    return target;
  }, []);

  const setBand = useCallback((next: GradeBand) => {
    setBandState(next);
    writeString(BAND_KEY, next);
    // onboarding 选学段 → 自动切主题（小学低年级走儿童皮肤）
    setThemeState(GRADE_BANDS[next].theme);
    writeString(THEME_KEY, GRADE_BANDS[next].theme);
    setState((prev) => ({ ...prev, hasProfile: true }));
  }, []);

  const setTheme = useCallback((next: ThemeName) => {
    setThemeState(next);
    writeString(THEME_KEY, next);
  }, []);

  const setMode = useCallback((next: "light" | "dark") => {
    setModeState(next);
    writeString(MODE_KEY, next);
  }, []);

  const value = useMemo<JourneyContextValue>(
    () => ({
      state,
      stage: state.stage,
      theme,
      mode,
      band,
      setBand,
      goTo,
      advance,
      mark,
      setTheme,
      setMode,
      canEnter: (target: JourneyStage) => canEnter(target, state),
      pathOf: stagePath,
    }),
    [advance, band, goTo, mark, mode, setBand, setMode, setTheme, state, theme],
  );

  return <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>;
}

export function useJourney(): JourneyContextValue {
  const ctx = useContext(JourneyContext);
  if (!ctx) throw new Error("useJourney 必须在 JourneyProvider 内使用");
  return ctx;
}

export { STAGES };
