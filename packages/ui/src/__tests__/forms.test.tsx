import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Checkbox, Input, Label, Select, Switch, Textarea } from "../forms";

describe("Input / Textarea / Label", () => {
  it("输入框可输入并支持 invalid 态", () => {
    render(
      <div>
        <Label htmlFor="phone">手机号</Label>
        <Input id="phone" placeholder="请输入手机号" invalid />
      </div>,
    );
    const input = screen.getByLabelText("手机号");
    expect(input).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(input, { target: { value: "13800000000" } });
    expect(input).toHaveValue("13800000000");
  });

  it("多行输入可输入", () => {
    render(<Textarea placeholder="作答" />);
    const textarea = screen.getByPlaceholderText("作答");
    fireEvent.change(textarea, { target: { value: "解答过程" } });
    expect(textarea).toHaveValue("解答过程");
  });
});

describe("Select", () => {
  it("渲染选项并可选择", () => {
    render(
      <Select
        aria-label="科目"
        placeholder="请选择"
        options={[
          { value: "math", label: "数学" },
          { value: "english", label: "英语" },
        ]}
      />,
    );
    const select = screen.getByLabelText("科目");
    fireEvent.change(select, { target: { value: "english" } });
    expect(select).toHaveValue("english");
    expect(screen.getByRole("option", { name: "数学" })).toBeTruthy();
  });
});

describe("Checkbox / Switch", () => {
  it("复选框可勾选", () => {
    render(<Checkbox label="记住我" />);
    const checkbox = screen.getByLabelText("记住我");
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it("开关具备 switch 角色并可切换", () => {
    render(<Switch label="开启提醒" />);
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);
    expect(toggle).toBeChecked();
  });
});
