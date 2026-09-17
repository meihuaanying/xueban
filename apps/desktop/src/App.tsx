/** 桌面端路由：登录守卫 + 主布局 + 八个功能页（T5.1）。 */

import { Navigate, Route, Routes } from "react-router-dom";
import { Spinner } from "@xueban/ui";

import { AppLayout } from "@/components/app-layout";
import { AuthProvider, useAuth } from "@/lib/auth";
import CoachPage from "@/routes/coach";
import DiagnosisPage from "@/routes/diagnosis";
import GradingPage from "@/routes/grading";
import LoginPage from "@/routes/login";
import PlanPage from "@/routes/plan";
import PracticePage from "@/routes/practice";
import ReviewPage from "@/routes/review";
import SettingsPage from "@/routes/settings";
import ToolsPage from "@/routes/tools";
import TutorPage from "@/routes/tutor";

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

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Navigate to="/diagnosis" replace />} />
          <Route path="/diagnosis" element={<DiagnosisPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/tutor" element={<TutorPage />} />
          <Route path="/coach" element={<CoachPage />} />
          <Route path="/practice" element={<PracticePage />} />
          <Route path="/grading" element={<GradingPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
