import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { JourneyProvider, useJourney } from "./journey-context";

function Probe() {
  const { subject, setSubject, setBand } = useJourney();
  return (
    <div>
      <span data-testid="subject">{subject}</span>
      <button type="button" onClick={() => setBand("junior")}>
        junior
      </button>
      <button type="button" onClick={() => setSubject("physics")}>
        physics
      </button>
      <button type="button" onClick={() => setBand("primary")}>
        primary
      </button>
    </div>
  );
}

function renderProbe() {
  return render(
    <MemoryRouter>
      <JourneyProvider>
        <Probe />
      </JourneyProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  window.localStorage.clear();
});

describe("学科选择（广东九科）", () => {
  it("默认数学", () => {
    renderProbe();
    expect(screen.getByTestId("subject")).toHaveTextContent("math");
  });

  it("初中可切物理，切回小学时回退数学", () => {
    renderProbe();
    fireEvent.click(screen.getByText("junior"));
    fireEvent.click(screen.getByText("physics"));
    expect(screen.getByTestId("subject")).toHaveTextContent("physics");

    fireEvent.click(screen.getByText("primary"));
    // 小学只开语数英：物理不属于小学学段，必须回落到默认数学
    expect(screen.getByTestId("subject")).toHaveTextContent("math");
  });

  it("学科选择落盘，刷新后保持", () => {
    const first = renderProbe();
    fireEvent.click(screen.getByText("junior"));
    fireEvent.click(screen.getByText("physics"));
    first.unmount();

    renderProbe();
    expect(screen.getByTestId("subject")).toHaveTextContent("physics");
  });
});
