"use client";

import { useState, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";

export interface TabsProps extends Omit<HTMLAttributes<HTMLDivElement>, "onChange"> {
  tabs: { key: string; label: string; content: ReactNode }[];
  defaultKey?: string;
  /** 受控联动回调（可选）：切换标签时触发 */
  onChange?: (key: string) => void;
}

/** 标签页 */
export function Tabs({ className, tabs, defaultKey, onChange, ...props }: TabsProps) {
  const [active, setActive] = useState(defaultKey ?? tabs[0]?.key ?? "");
  const current = tabs.find((tab) => tab.key === active) ?? tabs[0];
  return (
    <div className={cn("w-full", className)} {...props}>
      <div role="tablist" className="flex gap-1 border-b border-border">
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
              "border-b-2 border-transparent px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground",
              tab.key === current?.key && "border-primary text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="pt-4">
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

/** 折叠面板（基于 details，天然可访问） */
export function Accordion({ className, items, ...props }: AccordionProps) {
  return (
    <div className={cn("divide-y divide-border rounded-lg border border-border", className)} {...props}>
      {items.map((item) => (
        <details key={item.key} className="group p-4">
          <summary className="cursor-pointer text-sm font-medium text-foreground">{item.title}</summary>
          <div className="pt-2 text-sm text-muted-foreground">{item.content}</div>
        </details>
      ))}
    </div>
  );
}

export interface BreadcrumbProps extends HTMLAttributes<HTMLElement> {
  items: { label: string; href?: string }[];
}

/** 面包屑 */
export function Breadcrumb({ className, items, ...props }: BreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className={cn("text-sm text-muted-foreground", className)} {...props}>
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-1">
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

/** 分页 */
export function Pagination({ className, page, pageCount, onChange, ...props }: PaginationProps) {
  const pages = Array.from({ length: Math.max(pageCount, 1) }, (_, index) => index + 1);
  return (
    <nav aria-label="分页" className={cn("flex items-center gap-1", className)} {...props}>
      <button
        type="button"
        className="rounded-md border border-border px-3 py-1 text-sm disabled:opacity-50"
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
          className={cn(
            "rounded-md border border-border px-3 py-1 text-sm",
            item === page && "bg-primary text-primary-foreground",
          )}
          onClick={() => onChange?.(item)}
        >
          {item}
        </button>
      ))}
      <button
        type="button"
        className="rounded-md border border-border px-3 py-1 text-sm disabled:opacity-50"
        disabled={page >= pageCount}
        onClick={() => onChange?.(page + 1)}
      >
        下一页
      </button>
    </nav>
  );
}
