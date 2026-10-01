import { expect, test } from "vitest";
import { DEFAULT_SETTINGS, mergeSettings, resolveModel } from "./store";

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
