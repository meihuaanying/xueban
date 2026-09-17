import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KnowledgeRadar, MathFormula, StatCard, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../data";

describe("Table", () => {
  it("渲染表头与数据行", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>知识点</TableHead>
            <TableHead>掌握度</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>一元一次方程</TableCell>
            <TableCell>82%</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByText("一元一次方程")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "掌握度" })).toBeTruthy();
  });
});

describe("StatCard", () => {
  it("渲染指标与上涨提示", () => {
    render(<StatCard title="本周练习" value={120} delta="较上周 +18%" tone="success" />);
    expect(screen.getByText("120")).toBeTruthy();
    expect(screen.getByText("较上周 +18%")).toBeTruthy();
  });
});

describe("KnowledgeRadar", () => {
  it("渲染雷达图标题", () => {
    render(
      <KnowledgeRadar
        title="掌握度雷达图"
        data={[
          { label: "方程", value: 80 },
          { label: "函数", value: 55 },
          { label: "几何", value: 70 },
        ]}
      />,
    );
    expect(screen.getByText("掌握度雷达图")).toBeTruthy();
  });
});

describe("MathFormula", () => {
  it("渲染 KaTeX 公式 HTML", () => {
    const { container } = render(<MathFormula formula="x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}" />);
    expect(container.querySelector(".katex")).toBeTruthy();
  });

  it("非法公式不抛异常", () => {
    const { container } = render(<MathFormula formula="\\frac{" />);
    expect(container.textContent).toBeTruthy();
  });
});
