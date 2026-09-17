import type { Story } from "@ladle/react";

export const Global: Story = ({ children }: { children?: React.ReactNode }) => (
  <div
    style={{
      minHeight: "100vh",
      padding: "24px",
      background: "#f7f9fc",
      fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
      color: "#0f172a",
    }}
  >
    {children}
  </div>
);
