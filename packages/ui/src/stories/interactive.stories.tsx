import type { Story } from "@ladle/react";

import { Accordion, Breadcrumb, Pagination, Tabs } from "../navigation";
import { Dialog, Tooltip } from "../overlay";
import { Checkbox, Input, Label, Select, Switch, Textarea } from "../forms";

export const InputDefault: Story = () => <Input placeholder="请输入手机号" />;
export const InputInvalid: Story = () => <Input invalid defaultValue="bad" />;

export const TextareaDefault: Story = () => <Textarea placeholder="写下你的解题步骤" />;
export const TextareaDisabled: Story = () => <Textarea disabled placeholder="不可编辑" />;

export const LabelDefault: Story = () => <Label>手机号</Label>;
export const LabelWithInput: Story = () => (
  <div className="space-y-1">
    <Label htmlFor="phone">手机号</Label>
    <Input id="phone" />
  </div>
);

export const SelectDefault: Story = () => (
  <Select
    placeholder="请选择科目"
    options={[
      { value: "math", label: "数学" },
      { value: "english", label: "英语" },
    ]}
  />
);
export const SelectNoPlaceholder: Story = () => (
  <Select options={[{ value: "cet", label: "四级" }]} defaultValue="cet" />
);

export const CheckboxDefault: Story = () => <Checkbox label="记住登录状态" />;
export const CheckboxChecked: Story = () => <Checkbox label="已同意协议" defaultChecked />;

export const SwitchOff: Story = () => <Switch label="通知提醒" />;
export const SwitchOn: Story = () => <Switch label="AI 讲解" defaultChecked />;

export const TabsDefault: Story = () => (
  <Tabs
    tabs={[
      { key: "diagnosis", label: "诊断", content: "完成入学诊断" },
      { key: "plan", label: "规划", content: "生成每日任务" },
    ]}
  />
);
export const TabsWithDefaultKey: Story = () => (
  <Tabs
    defaultKey="b"
    tabs={[
      { key: "a", label: "A", content: "内容 A" },
      { key: "b", label: "B", content: "内容 B" },
    ]}
  />
);

export const AccordionFaq: Story = () => (
  <Accordion
    items={[
      { key: "1", title: "守护型讲解是什么？", content: "分层提示，不直接给答案。" },
      { key: "2", title: "如何收费？", content: "月/季/年订阅。" },
    ]}
  />
);
export const AccordionSingle: Story = () => (
  <Accordion items={[{ key: "only", title: "只有一条", content: "内容" }]} />
);

export const BreadcrumbDefault: Story = () => (
  <Breadcrumb items={[{ label: "首页", href: "/" }, { label: "帮助中心" }]} />
);
export const BreadcrumbDeep: Story = () => (
  <Breadcrumb
    items={[{ label: "首页", href: "/" }, { label: "家长端", href: "/parents" }, { label: "周报" }]}
  />
);

export const PaginationMiddle: Story = () => <Pagination page={2} pageCount={5} />;
export const PaginationFirst: Story = () => <Pagination page={1} pageCount={3} />;

export const DialogOpen: Story = () => (
  <Dialog open title="开始试用">
    试用 7 天，随时可取消。
  </Dialog>
);
export const DialogClosed: Story = () => (
  <Dialog open={false} title="隐藏的对话框">
    不应显示
  </Dialog>
);

export const TooltipDefault: Story = () => <Tooltip content="掌握度由 BKT 动态计算">掌握度</Tooltip>;
export const TooltipLong: Story = () => (
  <Tooltip content="连续答错会触发前置知识回溯">卡顿检测</Tooltip>
);
