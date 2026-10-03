import { useId, useState } from "react";
import type { NewJob } from "../lib/review";
import { TextArea, TextField } from "./Field";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const THIS_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: THIS_YEAR + 1 - 1970 + 1 }, (_, i) => THIS_YEAR + 1 - i);
const SELECT = "h-11 min-w-0 flex-1 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink disabled:opacity-50";

/** Month + year as two selects, giving "YYYY-MM" (or "" until both are
 *  chosen). Works in every browser, unlike <input type="month">. */
function MonthYear({ label, value, onChange, disabled }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [partial, setPartial] = useState(() => ({ year: value.slice(0, 4), month: value.slice(5, 7) }));
  const year = value ? value.slice(0, 4) : partial.year;
  const month = value ? value.slice(5, 7) : partial.month;
  const set = (next: { year: string; month: string }) => {
    setPartial(next);
    onChange(next.year && next.month ? `${next.year}-${next.month}` : "");
  };
  return (
    <fieldset className="flex min-w-0 flex-col gap-1.5" disabled={disabled}>
      <legend className="mb-1.5 text-sm font-medium text-ink">{label}</legend>
      <div className="flex gap-2">
        <select aria-label={`${label}: month`} id={id} value={month} onChange={(e) => set({ year, month: e.target.value })} className={SELECT}>
          <option value="">Month</option>
          {MONTHS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, "0")}>{m}</option>)}
        </select>
        <select aria-label={`${label}: year`} value={year} onChange={(e) => set({ month, year: e.target.value })} className={SELECT}>
          <option value="">Year</option>
          {YEARS.map((y) => <option key={y} value={String(y)}>{y}</option>)}
        </select>
      </div>
    </fieldset>
  );
}

/** A job that isn't on the resume yet (P3.3). Bullets are drafted only
 *  from the description. */
export function AddJobForm({ value, onChange }: { value: NewJob; onChange: (v: NewJob) => void }) {
  const currentId = useId();
  const set = (patch: Partial<NewJob>) => onChange({ ...value, ...patch });
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <TextField label="Company *" value={value.company} onChange={(e) => set({ company: e.target.value })} />
      <TextField label="Job title *" value={value.title} onChange={(e) => set({ title: e.target.value })} />
      <TextField label="Location" value={value.location} placeholder="City, Country" onChange={(e) => set({ location: e.target.value })} />
      <label htmlFor={currentId} className="flex min-h-11 cursor-pointer items-center gap-3 self-end text-sm">
        <input id={currentId} type="checkbox" checked={value.current} onChange={(e) => set({ current: e.target.checked })}
          className="size-[18px] accent-[var(--pencil)]" />
        I currently work here
      </label>
      <MonthYear label="Start *" value={value.start} onChange={(start) => set({ start })} />
      <MonthYear label={value.current ? "End (not needed)" : "End *"} value={value.end} disabled={value.current}
        onChange={(end) => set({ end })} />
      <TextArea label="What did you do there? One point per line, in your own words *" rows={4} className="md:col-span-2"
        value={value.description} placeholder="One line per achievement, e.g. Managed a team of 6 on night shifts; cut stock losses by 15%."
        onChange={(e) => set({ description: e.target.value })} />
    </div>
  );
}
