/**
 * 正反馈音效（§4.1「答对撒花/音效」）。
 *
 * 为什么用 Web Audio 现场合成而不是放一个音频文件：
 * 1. **不引资产**。一个 mp3/ogg 要么进 bundle（§8-9 的 1MB 红线本来就紧），要么走网络
 *    （桌面包离线打开就没有声音）。三个正弦音用几十行代码就够了。
 * 2. **不引依赖**。`AudioContext` 是浏览器自带的，`new Audio(...)` 反而要管文件路径、
 *    加载失败、跨域一堆事。
 * 3. **可控**。音量、音高、包络都在代码里，改起来不用重新导一遍音频。
 *
 * 只做「答对」一种音效，**刻意不做答错音**：§4.1 的原话是「正反馈动效」，而一个 7 岁
 * 孩子听到「叮——错了」的提示音，收到的信息是「你又错了」，不是「再试一次」。做错时的
 * 引导已经在文字与三层提示里，不需要再加一层声音去强调失败。
 *
 * 三条纪律，缺一不可：
 * - **失败静默**：没有 `AudioContext`、浏览器拒绝、设备静音，一律静默跳过，绝不抛错——
 *   音效是锦上添花，不能因为它打断答题。
 * - **只在用户手势后发声**：浏览器的自动播放策略要求 `AudioContext` 在用户交互后
 *   `resume()`，而本模块只在答题点击之后被调用，天然满足。
 * - **尊重用户的关闭开关**：由宿主（`useSoundPreference`）决定要不要调，本模块不管偏好。
 */

/** 答对的三音上行：C6 → E6 → G6（大三和弦分解，明亮但不刺耳）。 */
const CHIME_NOTES_HZ = [1046.5, 1318.5, 1568.0] as const;
/** 音符间隔。太快会糊成一声「嘀」，太慢就不像「做对了」的即时反馈。 */
const CHIME_STEP_SECONDS = 0.075;
/** 单音尾长：指数衰减到接近零。 */
const CHIME_TAIL_SECONDS = 0.26;
/** 峰值增益。刻意压低：孩子常把音量开得很大，正反馈不该炸耳朵。 */
const CHIME_PEAK_GAIN = 0.08;
/** 起音时间：短到听不出渐入，又足够避免爆音（爆音来自增益的瞬间跳变）。 */
const CHIME_ATTACK_SECONDS = 0.012;

type AudioContextConstructor = new () => AudioContext;

function audioContextConstructor(): AudioContextConstructor | null {
  if (typeof window === "undefined") return null;
  // 不用 `window as Window & {...}`：本项目的 DOM 类型里 `Window` 上没有
  // `AudioContext`（只有全局作用域上有），交叉类型反而把它擦掉了。
  // 这里直接按「可能存在的构造器」取，取不到就返回 null。
  const scoped = window as unknown as {
    AudioContext?: AudioContextConstructor;
    // Safari 至今仍只暴露 webkitAudioContext，必须两者都认
    webkitAudioContext?: AudioContextConstructor;
  };
  return scoped.AudioContext ?? scoped.webkitAudioContext ?? null;
}

/** 复用一个 `AudioContext`：浏览器对同时存在的实例数有上限，每题新建会很快耗尽。 */
let sharedContext: AudioContext | null = null;

function resolveContext(): AudioContext | null {
  const Constructor = audioContextConstructor();
  if (Constructor === null) return null;
  if (sharedContext === null || sharedContext.state === "closed") {
    try {
      sharedContext = new Constructor();
    } catch {
      // 某些环境（无音频设备、策略禁止）构造函数本身就会抛
      return null;
    }
  }
  return sharedContext;
}

/**
 * 播一次「答对了」的提示音。没有音频能力时静默返回。
 *
 * 调用点必须在用户手势之后（例如答题按钮的点击处理里），否则浏览器会挂起
 * `AudioContext`，声音不会响——这不是 bug，是自动播放策略。
 */
export function playCorrectChime(): void {
  const context = resolveContext();
  if (context === null) return;

  try {
    // 首次调用时上下文通常是 suspended 的，resume 是异步的；不等它也能排好音符，
    // 因为 currentTime 在恢复后会继续走。
    if (context.state === "suspended") void context.resume();

    const startAt = context.currentTime;
    CHIME_NOTES_HZ.forEach((frequency, index) => {
      const noteAt = startAt + index * CHIME_STEP_SECONDS;
      const oscillator = context.createOscillator();
      const envelope = context.createGain();

      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, noteAt);

      // 指数包络比线性更像真实乐器：起音快、尾巴自然收干。
      // exponentialRamp 的目标值不能是 0，所以用 0.0001 代替。
      envelope.gain.setValueAtTime(0.0001, noteAt);
      envelope.gain.exponentialRampToValueAtTime(
        CHIME_PEAK_GAIN,
        noteAt + CHIME_ATTACK_SECONDS,
      );
      envelope.gain.exponentialRampToValueAtTime(0.0001, noteAt + CHIME_TAIL_SECONDS);

      oscillator.connect(envelope);
      envelope.connect(context.destination);
      oscillator.start(noteAt);
      oscillator.stop(noteAt + CHIME_TAIL_SECONDS + 0.02);
    });
  } catch {
    // 设备/浏览器不给放就跳过。答题流程不该因为音效失败而中断。
  }
}
