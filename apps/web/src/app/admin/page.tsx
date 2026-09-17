"use client";

/** 运营后台（T7.3 / F-44~F-47）：题库、巡检、指标看板、A/B 实验。 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  StatCard,
  Tabs,
} from "@xueban/ui";

import {
  ApiError,
  adminApi,
  type AdminQuestion,
  type Coverage,
  type ExperimentReport,
  type InspectionReport,
  type MetricsOverview,
} from "@/lib/api";
import { clearTokens, loadAccessToken, saveAccessToken } from "@/lib/auth-storage";

interface ExperimentItem {
  id: string;
  key: string;
  name: string;
  status: string;
}

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [me, setMe] = useState<{ role: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [newStem, setNewStem] = useState("");
  const [newAnswer, setNewAnswer] = useState("A");
  const [newAnalysis, setNewAnalysis] = useState("");
  const [versionInfo, setVersionInfo] = useState<Record<string, number>>({});

  const [reports, setReports] = useState<InspectionReport[]>([]);
  const [lastInspection, setLastInspection] = useState<InspectionReport | null>(null);

  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);

  const [experiments, setExperiments] = useState<ExperimentItem[]>([]);
  const [experimentKey, setExperimentKey] = useState("");
  const [report, setReport] = useState<ExperimentReport | null>(null);

  const loadAll = useCallback(async (activeToken: string) => {
    const [questionData, coverageData, reportData, metricsData, experimentsData] =
      await Promise.all([
        adminApi.questions(activeToken),
        adminApi.coverage(activeToken),
        adminApi.inspectionReports(activeToken),
        adminApi.metrics(activeToken),
        adminApi.experiments(activeToken),
      ]);
    setQuestions(questionData.items);
    setCoverage(coverageData);
    setReports(reportData);
    setMetrics(metricsData);
    setExperiments(experimentsData);
  }, []);

  const bootstrap = useCallback(async () => {
    const stored = loadAccessToken();
    if (!stored) return;
    setToken(stored);
    try {
      const profile = await adminApi.me(stored);
      setMe({ role: profile.role });
      if (profile.role === "admin") await loadAll(stored);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载后台数据失败。");
    }
  }, [loadAll]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  async function handleLogin() {
    setBusy(true);
    setError(null);
    try {
      const result = await adminApi.login(phone, password);
      saveAccessToken(result.access_token);
      setToken(result.access_token);
      const profile = await adminApi.me(result.access_token);
      setMe({ role: profile.role });
      if (profile.role !== "admin") {
        setError("该账号不是管理员，无法进入运营后台。");
        clearTokens();
        setToken(null);
        return;
      }
      await loadAll(result.access_token);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "登录失败，请检查管理员账号。");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateQuestion() {
    if (!token || !newStem.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await adminApi.createQuestion(token, {
        subject: "math",
        stem: newStem.trim(),
        answer: newAnswer.trim(),
        analysis: newAnalysis.trim(),
      });
      setNewStem("");
      setNewAnalysis("");
      const [questionData, coverageData] = await Promise.all([
        adminApi.questions(token),
        adminApi.coverage(token),
      ]);
      setQuestions(questionData.items);
      setCoverage(coverageData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "创建题目失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleTransition(question: AdminQuestion, target: string) {
    if (!token) return;
    setBusy(true);
    try {
      await adminApi.transition(token, question.id, target);
      setQuestions((await adminApi.questions(token)).items);
      setCoverage(await adminApi.coverage(token));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "流转失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleVersions(question: AdminQuestion) {
    if (!token) return;
    try {
      const versions = await adminApi.versions(token, question.id);
      setVersionInfo((prev) => ({ ...prev, [question.id]: versions.length }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "读取版本历史失败。");
    }
  }

  async function handleInspect() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const result = await adminApi.inspect(token, 50);
      setLastInspection(result);
      setReports(await adminApi.inspectionReports(token));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "巡检执行失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateExperiment() {
    if (!token || !experimentKey.trim()) return;
    setBusy(true);
    try {
      await adminApi.createExperiment(token, {
        key: experimentKey.trim(),
        name: `提示词实验 ${experimentKey.trim()}`,
        variants: [
          { name: "control", weight: 1 },
          { name: "v2", weight: 1 },
        ],
      });
      setExperimentKey("");
      setExperiments(await adminApi.experiments(token));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "创建实验失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleReport(experimentId: string) {
    if (!token) return;
    try {
      setReport(await adminApi.experimentReport(token, experimentId));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "读取实验报告失败。");
    }
  }

  function handleLogout() {
    clearTokens();
    setToken(null);
    setMe(null);
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-md space-y-4 px-6 py-16" data-testid="admin-login">
        <h1 className="text-3xl font-bold tracking-tight">运营后台</h1>
        <p className="text-sm text-muted-foreground">
          管理员账号由运维在开发/生产环境预置（开发环境见 DEV_ADMIN_PHONE 配置）。
        </p>
        {error ? (
          <Alert variant="danger" title="登录未完成">
            {error}
          </Alert>
        ) : null}
        <Card>
          <CardContent className="space-y-3 pt-6">
            <div className="space-y-2">
              <Label htmlFor="admin-phone">管理员手机号</Label>
              <Input
                id="admin-phone"
                data-testid="admin-phone"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-password">密码</Label>
              <Input
                id="admin-password"
                type="password"
                data-testid="admin-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            <Button disabled={busy} onClick={() => void handleLogin()} data-testid="admin-login-submit">
              进入后台
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (me && me.role !== "admin") {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <Alert variant="warning" title="当前账号不是管理员">
          运营后台仅限管理员访问。
        </Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-16" data-testid="admin-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">运营后台</h1>
          <p className="mt-1 text-sm text-muted-foreground">题库审核 · 质量巡检 · 数据看板 · A/B 实验</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleLogout}>
          退出后台
        </Button>
      </div>

      {error ? (
        <Alert variant="danger" title="操作未完成">
          {error}
        </Alert>
      ) : null}

      <Tabs
        defaultKey="questions"
        tabs={[
          {
            key: "questions",
            label: "题库管理",
            content: (
              <div className="space-y-4">
                {coverage ? (
                  <div className="grid gap-4 sm:grid-cols-4" data-testid="coverage-card">
                    <StatCard title="题库总量" value={coverage.total} />
                    <StatCard
                      title="解析覆盖率"
                      value={`${Math.round(coverage.coverage_rate * 100)}%`}
                      tone={coverage.coverage_rate >= 0.95 ? "success" : "warning"}
                      hint="门禁 ≥95%"
                    />
                    <StatCard title="已上线" value={coverage.published} />
                    <StatCard title="草稿 / 待审" value={`${coverage.draft} / ${coverage.review}`} />
                  </div>
                ) : null}

                <Card>
                  <CardHeader>
                    <CardTitle>新建题目（草稿）</CardTitle>
                    <CardDescription>草稿 → 审核 → 上线；解析修改会保留版本历史。</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-2">
                      <Label htmlFor="new-stem">题干</Label>
                      <Input
                        id="new-stem"
                        data-testid="new-stem"
                        value={newStem}
                        onChange={(event) => setNewStem(event.target.value)}
                      />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="new-answer">正确答案</Label>
                        <Input
                          id="new-answer"
                          data-testid="new-answer"
                          value={newAnswer}
                          onChange={(event) => setNewAnswer(event.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="new-analysis">解析</Label>
                        <Input
                          id="new-analysis"
                          data-testid="new-analysis"
                          value={newAnalysis}
                          onChange={(event) => setNewAnalysis(event.target.value)}
                        />
                      </div>
                    </div>
                    <Button disabled={busy || !newStem.trim()} onClick={() => void handleCreateQuestion()} data-testid="create-question">
                      创建草稿
                    </Button>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>题目列表</CardTitle>
                    <CardDescription>共 {questions.length} 条（最近 20 条）</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {questions.map((question) => (
                      <div
                        key={question.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-4 py-3 text-sm"
                        data-testid="admin-question"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-foreground">{question.stem}</p>
                          <p className="text-xs text-muted-foreground">
                            {question.subject} · 难度 {question.difficulty} · {question.answer}
                            {versionInfo[question.id] ? ` · 版本 ${versionInfo[question.id]}` : ""}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={
                              question.status === "published"
                                ? "success"
                                : question.status === "review"
                                  ? "warning"
                                  : "outline"
                            }
                          >
                            {question.status === "published" ? "已上线" : question.status === "review" ? "待审核" : "草稿"}
                          </Badge>
                          {question.status === "draft" ? (
                            <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleTransition(question, "review")}>
                              提交审核
                            </Button>
                          ) : null}
                          {question.status === "review" ? (
                            <Button size="sm" disabled={busy} onClick={() => void handleTransition(question, "published")}>
                              上线
                            </Button>
                          ) : null}
                          <Button size="sm" variant="ghost" onClick={() => void handleVersions(question)}>
                            版本历史
                          </Button>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            ),
          },
          {
            key: "quality",
            label: "质量巡检",
            content: (
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <CardTitle>AI 质量巡检（F-45）</CardTitle>
                      <Button disabled={busy} onClick={() => void handleInspect()} data-testid="run-inspection">
                        立即巡检（抽样 50）
                      </Button>
                    </div>
                    <CardDescription>
                      SymPy + 规则双通道校验；错题率超 3% 自动触发 webhook 告警（可接飞书机器人）。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {lastInspection ? (
                      <Alert
                        variant={lastInspection.alerted ? "danger" : "success"}
                        title={lastInspection.alerted ? "已触发告警" : "巡检通过"}
                      >
                        抽样 {lastInspection.sample_size} 条 · 异常 {lastInspection.flagged_count} 条 · 错题率{" "}
                        {(lastInspection.wrong_rate * 100).toFixed(1)}% · 红线命中 {lastInspection.redline_hits}
                      </Alert>
                    ) : null}
                    <div className="space-y-2 text-sm">
                      {reports.map((item) => (
                        <div key={item.id} className="rounded-lg border border-border px-4 py-2" data-testid="inspection-report">
                          {item.run_date} · 抽样 {item.sample_size} · 异常 {item.flagged_count} · 错题率{" "}
                          {(item.wrong_rate * 100).toFixed(1)}% · {item.alerted ? "已告警" : "未告警"}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            ),
          },
          {
            key: "metrics",
            label: "数据看板",
            content: (
              <div className="grid gap-4 sm:grid-cols-3" data-testid="metrics-card">
                <StatCard title="用户总数" value={metrics?.users_total ?? "—"} />
                <StatCard title="近 7 天活跃" value={metrics?.users_active_7d ?? "—"} />
                <StatCard
                  title="次日留存"
                  value={metrics ? `${Math.round(metrics.retention_d1 * 100)}%` : "—"}
                />
                <StatCard
                  title="七日留存"
                  value={metrics ? `${Math.round(metrics.retention_d7 * 100)}%` : "—"}
                />
                <StatCard
                  title="任务完成率（7 天）"
                  value={metrics ? `${Math.round(metrics.task_completion_rate_7d * 100)}%` : "—"}
                />
                <StatCard
                  title="续费率"
                  value={metrics ? `${Math.round(metrics.renewal_rate * 100)}%` : "—"}
                />
                <StatCard
                  title="掌握度提升（7 天）"
                  value={metrics ? `${(metrics.mastery_improvement * 100).toFixed(1)}%` : "—"}
                  tone="success"
                />
              </div>
            ),
          },
          {
            key: "experiments",
            label: "A/B 实验",
            content: (
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>创建实验（F-47）</CardTitle>
                    <CardDescription>同用户恒定同组；报告含两比例 z 检验与显著性结论。</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-2">
                      <Label htmlFor="experiment-key">实验 key</Label>
                      <Input
                        id="experiment-key"
                        data-testid="experiment-key"
                        value={experimentKey}
                        onChange={(event) => setExperimentKey(event.target.value)}
                        placeholder="prompt-v2"
                      />
                    </div>
                    <Button disabled={busy || !experimentKey.trim()} onClick={() => void handleCreateExperiment()} data-testid="create-experiment">
                      创建实验
                    </Button>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>实验列表</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {experiments.map((experiment) => (
                      <div
                        key={experiment.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-4 py-3 text-sm"
                        data-testid="experiment-row"
                      >
                        <div>
                          <p className="font-medium text-foreground">{experiment.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {experiment.key} · {experiment.status}
                          </p>
                        </div>
                        <Button size="sm" variant="outline" onClick={() => void handleReport(experiment.id)}>
                          查看报告
                        </Button>
                      </div>
                    ))}
                    {report ? (
                      <div className="space-y-2 rounded-lg border border-border p-4 text-sm" data-testid="experiment-report">
                        <p className="font-medium text-foreground">{report.conclusion}</p>
                        {report.variants.map((variant) => (
                          <p key={variant.name} className="text-muted-foreground">
                            {variant.name}：参与 {variant.participants} · 成功率{" "}
                            {(variant.conversion_rate * 100).toFixed(1)}%
                            {variant.p_value !== null ? ` · p=${variant.p_value}` : ""}
                            {variant.significant ? " · 显著" : ""}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </div>
            ),
          },
        ]}
      />
    </main>
  );
}
