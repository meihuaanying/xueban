import type { Story } from "@ladle/react";

import { Badge } from "../feedback";
import { Button } from "../button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../card";

export const ButtonPrimary: Story = () => <Button>免费开始学习</Button>;
export const ButtonSecondary: Story = () => <Button variant="secondary">查看学习计划</Button>;

export const CardDefault: Story = () => (
  <Card className="max-w-sm">
    <CardHeader>
      <CardTitle>今日任务</CardTitle>
      <CardDescription>完成学习、练习与复习</CardDescription>
    </CardHeader>
    <CardContent>3 / 4 已完成</CardContent>
  </Card>
);
export const CardPlain: Story = () => <Card className="p-4">纯卡片内容</Card>;

export const BadgeDefault: Story = () => <Badge>新增</Badge>;
export const BadgeVariants: Story = () => (
  <div className="flex gap-2">
    <Badge variant="success">已掌握</Badge>
    <Badge variant="warning">待巩固</Badge>
    <Badge variant="danger">薄弱</Badge>
    <Badge variant="outline">草稿</Badge>
  </div>
);
