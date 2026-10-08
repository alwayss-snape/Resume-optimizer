import type { ProjectChoice } from "../lib/types";

/** Which projects each job keeps for this job description (P10.13): the
 *  suggestion with its reason, and a tick to keep or leave out any project. */
export function ProjectChoices({ projects, rankedByImpact, leftOut, onToggle, drafting = null }: {
  projects: ProjectChoice[];
  rankedByImpact: boolean;
  leftOut: string[];
  onToggle: (key: string) => void;
  drafting?: string | null; // a project brought back, being written (P11.11)
}) {
  if (!projects.length) return null;
  const jobs: { id: string; label: string; items: ProjectChoice[] }[] = [];
  for (const p of projects) {
    let job = jobs.find((j) => j.id === p.experience_id);
    if (!job) jobs.push((job = { id: p.experience_id, label: p.job, items: [] }));
    job.items.push(p);
  }
  const out = new Set(leftOut);
  return (
    <section aria-labelledby="projects-title" className="sheet flex flex-col gap-5 rounded-[3px] p-6">
      <div className="flex flex-col gap-1">
        <h2 id="projects-title" className="text-[15px] font-semibold tracking-[-0.01em]">Projects on your resume</h2>
        <p className="m-0 text-[13px] leading-relaxed text-muted">
          {rankedByImpact
            ? "The job description is short, so projects are ranked mostly by impact: in production, scale and results, awards. "
            : "Each job keeps the projects closest to this job. "}
          Untick a project to leave it out, or tick one to bring it back; it's written like the rest.
        </p>
      </div>
      {jobs.map((job) => (
        <fieldset key={job.id} className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium text-ink">
            {job.label}
            <span className="tabular ml-2 text-[13px] font-normal text-muted">
              {job.items.filter((p) => !out.has(p.key)).length} of {job.items.length} kept
            </span>
          </legend>
          {job.items.map((p) => {
            const kept = !out.has(p.key);
            const id = `project-${p.key}`;
            return (
              <div key={p.key} className="flex items-start gap-3">
                <input id={id} type="checkbox" checked={kept} onChange={() => onToggle(p.key)}
                  aria-describedby={`${id}-why`} className="mt-0.5 size-[18px] shrink-0 accent-[var(--pencil)]" />
                <label htmlFor={id} className="flex min-w-0 cursor-pointer flex-col gap-0.5 text-sm">
                  <span className={kept ? "font-medium text-ink" : "text-muted line-through decoration-1"}>{p.name}</span>
                  <span id={`${id}-why`} className="text-[13px] text-muted">
                    {p.chosen ? "Suggested. " : "Not suggested. "}{p.reason}.
                    {drafting === p.key ? <span role="status" className="ml-1 text-pencil">Writing it now…</span> : null}
                  </span>
                </label>
              </div>
            );
          })}
        </fieldset>
      ))}
    </section>
  );
}
