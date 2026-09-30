"use client";

/** onboarding：选学段 → 自动切主题 → 进入首次诊断（§7 P0）。 */
import { AudioButton, Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";
import { APP_NAME } from "@xueban/core";
import { useCallback } from "react";

import { useJourney } from "@/journey/journey-context";
import { GRADE_BANDS, type GradeBand } from "@/journey/stages";

const BANDS: { id: GradeBand; hint: string }[] = [
  { id: "primary", hint: "大字号、大按钮、全部文字可朗读，适合 6~9 岁。" },
  { id: "junior", hint: "信息密度更高，强调知识地图与掌握度。" },
  { id: "senior", hint: "面向高考复习，错题驱动 + 深度讲解。" },
];

export default function OnboardingPage() {
  const { band, setBand, goTo, theme } = useJourney();

  const choose = useCallback(
    (next: GradeBand) => {
      setBand(next);
      goTo("diagnosis");
    },
    [goTo, setBand],
  );

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-lg bg-background p-lg text-foreground"
      data-testid="onboarding"
    >
      <header className="flex flex-col items-center gap-xs text-center">
        <span className="text-app-sm text-muted-foreground">{APP_NAME} · 学习旅程</span>
        <div className="flex items-center gap-sm">
          <h1 className="text-app-3xl font-bold">选择你的学段</h1>
          <AudioButton text="选择你的学段" />
        </div>
        <p className="max-w-xl text-app-sm text-muted-foreground">
          学段决定界面风格与默认学科；选好后会自动切换主题，接着做一次诊断来生成属于你的学习规划。
        </p>
      </header>

      <ul className="grid w-full max-w-4xl gap-md md:grid-cols-3" data-testid="onboarding-bands">
        {BANDS.map(({ id, hint }) => {
          const preset = GRADE_BANDS[id];
          const selected = band === id;
          return (
            <li key={id}>
              <Card
                className={selected ? "h-full border-primary bg-primary-soft" : "h-full"}
                data-testid={`onboarding-band-${id}`}
              >
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {preset.label}
                    {preset.theme === "kids" ? (
                      <span className="text-app-xs text-primary">儿童模式</span>
                    ) : null}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-sm">
                  <p className="text-app-sm text-muted-foreground">{hint}</p>
                  <p className="text-app-xs text-muted-foreground">
                    默认学科：{preset.subject === "math" ? "数学" : preset.subject} · 难度基准{" "}
                    {preset.grade === "grade1" ? "一年级" : preset.grade === "grade7" ? "七年级" : "高一年级"}
                  </p>
                  <Button
                    onClick={() => choose(id)}
                    aria-pressed={selected}
                    data-testid={`onboarding-choose-${id}`}
                  >
                    {selected ? "继续诊断" : `以${preset.label}开始`}
                  </Button>
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>

      <p className="text-app-xs text-muted-foreground" data-testid="onboarding-theme">
        当前主题：{theme === "kids" ? "儿童模式" : "专注模式"}（选择学段后自动切换）
      </p>
    </main>
  );
}
