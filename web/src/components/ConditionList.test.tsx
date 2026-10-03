import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import type { Condition } from "../lib/types";
import { ConditionList } from "./ConditionList";

const CONDITIONS: Condition[] = [
  { id: "c1", text: "Current RN license in Arizona", kind: "licence", label: "Licence or registration", priority: "required", auto: null, note: null },
  { id: "c2", text: "Minimum 2 years of acute care experience", kind: "years", label: "Years of experience", priority: "required", auto: "met", note: "About 5.6 years." },
];

test("ticks the user's own conditions; years are checked by code", async () => {
  const onToggle = vi.fn();
  render(<ConditionList conditions={CONDITIONS} ticked={[]} onToggle={onToggle} />);
  await userEvent.click(screen.getByRole("checkbox", { name: /Current RN license in Arizona/ }));
  expect(onToggle).toHaveBeenCalledWith("c1");
  expect(screen.getAllByRole("checkbox")).toHaveLength(1); // the years line isn't a tick box
  expect(screen.getByText("About 5.6 years.")).toBeInTheDocument();
});
