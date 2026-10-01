import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";
import { DEFAULT_SETTINGS, useApp } from "../lib/store";
import { SettingsPopover } from "./SettingsPopover";

const config = { provider: "groq", provider_label: "Groq (cloud)", models: ["openai/gpt-oss-120b", "openai/gpt-oss-20b"] };

beforeEach(() => useApp.setState({ settings: DEFAULT_SETTINGS }));

test("opens, changes settings, and closes on Escape", async () => {
  const user = userEvent.setup();
  render(<SettingsPopover config={config} />);
  const gear = screen.getByRole("button", { name: "Settings" });
  expect(gear).toHaveAttribute("aria-expanded", "false");

  await user.click(gear);
  expect(screen.getByRole("group", { name: "Settings" })).toBeInTheDocument();
  expect(screen.getByLabelText("AI MODEL")).toHaveFocus(); // focus moves into the menu
  expect(screen.getByText("Provider: Groq (cloud)")).toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("AI MODEL"), "openai/gpt-oss-20b");
  await user.click(screen.getByRole("switch", { name: /Strict factual mode/ }));
  await user.click(screen.getByRole("radio", { name: "Light" }));
  expect(useApp.getState().settings).toMatchObject({ model: "openai/gpt-oss-20b", strictFactual: true, theme: "light" });

  await user.selectOptions(screen.getByLabelText("AI MODEL"), "openai/gpt-oss-120b");
  expect(useApp.getState().settings.model).toBeNull(); // the default is stored as "no choice"

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("group", { name: "Settings" })).toBeNull();
  expect(gear).toHaveFocus();
});

test("a saved model the provider no longer offers falls back to the default", async () => {
  useApp.setState({ settings: { ...DEFAULT_SETTINGS, model: "qwen3:4b" } });
  render(<SettingsPopover config={config} />);
  await userEvent.click(screen.getByRole("button", { name: "Settings" }));
  expect(screen.getByLabelText("AI MODEL")).toHaveValue("openai/gpt-oss-120b");
});

test("says so when the server can't be reached", async () => {
  render(<SettingsPopover config={null} />);
  await userEvent.click(screen.getByRole("button", { name: "Settings" }));
  expect(screen.getByLabelText("AI MODEL")).toBeDisabled();
  expect(screen.getByText(/Can't reach the server/)).toBeInTheDocument();
});

test("switches are named by their label, with the help as description", async () => {
  render(<SettingsPopover config={config} />);
  await userEvent.click(screen.getByRole("button", { name: "Settings" }));
  const reuse = screen.getByRole("switch", { name: "Reuse my answers" });
  expect(reuse).toHaveAccessibleDescription(/Never shared/);
  await userEvent.click(reuse);
  expect(useApp.getState().settings.rememberAnswers).toBe(false);
});
