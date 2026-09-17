"use client";

import katex from "katex";
import type { HTMLAttributes } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart as RechartsRadarChart,
  ResponsiveContainer,
} from "recharts";

import { cn } from "./cn";

/** 数据表格（基础原语） */
export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full caption-bottom text-sm", className)} {...props} />;
}

export function TableHeader({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("[&_tr]:border-b", className)} {...props} />;
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("border-b border-border transition-colors hover:bg-muted/50", className)} {...props} />;
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn("h-10 px-3 text-left align-middle text-xs font-medium text-muted-foreground", className)}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-3 py-3 align-middle text-foreground", className)} {...props} />;
}

export interface StatCardProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  value: string | number;
  hint?: string;
  delta?: string;
  tone?: "default" | "success" | "warning" | "danger";
}

/** 指标卡（学情看板） */
export function StatCard({ className, title, value, hint, delta, tone = "default", ...props }: StatCardProps) {
  const toneClass = {
    default: "text-foreground",
    success: "text-green-600",
    warning: "text-amber-600",
    danger: "text-red-600",
  }[tone];
  return (
    <div className={cn("rounded-xl border border-border bg-card p-5", className)} {...props}>
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className={cn("mt-1 text-3xl font-semibold", toneClass)}>{value}</p>
      {delta ? <p className="mt-1 text-xs text-muted-foreground">{delta}</p> : null}
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export interface RadarPoint {
  label: string;
  value: number;
  fullMark?: number;
}

export interface KnowledgeRadarProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  data: RadarPoint[];
  height?: number;
}

/** 知识点掌握度雷达图（F-03） */
export function KnowledgeRadar({ className, title, data, height = 240, ...props }: KnowledgeRadarProps) {
  return (
    <div className={cn("rounded-xl border border-border bg-card p-4", className)} {...props}>
      {title ? <p className="mb-2 text-sm font-medium text-foreground">{title}</p> : null}
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RechartsRadarChart data={data} outerRadius="70%">
            <PolarGrid />
            <PolarAngleAxis dataKey="label" tick={{ fontSize: 12 }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} />
            <Radar
              name="掌握度"
              dataKey="value"
              stroke="#1f66f5"
              fill="#3386ff"
              fillOpacity={0.4}
            />
          </RechartsRadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export interface MathFormulaProps extends HTMLAttributes<HTMLSpanElement> {
  formula: string;
  displayMode?: boolean;
}

/** 数学公式渲染（KaTeX；样式由宿主应用引入 katex 主题） */
export function MathFormula({ className, formula, displayMode = false, ...props }: MathFormulaProps) {
  let html = "";
  try {
    html = katex.renderToString(formula, { throwOnError: false, displayMode });
  } catch {
    html = formula;
  }
  return (
    <span
      className={cn(displayMode && "block text-center", className)}
      // KaTeX 输出为受控 HTML（throwOnError=false 不执行脚本）
      dangerouslySetInnerHTML={{ __html: html }}
      {...props}
    />
  );
}
