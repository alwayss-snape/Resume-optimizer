import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ProgressPanel, progressHandler, type Wait } from "./ProgressPanel";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

let push: (message: string, waitSeconds?: number) => void = () => {};

function Harness() {
  const [messages, setMessages] = useState<string[] | null>(["Analysing the job description"]);
  const [wait, setWait] = useState<Wait | null>(null);
  push = progressHandler(setMessages, setWait);
  return <ProgressPanel title="Working…" messages={messages ?? []} wait={wait} />;
}

test("an AI wait is one countdown under the running step, never a finished step (P9.7)", () => {
  render(<Harness />);
  act(() => push("Rewriting 10 bullets for Acme"));
  act(() => push("The free AI service asked us to wait; trying again in 18 s", 18));
  act(() => push("The free AI service asked us to wait; trying again in 27 s", 27));
  // Two steps, the second still running; one countdown line, the latest wait.
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(screen.getAllByTestId("wait")).toHaveLength(1);
  expect(screen.getByTestId("wait")).toHaveTextContent("trying again in 27 s");
  expect(screen.getAllByRole("listitem")[1]).toHaveTextContent(/^Rewriting 10 bullets for Acme.*\(in progress\)$/);
  act(() => vi.advanceTimersByTime(5000));
  expect(screen.getByTestId("wait")).toHaveTextContent("trying again in 22 s");
  act(() => vi.advanceTimersByTime(30000));
  expect(screen.getByTestId("wait")).toHaveTextContent("trying again now…");
  // The next step ends the wait.
  act(() => push("Fact-checking every proposal"));
  expect(screen.queryByTestId("wait")).not.toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
});
