/**
 * P0 设计稿走查：设计系统层（令牌 + 视觉语言）
 * 并排渲染 focus / kids 两套主题；控件形态为示意块，评审放行后换成 packages/ui 正式组件。
 */
import type { Story } from "@ladle/react";

import { Row, Swatches, ThemePair } from "./design/frame";

const SURFACE = [
  { name: "background", varName: "--background" },
  { name: "surface-raised", varName: "--surface-raised" },
  { name: "surface-sunken", varName: "--surface-sunken" },
  { name: "card", varName: "--card" },
  { name: "sidebar", varName: "--sidebar" },
];

const ACCENT = [
  { name: "primary", varName: "--primary" },
  { name: "primary-soft", varName: "--primary-soft" },
  { name: "secondary", varName: "--secondary" },
  { name: "accent", varName: "--accent" },
  { name: "ring", varName: "--ring" },
  { name: "border", varName: "--border" },
];

const STATUS = [
  { name: "success", varName: "--success" },
  { name: "warning", varName: "--warning" },
  { name: "destructive", varName: "--destructive" },
  { name: "info", varName: "--info" },
  { name: "muted-fg", varName: "--muted-foreground" },
  { name: "foreground", varName: "--foreground" },
];

const MASTERY = [
  { name: "1 未接触", varName: "--mastery-1" },
  { name: "2 初识", varName: "--mastery-2" },
  { name: "3 入门", varName: "--mastery-3" },
  { name: "4 熟练", varName: "--mastery-4" },
  { name: "5 精通", varName: "--mastery-5" },
];

const HINT = [
  { name: "hint-1 轻推", varName: "--hint-1" },
  { name: "hint-2 举一反三", varName: "--hint-2" },
  { name: "hint-3 微支架", varName: "--hint-3" },
];

function Bar({ fill, tone }: { fill: number; tone: string }) {
  return (
    <div
      style={{
        height: "var(--mastery-bar-height)",
        background: "var(--surface-sunken)",
        borderRadius: "var(--radius-pill)",
        overflow: "hidden",
        border: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          width: `${Math.round(fill * 100)}%`,
          height: "100%",
          background: `var(${tone})`,
          borderRadius: "var(--radius-pill)",
        }}
      />
    </div>
  );
}

function MasteryStack() {
  const rows: { label: string; fill: number; tone: string }[] = [
    { label: "10 以内加减", fill: 0.95, tone: "--mastery-5" },
    { label: "认识图形", fill: 0.62, tone: "--mastery-3" },
    { label: "拼音声母", fill: 0.3, tone: "--mastery-2" },
    { label: "认识钟表", fill: 0, tone: "--mastery-1" },
  ];
  return (
    <div style={{ display: "grid", gap: "var(--space-xs)" }}>
      {rows.map((row) => (
        <div
          key={row.label}
          style={{ display: "grid", gridTemplateColumns: "1fr 90px 34px", gap: 8, alignItems: "center" }}
        >
          <span style={{ fontSize: "var(--text-app-sm)" }}>{row.label}</span>
          <Bar fill={row.fill} tone={row.tone} />
          <span
            style={{
              fontSize: "var(--text-app-xs)",
              color: "var(--muted-foreground)",
              textAlign: "right",
            }}
          >
            {Math.round(row.fill * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function HintStack() {
  const hints = [
    "先看看图：把 3 个苹果和 2 个苹果放在一起。",
    "想想「加」是什么意思——合起来变多了。",
    "把手指伸出来数一数：1、2、3、4、5。",
  ];
  return (
    <div style={{ display: "grid", gap: "var(--space-xs)" }}>
      {hints.map((hint, index) => (
        <div
          key={hint}
          style={{
            borderLeft: `3px solid var(--hint-${index + 1})`,
            background: "var(--surface-sunken)",
            borderRadius: "var(--radius-sm)",
            padding: "var(--space-xs) var(--space-sm)",
            fontSize: "var(--text-app-sm)",
          }}
        >
          {hint}
        </div>
      ))}
      <p style={{ margin: 0, fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
        守护型红线：三层之后仍不给答案，转「我不懂」→ 建议看动画讲解
      </p>
    </div>
  );
}

function QuestionCard() {
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        boxShadow: "var(--shadow-card)",
        padding: "var(--space-sm)",
        display: "grid",
        gap: "var(--space-xs)",
      }}
    >
      <div style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
        1 / 5 · 难度 2 · 20 以内加减
      </div>
      <div style={{ fontSize: "var(--text-app-lg)", fontWeight: 600 }}>3 + 14 = ？</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {["A. 15", "B. 16", "C. 17", "D. 18"].map((label, index) => (
          <div
            key={label}
            style={{
              minHeight: "var(--tap-min)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-control)",
              border: `1px solid ${index === 2 ? "var(--primary)" : "var(--border)"}`,
              background: index === 2 ? "var(--primary-soft)" : "transparent",
              fontSize: "var(--text-app)",
              fontWeight: 500,
            }}
          >
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

function KnowledgeMap() {
  const nodes = [
    { label: "数", level: 5 },
    { label: "形", level: 3 },
    { label: "声", level: 2 },
    { label: "钟", level: 1 },
    { label: "算", level: 4 },
  ];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-xs)" }}>
      {nodes.map((node) => (
        <div
          key={node.label}
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
            border: "1px solid var(--border)",
          }}
        >
          {node.label}
        </div>
      ))}
    </div>
  );
}

function TodayPage() {
  return (
    <div style={{ display: "grid", gap: "var(--space-sm)" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: "var(--text-app-2xl)", fontWeight: 700 }}>今日任务</div>
        <div style={{ display: "flex", gap: 6 }}>
          <div
            style={{
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              borderRadius: "var(--radius-pill)",
              padding: "4px 10px",
              fontSize: "var(--text-app-sm)",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            🔥 7 天
          </div>
          <div
            style={{
              background: "var(--surface-sunken)",
              borderRadius: "var(--radius-pill)",
              padding: "4px 10px",
              fontSize: "var(--text-app-sm)",
              display: "flex",
              alignItems: "center",
              minHeight: "var(--tap-min)",
            }}
          >
            🔊 朗读
          </div>
        </div>
      </header>
      <div
        style={{
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          boxShadow: "var(--shadow-card)",
          padding: "var(--space-sm)",
          display: "grid",
          gap: "var(--space-xs)",
        }}
      >
        <div style={{ fontSize: "var(--text-app-sm)", color: "var(--muted-foreground)" }}>
          今日进度 · 3 / 5 题
        </div>
        <Bar fill={0.6} tone="--primary" />
        <div style={{ fontSize: "var(--text-app)", fontWeight: 600 }}>
          继续：10 以内加减 · 认识图形
        </div>
        <div
          style={{
            background: "var(--primary)",
            color: "var(--primary-foreground)",
            borderRadius: "var(--radius-control)",
            minHeight: "var(--tap-min)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 600,
            fontSize: "var(--text-app-md)",
          }}
        >
          继续学习
        </div>
      </div>
      <KnowledgeMap />
      <MasteryStack />
    </div>
  );
}

export const Palette: Story = () => (
  <ThemePair>
    {() => (
      <div>
        <Row title="语义 · 表面">
          <Swatches items={SURFACE} />
        </Row>
        <Row title="语义 · 强调与描边">
          <Swatches items={ACCENT} />
        </Row>
        <Row title="语义 · 状态与文字">
          <Swatches items={STATUS} />
        </Row>
        <Row title="核心视觉语言 · 掌握度五档">
          <Swatches items={MASTERY} />
        </Row>
        <Row title="守护型三层提示">
          <Swatches items={HINT} />
        </Row>
      </div>
    )}
  </ThemePair>
);

export const Typography: Story = () => (
  <ThemePair>
    {() => (
      <Row title="字阶（同一套语义类，主题仅改旋钮）">
        <div style={{ display: "grid", gap: 6 }}>
          {[
            ["app-xs · 12/16", "var(--text-app-xs)"],
            ["app-sm · 13/16", "var(--text-app-sm)"],
            ["app · 14/16（基准）", "var(--text-app)"],
            ["app-md · 15/16", "var(--text-app-md)"],
            ["app-lg · 18/16", "var(--text-app-lg)"],
            ["app-xl · 22/16", "var(--text-app-xl)"],
            ["app-2xl · 28/16", "var(--text-app-2xl)"],
            ["app-3xl · 36/16", "var(--text-app-3xl)"],
          ].map(([label, size]) => (
            <div key={label} style={{ display: "grid", gap: 2 }}>
              <span style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
                {label}
              </span>
              <span style={{ fontSize: size, fontWeight: 500 }}>20 以内加减法</span>
            </div>
          ))}
        </div>
      </Row>
    )}
  </ThemePair>
);

export const SpacingAndRadius: Story = () => (
  <ThemePair>
    {() => (
      <div>
        <Row title="间距 · 8pt 网格">
          <div style={{ display: "grid", gap: 6 }}>
            {["xs 8", "sm 16", "md 24", "lg 32", "xl 40", "2xl 48"].map((label) => {
              const token = `--space-${label.split(" ")[0]}`;
              return (
                <div key={label} style={{ display: "grid", gridTemplateColumns: "48px 1fr", gap: 8 }}>
                  <span style={{ fontSize: "var(--text-app-xs)", color: "var(--muted-foreground)" }}>
                    {label}
                  </span>
                  <div style={{ height: 10, width: `var(${token})`, background: "var(--primary)" }} />
                </div>
              );
            })}
          </div>
        </Row>
        <Row title="圆角与控件高度（旋钮换肤）">
          <div style={{ display: "grid", gap: 6 }}>
            {["sm", "md", "lg", "xl", "2xl"].map((token) => (
              <div
                key={token}
                style={{
                  height: "var(--input-height)",
                  borderRadius: `var(--radius-${token})`,
                  background: "var(--surface-sunken)",
                  border: "1px solid var(--border)",
                  display: "flex",
                  alignItems: "center",
                  padding: "0 var(--space-sm)",
                  fontSize: "var(--text-app-sm)",
                }}
              >
                radius-{token} · input-height
              </div>
            ))}
            <div
              style={{
                height: "var(--tap-min)",
                borderRadius: "var(--radius-control)",
                background: "var(--primary-soft)",
                color: "var(--primary-foreground)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "var(--text-app-xs)",
              }}
            >
              最小热区 --tap-min
            </div>
          </div>
        </Row>
      </div>
    )}
  </ThemePair>
);

export const LearningBits: Story = () => (
  <ThemePair>
    {() => (
      <div>
        <Row title="题卡 QuestionCard">
          <QuestionCard />
        </Row>
        <Row title="知识地图节点 KnowledgeMap">
          <KnowledgeMap />
        </Row>
        <Row title="掌握度条 MasteryBar">
          <MasteryStack />
        </Row>
        <Row title="三层提示 HintStack">
          <HintStack />
        </Row>
      </div>
    )}
  </ThemePair>
);

export const TodayTaskPage: Story = () => (
  <ThemePair width={480}>
    {() => <TodayPage />}
  </ThemePair>
);
