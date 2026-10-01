import { STEPS, stepIndex, useApp } from "../lib/store";
import { Icon } from "./Icon";

/** Where you are in the flow. Steps already reached are links back; later
 *  ones are plain text. Collapses to "Step 2 of 4" on narrow screens. */
export function Stepper() {
  const { step, reached, goTo } = useApp();
  const current = stepIndex(step);

  return (
    <nav aria-label="Progress">
      <div className="flex items-center gap-3 text-[13px] text-muted md:hidden">
        {current > 0 && (
          <button type="button" onClick={() => goTo(STEPS[current - 1].id)}
            aria-label={`Back to ${STEPS[current - 1].label}`}
            className="flex min-h-11 items-center gap-1 text-muted hover:text-ink">
            <Icon name="arrow-right" size={14} className="rotate-180" />
            {STEPS[current - 1].label}
          </button>
        )}
        <p>
          Step {current + 1} of {STEPS.length} · <span className="text-ink">{STEPS[current].label}</span>
        </p>
      </div>
      <ol className="hidden items-center gap-3.5 text-[13px] md:flex">
        {STEPS.map((s, i) => {
          const done = i < current;
          const isCurrent = i === current;
          const canVisit = i <= reached && !isCurrent;
          const marker = (
            <span
              className={`flex size-[22px] items-center justify-center rounded-full text-[11px] ${
                done ? "bg-line text-gold" : isCurrent ? "border border-gold text-gold" : "border border-line-strong"
              }`}
            >
              {done ? <Icon name="check" size={12} strokeWidth={2.4} /> : i + 1}
            </span>
          );
          return (
            <li key={s.id} className="flex items-center gap-3.5">
              {i > 0 && <span aria-hidden="true" className={`h-px w-7 ${i <= current ? "bg-gold" : "bg-line-strong"}`} />}
              {canVisit ? (
                <button type="button" onClick={() => goTo(s.id)}
                  className="flex min-h-11 items-center gap-2 text-muted transition-colors hover:text-ink">
                  {marker}
                  {s.label}
                </button>
              ) : (
                <span aria-current={isCurrent ? "step" : undefined}
                  className={`flex min-h-11 items-center gap-2 ${isCurrent ? "text-ink" : "text-muted"}`}>
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
