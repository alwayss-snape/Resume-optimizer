import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { CvModeChoice } from "./CvModeChoice";

test("shows the suggested CV type with its signals and lets the user change it (P10.5)", async () => {
  const onChange = vi.fn();
  const suggested = { mode: "academic", label: "Academic CV", evidence: ["a “Professor” role", "an ORCID iD"] };
  render(<CvModeChoice id="m" value="academic" suggested={suggested} onChange={onChange} />);
  expect(screen.getByLabelText("CV type")).toHaveValue("academic");
  expect(screen.getByText(/Suggested as Academic CV: a “Professor” role, an ORCID iD\./)).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("CV type"), "standard");
  expect(onChange).toHaveBeenCalledWith("standard");
});
