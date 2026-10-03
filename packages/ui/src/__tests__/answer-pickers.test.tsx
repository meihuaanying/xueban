/**
 * 小学题型的作答控件测试（§6.1 / §4.1）。
 *
 * 重点验证交互契约而不是像素：LinkMatcher 是「点左再右」的两步配对，
 * CorrectBurst 必须尊重 prefers-reduced-motion。
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CorrectBurst, JUDGE_OPTIONS, LinkMatcher } from "../learning/answer-pickers";

const LEFT = ["铅笔盒", "乒乓球"];
const RIGHT = ["长方形", "圆形"];

describe("LinkMatcher（连线题作答台）", () => {
  it("先点左再点右才完成一次配对", () => {
    const onChange = vi.fn();
    render(<LinkMatcher left={LEFT} right={RIGHT} onChange={onChange} />);

    fireEvent.click(screen.getByTestId("link-left-铅笔盒"));
    fireEvent.click(screen.getByTestId("link-right-长方形"));

    expect(onChange).toHaveBeenCalledWith({ 铅笔盒: "长方形" }, false);
  });

  it("没选中左项时右项不可点（先点左才让点右）", () => {
    render(<LinkMatcher left={LEFT} right={RIGHT} />);
    expect(screen.getByTestId("link-right-长方形")).toBeDisabled();
  });

  it("点已配对的右项解除配对", () => {
    const onChange = vi.fn();
    render(
      <LinkMatcher
        left={LEFT}
        right={RIGHT}
        value={{ 铅笔盒: "长方形" }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("link-left-铅笔盒"));
    fireEvent.click(screen.getByTestId("link-right-长方形"));

    expect(onChange).toHaveBeenCalledWith({}, false);
  });

  it("同一右项被两个左项占用时先解旧配，不会出现一右配二左", () => {
    const onChange = vi.fn();
    render(
      <LinkMatcher
        left={LEFT}
        right={RIGHT}
        value={{ 铅笔盒: "长方形" }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("link-left-乒乓球"));
    fireEvent.click(screen.getByTestId("link-right-长方形"));

    expect(onChange).toHaveBeenCalledWith({ 乒乓球: "长方形" }, false);
  });

  it("全部配好时 complete 为真并再触发一次 onComplete", () => {
    const onChange = vi.fn();
    const onComplete = vi.fn();
    render(
      <LinkMatcher
        left={LEFT}
        right={RIGHT}
        value={{ 乒乓球: "圆形" }}
        onChange={onChange}
        onComplete={onComplete}
      />,
    );
    fireEvent.click(screen.getByTestId("link-left-铅笔盒"));
    fireEvent.click(screen.getByTestId("link-right-长方形"));

    expect(onChange).toHaveBeenCalledWith(
      { 铅笔盒: "长方形", 乒乓球: "圆形" },
      true,
    );
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("进度文案如实反映已配对数", () => {
    render(<LinkMatcher left={LEFT} right={RIGHT} value={{ 铅笔盒: "长方形" }} />);
    expect(screen.getByTestId("link-progress")).toHaveTextContent("已配对 1 / 2");
  });

  it("disabled 时两侧都不能操作", () => {
    render(<LinkMatcher left={LEFT} right={RIGHT} disabled />);
    expect(screen.getByTestId("link-left-铅笔盒")).toBeDisabled();
    expect(screen.getByTestId("link-right-长方形")).toBeDisabled();
  });
});

describe("JUDGE_OPTIONS（判断题默认按钮）", () => {
  it("提供对/错两个大按钮，key 直接是中文答案", () => {
    expect(JUDGE_OPTIONS.map((option) => option.key)).toEqual(["对", "错"]);
  });
});

describe("CorrectBurst（答对撒花）", () => {
  it("撒花不可交互、不参与朗读，且尊重 prefers-reduced-motion", () => {
    const { container } = render(<CorrectBurst count={5} />);
    expect(screen.queryByText(/./)).toBeNull();
    expect(container.querySelector("[aria-hidden]")).not.toBeNull();
    const style = container.querySelector("style")?.textContent ?? "";
    expect(style).toContain("prefers-reduced-motion");
    expect(container.querySelectorAll(".xb-confetti-piece")).toHaveLength(5);
  });
});
