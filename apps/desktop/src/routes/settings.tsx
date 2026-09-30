/** 设置页（T5.7）：账号、订阅、通知与关于；数据层使用 TanStack Query。 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AboutSection,
  AccountSection,
  BehaviorSection,
  NotificationSection,
  SubscriptionSection,
} from "@/components/settings-sections";
import { ErrorBlock, LoadingBlock, SectionTitle } from "@/components/state";
import { ApiError, api, type BehaviorProfile, type SubscriptionState } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [reviewNotify, setReviewNotify] = useState(true);
  const [taskNotify, setTaskNotify] = useState(true);

  const subscriptionQuery = useQuery<SubscriptionState>({
    queryKey: ["billing", "subscription"],
    queryFn: api.subscription,
  });
  const behaviorQuery = useQuery<BehaviorProfile>({
    queryKey: ["profile", "behavior"],
    queryFn: api.behavior,
  });
  const trialMutation = useMutation({
    mutationFn: api.startTrial,
    onSuccess: (data) => {
      queryClient.setQueryData(["billing", "subscription"], data);
    },
    onError: (caught) => {
      setError(caught instanceof ApiError ? caught.message : "试用开通失败。");
    },
  });

  if (subscriptionQuery.isPending) return <LoadingBlock rows={3} label="加载设置" />;

  if (subscriptionQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl">
        <ErrorBlock
          message={
            subscriptionQuery.error instanceof ApiError
              ? subscriptionQuery.error.message
              : "加载设置数据失败。"
          }
          onRetry={() => void subscriptionQuery.refetch()}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <SectionTitle hint="账号信息与订阅状态实时来自 API；登录态持久化于系统凭据库。">设置</SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <AccountSection user={user} onRefresh={() => void refreshUser()} />

      <SubscriptionSection
        subscription={subscriptionQuery.data}
        trialPending={trialMutation.isPending}
        onStartTrial={() => void trialMutation.mutate()}
      />

      <BehaviorSection profile={behaviorQuery.data} />

      <NotificationSection
        reviewNotify={reviewNotify}
        taskNotify={taskNotify}
        onReviewChange={setReviewNotify}
        onTaskChange={setTaskNotify}
      />

      <AboutSection />
    </div>
  );
}
