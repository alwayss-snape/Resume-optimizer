import { useEffect, useId, useState } from "react";
import type { GapInput } from "../lib/review";
import type { GapQuestion } from "../lib/types";
import { Icon } from "./Icon";

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
      <label htmlFor={id} className="text-sm font-medium text-ink">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink">
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
  const ticksId = useId();
  // Opens once something is ticked or written; after that only the user closes it.
  const [open, setOpen] = useState(value.ticked.length > 0 || Boolean(value.answer) || value.target !== "auto");
  useEffect(() => {
    if (value.ticked.length > 0) setOpen(true);
  }, [value.ticked.length]);
  const toggle = (k: string) =>
    onChange({ ...value, ticked: value.ticked.includes(k) ? value.ticked.filter((x) => x !== k) : [...value.ticked, k] });
  return (
    <fieldset className="sheet flex flex-col gap-4 rounded-[3px] p-5 md:p-6">
      <legend className="sr-only">The job asks for: {q.requirement}</legend>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p aria-hidden="true" className="m-0 max-w-[60ch] font-serif text-[18px] leading-snug">“{q.requirement}”</p>
        {q.priority === "preferred" && <span className="rounded-[3px] border border-field px-2 py-0.5 text-xs text-muted">Nice to have</span>}
      </div>
      {q.saved_keywords.length > 0 && (
        <p className="m-0 text-xs text-muted">
          You confirmed {q.saved_keywords.join(", ")} earlier in this visit. Untick anything that doesn't apply here.
        </p>
      )}
      <div role="group" aria-labelledby={ticksId} className="flex flex-col gap-2.5">
        <span id={ticksId} className="text-sm text-muted">{q.tick_label ?? "Tick what you have really used:"}</span>
        <div className="flex flex-wrap gap-2.5">
          {q.keywords.map((k) => {
            const on = value.ticked.includes(k);
            return (
              <label key={k} className={`flex min-h-11 cursor-pointer items-center gap-2.5 rounded-[3px] border px-4 text-sm font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pencil ${
                on ? "border-pencil bg-pencil-soft" : "border-field hover:border-ink"}`}>
                <input type="checkbox" checked={on} onChange={() => toggle(k)} className="size-4" />
                {k}
              </label>
            );
          })}
        </div>
      </div>
      <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)} className="group">
        <summary className="flex min-h-11 w-fit cursor-pointer list-none items-center gap-2 text-sm font-medium text-pencil [&::-webkit-details-marker]:hidden">
          <Icon name="arrow-right" size={14} strokeWidth={2} className="transition-transform group-open:rotate-90" />
          Describe it in your own words (optional)
        </summary>
        <div className="mt-2 grid gap-3.5 md:grid-cols-[2fr_1fr]">
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor={answerId} className="text-sm font-medium text-ink">Where and how? It becomes a bullet as you write it.</label>
            <textarea id={answerId} rows={2} value={value.answer} onChange={(e) => onChange({ ...value, answer: e.target.value })}
              aria-describedby={value.ticked.length > 0 && !value.answer.trim() ? `${answerId}-hint` : undefined}
              className="resize-y rounded-[3px] border border-field bg-panel px-3.5 py-2.5 text-sm leading-relaxed text-ink focus-visible:border-pencil" />
            {value.ticked.length > 0 && !value.answer.trim() && (
              <p id={`${answerId}-hint`} className="m-0 text-xs text-muted">
                Where did you use it? Without a line saying where, it's only listed, and an interviewer will ask.
              </p>
            )}
          </div>
          <TargetSelect value={value.target} onChange={(target) => onChange({ ...value, target })} options={targets} />
        </div>
      </details>
    </fieldset>
  );
}
