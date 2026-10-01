import { renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useTheme } from "./useTheme";

const listeners: (() => void)[] = [];
let prefersLight = false;

afterEach(() => vi.unstubAllGlobals());

function stubMatchMedia() {
  vi.stubGlobal("matchMedia", () => ({
    get matches() {
      return prefersLight;
    },
    addEventListener: (_: string, fn: () => void) => listeners.push(fn),
    removeEventListener: () => undefined,
  }));
}

test("applies an explicit theme", () => {
  renderHook(() => useTheme("light"));
  expect(document.documentElement.dataset.theme).toBe("light");
});

test("'system' follows the OS setting, live", () => {
  stubMatchMedia();
  prefersLight = true;
  renderHook(() => useTheme("system"));
  expect(document.documentElement.dataset.theme).toBe("light");
  prefersLight = false;
  listeners.forEach((fn) => fn());
  expect(document.documentElement.dataset.theme).toBe("dark");
});
