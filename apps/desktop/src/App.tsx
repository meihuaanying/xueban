/** 桌面端路由：登录守卫 + 旅程制学习闭环（P0，§7 旅程状态机驱动）。 */

import { Navigate, Route, Routes } from "react-router-dom";
import { Spinner } from "@xueban/ui";

import { AppLayout } from "@/components/app-layout";
import { JourneyProvider } from "@/journey/journey-context";
import { stagePath, STAGES } from "@/journey/stages";
import { AuthProvider, useAuth } from "@/lib/auth";
import DiagnosisStagePage from "@/routes/journey/diagnosis";
import LoginPage from "@/routes/login";
import MistakesStagePage from "@/routes/journey/mistakes";
import OnboardingPage from "@/routes/onboarding";
import PlanStagePage from "@/routes/journey/plan";
import ReviewStagePage from "@/routes/journey/review";
import SettingsPage from "@/routes/settings";
import TodayStagePage from "@/routes/journey/today";
import UnitStagePage from "@/routes/journey/unit";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center" aria-label="登录态检查中">
        <Spinner size="lg" />
      </div>
    );
  }
  if (status === "anonymous") {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** 旅程骨架：JourneyProvider 提供状态机与双主题，AppLayout 提供壳 */
function JourneyShell() {
  return (
    <JourneyProvider>
      <AppLayout />
    </JourneyProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/onboarding"
          element={
            <RequireAuth>
              <JourneyShell />
            </RequireAuth>
          }
        >
          <Route index element={<OnboardingPage />} />
        </Route>
        <Route
          path="/journey"
          element={
            <RequireAuth>
              <JourneyShell />
            </RequireAuth>
          }
        >
          {STAGES.map((stage) => (
            <Route
              key={stage.id}
              path={stage.id}
              element={
                <RouteView stageId={stage.id}>
                  {stage.id === "today" ? <TodayStagePage /> : null}
                  {stage.id === "diagnosis" ? <DiagnosisStagePage /> : null}
                  {stage.id === "plan" ? <PlanStagePage /> : null}
                  {stage.id === "unit" ? <UnitStagePage /> : null}
                  {stage.id === "mistakes" ? <MistakesStagePage /> : null}
                  {stage.id === "review" ? <ReviewStagePage /> : null}
                </RouteView>
              }
            />
          ))}
          <Route index element={<Navigate to={stagePath("today")} replace />} />
        </Route>
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/journey/today" replace />} />
        <Route path="*" element={<Navigate to="/journey/today" replace />} />
      </Routes>
    </AuthProvider>
  );
}

/** 阶段页懒加载占位：Suspense 边界在 AppLayout 之上，此处仅做引入 */
function RouteView({ stageId, children }: { stageId: string; children: React.ReactNode }) {
  return <div data-journey-stage={stageId}>{children}</div>;
}
