"use client";

/** 家长端（T7.1 / F-40~F-43）：绑定孩子、学情看板、防沉迷、安全报告、亲子任务、免登录链接。 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
  Select,
  StatCard,
  buttonVariants,
  cn,
} from "@xueban/ui";

import {
  ApiError,
  parentApi,
  type ChildInfo,
  type ParentControls,
  type ParentDashboard,
  type ParentTask,
  type SafetyReport,
} from "@/lib/api";
import { loadAccessToken } from "@/lib/auth-storage";

type PageState = "loading" | "unauthenticated" | "not-parent" | "ready";

export default function ParentsPage() {
  const [state, setState] = useState<PageState>("loading");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [children, setChildren] = useState<ChildInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [childPhone, setChildPhone] = useState("");
  const [dashboard, setDashboard] = useState<ParentDashboard | null>(null);
  const [controls, setControls] = useState<ParentControls | null>(null);
  const [dailyLimit, setDailyLimit] = useState("60");
  const [restAfter, setRestAfter] = useState("40");
  const [enabled, setEnabled] = useState(true);
  const [parentPassword, setParentPassword] = useState("");
  const [controlsMessage, setControlsMessage] = useState<string | null>(null);
  const [safety, setSafety] = useState<SafetyReport | null>(null);
  const [tasks, setTasks] = useState<ParentTask[]>([]);
  const [sharePath, setSharePath] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const bootstrap = useCallback(async () => {
    const stored = loadAccessToken();
    if (!stored) {
      setState("unauthenticated");
      return;
    }
    setToken(stored);
    try {
      const me = await parentApi.me(stored);
      if (me.role !== "parent") {
        setState("not-parent");
        return;
      }
      const list = await parentApi.children(stored);
      setChildren(list);
      setSelected(list[0]?.id ?? null);
      setState("ready");
    } catch {
      setState("unauthenticated");
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const loadChild = useCallback(
    async (childId: string) => {
      if (!token) return;
      setBusy(true);
      setError(null);
      try {
        const [dashboardData, controlsData, safetyData, taskData] = await Promise.all([
          parentApi.dashboard(token, childId),
          parentApi.controls(token, childId),
          parentApi.safety(token, childId),
          parentApi.tasks(token, childId),
        ]);
        setDashboard(dashboardData);
        setControls(controlsData);
        setDailyLimit(String(controlsData.daily_limit_minutes));
        setRestAfter(String(controlsData.rest_after_minutes));
        setEnabled(controlsData.is_enabled);
        setSafety(safetyData);
        setTasks(taskData.tasks);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "加载孩子数据失败。");
      } finally {
        setBusy(false);
      }
    },
    [token],
  );

  useEffect(() => {
    if (selected) void loadChild(selected);
  }, [selected, loadChild]);

  async function handleBind() {
    if (!token || !childPhone.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const child = await parentApi.bindChild(token, childPhone.trim());
      const list = await parentApi.children(token);
      setChildren(list);
      setSelected(child.id);
      setChildPhone("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "绑定失败，请检查手机号。");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveControls() {
    if (!token || !selected) return;
    setBusy(true);
    setError(null);
    setControlsMessage(null);
    try {
      const updated = await parentApi.updateControls(token, {
        child_id: selected,
        parent_password: parentPassword,
        is_enabled: enabled,
        daily_limit_minutes: Number(dailyLimit),
        rest_after_minutes: Number(restAfter),
      });
      setControls(updated);
      setControlsMessage("已保存，服务端即时生效。");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "保存失败（家长密码是否正确？）。");
    } finally {
      setBusy(false);
    }
  }

  async function handleShare() {
    if (!token || !selected) return;
    setBusy(true);
    try {
      const link = await parentApi.createLink(token, selected);
      setSharePath(link.url_path);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "生成分享链接失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke() {
    if (!token || !sharePath) return;
    const shareToken = sharePath.split("/").pop() ?? "";
    setBusy(true);
    try {
      await parentApi.revokeLink(token, shareToken);
      setSharePath(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "吊销失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm(taskId: string) {
    if (!token) return;
    setBusy(true);
    try {
      const updated = await parentApi.confirmTask(token, taskId);
      setTasks((prev) => prev.map((task) => (task.id === taskId ? updated : task)));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "确认失败（孩子尚未完成？）。");
    } finally {
      setBusy(false);
    }
  }

  if (state === "loading") {
    return (
      <main className="mx-auto max-w-5xl px-6 py-16">
        <p className="text-sm text-muted-foreground">加载中…</p>
      </main>
    );
  }

  if (state === "unauthenticated") {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>请先登录家长账号</CardTitle>
            <CardDescription>家长端需要家长角色账号（可在注册页选择「家长」）。</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-3">
            <Link href="/register" className={cn(buttonVariants({}))}>
              注册家长账号
            </Link>
            <Link href="/app" className={cn(buttonVariants({ variant: "outline" }))}>
              进入学习中心
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (state === "not-parent") {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <Alert variant="warning" title="当前账号不是家长角色">
          家长端仅限家长账号访问。请使用家长账号登录，或注册家长账号后绑定孩子。
        </Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-16" data-testid="parents-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">家长端</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          学情看板、防沉迷与安全报告均来自服务端（家长只能查看自己绑定的孩子）。
        </p>
      </div>

      {error ? (
        <Alert variant="danger" title="操作未完成">
          {error}
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>孩子账号</CardTitle>
          <CardDescription>输入孩子注册时使用的手机号完成绑定。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2" data-testid="children-list">
            {children.map((child) => (
              <Button
                key={child.id}
                variant={selected === child.id ? "primary" : "outline"}
                onClick={() => setSelected(child.id)}
              >
                {child.nickname ?? child.phone}
              </Button>
            ))}
            {children.length === 0 ? (
              <p className="text-sm text-muted-foreground">尚未绑定孩子。</p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="child-phone">孩子手机号</Label>
              <Input
                id="child-phone"
                data-testid="child-phone"
                value={childPhone}
                onChange={(event) => setChildPhone(event.target.value)}
                placeholder="11 位手机号"
              />
            </div>
            <Button disabled={busy || !childPhone.trim()} onClick={() => void handleBind()} data-testid="bind-child">
              绑定孩子
            </Button>
          </div>
        </CardContent>
      </Card>

      {selected && dashboard ? (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <StatCard title="连续打卡" value={`${dashboard.streak_days} 天`} tone="success" />
            <StatCard title="近 7 天练习" value={`${dashboard.practice_7d} 题`} />
            <StatCard
              title="任务完成率"
              value={`${Math.round(dashboard.task_completion_7d * 100)}%`}
            />
            <StatCard title="待掌握错题" value={dashboard.mistakes_active} tone="danger" />
          </div>

          <Card data-testid="parent-dashboard">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle>学情看板（F-41）</CardTitle>
                <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleShare()}>
                  生成免登录链接
                </Button>
              </div>
              <CardDescription>
                掌握度分布：红 {dashboard.mastery.red_count} · 黄 {dashboard.mastery.yellow_count} · 绿{" "}
                {dashboard.mastery.green_count}；平均{" "}
                {dashboard.mastery.average_mastery === null
                  ? "—"
                  : `${Math.round(dashboard.mastery.average_mastery * 100)}%`}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {sharePath ? (
                <Alert variant="success" title="分享链接已生成（只读、可吊销）">
                  <p className="break-all" data-testid="share-link">
                    {sharePath}
                  </p>
                  <div className="mt-2">
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleRevoke()}>
                      吊销链接
                    </Button>
                  </div>
                </Alert>
              ) : null}
            </CardContent>
          </Card>

          <Card data-testid="parent-controls">
            <CardHeader>
              <CardTitle>防沉迷设置（F-40）</CardTitle>
              <CardDescription>修改需家长密码；学习端由服务端判定后锁屏，无法本地绕过。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="flex items-center gap-3 text-sm">
                <Checkbox
                  checked={enabled}
                  onChange={(event) => setEnabled(event.target.checked)}
                  data-testid="controls-enabled"
                />
                启用防沉迷
              </label>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="daily-limit">每日上限（分钟）</Label>
                  <Select
                    id="daily-limit"
                    data-testid="daily-limit"
                    options={[
                      { value: "30", label: "30 分钟" },
                      { value: "60", label: "60 分钟" },
                      { value: "120", label: "120 分钟" },
                    ]}
                    value={dailyLimit}
                    onChange={(event) => setDailyLimit(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rest-after">休息提醒（分钟）</Label>
                  <Input
                    id="rest-after"
                    data-testid="rest-after"
                    value={restAfter}
                    onChange={(event) => setRestAfter(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="parent-password">家长密码</Label>
                  <Input
                    id="parent-password"
                    type="password"
                    data-testid="parent-password"
                    value={parentPassword}
                    onChange={(event) => setParentPassword(event.target.value)}
                  />
                </div>
              </div>
              {controlsMessage ? <p className="text-sm text-success">{controlsMessage}</p> : null}
              <p className="text-xs text-muted-foreground">
                当前设置：上限 {controls?.daily_limit_minutes ?? "—"} 分钟 · 休息提醒{" "}
                {controls?.rest_after_minutes ?? "—"} 分钟 · {controls?.is_enabled ? "已启用" : "已关闭"}
              </p>
              <Button disabled={busy || !parentPassword} onClick={() => void handleSaveControls()} data-testid="save-controls">
                保存设置
              </Button>
            </CardContent>
          </Card>

          <Card data-testid="parent-safety">
            <CardHeader>
              <CardTitle>安全报告（F-42）</CardTitle>
              <CardDescription>
                {safety ? `${safety.week_start} ~ ${safety.week_end}` : ""} · 拦截 {safety?.blocked_count ?? 0} 次 · 对话留痕{" "}
                {safety?.trace_total ?? 0} 条
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {(safety?.events ?? []).map((event) => (
                <div key={event.id} className="rounded-lg border border-border px-4 py-2">
                  <p className="text-foreground">
                    <Badge variant="danger">{event.action}</Badge> {event.scene} · {event.snippet}
                  </p>
                </div>
              ))}
              {(safety?.traces ?? []).slice(0, 3).map((trace) => (
                <p key={trace.id} className="text-muted-foreground">
                  [{trace.role}] {trace.excerpt}
                </p>
              ))}
              {safety && safety.total_events === 0 && safety.trace_total === 0 ? (
                <p className="text-muted-foreground">本周没有拦截记录与对话留痕。</p>
              ) : null}
            </CardContent>
          </Card>

          <Card data-testid="parent-tasks">
            <CardHeader>
              <CardTitle>亲子任务（F-43）</CardTitle>
              <CardDescription>孩子完成后家长确认，形成闭环。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-4 py-3 text-sm"
                  data-testid="parent-task"
                >
                  <div>
                    <p className="font-medium text-foreground">{task.title}</p>
                    <p className="text-xs text-muted-foreground">{task.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={task.status === "confirmed" ? "success" : task.status === "child_done" ? "warning" : "outline"}
                    >
                      {task.status === "confirmed" ? "已确认" : task.status === "child_done" ? "待确认" : "进行中"}
                    </Badge>
                    {task.status === "child_done" ? (
                      <Button size="sm" disabled={busy} onClick={() => void handleConfirm(task.id)}>
                        确认完成
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      ) : null}
    </main>
  );
}
