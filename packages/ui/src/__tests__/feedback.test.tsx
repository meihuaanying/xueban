import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Alert, Avatar, Badge, Progress, Separator, Skeleton, Spinner, Toast } from "../feedback";

describe("Badge / Separator / Skeleton / Spinner", () => {
  it("徽标渲染不同变体", () => {
    render(
      <div>
        <Badge>默认</Badge>
        <Badge variant="success">已掌握</Badge>
        <Badge variant="danger">待复习</Badge>
      </div>,
    );
    expect(screen.getByText("已掌握")).toBeTruthy();
    expect(screen.getByText("待复习")).toBeTruthy();
  });

  it("分隔线与骨架屏渲染", () => {
    render(
      <div>
        <Separator />
        <Skeleton data-testid="skeleton" />
      </div>,
    );
    expect(screen.getByRole("separator")).toBeTruthy();
    expect(screen.getByTestId("skeleton")).toBeTruthy();
  });

  it("加载指示器带 role=status", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toBeTruthy();
  });
});

describe("Alert / Progress / Avatar / Toast", () => {
  it("提示条展示标题与内容", () => {
    render(
      <Alert variant="warning" title="注意">
        今日时长已达上限
      </Alert>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("今日时长已达上限");
  });

  it("进度条 aria 属性正确", () => {
    render(<Progress value={60} max={100} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-label", "进度");
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "60");
    expect(progress).toHaveAttribute("aria-valuemax", "100");
  });

  it("头像无图时显示首字", () => {
    render(<Avatar name="学伴" />);
    expect(screen.getByText("学")).toBeTruthy();
  });

  it("Toast 可关闭", () => {
    const onClose = vi.fn();
    render(<Toast title="已保存" description="学习计划已更新" onClose={onClose} />);
    expect(screen.getByText("学习计划已更新")).toBeTruthy();
    screen.getByLabelText("关闭提示").click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
