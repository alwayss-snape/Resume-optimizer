import { expect, test } from "vitest";
import { DEFAULT_SETTINGS, SETTINGS_KEY, mergeSettings, resolveModel, useApp } from "./store";

test("resolveModel keeps only a model the provider offers, and the default as null", () => {
  const offered = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"];
  expect(resolveModel("openai/gpt-oss-20b", offered)).toBe("openai/gpt-oss-20b");
  expect(resolveModel("openai/gpt-oss-120b", offered)).toBeNull();
  expect(resolveModel("qwen3:4b", offered)).toBeNull(); // saved under another provider
  expect(resolveModel("qwen3:4b", undefined)).toBeNull();
});

test("saved settings merge over the defaults and drop invalid values", () => {
  expect(mergeSettings(undefined)).toEqual(DEFAULT_SETTINGS);
  expect(mergeSettings({ theme: "light" })).toEqual({ ...DEFAULT_SETTINGS, theme: "light" });
  expect(mergeSettings({ theme: "neon", strictFactual: "yes", model: 3 })).toEqual(DEFAULT_SETTINGS);
});

test("the theme defaults to following the system", () => {
  expect(DEFAULT_SETTINGS.theme).toBe("system");
});

test("a 'dark' saved before the redesign becomes 'system' once; a later choice of dark is kept", async () => {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ state: { settings: { theme: "dark", strictFactual: true } }, version: 1 }));
  await useApp.persist.rehydrate();
  expect(useApp.getState().settings).toMatchObject({ theme: "system", strictFactual: true });

  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ state: { settings: { theme: "dark" } }, version: 2 }));
  await useApp.persist.rehydrate();
  expect(useApp.getState().settings.theme).toBe("dark");
  localStorage.removeItem(SETTINGS_KEY);
});
