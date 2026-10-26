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
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";

import {
  GRADE_BANDS,
  GRADE_LABELS,
  STAGES,
  SUBJECT_LABELS,
  SUBJECT_OPTIONS,
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
const GRADE_KEY = "xueban.grade";
const SUBJECT_KEY = "xueban.subject";

export type ThemeName = "focus" | "kids";

interface JourneyContextValue {
  state: JourneyState;
  stage: JourneyStage;
  theme: ThemeName;
  mode: "light" | "dark";
  band: GradeBand | null;
  setBand: (band: GradeBand) => void;
  /** 学段内选定的年级（grade1~12）；未选过时为学段默认年级 */
  grade: string | null;
  setGrade: (grade: string) => void;
  /** 当前学习的学科（广东九科按学段可切换）；未选过时为学段默认学科 */
  subject: string;
  setSubject: (subject: string) => void;
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
  // 年级跟随学段：切学段时若存的年级不属于新学段则回落到该学段默认年级。
  const [grade, setGradeState] = useState<string | null>(() => {
    const raw = readString(GRADE_KEY);
    if (raw && raw in GRADE_LABELS) return raw;
    return null;
  });
  // 学科跟随学段：切学段时若存的学科不属于新学段则回落到该学段默认学科。
  const [subject, setSubjectState] = useState<string>(() => {
    const raw = readString(SUBJECT_KEY);
    if (raw && raw in SUBJECT_LABELS) return raw;
    return GRADE_BANDS.primary.subject;
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

  // 旅程状态机驱动路由：stage 变化即跳转（挂载时不跳，避免覆盖用户直接访问的 URL）。
  // 用 effect 而不是 goTo 里直接 navigate，mark()/goTo() 同一批次的顺序才不会影响跳转目标。
  const navigate = useNavigate();
  const lastStage = useRef(state.stage);
  useEffect(() => {
    if (state.stage === lastStage.current) return;
    lastStage.current = state.stage;
    navigate(stagePath(state.stage));
  }, [navigate, state.stage]);

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
    // onboarding 选学段 → 自动切主题（小学走儿童皮肤）
    setThemeState(GRADE_BANDS[next].theme);
    writeString(THEME_KEY, GRADE_BANDS[next].theme);
    setState((prev) => ({ ...prev, hasProfile: true }));
    // 学段切换时年级同步回落（旧年级多半不属于新学段）
    setGradeState((prevGrade) => {
      if (prevGrade && GRADE_BANDS[next].grades.includes(prevGrade)) return prevGrade;
      writeString(GRADE_KEY, GRADE_BANDS[next].grade);
      return GRADE_BANDS[next].grade;
    });
    // 学科同步回落：小学只开语数英，初中/高中九科；旧学科不在新学段时回默认。
    setSubjectState((prevSubject) => {
      if (SUBJECT_OPTIONS[next].includes(prevSubject)) return prevSubject;
      writeString(SUBJECT_KEY, GRADE_BANDS[next].subject);
      return GRADE_BANDS[next].subject;
    });
  }, []);

  const setGrade = useCallback((next: string) => {
    setGradeState(next);
    writeString(GRADE_KEY, next);
  }, []);

  const setSubject = useCallback((next: string) => {
    setSubjectState(next);
    writeString(SUBJECT_KEY, next);
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
      grade,
      setGrade,
      subject,
      setSubject,
      goTo,
      advance,
      mark,
      setTheme,
      setMode,
      canEnter: (target: JourneyStage) => canEnter(target, state),
      pathOf: stagePath,
    }),
    [
      advance,
      band,
      goTo,
      grade,
      mark,
      mode,
      setBand,
      setGrade,
      setMode,
      setSubject,
      setTheme,
      state,
      subject,
      theme,
    ],
  );

  return <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>;
}

export function useJourney(): JourneyContextValue {
  const ctx = useContext(JourneyContext);
  if (!ctx) throw new Error("useJourney 必须在 JourneyProvider 内使用");
  return ctx;
}

export { STAGES };
