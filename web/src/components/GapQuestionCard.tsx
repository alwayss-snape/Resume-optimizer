import { useId } from "react";
import type { GapInput } from "../lib/review";
import type { GapQuestion } from "../lib/types";

export interface TargetOption {
  value: string;
  label: string;
}

export function TargetSelect({ value, onChange, options, label = "Add it to" }: {
  value: string;
  onChange: (v: string) => void;
  options: TargetOption[];
  label?: string;
}) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] text-muted">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="h-11 border border-field bg-panel-2 px-3 text-sm text-ink">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

/** Suggest-and-confirm (P3.1): a JD line the resume doesn't show yet. Only
 *  ticked keywords and the user's own words are used. */
export function GapQuestionCard({ question: q, value, onChange, targets }: {
  question: GapQuestion;
  value: GapInput;
  onChange: (v: GapInput) => void;
  targets: TargetOption[];
}) {
  const answerId = useId();
  const toggle = (k: string) =>
    onChange({ ...value, ticked: value.ticked.includes(k) ? value.ticked.filter((x) => x !== k) : [...value.ticked, k] });
  return (
    <fieldset className="flex flex-col gap-4 border border-line bg-panel p-5 md:p-6">
      <legend className="sr-only">The job asks for: {q.requirement}</legend>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p aria-hidden="true" className="m-0 font-display text-[22px] leading-snug md:text-2xl">“{q.requirement}”</p>
        {q.priority === "preferred" && <span className="border border-field px-2 py-0.5 text-[11px] text-muted">Nice to have</span>}
      </div>
      {q.saved_keywords.length > 0 && (
        <p className="m-0 text-xs text-muted">
          You confirmed {q.saved_keywords.join(", ")} earlier in this visit. Untick anything that doesn't apply here.
        </p>
      )}
      <div className="flex flex-wrap gap-2.5">
        {q.keywords.map((k) => {
          const on = value.ticked.includes(k);
          return (
            <label key={k} className={`flex min-h-11 cursor-pointer items-center gap-2.5 border px-4 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gold ${
              on ? "border-gold bg-gold-soft" : "border-field"}`}>
              <input type="checkbox" checked={on} onChange={() => toggle(k)} className="size-4 accent-[var(--gold)]" />
              I have used {k}
            </label>
          );
        })}
      </div>
      <div className="grid gap-3.5 md:grid-cols-[2fr_1fr]">
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor={answerId} className="text-[13px] text-muted">Where and how? (optional, your own words; becomes a bullet)</label>
          <textarea id={answerId} rows={2} value={value.answer} onChange={(e) => onChange({ ...value, answer: e.target.value })}
            className="resize-y border border-field bg-panel-2 px-3.5 py-2.5 text-sm leading-relaxed text-ink" />
        </div>
        <TargetSelect value={value.target} onChange={(target) => onChange({ ...value, target })} options={targets} />
      </div>
    </fieldset>
  );
}
