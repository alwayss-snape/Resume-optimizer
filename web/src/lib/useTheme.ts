import { useLayoutEffect } from "react";
import type { Theme } from "./store";

/** Applies the chosen theme to <html data-theme>, following the system
 *  setting live when the choice is "system" (dark only when the OS asks for it). */
export function useTheme(theme: Theme) {
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (theme !== "system") {
      root.dataset.theme = theme;
      return;
    }
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    const apply = () => (root.dataset.theme = query?.matches ? "dark" : "light");
    apply();
    query?.addEventListener("change", apply);
    return () => query?.removeEventListener("change", apply);
  }, [theme]);
}
