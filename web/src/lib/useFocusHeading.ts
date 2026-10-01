import { useEffect, useRef } from "react";

/** Moves focus to a page's heading when the page appears, so keyboard and
 *  screen-reader users land on the new step instead of <body>. */
export function useFocusHeading<T extends HTMLElement = HTMLHeadingElement>(enabled = true) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (!enabled) return;
    ref.current?.focus({ preventScroll: true });
    window.scrollTo?.({ top: 0 });
  }, [enabled]);
  return ref;
}
