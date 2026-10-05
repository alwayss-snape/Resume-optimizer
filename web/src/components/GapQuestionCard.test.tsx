import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import type { GapQuestion } from "../lib/types";
import { GapQuestionCard } from "./GapQuestionCard";

const Q: GapQuestion = {
  id: "gap_1", requirement: "Fast learner with deep curiosity about AI; CI and unit tests", priority: "required",
  keywords: ["CI", "Fast learner"], question: "The job asks for CI and Fast learner.",
  kinds: { CI: "hard", "Fast learner": "soft" }, saved_keywords: [], saved_answer: "",
};

test("a ticked trait says it isn't listed under Skills (P9.12)", () => {
  const { rerender } = render(<GapQuestionCard question={Q} value={{ ticked: ["CI"], answer: "", target: "auto" }}
    onChange={() => {}} targets={[]} />);
  expect(screen.getByText(/Where did you use it\?/)).toBeInTheDocument();
  rerender(<GapQuestionCard question={Q} value={{ ticked: ["CI", "Fast learner"], answer: "", target: "auto" }}
    onChange={() => {}} targets={[]} />);
  expect(screen.getByText(/isn't listed under Skills; it shows through your work/)).toBeInTheDocument();
});
