/**
 * P0 设计稿走查：桌面端完整骨架（REBUILD §4.1「学院派骨架」）
 * 左侧知识地图导航 + 主区内容流 + 掌握度为核心视觉语言；≥1280px 宽。
 * 本 story 渲染**单主题**（由 ?theme= 决定），以便看整页骨架比例。
 */
import type { Story } from "@ladle/react";

import { Px, currentTheme } from "./design/frame";

const NODES: { label: string; level: number; name: string }[] = [
  { label: "数", level: 5, name: "10 以内加减" },
  { label: "形", level: 3, name: "认识图形" },
  { label: "算", level: 4, name: "20 以内进位" },
  { label: "声", level: 2, name: "拼音声母" },
  { label: "钟", level: 1, name: "认识钟表" },
];

function Panel({
  title,
  children,
  style,
}: {
  title?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <section
      style={{
        background: "var(--card)",
        border: "var(--card-border)",
        borderRadius: "var(--card-radius)",
        boxShadow: "var(--shadow-card)",
        padding: "var(--card-padding)",
        display: "grid",
        gap: "var(--space-xs)",
        ...style,
      }}
    >
      {title ? (
        <h3 style={{ margin: 0, fontSize: "var(--text-app-md)", fontWeight: 700 }}>{title}</h3>
      ) : null}
      {children}
    </section>
  );
}

function Sidebar() {
  return (
    <aside
      style={{
        width: "var(--sidebar-width)",
        flex: "0 0 auto",
        background: "var(--sidebar)",
        borderRight: "1px solid var(--sidebar-border)",
        padding: "var(--space-sm)",
        display: "grid",
        gap: "var(--space-sm)",
        alignContent: "start",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "var(--radius-control)",
            background: "var(--primary)",
            color: "var(--primary-foreground)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 800,
          }}
        >
          学
        </div>
        <div style={{ display: "grid" }}>
          <span style={{ fontWeight: 700, fontSize: "var(--text-app-md)" }}>学伴</span>
          <span style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
            一年级 · 数学
          </span>
        </div>
      </div>

      <nav style={{ display: "grid", gap: 2 }}>
        {["今日任务", "诊断", "学习规划", "错题复习", "复盘"].map((item, index) => (
          <div
            key={item}
            style={{
              minHeight: "var(--tap-min)",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "0 var(--space-xs)",
              borderRadius: "var(--radius-control)",
              background: index === 0 ? "var(--primary-soft)" : "transparent",
              color: index === 0 ? "var(--accent-foreground)" : "var(--foreground)",
              fontWeight: index === 0 ? 700 : 500,
              fontSize: "var(--text-app)",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: 999,
                background: index === 0 ? "var(--primary)" : "var(--border-strong)",
              }}
            />
            {item}
          </div>
        ))}
      </nav>

      <div style={{ display: "grid", gap: 6 }}>
        <span style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
          知识地图（按掌握度着色）
        </span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {NODES.map((node) => (
            <div
              key={node.label}
              title={node.name}
              style={{
                width: "var(--kmap-node)",
                height: "var(--kmap-node)",
                borderRadius: "var(--radius-control)",
                background: `var(--mastery-${node.level})`,
                color: node.level >= 4 ? "var(--primary-foreground)" : "var(--card)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "var(--text-app-lg)",
                fontWeight: 700,
                border: "1px solid var(--border-strong)",
              }}
            >
              {node.label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gap: 6 }}>
        <span style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
          学科总掌握度
        </span>
        {NODES.slice(0, 3).map((node, index) => (
          <div key={node.label} style={{ display: "grid", gap: 2 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: "var(--text-app-xs)" }}>{node.name}</span>
              <span style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
                {[95, 62, 78][index]}%
              </span>
            </div>
            <div
              style={{
                height: "var(--mastery-bar-height)",
                background: "var(--surface-sunken)",
                borderRadius: "var(--radius-pill)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${[95, 62, 78][index]}%`,
                  height: "100%",
                  background: `var(--mastery-${node.level})`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

function Main() {
  return (
    <main
      style={{
        flex: "1 1 auto",
        minWidth: 0,
        padding: "var(--space-md)",
        display: "grid",
        gap: "var(--space-sm)",
        alignContent: "start",
        background: "var(--background)",
      }}
    >
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "var(--text-app-2xl)", fontWeight: 700 }}>今日任务</h1>
          <p style={{ margin: 0, fontSize: "var(--text-app-sm)", color: "var(--muted-foreground)" }}>
            周三 · 诊断 → 规划 → 学习 → 复习 → 复盘
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <div
            style={{
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              borderRadius: "var(--radius-pill)",
              padding: "4px 12px",
              fontWeight: 700,
              fontSize: "var(--text-app-sm)",
              minHeight: "var(--tap-min)",
              display: "flex",
              alignItems: "center",
            }}
          >
            🔥 连续 7 天
          </div>
          <div
            style={{
              background: "var(--surface-sunken)",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--radius-pill)",
              padding: "4px 12px",
              fontSize: "var(--text-app-sm)",
              minHeight: "var(--tap-min)",
              display: "flex",
              alignItems: "center",
            }}
          >
            🔊 朗读本页
          </div>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "var(--space-sm)" }}>
        <Panel title="继续：10 以内加减">
          <div style={{ fontSize: "var(--text-app-sm)", color: "var(--muted-foreground)" }}>
            今日进度 3 / 5 题
          </div>
          <div
            style={{
              height: "var(--mastery-bar-height)",
              background: "var(--surface-sunken)",
              borderRadius: "var(--radius-pill)",
              overflow: "hidden",
            }}
          >
            <div style={{ width: "60%", height: "100%", background: "var(--primary)" }} />
          </div>
          <div
            style={{
              minHeight: "var(--tap-min)",
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              borderRadius: "var(--radius-control)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: "var(--text-app-md)",
            }}
          >
            继续学习
          </div>
        </Panel>

        <Panel title="待复习（错题本 3）">
          <div style={{ display: "grid", gap: 6 }}>
            {["3 + 14 = ？", "认识钟表 · 整时", "b、d 区分"].map((item, index) => (
              <div
                key={item}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                  padding: "var(--space-xs)",
                  background: "var(--surface-sunken)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "var(--text-app-sm)",
                }}
              >
                <span>{item}</span>
                <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
                  <span
                    style={{
                      fontSize: 11,
                      padding: "1px 6px",
                      borderRadius: 999,
                      background: `var(--mastery-${[2, 1, 2][index]})`,
                      color: "var(--card)",
                    }}
                  >
                    {["初识", "未接触", "初识"][index]}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="学习单元：讲解 ⇄ 练习">
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {["讲解", "练习", "三层提示", "动画讲解"].map((item, index) => (
            <div
              key={item}
              style={{
                minHeight: "var(--tap-min)",
                padding: "0 var(--space-sm)",
                display: "flex",
                alignItems: "center",
                borderRadius: "var(--radius-control)",
                border: `1px solid ${index === 0 ? "var(--primary)" : "var(--border-strong)"}`,
                background: index === 0 ? "var(--primary-soft)" : "transparent",
                color: index === 0 ? "var(--accent-foreground)" : "var(--foreground)",
                fontSize: "var(--text-app-sm)",
                fontWeight: index === 0 ? 700 : 500,
              }}
            >
              {item}
            </div>
          ))}
        </div>
        <div
          style={{
            borderLeft: "3px solid var(--hint-1)",
            background: "var(--surface-sunken)",
            borderRadius: "var(--radius-sm)",
            padding: "var(--space-xs) var(--space-sm)",
            fontSize: "var(--text-app-sm)",
          }}
        >
          一层提示：先看看图——把 3 个苹果和 2 个苹果放在一起。
        </div>
        <div
          style={{
            fontSize: "var(--text-app-xs)",
            color: "var(--muted-foreground)",
          }}
        >
          守护型红线：三层之后仍不给答案 → 「我不懂」→ 建议看动画讲解
        </div>
      </Panel>
    </main>
  );
}

function AppShell() {
  const { theme, mode } = currentTheme();
  return (
    <div
      data-theme={theme}
      data-mode={mode}
      className={mode === "dark" ? "dark" : undefined}
      style={{
        width: 1320,
        display: "flex",
        minHeight: 720,
        background: "var(--background)",
        color: "var(--foreground)",
        borderRadius: "var(--radius-card)",
        overflow: "hidden",
        border: "1px solid var(--border-strong)",
        boxShadow: "var(--shadow-lg)",
        fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
        fontSize: "var(--text-app)",
        lineHeight: "var(--leading-app)",
      }}
    >
      <Sidebar />
      <Main />
    </div>
  );
}

export const DesktopShell: Story = () => (
  <div style={{ display: "grid", gap: 8 }}>
    <div style={{ fontSize: 12, color: "#6b7280" }}>
      学院派骨架 · 1320px 桌面页 · 左知识地图 + 中内容流 + 掌握度核心视觉语言 ·
      侧栏宽度 <Px>264px（kids 240px）</Px>
    </div>
    <AppShell />
  </div>
);
