import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { TextArea, TextField } from "../components/Field";
import { Icon } from "../components/Icon";
import { ProgressPanel } from "../components/ProgressPanel";
import { draftProposals, friendlyError } from "../lib/api";
import { beginStep, isAbort } from "../lib/inflight";
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

  const setCandidate = (field: keyof DetailsData["candidate"], value: string) =>
    setForm((f) => ({ ...f, candidate: { ...f.candidate, [field]: value } }));
  const setJob = (i: number, patch: Partial<JobDetails>) =>
    setForm((f) => ({ ...f, experience: f.experience.map((e, j) => (j === i ? { ...e, ...patch } : e)) }));
  const rolesOf = (job: JobDetails): Role[] => (job.roles.length ? job.roles : [{ title: "", start_date: "", end_date: "" }]);
  const setRole = (i: number, r: number, patch: Partial<Role>) =>
    setJob(i, { roles: rolesOf(form.experience[i]).map((role, k) => (k === r ? { ...role, ...patch } : role)) });

  const submit = async () => {
    setError(null);
    setProgress([]);
    const corrections = { ...form, candidate: { ...form.candidate, links: links.split("\n").map((l) => l.trim()).filter(Boolean) } };
    // Unchanged: send nothing, so the server keeps exactly what it read.
    const changed = JSON.stringify(corrections) !== JSON.stringify(run.details);
    const step = beginStep();
    try {
      const drafted = await draftProposals(changed ? corrections : null,
        (m) => step.isCurrent() && setProgress((p) => [...(p ?? []), m]), step.signal);
      if (!step.isCurrent()) return; // the user left this run
      updateRun({ details: corrections, drafted, results: null, review: null });
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
        <h1 ref={progressHeading} tabIndex={-1} className="font-display text-[40px] font-medium leading-tight outline-none">
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
        <h1 ref={heading} tabIndex={-1} className="font-display text-[40px] font-medium leading-tight outline-none md:text-5xl">
          Check your details
        </h1>
        <p className="max-w-[640px] text-muted">
          This is what we read from your file. Fix anything that's wrong, then continue. You'll review the bullet points next.
        </p>
      </div>

      {run.parseIssues.length > 0 && (
        <ul className="flex flex-col gap-2 border border-pencil/60 bg-pencil-soft p-4 text-sm">
          {run.parseIssues.map((issue) => (
            <li key={issue}>Possible reading problem: {issue}</li>
          ))}
        </ul>
      )}

      <section aria-labelledby="you" className="flex flex-col gap-5 border border-line bg-panel p-6 md:p-7">
        <h2 id="you" className="font-display text-[26px] font-semibold">You</h2>
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
        <h2 id="jobs" className="font-display text-[26px] font-semibold">Experience</h2>
        {form.experience.length === 0 && <p className="text-sm text-muted">No jobs were found in your resume.</p>}
        {form.experience.map((job, i) => (
          <fieldset key={job.id} className="flex flex-col gap-4 border border-line bg-panel p-6">
            <legend className="sr-only">Job {i + 1}</legend>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-xs tracking-[0.2em] text-pencil">JOB {i + 1}</span>
              <span className="text-xs text-muted">
                {job.bullets} bullet{job.bullets === 1 ? "" : "s"}{job.groups ? ` in ${job.groups} sub-sections` : ""}
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
      </section>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
        <Button onClick={() => goTo("upload")}>Back</Button>
        <Button type="submit" variant="primary" size="lg">
          Looks right, draft rewrites <Icon name="arrow-right" />
        </Button>
        {error && <p ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-danger outline-none">{error}</p>}
      </div>
    </form>
  );
}
