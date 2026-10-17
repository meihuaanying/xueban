/**
 * 答题音效测试（§4.1「答对撒花/音效」）。
 *
 * 这一层的重点不是「声音好不好听」（听不出来），而是两条硬契约：
 * 1. 没有音频能力时必须**静默**——不能因为音效把答题流程带崩；
 * 2. 有音频能力时确实排了三个音、且都在用户手势后的当前时间轴上。
 *
 * 用 `vi.resetModules()` + 动态 `import()` 拿全新模块实例：模块内有一个共享的
 * `AudioContext` 单例，不重置的话第一个用例的假上下文会被后面的用例继承，
 * 断言就会串味。
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

interface FakeOscillator {
  type: string;
  frequency: { setValueAtTime: ReturnType<typeof vi.fn> };
  connect: ReturnType<typeof vi.fn>;
  start: ReturnType<typeof vi.fn>;
  stop: ReturnType<typeof vi.fn>;
}

interface FakeGain {
  gain: {
    setValueAtTime: ReturnType<typeof vi.fn>;
    exponentialRampToValueAtTime: ReturnType<typeof vi.fn>;
  };
  connect: ReturnType<typeof vi.fn>;
}

function makeFakeContext() {
  const oscillators: FakeOscillator[] = [];
  const gains: FakeGain[] = [];
  const resume = vi.fn(() => Promise.resolve());

  const context = {
    state: "running" as string,
    currentTime: 10,
    destination: { name: "destination" },
    resume,
    createOscillator: () => {
      const oscillator: FakeOscillator = {
        type: "",
        frequency: { setValueAtTime: vi.fn() },
        connect: vi.fn(),
        start: vi.fn(),
        stop: vi.fn(),
      };
      oscillators.push(oscillator);
      return oscillator;
    },
    createGain: () => {
      const gain: FakeGain = {
        gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
        connect: vi.fn(),
      };
      gains.push(gain);
      return gain;
    },
  };

  return { context, oscillators, gains, resume };
}

async function loadModule() {
  vi.resetModules();
  return import("../learning/sound");
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("playCorrectChime", () => {
  it("没有 AudioContext 时静默返回，不抛错", async () => {
    const { playCorrectChime } = await loadModule();
    expect(() => playCorrectChime()).not.toThrow();
  });

  it("有 AudioContext 时排出三个音，且都接了包络与输出", async () => {
    const { context, oscillators, gains } = makeFakeContext();
    vi.stubGlobal("AudioContext", vi.fn(() => context));
    const { playCorrectChime } = await loadModule();

    playCorrectChime();

    expect(oscillators).toHaveLength(3);
    expect(gains).toHaveLength(3);
    for (const oscillator of oscillators) {
      expect(oscillator.type).toBe("sine");
      expect(oscillator.start).toHaveBeenCalledTimes(1);
      expect(oscillator.stop).toHaveBeenCalledTimes(1);
      expect(oscillator.connect).toHaveBeenCalledTimes(1);
    }
    // 音量必须被压低：孩子常把系统音量开得很大，正反馈不该炸耳朵
    for (const gain of gains) {
      const peaks = gain.gain.exponentialRampToValueAtTime.mock.calls.map((call) => call[0]);
      expect(Math.max(...peaks)).toBeLessThanOrEqual(0.1);
    }
  });

  it("音高逐音上行（大三和弦分解），不是同一个音重复三遍", async () => {
    const { context, oscillators } = makeFakeContext();
    vi.stubGlobal("AudioContext", vi.fn(() => context));
    const { playCorrectChime } = await loadModule();

    playCorrectChime();

    const pitches = oscillators.map(
      (oscillator) => oscillator.frequency.setValueAtTime.mock.calls[0]?.[0] as number,
    );
    expect(pitches).toHaveLength(3);
    expect(pitches[0]).toBeLessThan(pitches[1] as number);
    expect(pitches[1]).toBeLessThan(pitches[2] as number);
  });

  it("上下文被挂起时先 resume（自动播放策略）", async () => {
    const { context, resume } = makeFakeContext();
    context.state = "suspended";
    vi.stubGlobal("AudioContext", vi.fn(() => context));
    const { playCorrectChime } = await loadModule();

    playCorrectChime();

    expect(resume).toHaveBeenCalledTimes(1);
  });

  it("构造 AudioContext 就抛错时也不把答题带崩", async () => {
    vi.stubGlobal(
      "AudioContext",
      vi.fn(() => {
        throw new Error("no audio device");
      }),
    );
    const { playCorrectChime } = await loadModule();
    expect(() => playCorrectChime()).not.toThrow();
  });

  it("共享上下文：连续两次调用只建一个 AudioContext", async () => {
    const { context } = makeFakeContext();
    const ctor = vi.fn(() => context);
    vi.stubGlobal("AudioContext", ctor);
    const { playCorrectChime } = await loadModule();

    playCorrectChime();
    playCorrectChime();

    // 浏览器对同时存在的 AudioContext 数量有上限，每题新建会很快耗尽
    expect(ctor).toHaveBeenCalledTimes(1);
  });
});
