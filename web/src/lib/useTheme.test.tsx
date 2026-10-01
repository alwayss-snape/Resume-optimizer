import { renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useTheme } from "./useTheme";

const listeners: (() => void)[] = [];
let prefersDark = false;

afterEach(() => vi.unstubAllGlobals());

function stubMatchMedia() {
  vi.stubGlobal("matchMedia", () => ({
    get matches() {
      return prefersDark;
    },
    addEventListener: (_: string, fn: () => void) => listeners.push(fn),
    removeEventListener: () => undefined,
  }));
}

test("applies an explicit theme", () => {
  renderHook(() => useTheme("dark"));
  expect(document.documentElement.dataset.theme).toBe("dark");
});

test("'system' is light when the OS has no dark preference", () => {
  stubMatchMedia();
  prefersDark = false;
  renderHook(() => useTheme("system"));
  expect(document.documentElement.dataset.theme).toBe("light");
});

test("'system' follows the OS setting, live", () => {
  stubMatchMedia();
  prefersDark = true;
  renderHook(() => useTheme("system"));
  expect(document.documentElement.dataset.theme).toBe("dark");
  prefersDark = false;
  listeners.forEach((fn) => fn());
  expect(document.documentElement.dataset.theme).toBe("light");
});
