import type { RoleBrief } from "../lib/types";
import { TextArea, TextField } from "./Field";

/** What the job really needs (P11.3): the competencies the projects were
 *  chosen for, each marked as stated in the job or inferred from its words,
 *  and the title and one-line positioning the headline and summary use. */
export function RoleBriefPanel({ brief, value, onChange }: {
  brief: RoleBrief;
  value: { title: string; positioning: string };
  onChange: (v: { title: string; positioning: string }) => void;
}) {
  return (
    <section aria-labelledby="brief-title" className="sheet flex flex-col gap-4 rounded-[3px] p-6">
      <div className="flex flex-col gap-1">
        <h2 id="brief-title" className="text-[15px] font-semibold tracking-[-0.01em]">What this job needs</h2>
        <p className="m-0 text-[13px] leading-relaxed text-muted">
          Read from the job description. “Inferred” means the job's words imply it; it guides which projects are shown and
          never changes the match score.
        </p>
      </div>
      <ul className="flex flex-wrap gap-2" aria-label="Competencies">
        {brief.competencies.map((c) => (
          <li key={c.name} title={`The job says: “${c.jd_words}”`}
            className={`rounded-[3px] border px-2.5 py-1 text-[13px] ${c.kind === "stated" ? "border-ink text-ink" : "border-dashed border-field text-ink"}`}>
            {c.name}<span className="ml-1.5 text-xs text-muted">{c.kind}</span>
          </li>
        ))}
      </ul>
      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <TextField label="Headline under your name (empty keeps yours)" value={value.title}
          onChange={(e) => onChange({ ...value, title: e.target.value })} />
        <TextArea label="How you fit (guides your summary)" rows={2} value={value.positioning}
          onChange={(e) => onChange({ ...value, positioning: e.target.value })} />
      </div>
    </section>
  );
}
