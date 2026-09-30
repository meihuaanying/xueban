"use client";

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
  return <table className={cn("w-full caption-bottom text-app", className)} {...props} />;
}

export function TableHeader({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("[&_tr]:border-b border-border-strong", className)} {...props} />;
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn("border-b border-border transition-colors hover:bg-muted/60", className)} {...props} />
  );
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "min-h-[var(--tap-min)] px-sm text-left align-middle text-app-xs font-medium text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-sm py-xs align-middle text-app text-foreground", className)} {...props} />;
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
    success: "text-success",
    warning: "text-warning",
    danger: "text-destructive",
  }[tone];
  return (
    <div className={cn("rounded-card border border-border bg-card p-sm", className)} {...props}>
      <p className="text-app-sm text-muted-foreground">{title}</p>
      <p className={cn("mt-xs text-app-2xl font-semibold", toneClass)}>{value}</p>
      {delta ? <p className="mt-xs text-app-xs text-muted-foreground">{delta}</p> : null}
      {hint ? <p className="mt-hair text-app-xs text-muted-foreground">{hint}</p> : null}
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
    <div className={cn("rounded-card border border-border bg-card p-sm", className)} {...props}>
      {title ? <p className="mb-xs text-app font-medium text-foreground">{title}</p> : null}
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RechartsRadarChart data={data} outerRadius="70%">
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis dataKey="label" tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
            <Radar
              name="掌握度"
              dataKey="value"
              stroke="var(--primary)"
              fill="var(--primary)"
              fillOpacity={0.32}
            />
          </RechartsRadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export { MathFormula, type MathFormulaProps } from "./formula";

