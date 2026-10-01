import { STEPS, stepIndex, useApp } from "../lib/store";
import { Icon } from "./Icon";

/** Where you are in the flow. Steps already reached are links back; later
 *  ones are plain text. Collapses to "Step 2 of 4" on narrow screens. */
export function Stepper() {
  const { step, reached, goTo, running } = useApp();
  const current = stepIndex(step);

  if (step === "report") {
    return (
      <nav aria-label="Progress">
        <p className="text-sm font-semibold text-ink">Match report</p>
      </nav>
    );
  }

  return (
    <nav aria-label="Progress">
      <div className="flex items-center gap-3 text-sm text-muted md:hidden">
        {current > 0 && !running && (
          <button type="button" onClick={() => goTo(STEPS[current - 1].id)}
            aria-label={`Back to ${STEPS[current - 1].label}`}
            className="flex min-h-11 items-center gap-1 text-muted hover:text-ink">
            <Icon name="arrow-right" size={14} className="rotate-180" />
            {STEPS[current - 1].label}
          </button>
        )}
        <p>
          Step {current + 1} of {STEPS.length} · <span className="font-semibold text-ink">{STEPS[current].label}</span>
        </p>
      </div>
      <ol className="hidden items-center gap-3 text-sm md:flex">
        {STEPS.map((s, i) => {
          const done = i < current;
          const isCurrent = i === current;
          const canVisit = i <= reached && !isCurrent && !running;
          const marker = (
            <span
              className={`tabular flex size-[22px] items-center justify-center rounded-full text-xs font-semibold ${
                done ? "bg-pencil-soft text-pencil" : isCurrent ? "bg-pencil text-on-pencil" : "border border-field text-muted"
              }`}
            >
              {done ? <Icon name="check" size={12} strokeWidth={2.4} /> : i + 1}
            </span>
          );
          return (
            <li key={s.id} className="flex items-center gap-3.5">
              {i > 0 && <span aria-hidden="true" className={`h-px w-6 ${i <= current ? "bg-pencil" : "bg-line-strong"}`} />}
              {canVisit ? (
                <button type="button" onClick={() => goTo(s.id)}
                  className="flex min-h-11 items-center gap-2 text-muted transition-colors hover:text-ink">
                  {marker}
                  {s.label}
                </button>
              ) : (
                <span aria-current={isCurrent ? "step" : undefined}
                  className={`flex min-h-11 items-center gap-2 ${isCurrent ? "font-semibold text-ink" : "text-muted"}`}>
                  {marker}
                  {s.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
