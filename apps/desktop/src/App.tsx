/** 桌面端路由：登录守卫 + 旅程制学习闭环（P0，§7 旅程状态机驱动）。 */

import { Navigate, Route, Routes } from "react-router-dom";
import { Spinner } from "@xueban/ui";

import { AppLayout } from "@/components/app-layout";
import { JourneyProvider } from "@/journey/journey-context";
import { type JourneyStage, stagePath, STAGES } from "@/journey/stages";
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

/** stage id → 阶段页组件（避免在 JSX 里写六段三元） */
const STAGE_VIEWS: Record<JourneyStage, React.ComponentType> = {
  today: TodayStagePage,
  diagnosis: DiagnosisStagePage,
  plan: PlanStagePage,
  unit: UnitStagePage,
  mistakes: MistakesStagePage,
  review: ReviewStagePage,
};

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
                  <StageView stage={stage.id} />
                </RouteView>
              }
            />
          ))}
          <Route index element={<Navigate to={stagePath("today")} replace />} />
        </Route>
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <JourneyShell />
            </RequireAuth>
          }
        >
          <Route index element={<SettingsPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/journey/today" replace />} />
        <Route path="*" element={<Navigate to="/journey/today" replace />} />
      </Routes>
    </AuthProvider>
  );
}

/** 按 stage id 渲染对应阶段页 */
function StageView({ stage }: { stage: JourneyStage }) {
  const View = STAGE_VIEWS[stage];
  return <View />;
}

/** 阶段页容器：挂 data-journey-stage 便于 E2E 定位当前站点 */
function RouteView({ stageId, children }: { stageId: string; children: React.ReactNode }) {
  return <div data-journey-stage={stageId}>{children}</div>;
}
