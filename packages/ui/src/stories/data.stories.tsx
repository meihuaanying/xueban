import type { Story } from "@ladle/react";

import {
  KnowledgeRadar,
  MathFormula,
  StatCard,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../data";

const sample = [
  { label: "方程", value: 80 },
  { label: "函数", value: 55 },
  { label: "几何", value: 70 },
  { label: "统计", value: 90 },
];

export const RadarDefault: Story = () => <KnowledgeRadar title="掌握度雷达图" data={sample} />;
export const RadarTall: Story = () => <KnowledgeRadar data={sample} height={320} />;

export const FormulaInline: Story = () => <MathFormula formula="x = 2" />;
export const FormulaDisplay: Story = () => (
  <MathFormula displayMode formula="x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}" />
);

export const StatDefault: Story = () => <StatCard title="平均掌握度" value="72%" />;
export const StatWithDelta: Story = () => (
  <StatCard title="本周练习" value={120} delta="较上周 +18%" tone="success" />
);

export const TableDefault: Story = () => (
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
      <TableRow>
        <TableCell>二次函数</TableCell>
        <TableCell>58%</TableCell>
      </TableRow>
    </TableBody>
  </Table>
);
export const TableEmpty: Story = () => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>错题</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <TableRow>
        <TableCell>暂无错题，继续保持</TableCell>
      </TableRow>
    </TableBody>
  </Table>
);
