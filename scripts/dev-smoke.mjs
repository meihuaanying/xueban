/**
 * 开发服务器冒烟脚本（M0 验收用，后续里程碑可复用）
 *
 * 依次启动 web / desktop / mobile 的开发服务器，轮询其可访问性后关闭。
 * 用法：node scripts/dev-smoke.mjs [web|desktop|mobile]
 */
import { execSync, spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const TARGETS = {
  web: {
    cwd: "apps/web",
    command: "pnpm exec next dev -p 3000",
    port: 3000,
    url: "http://127.0.0.1:3000",
    expect: "学伴",
    timeoutMs: 180_000,
  },
  desktop: {
    cwd: "apps/desktop",
    command: "pnpm exec vite --port 1420",
    port: 1420,
    url: "http://127.0.0.1:1420",
    expect: 'id="root"',
    timeoutMs: 60_000,
  },
  mobile: {
    cwd: "apps/mobile",
    command: "pnpm exec expo start --port 8081",
    port: 8081,
    url: "http://127.0.0.1:8081/status",
    expect: "packager-status:running",
    timeoutMs: 120_000,
  },
};

/** 结束占用指定端口的进程（Windows 使用 netstat+taskkill，类 Unix 使用 lsof） */
function killPort(port) {
  try {
    if (process.platform === "win32") {
      const output = execSync("netstat -ano", { encoding: "utf8" });
      const pids = new Set(
        output
          .split(/\r?\n/)
          .filter((line) => line.includes("LISTENING") && line.includes(`:${port} `))
          .map((line) => line.trim().split(/\s+/).pop())
          .filter(Boolean),
      );
      for (const pid of pids) {
        try {
          execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
        } catch {
          // 进程可能已退出
        }
      }
    } else {
      execSync(`fuser -k ${port}/tcp`, { stdio: "ignore" });
    }
  } catch {
    // 清理失败不阻塞主流程
  }
}

function run(name) {
  const target = TARGETS[name];
  if (!target) {
    throw new Error(`未知目标：${name}`);
  }
  killPort(target.port);

  return new Promise((resolve) => {
    let settled = false;
    let logs = "";
    const child = spawn(target.command, {
      cwd: target.cwd,
      shell: true,
      env: { ...process.env, CI: "1", BROWSER: "none", FORCE_COLOR: "0" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout.on("data", (chunk) => {
      logs += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      logs += chunk.toString();
    });

    const startedAt = Date.now();
    const finish = (ok, detail) => {
      if (settled) {
        return;
      }
      settled = true;
      killPort(target.port);
      try {
        child.kill();
      } catch {
        // 忽略
      }
      resolve({ name, ok, detail, logs });
    };

    // 总看门狗：超出目标超时后强制结束
    const watchdog = setTimeout(() => {
      finish(false, `超时 ${target.timeoutMs}ms 未就绪`);
    }, target.timeoutMs);
    watchdog.unref?.();

    const poll = async () => {
      if (settled) {
        return;
      }
      try {
        const response = await fetch(target.url);
        const body = await response.text();
        if (response.ok && body.includes(target.expect)) {
          finish(
            true,
            `${target.url} 返回 ${response.status}，命中 "${target.expect}"，用时 ${Math.round(
              (Date.now() - startedAt) / 1000,
            )}s`,
          );
          return;
        }
      } catch {
        // 服务器尚未就绪，继续轮询
      }
      await delay(2_000);
      if (!settled) {
        await poll();
      }
    };

    void poll();
  });
}

let failed = false;
for (const name of process.argv.slice(2).length > 0 ? process.argv.slice(2) : Object.keys(TARGETS)) {
  const result = await run(name);
  failed = failed || !result.ok;
  console.log(`[${result.ok ? "PASS" : "FAIL"}] ${name}: ${result.detail}`);
  if (!result.ok) {
    console.log(result.logs.slice(-2_000));
  }
}

process.exit(failed ? 1 : 0);
