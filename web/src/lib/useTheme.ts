import { useLayoutEffect } from "react";
import type { Theme } from "./store";

/** Applies the chosen theme to <html data-theme>, following the system
 *  setting live when the choice is "system". */
export function useTheme(theme: Theme) {
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (theme !== "system") {
      root.dataset.theme = theme;
      return;
    }
    const query = window.matchMedia?.("(prefers-color-scheme: light)");
    const apply = () => (root.dataset.theme = query?.matches ? "light" : "dark");
    apply();
    query?.addEventListener("change", apply);
    return () => query?.removeEventListener("change", apply);
  }, [theme]);
}
