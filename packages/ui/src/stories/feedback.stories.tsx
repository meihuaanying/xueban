import type { Story } from "@ladle/react";

import { Alert, Avatar, Progress, Separator, Skeleton, Spinner, Toast } from "../feedback";

export const AlertInfo: Story = () => <Alert title="提示">每天练习 20~30 分钟效果最佳。</Alert>;
export const AlertDanger: Story = () => (
  <Alert variant="danger" title="注意">
    今日使用时长已达家长设定上限。
  </Alert>
);

export const ProgressHalf: Story = () => <Progress value={50} />;
export const ProgressFull: Story = () => <Progress value={100} />;

export const SkeletonLine: Story = () => <Skeleton className="h-4 w-48" />;
export const SkeletonBlock: Story = () => <Skeleton className="h-24 w-full" />;

export const SpinnerMedium: Story = () => <Spinner />;
export const SpinnerSmall: Story = () => <Spinner size="sm" />;

export const SeparatorDefault: Story = () => <Separator />;
export const SeparatorNarrow: Story = () => <Separator className="w-32" />;

export const AvatarInitial: Story = () => <Avatar name="学伴" />;
export const AvatarSizes: Story = () => (
  <div className="flex items-center gap-2">
    <Avatar name="张三" size="sm" />
    <Avatar name="李四" size="md" />
    <Avatar name="王五" size="lg" />
  </div>
);

export const ToastSuccess: Story = () => <Toast variant="success" title="已保存" description="学习计划已更新" />;
export const ToastDanger: Story = () => <Toast variant="danger" title="提交失败" description="请检查网络后重试" />;
