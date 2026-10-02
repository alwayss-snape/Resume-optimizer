import { useEffect, useRef, useState } from "react";
import { AddJobForm } from "../components/AddJobForm";
import { Button } from "../components/Button";
import { TextArea, TextField } from "../components/Field";
import { Icon } from "../components/Icon";
import { ProgressPanel } from "../components/ProgressPanel";
import { type Corrections, draftProposals, friendlyError } from "../lib/api";
import { beginStep, isAbort } from "../lib/inflight";
import { EMPTY_JOB, type NewJob, addedJob, anyJobField, newJobProblem } from "../lib/review";
import { useApp } from "../lib/store";
import type { Details as DetailsData, JobDetails, Role } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";

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
  const nextKey = useRef(0);
  const addedRefs = useRef(new Map<number, HTMLElement>());
  const focusAdded = useRef<number | null>(null);
  const [progress, setProgress] = useState<string[] | null>(null);
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
  // A new job card takes focus on its first field.
  useEffect(() => {
    if (focusAdded.current === null) return;
    addedRefs.current.get(focusAdded.current)?.querySelector("input")?.focus();
    focusAdded.current = null;
  }, [added]);

  const addJob = () => {
    const key = nextKey.current++;
    focusAdded.current = key;
    setAdded((a) => [...a, { key, job: EMPTY_JOB }]);
  };
  const setAddedJob = (key: number, job: NewJob) => setAdded((a) => a.map((x) => (x.key === key ? { ...x, job } : x)));
  const toggleRemoved = (id: string) => setRemoved((r) => (r.includes(id) ? r.filter((x) => x !== id) : [...r, id]));

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
    for (const [n, a] of newJobs.entries()) {
      const problem = newJobProblem(a.job, "remove it");
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
    const fixed: Corrections = { ...form, candidate: { ...form.candidate, links: links.split("\n").map((l) => l.trim()).filter(Boolean) } };
    // Unchanged: send nothing, so the server keeps exactly what it read.
    const changed = JSON.stringify(fixed) !== JSON.stringify(run.details) || removed.length > 0 || newJobs.length > 0;
    const corrections: Corrections = {
      ...fixed, experience: fixed.experience.filter((e) => !removed.includes(e.id)),
      ...(removed.length ? { removed_jobs: removed } : {}),
      ...(newJobs.length ? { added_jobs: newJobs.map((a) => addedJob(a.job)) } : {}),
    };
    const step = beginStep();
    try {
      const drafted = await draftProposals(changed ? corrections : null,
        (m) => step.isCurrent() && setProgress((p) => [...(p ?? []), m]), step.signal);
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
        <p className="text-muted">Every rewrite is fact-checked against your resume. This usually takes under a minute.</p>
        <ProgressPanel title="Working…" messages={progress.length ? progress : ["Starting"]} />
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
          <TextField label="Headline (optional)" value={c.headline} placeholder="e.g. Senior Data Scientist"
            onChange={(e) => setCandidate("headline", e.target.value)} />
          <TextField label="Email" type="email" value={c.email} onChange={(e) => setCandidate("email", e.target.value)} autoComplete="email" />
          <TextField label="Phone" type="tel" value={c.phone} onChange={(e) => setCandidate("phone", e.target.value)} autoComplete="tel" />
          <TextField label="Location" value={c.location} onChange={(e) => setCandidate("location", e.target.value)} />
          <TextArea label="Links (one per line)" rows={3} value={links} placeholder={"linkedin.com/in/you\ngithub.com/you"}
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
            <Button variant="ghost" onClick={() => toggleRemoved(job.id)}>Undo</Button>
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
                <Button variant="ghost" aria-label={`Remove job ${i + 1}${job.company ? `, ${job.company}` : ""}`}
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
          <fieldset key={key} ref={(el) => { if (el) addedRefs.current.set(key, el); else addedRefs.current.delete(key); }}
            className="sheet flex flex-col gap-4 rounded-[3px] p-6">
            <legend className="sr-only">New job {n + 1}</legend>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[15px] font-semibold">New job {n + 1}</span>
              <Button variant="ghost" aria-label={`Remove new job ${n + 1}`}
                onClick={() => setAdded((a) => a.filter((x) => x.key !== key))}>Remove</Button>
            </div>
            <p className="m-0 text-[13px] text-muted">
              Your lines become its bullet points as written; the next step suggests tailored wording you can accept or reject.
            </p>
            <AddJobForm value={job} onChange={(j) => setAddedJob(key, j)} />
          </fieldset>
        ))}
        <button type="button" onClick={addJob}
          className="flex min-h-15 items-center gap-2.5 rounded-[3px] border border-dashed border-field bg-panel px-5 text-left text-sm font-medium transition-colors hover:border-pencil hover:text-pencil">
          <Icon name="close" size={16} className="rotate-45 text-pencil" />
          {form.experience.length || added.length ? "Add a job we missed" : "Add a job"}
        </button>
      </section>

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
