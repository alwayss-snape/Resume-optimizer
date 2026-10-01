import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import type { Decision } from "../lib/review";
import { DRAFTED } from "../test/fixtures";
import { ProposalCard } from "./ProposalCard";

const proposal = DRAFTED.proposals[0];

function Harness({ onNavigate = vi.fn() }: { onNavigate?: (s: 1 | -1) => void }) {
  const [decision, setDecision] = useState<Decision>("accept");
  const [text, setText] = useState<string | null>(null);
  return (
    <ProposalCard proposal={proposal} index={0} decision={decision} text={text ?? proposal.proposed}
      edited={text !== null} onDecide={setDecision} onEdit={setText} onNavigate={onNavigate} />
  );
}

test("shows the diff: added words marked, keywords bold", () => {
  render(<Harness />);
  expect(screen.getByText("forecasting").closest("ins")).not.toBeNull();
  expect(screen.getAllByText("Python")[1].closest("strong")).not.toBeNull();
});

test("keyboard: R rejects, Undo restores, arrows navigate", async () => {
  const onNavigate = vi.fn();
  const user = userEvent.setup();
  render(<Harness onNavigate={onNavigate} />);
  screen.getByRole("article").focus();
  await user.keyboard("{ArrowDown}");
  expect(onNavigate).toHaveBeenCalledWith(1);
  await user.keyboard("r");
  expect(screen.getByRole("article", { name: /rejected/ })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Undo" }));
  expect(screen.getByRole("button", { name: /Accepted/ })).toHaveAttribute("aria-pressed", "true");
});

test("E edits; saving keeps the user's wording; Escape cancels", async () => {
  const user = userEvent.setup();
  render(<Harness />);
  screen.getByRole("article").focus();
  await user.keyboard("e");
  const box = screen.getByLabelText("YOUR VERSION");
  expect(box).toHaveFocus();
  await user.clear(box);
  await user.type(box, "Shipped forecasting dashboards");
  await user.click(screen.getByRole("button", { name: "Save edit" }));
  expect(screen.getByText("Shipped forecasting dashboards")).toBeInTheDocument();
  expect(screen.getByText("Your wording")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Edit" }));
  await user.keyboard("{Escape}");
  expect(screen.queryByLabelText("YOUR VERSION")).toBeNull();
});

test("normalizeEdit: blank or unchanged text means the proposal", async () => {
  const { normalizeEdit } = await import("./ProposalCard");
  expect(normalizeEdit("   ", "Built X")).toBeNull();
  expect(normalizeEdit("Built X ", "Built X")).toBeNull();
  expect(normalizeEdit("Shipped X", "Built X")).toBe("Shipped X");
});

test("focus returns to the card after Reject and Undo", async () => {
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole("button", { name: "Reject" }));
  await waitFor(() => expect(screen.getByRole("article", { name: /rejected/ })).toHaveFocus());
  await user.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(screen.getByRole("article")).toHaveFocus());
});

test("Cancel on a rejected card restores the rejection; Save accepts it", async () => {
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole("button", { name: "Reject" }));
  screen.getByRole("article").focus();
  await user.keyboard("e");
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("article", { name: /rejected/ })).toBeInTheDocument();

  screen.getByRole("article").focus();
  await user.keyboard("e");
  await user.type(screen.getByLabelText("YOUR VERSION"), " today");
  await user.click(screen.getByRole("button", { name: "Save edit" }));
  expect(screen.getByRole("button", { name: /Accepted/ })).toBeInTheDocument();
});

test("the card announces its shortcuts", () => {
  render(<Harness />);
  expect(screen.getByRole("article")).toHaveAttribute("aria-keyshortcuts", "A R E ArrowUp ArrowDown");
});
