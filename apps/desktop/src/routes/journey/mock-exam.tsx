"use client";

/** 新高考数学 19 题结构模考：组卷 → 限时作答 → 交卷 → 解答题批改。 */

import { Link } from "react-router-dom";

import { useMockExam } from "@/journey/use-mock-exam";

import { ExamReportView, ExamRunner, MockExamIntro } from "./mock-exam-parts";

export default function MockExamPage() {
  const exam = useMockExam();

  return (
    <section
      aria-label="新高考数学模考"
      data-testid="stage-mock-exam"
      className="flex min-w-0 flex-1 flex-col gap-md p-lg text-foreground"
    >
      <header className="flex flex-col gap-hair">
        <p className="text-app-xs text-muted-foreground">专项 · 新高考数学</p>
        <h1 className="text-app-2xl font-semibold">19 题结构模考</h1>
        <p className="text-app text-muted-foreground">
          按广东 2026 新高考数学卷结构组卷，客观题自动判分，解答题按步骤给分。
        </p>
      </header>

      {exam.phase === "intro" ? (
        <MockExamIntro busy={exam.busy} error={exam.error} onStart={() => void exam.start()} />
      ) : null}

      {exam.phase === "running" && exam.exam && exam.current ? (
        <ExamRunner
          exam={exam.exam}
          current={exam.current}
          index={exam.index}
          answers={exam.answers}
          answeredCount={exam.answeredCount}
          remaining={exam.remaining}
          busy={exam.busy}
          error={exam.error}
          onAnswer={exam.answer}
          onNavigate={exam.setIndex}
          onSubmit={() => void exam.submit()}
        />
      ) : null}

      {exam.phase === "report" && exam.exam && exam.report ? (
        <ExamReportView
          exam={exam.exam}
          report={exam.report}
          answers={exam.answers}
          grades={exam.grades}
          subjectiveCount={exam.subjectiveCount}
          busy={exam.busy}
          error={exam.error}
          onGrade={(questionId, answer) => void exam.gradeSubjective(questionId, answer)}
        />
      ) : null}

      <Link
        to="/journey/review"
        className="text-app-sm text-info underline"
        onClick={() => exam.discard()}
      >
        返回复盘
      </Link>
    </section>
  );
}
