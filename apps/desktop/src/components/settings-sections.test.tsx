import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AboutSection,
  AccountSection,
  BehaviorSection,
  NotificationSection,
  SubscriptionSection,
} from "@/components/settings-sections";

const USER = {
  id: "u-1",
  phone: "13900000000",
  nickname: "小伴",
  role: "student",
  is_k12: true,
  subject: "math",
  grade: "grade1",
} as unknown as Parameters<typeof AccountSection>[0]["user"];

const SUBSCRIPTION = {
  plan: "trial",
  expires_at: "2026-10-07",
  auto_renew: false,
  trial_used: false,
} as unknown as Parameters<typeof SubscriptionSection>[0]["subscription"];

const PROFILE = {
  learning_style_label: "视觉型",
  independent_score: 0.62,
  assisted_score: 0.88,
  evidence: [{ feature: "hint_dependence", value: 0.4 }],
} as unknown as Parameters<typeof BehaviorSection>[0]["profile"];

describe("AccountSection", () => {
  it("渲染手机号、昵称与 K12 徽标", () => {
    render(<AccountSection user={USER} onRefresh={vi.fn()} />);
    expect(screen.getByTestId("account-phone")).toHaveTextContent("13900000000");
    expect(screen.getByText(/昵称：小伴/)).toBeInTheDocument();
    expect(screen.getAllByText(/已开启/).length).toBeGreaterThan(0);
    expect(screen.getByText(/角色：学生/)).toBeInTheDocument();
  });

  it("无用户时回退为占位符，未开启 K12", () => {
    render(<AccountSection user={null} onRefresh={vi.fn()} />);
    expect(screen.getByTestId("account-phone")).toHaveTextContent("—");
    expect(screen.getByText(/昵称：未设置/)).toBeInTheDocument();
    expect(screen.getByText(/K12 保护：/)).toBeInTheDocument();
    expect(screen.getAllByText(/未开启/).length).toBeGreaterThan(0);
  });

  it("家长角色显示家长文案", () => {
    render(
      <AccountSection user={{ ...USER, role: "parent" } as typeof USER} onRefresh={vi.fn()} />,
    );
    expect(screen.getByText(/角色：家长/)).toBeInTheDocument();
  });

  it("刷新按钮触发 onRefresh", () => {
    const onRefresh = vi.fn();
    render(<AccountSection user={USER} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("非 Tauri 环境显示浏览器本地存储说明", () => {
    render(<AccountSection user={USER} onRefresh={vi.fn()} />);
    expect(screen.getByText(/浏览器本地存储/)).toBeInTheDocument();
  });
});

describe("SubscriptionSection", () => {
  it("试用中显示到期时间且不开通按钮", () => {
    render(
      <SubscriptionSection subscription={SUBSCRIPTION} onStartTrial={vi.fn()} trialPending={false} />,
    );
    expect(screen.getByTestId("subscription-plan")).toHaveTextContent("试用中");
    expect(screen.getByText(/到期时间：2026-10-07/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开通 7 天试用|开通中/ })).toBeNull();
  });

  it("未订阅时套餐回退为破折号", () => {
    render(
      <SubscriptionSection subscription={undefined} onStartTrial={vi.fn()} trialPending={false} />,
    );
    expect(screen.getByTestId("subscription-plan")).toHaveTextContent("—");
  });

  it("免费版未试用过时展示开通按钮并可点击", () => {
    const onStartTrial = vi.fn();
    render(
      <SubscriptionSection
        subscription={
          { plan: "free", expires_at: null, auto_renew: false, trial_used: false } as typeof SUBSCRIPTION
        }
        onStartTrial={onStartTrial}
        trialPending={false}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "开通 7 天试用" }));
    expect(onStartTrial).toHaveBeenCalledTimes(1);
  });

  it("开通进行中按钮禁用并显示开通中", () => {
    render(
      <SubscriptionSection
        subscription={
          { plan: "free", expires_at: null, auto_renew: false, trial_used: false } as typeof SUBSCRIPTION
        }
        onStartTrial={vi.fn()}
        trialPending
      />,
    );
    expect(screen.getByRole("button", { name: "开通中…" })).toBeDisabled();
  });

  it("试用已用过时给出提示而非开通按钮", () => {
    render(
      <SubscriptionSection
        subscription={
          { plan: "free", expires_at: null, auto_renew: true, trial_used: true } as typeof SUBSCRIPTION
        }
        onStartTrial={vi.fn()}
        trialPending={false}
      />,
    );
    expect(screen.getByText(/试用已使用过/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "开通 7 天试用" })).toBeNull();
  });

  it("专业版显示专业版并开启自动续费文案", () => {
    render(
      <SubscriptionSection
        subscription={
          { plan: "pro", expires_at: "2027-01-01", auto_renew: true, trial_used: false } as typeof SUBSCRIPTION
        }
        onStartTrial={vi.fn()}
        trialPending={false}
      />,
    );
    expect(screen.getByTestId("subscription-plan")).toHaveTextContent("专业版");
    expect(screen.getByText(/自动续费：已开启/)).toBeInTheDocument();
  });
});

describe("BehaviorSection", () => {
  it("有画像时渲染风格、独立能力分与可解释依据", () => {
    render(<BehaviorSection profile={PROFILE} />);
    expect(screen.getByText("视觉型")).toBeInTheDocument();
    expect(screen.getByText(/0\.62/)).toBeInTheDocument();
    expect(screen.getByText(/hint_dependence/)).toBeInTheDocument();
  });

  it("独立能力分缺失时回退为破折号", () => {
    render(
      <BehaviorSection
        profile={{ ...PROFILE, independent_score: null } as unknown as typeof PROFILE}
      />,
    );
    expect(screen.getByText(/—/)).toBeInTheDocument();
  });

  it("无画像时给出数据不足空态", () => {
    render(<BehaviorSection profile={undefined} />);
    expect(screen.getByText(/数据不足/)).toBeInTheDocument();
  });
});

describe("NotificationSection", () => {
  it("两个开关按当前值渲染且可切换回调", () => {
    const onReviewChange = vi.fn();
    const onTaskChange = vi.fn();
    const { rerender } = render(
      <NotificationSection
        reviewNotify
        taskNotify={false}
        onReviewChange={onReviewChange}
        onTaskChange={onTaskChange}
      />,
    );
    const switches = () => screen.getAllByRole("switch");
    const review = switches()[0]!;
    const task = switches()[1]!;
    expect(review).toBeChecked();
    expect(task).not.toBeChecked();
    fireEvent.click(review);
    expect(onReviewChange).toHaveBeenCalledWith(false);
    fireEvent.click(task);
    expect(onTaskChange).toHaveBeenCalledWith(true);
    rerender(
      <NotificationSection
        reviewNotify={false}
        taskNotify
        onReviewChange={onReviewChange}
        onTaskChange={onTaskChange}
      />,
    );
    expect(switches()[0]).not.toBeChecked();
    expect(switches()[1]).toBeChecked();
  });
});

describe("AboutSection", () => {
  it("渲染版本与守护型红线说明，并可注入子节点", () => {
    render(
      <AboutSection>
        <span>附加信息</span>
      </AboutSection>,
    );
    expect(screen.getByText(/v0\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/不直接给答案/)).toBeInTheDocument();
    expect(screen.getByText("附加信息")).toBeInTheDocument();
  });
});
