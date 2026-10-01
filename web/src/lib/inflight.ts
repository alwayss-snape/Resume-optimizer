// The one long step that may be running (parse, analyse, draft, tailor).
// Starting another, or "Start over", aborts it, and a result that arrives
// after that is ignored, so it can never drag the user back into an old run.
import { useApp } from "./store";

let controller: AbortController | null = null;
let generation = 0;

export function beginStep(): { signal: AbortSignal; isCurrent: () => boolean; end: () => void } {
  controller?.abort();
  controller = new AbortController();
  const mine = ++generation;
  useApp.setState({ running: true });
  return {
    signal: controller.signal,
    isCurrent: () => mine === generation,
    end: () => {
      if (mine === generation) useApp.setState({ running: false });
    },
  };
}

export function cancelSteps() {
  controller?.abort();
  controller = null;
  generation++;
  useApp.setState({ running: false });
}

export const isAbort = (e: unknown) => (e as Error)?.name === "AbortError";
