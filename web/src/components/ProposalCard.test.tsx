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

test("marked up (default): one proof line, removed words struck, added underlined, keywords bold", () => {
  const { container } = render(<Harness />);
  expect(screen.getByText("forecasting").closest("ins")).not.toBeNull();
  expect(screen.getByText("Python").closest("strong")).not.toBeNull();
  expect(container.querySelectorAll("p strong").length).toBe(1); // shared words appear once, not on two sides
});

test("side by side: the original and the proposal as two columns", () => {
  render(
    <ProposalCard proposal={proposal} index={0} decision="accept" text={proposal.proposed} edited={false}
      onDecide={vi.fn()} onEdit={vi.fn()} onNavigate={vi.fn()} view="split" />,
  );
  expect(screen.getByText("Original")).toBeInTheDocument();
  expect(screen.getByText("Proposed")).toBeInTheDocument();
  expect(screen.getAllByText("Python")[1].closest("strong")).not.toBeNull();
});

test("mergeProof weaves both sides; misaligned sides fall back", async () => {
  const { mergeProof } = await import("./DiffText");
  const merged = mergeProof(
    [{ text: "Made" , changed: true }, { text: "dashboards" }],
    [{ text: "Built", changed: true }, { text: "dashboards" }],
  );
  expect(merged?.map((p) => `${p.kind}:${p.text}`)).toEqual(["del:Made", "ins:Built", "same:dashboards"]);
  expect(mergeProof([{ text: "a" }], [{ text: "b" }])).toBeNull();
  const quiet = mergeProof(
    [{ text: "1,200" }, { text: "stores", changed: true }, { text: "Python", changed: true }],
    [{ text: "1,200" }, { text: "stores,", changed: true }, { text: "python", changed: true }],
  );
  // a comma alone is not a change; a change of case still is
  expect(quiet?.map((p) => `${p.kind}:${p.text}`)).toEqual(["same:1,200", "same:stores,", "del:Python", "ins:python"]);
  // the proposal's line breaks stay; a changed full stop stays marked
  const lines = mergeProof(
    [{ text: "Tools:" }, { text: "\n" }, { text: "SQL." , changed: true }],
    [{ text: "Tools:" }, { text: "\n" }, { text: "SQL", changed: true }],
  );
  expect(lines?.map((p) => `${p.kind}:${p.text}`)).toEqual(["same:Tools:", "same:\n", "del:SQL.", "ins:SQL"]);
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
  const box = screen.getByLabelText("Your version");
  expect(box).toHaveFocus();
  await user.clear(box);
  await user.type(box, "Shipped forecasting dashboards");
  await user.click(screen.getByRole("button", { name: "Save edit" }));
  expect(screen.getByText("Shipped forecasting dashboards")).toBeInTheDocument();
  expect(screen.getByText("Your wording")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Edit" }));
  await user.keyboard("{Escape}");
  expect(screen.queryByLabelText("Your version")).toBeNull();
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
  await user.type(screen.getByLabelText("Your version"), " today");
  await user.click(screen.getByRole("button", { name: "Save edit" }));
  expect(screen.getByRole("button", { name: /Accepted/ })).toBeInTheDocument();
});

test("the card announces its shortcuts", () => {
  render(<Harness />);
  expect(screen.getByRole("article")).toHaveAttribute("aria-keyshortcuts", "A R E ArrowUp ArrowDown");
});
