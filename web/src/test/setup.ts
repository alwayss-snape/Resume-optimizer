import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  try {
    localStorage.clear();
  } catch {
    // storage can be unavailable; nothing to clear
  }
});

// jsdom has no scrolling.
window.scrollTo = () => undefined;
Element.prototype.scrollIntoView = () => undefined;

// jsdom has no IntersectionObserver (every browser does); nothing ever intersects here.
if (typeof window.IntersectionObserver === "undefined") {
  class NoIntersections {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  }
  Object.assign(window, { IntersectionObserver: NoIntersections });
  Object.assign(globalThis, { IntersectionObserver: NoIntersections });
}
