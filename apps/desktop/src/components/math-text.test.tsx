import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MathText } from "./math-text";

describe("MathText 公式渲染（T5.4）", () => {
  it("行内公式与文本混合渲染", () => {
    const { container } = render(<MathText content={"先化简 $x^2 + 1$，再代入 $x = 2$ 计算。"} />);
    expect(container.textContent).toContain("先化简");
    expect(container.querySelectorAll(".katex").length).toBe(2);
  });

  it("块级公式使用 display 模式", () => {
    const { container } = render(<MathText content={"因式分解：\n$$a^2 - b^2 = (a+b)(a-b)$$"} />);
    expect(container.querySelectorAll(".katex-display").length).toBe(1);
  });

  it("纯文本内容不产生公式节点", () => {
    const { container } = render(<MathText content={"这道题考察的是乘法分配律。"} />);
    expect(container.querySelectorAll(".katex").length).toBe(0);
    expect(container.textContent).toContain("乘法分配律");
  });

  it("渲染快照稳定（三层提示文本）", () => {
    const { container } = render(
      <MathText content={"思路提示：观察 $\\frac{1}{2} + \\frac{1}{3}$ 的通分方式。"} />,
    );
    expect(container.innerHTML).toMatchSnapshot();
  });
});
