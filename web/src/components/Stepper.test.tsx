import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";
import { useApp } from "../lib/store";
import { Stepper } from "./Stepper";

beforeEach(() => useApp.setState({ step: "upload", reached: 0 }));

test("marks the current step and offers no way forward", () => {
  const { container } = render(<Stepper />);
  expect(container.querySelector('[aria-current="step"]')).toHaveTextContent("Upload");
  expect(screen.queryByRole("button")).toBeNull();
});

test("steps already reached are links back; later ones are not", async () => {
  useApp.getState().advance("review");
  useApp.getState().goTo("details");
  render(<Stepper />);
  const back = screen.getAllByRole("button", { name: /Upload/ })[0];
  expect(screen.getByRole("button", { name: /Review/ })).toBeInTheDocument(); // reached, ahead of current
  expect(screen.queryByRole("button", { name: /Results/ })).toBeNull();
  await userEvent.click(back);
  expect(useApp.getState().step).toBe("upload");
});

test("on phones a back button returns to the previous step", async () => {
  useApp.getState().advance("details");
  render(<Stepper />);
  await userEvent.click(screen.getByRole("button", { name: "Back to Upload" }));
  expect(useApp.getState().step).toBe("upload");
});

test("goTo never jumps past the furthest step reached", () => {
  useApp.getState().goTo("results");
  expect(useApp.getState().step).toBe("upload");
});
