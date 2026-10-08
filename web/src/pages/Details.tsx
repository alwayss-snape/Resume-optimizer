import { useEffect, useRef, useState } from "react";
import { AddJobForm } from "../components/AddJobForm";
import { Button } from "../components/Button";
import { TextArea, TextField } from "../components/Field";
import { Icon } from "../components/Icon";
import { ProgressPanel, progressHandler, type Wait } from "../components/ProgressPanel";
import { type Corrections, draftProposals, friendlyError } from "../lib/api";
import { beginStep, isAbort } from "../lib/inflight";
import { EMPTY_JOB, type NewJob, addedJob, anyJobField, newJobProblem } from "../lib/review";
import { useApp } from "../lib/store";
import type { Details as DetailsData, JobDetails, Role } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";

// The server's limit on bullets for a new job (TailorService.MAX_NEW_ROLE_BULLETS).
const MAX_NEW_JOB_LINES = 40; // a project bank to choose from (P10.13); the server keeps the same cap

/** Step 2 (P3.5): confirm or fix what was read from the file before any
 *  rewriting. Bullets are reviewed in the next step. */
export function Details() {
  const { run, updateRun, advance, goTo } = useApp();
  const heading = useFocusHeading();
  const [form, setForm] = useState<DetailsData>(() => structuredClone(run.details!));
  const [links, setLinks] = useState(() => run.details!.candidate.links.join("\n"));
  // Jobs the file was missing (added here) or that were misread (removed).
  const [added, setAdded] = useState<{ key: number; job: NewJob }[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  // Where each line the parse couldn't place goes; kept under "Additional information" unless moved (P8.26).
  const [placed, setPlaced] = useState<Record<string, string>>(() =>
    Object.fromEntries((run.unplaced ?? []).map((l) => [l.id, "other"])));
  const nextKey = useRef(0);
  // Where focus goes after a job card appears or goes away (a CSS selector).
  const focusNext = useRef<string | null>(null);
  const [progress, setProgress] = useState<string[] | null>(null);
  const [wait, setWait] = useState<Wait | null>(null);
  const [error, setError] = useState<string | null>(null);
  const progressHeading = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const showingProgress = progress !== null;

  // Focus follows the view: the progress heading while drafting, the error
  // when the form comes back after a failure.
  useEffect(() => {
    if (showingProgress) progressHeading.current?.focus({ preventScroll: true });
  }, [showingProgress]);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);
  // A new card focuses its first field; Remove focuses Undo and back; a
  // deleted new card hands focus to "Add a job".
  useEffect(() => {
    if (focusNext.current === null) return;
    document.querySelector<HTMLElement>(focusNext.current)?.focus();
    focusNext.current = null;
  }, [added, removed]);

  const addJob = () => {
    const key = nextKey.current++;
    focusNext.current = `[data-job="new-${key}"] input`;
    setAdded((a) => [...a, { key, job: EMPTY_JOB }]);
  };
  const dropAdded = (key: number) => {
    focusNext.current = "[data-job='add']";
    setAdded((a) => a.filter((x) => x.key !== key));
  };
  const setAddedJob = (key: number, job: NewJob) => setAdded((a) => a.map((x) => (x.key === key ? { ...x, job } : x)));
  const toggleRemoved = (id: string) => {
    const undoing = removed.includes(id);
    focusNext.current = `[data-job="${undoing ? "remove" : "undo"}-${id}"]`;
    setRemoved((r) => (undoing ? r.filter((x) => x !== id) : [...r, id]));
  };

  const setCandidate = (field: keyof DetailsData["candidate"], value: string) =>
    setForm((f) => ({ ...f, candidate: { ...f.candidate, [field]: value } }));
  const setJob = (i: number, patch: Partial<JobDetails>) =>
    setForm((f) => ({ ...f, experience: f.experience.map((e, j) => (j === i ? { ...e, ...patch } : e)) }));
  const rolesOf = (job: JobDetails): Role[] => (job.roles.length ? job.roles : [{ title: "", start_date: "", end_date: "" }]);
  const setRole = (i: number, r: number, patch: Partial<Role>) =>
    setJob(i, { roles: rolesOf(form.experience[i]).map((role, k) => (k === r ? { ...role, ...patch } : role)) });

  const submit = async () => {
    setError(null);
    const newJobs = added.filter((a) => anyJobField(a.job));
    for (const [n, a] of added.entries()) { // numbered as the cards are
      const lines = a.job.description.split("\n").filter((l) => l.trim()).length;
      const problem = newJobProblem(a.job, "remove it")
        ?? (lines > MAX_NEW_JOB_LINES ? `Keep it to ${MAX_NEW_JOB_LINES} lines (one per bullet point); it has ${lines}.` : null);
      if (problem) {
        setError(`New job ${n + 1}: ${problem}`);
        return;
      }
    }
    if (removed.length === form.experience.length && form.experience.length > 0 && newJobs.length === 0) {
      setError("Keep at least one job, or add the right one.");
      return;
    }
    setProgress([]);
    setWait(null);
    const fixed: Corrections = { ...form, candidate: { ...form.candidate, links: links.split("\n").map((l) => l.trim()).filter(Boolean) } };
    // Unchanged: send nothing, so the server keeps exactly what it read.
    // "Leave it out" (an empty target) isn't sent: the line stays off the resume (P9.1).
    const placements = Object.entries(placed).filter(([, target]) => target).map(([id, target]) => ({ id, target }));
    const changed = JSON.stringify(fixed) !== JSON.stringify(run.details) || removed.length > 0 || newJobs.length > 0
      || placements.length > 0;
    const corrections: Corrections = {
      ...fixed, experience: fixed.experience.filter((e) => !removed.includes(e.id)),
      ...(removed.length ? { removed_jobs: removed } : {}),
      ...(newJobs.length ? { added_jobs: newJobs.map((a) => addedJob(a.job)) } : {}),
      ...(placements.length ? { placed: placements } : {}),
    };
    const step = beginStep();
    try {
      const onProgress = progressHandler(setProgress, setWait);
      const drafted = await draftProposals(changed ? corrections : null,
        (m, w) => step.isCurrent() && onProgress(m, w), step.signal);
      if (!step.isCurrent()) return; // the user left this run
      // The server's own read-back, so added jobs come back as ordinary ones.
      updateRun({ details: drafted.details ?? fixed, drafted, results: null, review: null });
      advance("review");
    } catch (e) {
      if (isAbort(e) || !step.isCurrent()) return;
      setError(friendlyError(e));
      setProgress(null);
    } finally {
      step.end();
    }
  };

  if (progress) {
    return (
      <section className="mx-auto flex max-w-[760px] flex-col gap-6 px-4 py-14 md:px-8">
        <h1 ref={progressHeading} tabIndex={-1} className="font-display text-[40px] font-bold leading-tight tracking-[-0.03em] outline-none">
          Drafting your rewrites
        </h1>
        <p className="text-muted">Every rewrite is fact-checked against your resume. This usually takes 1–2 minutes, longer
          when the free AI service asks us to wait.</p>
        <ProgressPanel title="Working…" messages={progress.length ? progress : ["Starting"]} wait={wait} />
      </section>
    );
  }

  const c = form.candidate;
  return (
    <form className="mx-auto flex max-w-[1000px] flex-col gap-8 px-4 py-12 md:px-8 md:py-14"
      onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <div className="flex flex-col gap-3">
        <h1 ref={heading} tabIndex={-1} className="font-display text-[40px] font-bold leading-tight tracking-[-0.035em] outline-none md:text-[48px]">
          Check your details
        </h1>
        <p className="max-w-[640px] text-muted">
          This is what we read from your file. Fix anything that's wrong, then continue. You'll review the bullet points next.
        </p>
      </div>

      {run.parseNotes.length > 0 && (
        <ul className="flex flex-col gap-2 rounded-[3px] border border-line bg-panel p-4 text-sm">
          {run.parseNotes.map((note) => (
            <li key={note} className="flex items-start gap-2">
              <Icon name="info" size={16} className="mt-0.5 shrink-0 text-pencil" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      )}

      {run.parseIssues.length > 0 && (
        <ul className="flex flex-col gap-2 rounded-[3px] border border-warning bg-panel p-4 text-sm">
          {run.parseIssues.map((issue) => (
            <li key={issue} className="flex items-start gap-2">
              <Icon name="alert" size={16} className="mt-0.5 shrink-0 text-warning" />
              <span><span className="font-semibold">Possible reading problem:</span> {issue}</span>
            </li>
          ))}
        </ul>
      )}

      <section aria-labelledby="you" className="sheet flex flex-col gap-5 rounded-[3px] p-6 md:p-7">
        <h2 id="you" className="font-display text-[22px] font-bold tracking-[-0.02em]">You</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="Name" value={c.name} onChange={(e) => setCandidate("name", e.target.value)} autoComplete="name" />
          <TextField label="Headline (optional)" value={c.headline} placeholder="e.g. Registered Nurse, Sales Manager, Data Analyst"
            onChange={(e) => setCandidate("headline", e.target.value)} />
          <TextField label="Email" type="email" value={c.email} onChange={(e) => setCandidate("email", e.target.value)} autoComplete="email" />
          <TextField label="Phone" type="tel" value={c.phone} onChange={(e) => setCandidate("phone", e.target.value)} autoComplete="tel" />
          <TextField label="Location" value={c.location} onChange={(e) => setCandidate("location", e.target.value)} />
          <TextArea label="Links (one per line)" rows={3} value={links} placeholder={"linkedin.com/in/you\nyour-portfolio.com"}
            onChange={(e) => setLinks(e.target.value)} />
        </div>
      </section>

      <section aria-labelledby="jobs" className="flex flex-col gap-5">
        <h2 id="jobs" className="mt-2 font-display text-[22px] font-bold tracking-[-0.02em]">Experience</h2>
        {form.experience.length === 0 && <p className="text-sm text-muted">No jobs were found in your resume.</p>}
        {form.experience.map((job, i) => removed.includes(job.id) ? (
          <div key={job.id} className="flex flex-wrap items-center justify-between gap-3 rounded-[3px] border border-dashed border-field px-6 py-3">
            <span className="text-sm text-muted">
              <del className="mark-del">Job {i + 1}{job.company ? `: ${job.company}` : ""}</del> won't be on your resume.
            </span>
            <Button variant="ghost" data-job={`undo-${job.id}`} aria-label={`Undo removing job ${i + 1}`}
              onClick={() => toggleRemoved(job.id)}>Undo</Button>
          </div>
        ) : (
          <fieldset key={job.id} className="sheet flex flex-col gap-4 rounded-[3px] p-6">
            <legend className="sr-only">Job {i + 1}</legend>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[15px] font-semibold">Job {i + 1}</span>
              <span className="flex items-center gap-3">
                <span className="tabular text-[13px] text-muted">
                  {job.bullets} bullet{job.bullets === 1 ? "" : "s"}{job.groups ? ` in ${job.groups} sub-sections` : ""}
                </span>
                <Button variant="ghost" data-job={`remove-${job.id}`} aria-label={`Remove job ${i + 1}${job.company ? `, ${job.company}` : ""}`}
                  onClick={() => toggleRemoved(job.id)}>Remove</Button>
              </span>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <TextField label="Company" value={job.company} onChange={(e) => setJob(i, { company: e.target.value })} />
              <TextField label="Location" value={job.location} onChange={(e) => setJob(i, { location: e.target.value })} />
            </div>
            {rolesOf(job).map((role, r) => (
              <div key={r} className="grid gap-4 md:grid-cols-[2fr_1fr_1fr]">
                <TextField label={r === 0 ? "Title" : "Earlier title"} value={role.title}
                  onChange={(e) => setRole(i, r, { title: e.target.value })} />
                <TextField label="Start" value={role.start_date} placeholder="Jan 2022"
                  onChange={(e) => setRole(i, r, { start_date: e.target.value })} />
                <TextField label="End" value={role.end_date} placeholder="Present"
                  onChange={(e) => setRole(i, r, { end_date: e.target.value })} />
              </div>
            ))}
          </fieldset>
        ))}
        {added.map(({ key, job }, n) => (
          <fieldset key={key} data-job={`new-${key}`} className="sheet flex flex-col gap-4 rounded-[3px] p-6">
            <legend className="sr-only">New job {n + 1}</legend>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[15px] font-semibold">New job {n + 1}</span>
              <Button variant="ghost" aria-label={`Remove new job ${n + 1}`}
                onClick={() => dropAdded(key)}>Remove</Button>
            </div>
            <p className="m-0 text-[13px] text-muted">
              One point per line, in your own words. Paste all your work: a short line ending in “:” names a
              project, and the lines under it are its points. The next step keeps the projects that suit this job
              best (you can change that) and suggests tailored wording you can accept or reject.
            </p>
            <AddJobForm value={job} onChange={(j) => setAddedJob(key, j)} />
          </fieldset>
        ))}
        <button type="button" data-job="add" onClick={addJob}
          className="flex min-h-15 items-center gap-2.5 rounded-[3px] border border-dashed border-field bg-panel px-5 text-left text-sm font-medium transition-colors hover:border-pencil hover:text-pencil">
          <Icon name="close" size={16} className="rotate-45 text-pencil" />
          {form.experience.length || added.length ? "Add a job we missed" : "Add a job"}
        </button>
      </section>

      {(run.unplaced ?? []).length > 0 && (
        <section aria-labelledby="unplaced" className="sheet flex flex-col gap-4 rounded-[3px] p-6 md:p-7">
          <div className="flex flex-col gap-1">
            <h2 id="unplaced" className="font-display text-[22px] font-bold tracking-[-0.02em]">Lines we couldn't place</h2>
            <p className="m-0 text-sm text-muted">They stay on your resume under "Additional information" unless you move them or leave them out.</p>
          </div>
          <ul className="m-0 flex flex-col p-0">
            {(run.unplaced ?? []).map((line) => (
              <li key={line.id} className="flex flex-col gap-2 border-t border-line py-3 first:border-t-0 sm:flex-row sm:items-center sm:justify-between">
                <span className="min-w-0 font-serif text-[15px] leading-relaxed">{line.text}</span>
                <label className="flex shrink-0 items-center gap-2 text-sm">
                  <span className="text-muted">Put it under</span>
                  <select value={placed[line.id] ?? "other"} onChange={(e) => setPlaced((p) => ({ ...p, [line.id]: e.target.value }))}
                    className="h-11 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink">
                    <option value="other">Additional information</option>
                    <option value="summary">Summary</option>
                    <option value="skills">Skills</option>
                    {form.experience.filter((e) => !removed.includes(e.id)).map((e) => (
                      <option key={e.id} value={e.id}>A bullet of {e.company || e.roles[0]?.title || "a job"}</option>
                    ))}
                    <option value="">Leave it out</option>
                  </select>
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(form.also_read ?? []).length > 0 && (
        <section aria-labelledby="also-read" className="flex flex-col gap-3">
          <h2 id="also-read" className="font-display text-[22px] font-bold tracking-[-0.02em]">Also read from your file</h2>
          <p className="m-0 text-sm text-muted">Kept as written. Reorder or hide any of it after tailoring, in Arrange.</p>
          <div className="grid gap-3 md:grid-cols-2">
            {(form.also_read ?? []).map((sec) => (
              <div key={sec.title} className="rounded-[3px] border border-line bg-panel p-4">
                <p className="m-0 text-sm font-semibold">{sec.title}</p>
                <ul className="m-0 mt-1.5 flex flex-col gap-1 p-0">
                  {sec.lines.slice(0, 5).map((l, i) => (
                    <li key={i} className="list-none break-words font-serif text-[14px] leading-relaxed">{l}</li>
                  ))}
                  {sec.lines.length > 5 && <li className="list-none text-xs text-muted">+{sec.lines.length - 5} more</li>}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
        <Button onClick={() => goTo("upload")}>Back</Button>
        <Button type="submit" variant="primary" size="lg">
          Looks right, draft rewrites <Icon name="arrow-right" />
        </Button>
        {error && (
          <p ref={errorRef} tabIndex={-1} role="alert" className="flex items-start gap-2 text-sm font-medium text-danger outline-none">
            <Icon name="alert" size={16} className="mt-0.5 shrink-0" /><span><span className="font-semibold">Error:</span> {error}</span>
          </p>
        )}
      </div>
    </form>
  );
}
