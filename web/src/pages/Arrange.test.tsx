import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { ARRANGEMENT } from "../lib/arrange.test";
import type { TailorResult } from "../lib/types";
import { Arrange } from "./Arrange";

const RESULT = {
  success: true, alignment_score: 50, initial_alignment_score: 40, keyword_match: null, content_lint: null,
  addition_note: null, warnings: [], docx_warnings: [], pdf_warnings: [], target_pages: 1, pages: 1, applied: null,
  files: { docx: true, pdf: true, changes: true }, arrangement: ARRANGEMENT,
} as TailorResult;

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

test("moves, hides and keeps trimmed content, then sends one layout after a pause", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    new Response(JSON.stringify({ ...RESULT, arrangement: { ...ARRANGEMENT, layout: JSON.parse(String(init?.body)).layout } })));
  vi.stubGlobal("fetch", fetchMock);
  const onResult = vi.fn();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(<Arrange result={RESULT} onResult={onResult} onBack={() => undefined} />);
  expect(screen.getByRole("heading", { name: "Arrange and edit" })).toHaveFocus();

  await user.click(screen.getByRole("button", { name: 'Move "One" up' }));
  await user.click(screen.getByRole("checkbox", { name: /Summary/ }));
  await user.click(screen.getByRole("button", { name: "Keep it" }));
  expect(fetchMock).not.toHaveBeenCalled(); // waits for a pause
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).layout;
  expect(sent.bullet_order.exp_001).toEqual(["b1", "b3", "b2"]);
  expect(sent.pinned).toEqual(["b9"]);
  expect(sent.hidden_sections.length).toBe(1);
  expect(onResult).toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Undo" }));
  expect(screen.getByRole("button", { name: "Restore my original order" })).toBeEnabled();
});

test("edit keeps the user's wording and shows the file's text", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(RESULT))));
  render(<Arrange result={RESULT} onResult={() => undefined} onBack={() => undefined} />);
  await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
  const box = screen.getByRole("textbox", { name: "Your wording" });
  await user.clear(box);
  await user.type(box, "Said my way");
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(screen.getByText("Said my way")).toBeInTheDocument();
  expect(screen.getByText("your words")).toBeInTheDocument();
});
