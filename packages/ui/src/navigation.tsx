"use client";

import { useState, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";

/** 导航类组件：尺寸/圆角/字阶走令牌 ⇒ kids 主题下热区与字号自动放大。 */

export interface TabItem {
  key: string;
  label: string;
  content: ReactNode;
}

export interface TabsProps extends Omit<HTMLAttributes<HTMLDivElement>, "onChange"> {
  tabs: TabItem[];
  defaultKey?: string;
  /** 受控联动回调（可选）：切换标签时触发 */
  onChange?: (key: string) => void;
}

export function Tabs({ className, tabs, defaultKey, onChange, ...props }: TabsProps) {
  const [active, setActive] = useState(defaultKey ?? tabs[0]?.key ?? "");
  const current = tabs.find((tab) => tab.key === active) ?? tabs[0];
  return (
    <div className={cn("w-full", className)} {...props}>
      <div role="tablist" className="flex gap-hair border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            type="button"
            aria-selected={tab.key === current?.key}
            onClick={() => {
              setActive(tab.key);
              onChange?.(tab.key);
            }}
            className={cn(
              "min-h-[var(--tap-min)] border-b-2 border-transparent px-sm py-xs text-app font-medium",
              "text-muted-foreground transition-colors hover:text-foreground",
              tab.key === current?.key && "border-primary text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="pt-sm">
        {current?.content}
      </div>
    </div>
  );
}

export interface AccordionItem {
  key: string;
  title: string;
  content: ReactNode;
}

export interface AccordionProps extends HTMLAttributes<HTMLDivElement> {
  items: AccordionItem[];
}

export function Accordion({ className, items, ...props }: AccordionProps) {
  return (
    <div
      className={cn(
        "divide-y divide-border rounded-card border border-border",
        className,
      )}
      {...props}
    >
      {items.map((item) => (
        <details key={item.key} className="group p-sm">
          <summary className="cursor-pointer text-app font-medium text-foreground">{item.title}</summary>
          <div className="pt-xs text-app-sm text-muted-foreground">{item.content}</div>
        </details>
      ))}
    </div>
  );
}

export interface BreadcrumbProps extends HTMLAttributes<HTMLElement> {
  items: { label: string; href?: string }[];
}

export function Breadcrumb({ className, items, ...props }: BreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className={cn("text-app-sm text-muted-foreground", className)} {...props}>
      <ol className="flex flex-wrap items-center gap-hair">
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-hair">
            {item.href ? (
              <a href={item.href} className="hover:text-foreground hover:underline">
                {item.label}
              </a>
            ) : (
              <span aria-current="page" className="font-medium text-foreground">
                {item.label}
              </span>
            )}
            {index < items.length - 1 ? <span aria-hidden="true">/</span> : null}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export interface PaginationProps extends Omit<HTMLAttributes<HTMLElement>, "onChange"> {
  page: number;
  pageCount: number;
  onChange?: (page: number) => void;
}

const pageButton =
  "min-h-[var(--tap-min)] rounded-control border border-border-strong px-sm text-app";

export function Pagination({ className, page, pageCount, onChange, ...props }: PaginationProps) {
  const pages = Array.from({ length: Math.max(pageCount, 1) }, (_, index) => index + 1);
  return (
    <nav aria-label="分页" className={cn("flex items-center gap-hair", className)} {...props}>
      <button
        type="button"
        className={cn(pageButton, "disabled:opacity-50")}
        disabled={page <= 1}
        onClick={() => onChange?.(page - 1)}
      >
        上一页
      </button>
      {pages.map((item) => (
        <button
          key={item}
          type="button"
          aria-current={item === page ? "page" : undefined}
          className={cn(pageButton, item === page && "bg-primary text-primary-foreground")}
          onClick={() => onChange?.(item)}
        >
          {item}
        </button>
      ))}
      <button
        type="button"
        className={cn(pageButton, "disabled:opacity-50")}
        disabled={page >= pageCount}
        onClick={() => onChange?.(page + 1)}
      >
        下一页
      </button>
    </nav>
  );
}
