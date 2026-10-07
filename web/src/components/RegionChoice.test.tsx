import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { RegionChoice } from "./RegionChoice";

const US = { region: "us", label: "US (Letter)", evidence: "Austin, TX" };

test("shows the suggestion with the JD's words and lets the user change it (P10.3)", async () => {
  const onChange = vi.fn();
  const { rerender } = render(<RegionChoice id="r" value="us" suggested={US} onChange={onChange} />);
  expect(screen.getByLabelText("Formatted for")).toHaveValue("us");
  expect(screen.getByText(/The job says “Austin, TX”\./)).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Formatted for"), "uk_eu");
  expect(onChange).toHaveBeenCalledWith("uk_eu");
  rerender(<RegionChoice id="r" value="uk_eu" suggested={US} onChange={onChange} />);
  expect(screen.getByText(/Suggested US \(Letter\): the job says “Austin, TX”/)).toBeInTheDocument();
  rerender(<RegionChoice id="r" value="other" suggested={{ region: "other", label: "Other (A4)", evidence: null }} onChange={onChange} />);
  expect(screen.getByText(/Nothing in the job says where/)).toBeInTheDocument();
});
