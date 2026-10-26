"use client";

/** onboarding：选学段 → 选年级 → 自动切主题 → 进入首次诊断（§7 P0；全学段扩展）。 */
import { AudioButton, Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";
import { APP_NAME } from "@xueban/core";
import { useCallback, useState } from "react";

import { useJourney } from "@/journey/journey-context";
import { GRADE_BANDS, gradeLabel, type GradeBand } from "@/journey/stages";

const BANDS: { id: GradeBand; hint: string }[] = [
  { id: "primary", hint: "大字号、大按钮、全部文字可朗读，适合 6~12 岁。" },
  { id: "junior", hint: "信息密度更高，强调知识地图与掌握度。" },
  { id: "senior", hint: "面向高考复习，错题驱动 + 深度讲解。" },
];

export default function OnboardingPage() {
  const { setBand, grade, setGrade, goTo, theme } = useJourney();
  // 引导流程固定从「选学段」开始：即使旧会话已存过学段，也不跳过第一步，
  // 否则用户（和 E2E）会在年级步里找不到自己学段的年级按钮。
  const [step, setStep] = useState<"band" | "grade">("band");
  const [pickedBand, setPickedBand] = useState<GradeBand | null>(null);

  const chooseBand = useCallback(
    (next: GradeBand) => {
      setBand(next);
      setPickedBand(next);
      setStep("grade");
    },
    [setBand],
  );

  const chooseGrade = useCallback(
    (next: string) => {
      setGrade(next);
      goTo("diagnosis");
    },
    [goTo, setGrade],
  );

  // 头部文案与卡片列表共用同一判据：只看「当前步 + 已选学段」，
  // 否则点「重选学段」回到列表时，标题还停在「选择你的年级」。
  const preset = step === "grade" && pickedBand ? GRADE_BANDS[pickedBand] : null;

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-lg bg-background p-lg text-foreground"
      data-testid="onboarding"
    >
      <header className="flex flex-col items-center gap-xs text-center">
        <span className="text-app-sm text-muted-foreground">{APP_NAME} · 学习旅程</span>
        <div className="flex items-center gap-sm">
          <h1 className="text-app-3xl font-bold">{preset ? "选择你的年级" : "选择你的学段"}</h1>
          <AudioButton text={preset ? "选择你的年级" : "选择你的学段"} />
        </div>
        <p className="max-w-xl text-app-sm text-muted-foreground">
          {preset
            ? "年级决定教材进度：诊断和练习会按你年级的知识点出题。"
            : "学段决定界面风格与默认学科；选好后会自动切换主题，接着选年级。"}
        </p>
      </header>

      {preset && step === "grade" ? (
        <ul
          className="grid w-full max-w-3xl grid-cols-2 gap-sm md:grid-cols-3"
          data-testid="onboarding-grades"
        >
          {preset.grades.map((option) => {
            const selected = grade === option;
            return (
              <li key={option}>
                <Card
                  className={selected ? "h-full border-primary bg-primary-soft" : "h-full"}
                  data-testid={`onboarding-grade-${option}`}
                >
                  <CardContent className="flex h-full flex-col items-start gap-sm">
                    <span className="text-app-lg font-semibold">{gradeLabel(option)}</span>
                    <Button
                      onClick={() => chooseGrade(option)}
                      aria-pressed={selected}
                      data-testid={`onboarding-choose-${option}`}
                    >
                      {selected ? "继续诊断" : `以${gradeLabel(option)}开始`}
                    </Button>
                  </CardContent>
                </Card>
              </li>
            );
          })}
          <li className="col-span-full">
            <Button
              variant="outline"
              onClick={() => setStep("band")}
              data-testid="onboarding-back"
            >
              ← 重选学段
            </Button>
          </li>
        </ul>
      ) : (
        <ul className="grid w-full max-w-4xl gap-md md:grid-cols-3" data-testid="onboarding-bands">
          {BANDS.map(({ id, hint }) => {
            const bandPreset = GRADE_BANDS[id];
            return (
              <li key={id}>
                <Card className="h-full" data-testid={`onboarding-band-${id}`}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      {bandPreset.label}
                      {bandPreset.theme === "kids" ? (
                        <span className="text-app-xs text-primary">儿童模式</span>
                      ) : null}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-sm">
                    <p className="text-app-sm text-muted-foreground">{hint}</p>
                    <p className="text-app-xs text-muted-foreground">
                      默认学科：{bandPreset.subject === "math" ? "数学" : bandPreset.subject}
                    </p>
                    <Button
                      onClick={() => chooseBand(id)}
                      data-testid={`onboarding-choose-${id}`}
                    >
                      选择{bandPreset.label}
                    </Button>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-app-xs text-muted-foreground" data-testid="onboarding-theme">
        当前主题：{theme === "kids" ? "儿童模式" : "专注模式"}（选择学段后自动切换）
      </p>
    </main>
  );
}
