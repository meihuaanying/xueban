import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JourneyStepper } from "./journey-blocks";
import { JourneyProvider } from "@/journey/journey-context";

/**
 * JourneyStepper 的 kids 档朗读（§4.1「所有文本支持 TTS」+ §7「无文字依赖导航」）。
 *
 * 步骤条是**每一站都要看的导航信息**，而一年级孩子很可能还不识字——这是 7 岁
 * 可用性检查单里最后一条 ⚠️。测试直接断言「朗读文案覆盖两处提示」，而不是只断言
 * 「有个喇叭图标」：图标在、读的内容不对，等于没做。
 */

class FakeUtterance {
  lang = "";
  rate = 1;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(readonly text: string) {}
}

const speak = vi.fn();
const cancel = vi.fn();

function stubSpeech(): void {
  vi.stubGlobal("speechSynthesis", { speak, cancel });
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
}

function renderStepper(theme: "kids" | "focus") {
  window.localStorage.setItem("xueban.theme", theme);
  window.localStorage.setItem("xueban.gradeBand", theme === "kids" ? "primary" : "junior");
  return render(
    <MemoryRouter>
      <JourneyProvider>
        <JourneyStepper />
      </JourneyProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  speak.mockClear();
  cancel.mockClear();
  stubSpeech();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("JourneyStepper · kids 档朗读入口", () => {
  it("kids 档给出朗读入口，focus 档不给（六页共用组件，不做成噪音）", () => {
    const kids = renderStepper("kids");
    expect(screen.getByTestId("journey-speak")).toBeTruthy();
    kids.unmount();

    renderStepper("focus");
    expect(screen.queryByTestId("journey-speak")).toBeNull();
    // 但提示文字本身在两种主题下都要有
    expect(screen.getByTestId("journey-next")).toBeTruthy();
  });

  it("朗读的是一句覆盖「当前 + 下一站」的话，而不是只读其中一半", () => {
    renderStepper("kids");
    fireEvent.click(screen.getByTestId("journey-speak"));

    expect(speak).toHaveBeenCalledTimes(1);
    const spoken = (speak.mock.calls[0]?.[0] as FakeUtterance).text;
    expect(spoken).toContain("当前在第");
    expect(spoken).toContain("下一站");
    const nextLabel = (screen.getByTestId("journey-next").textContent ?? "").replace("下一站：", "");
    expect(nextLabel.length).toBeGreaterThan(0);
    expect(spoken).toContain(nextLabel);
  });

  it("朗读先打断上一次，避免连点后两句叠着念", () => {
    renderStepper("kids");
    fireEvent.click(screen.getByTestId("journey-speak"));
    expect(cancel).toHaveBeenCalled();
  });

  it("没有 speechSynthesis 的环境只隐藏朗读入口，不抛错也不挡住前往下一站", () => {
    vi.unstubAllGlobals(); // 模拟不支持 Web Speech 的设备/浏览器
    renderStepper("kids");

    expect(screen.queryByTestId("journey-speak")).toBeNull();
    expect(screen.getByTestId("journey-next")).toBeTruthy();
    expect(screen.getByTestId("journey-advance")).toBeTruthy();
  });
});
