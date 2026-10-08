import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { TextArea } from "../components/Field";
import { Icon } from "../components/Icon";
import { ProgressPanel, progressHandler, type Wait } from "../components/ProgressPanel";
import { draftProposals, friendlyError } from "../lib/api";
import { beginStep, isAbort } from "../lib/inflight";
import { type InterviewAnswer, useApp } from "../lib/store";
import type { InterviewQuestion } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";

/** Step 3 (P11.2): a few questions before anything is written, the way a
 *  recruiter would ask: a need of the job no project shows yet, or a project
 *  with no number on it. Every answer is optional and used in your words. */
export function Questions() {
  const { run, updateRun, advance } = useApp();
  const heading = useFocusHeading(true);
  const prepared = run.prepared!;
  const jobs = run.details?.experience ?? [];
  const [progress, setProgress] = useState<string[] | null>(null);
  const [wait, setWait] = useState<Wait | null>(null);
  const [error, setError] = useState<string | null>(null);
  const progressHeading = useRef<HTMLHeadingElement>(null);
  const answers = run.answers;

  // Saved answers from an earlier application start filled in.
  useEffect(() => {
    const prefill = Object.fromEntries(prepared.questions.filter((q) => q.saved_answer && !answers[q.id])
      .map((q) => [q.id, { ...start(q), answer: q.saved_answer }]));
    if (Object.keys(prefill).length) updateRun({ answers: { ...answers, ...prefill } });
  }, [prepared]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (progress !== null) progressHeading.current?.focus({ preventScroll: true });
  }, [progress !== null]); // eslint-disable-line react-hooks/exhaustive-deps

  // A need's answer starts at the best guess of where it belongs; the user picks.
  function start(q: InterviewQuestion): InterviewAnswer {
    return { answer: "", experience_id: q.experience_id || jobs[0]?.id || "", project: q.project };
  }
  const set = (id: string, patch: Partial<InterviewAnswer>) => {
    const now = useApp.getState().run.answers;
    const q = prepared.questions.find((x) => x.id === id)!;
    updateRun({ answers: { ...now, [id]: { ...(now[id] ?? start(q)), ...patch } } });
  };

  const draft = async (skip: boolean) => {
    setError(null);
    setProgress([]);
    setWait(null);
    const step = beginStep();
    const onProgress = progressHandler(setProgress, setWait);
    const sent = skip ? [] : Object.entries(useApp.getState().run.answers)
      .filter(([, a]) => a.answer.trim()).map(([id, a]) => ({ id, ...a }));
    try {
      const drafted = await draftProposals(null, (m, w) => step.isCurrent() && onProgress(m, w), step.signal, sent);
      if (!step.isCurrent()) return;
      updateRun({ details: drafted.details ?? run.details, drafted, results: null, review: null });
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
        <p className="text-muted">Your answers go in your own words; every rewrite is fact-checked against your resume and
          notes. Usually 1–2 minutes, longer when the free AI service asks us to wait.</p>
        <ProgressPanel title="Working…" messages={progress.length ? progress : ["Starting"]} wait={wait} />
      </section>
    );
  }

  const answered = prepared.questions.filter((q) => answers[q.id]?.answer.trim()).length;
  return (
    <section className="mx-auto flex max-w-[860px] flex-col gap-8 px-4 py-12 md:px-8">
      <div className="flex flex-col gap-3">
        <h1 ref={heading} tabIndex={-1} className="font-display text-[44px] font-bold leading-none tracking-[-0.035em] outline-none">
          A few questions
        </h1>
        <p className="m-0 max-w-[640px] text-muted">
          Before anything is written: what the job needs that your resume doesn't show yet, and numbers your projects
          don't have. Answer in your own words, or skip any. Nothing is added that you don't write here.
        </p>
      </div>

      <ol className="m-0 flex list-none flex-col gap-5 p-0">
        {prepared.questions.map((q, i) => {
          const value = answers[q.id] ?? start(q);
          return (
            <li key={q.id} className="sheet flex flex-col gap-3 rounded-[3px] p-6">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="tabular text-[13px] font-semibold text-pencil">{i + 1}</span>
                <span className="text-sm font-semibold">
                  {q.kind === "need" ? q.competency : q.project}
                  {q.kind === "figure" && q.job ? <span className="font-normal text-muted"> · {q.job}</span> : null}
                </span>
              </div>
              <p className="m-0 text-[15px] leading-relaxed">{q.question}</p>
              <TextArea label="Your answer (optional)" rows={3} value={value.answer} placeholder={q.hint}
                onChange={(e) => set(q.id, { answer: e.target.value })} />
              {q.kind === "need" && (q.options?.length ?? 0) > 0 && (
                <label className="flex flex-col gap-1.5 text-sm font-medium">
                  Where did you do it?
                  <select value={`${value.experience_id}::${value.project}`}
                    onChange={(e) => {
                      const [experience_id, ...rest] = e.target.value.split("::");
                      set(q.id, { experience_id, project: rest.join("::") });
                    }}
                    className="h-11 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink">
                    {q.options!.map((o) => (
                      <option key={`${o.experience_id}::${o.project}`} value={`${o.experience_id}::${o.project}`}>{o.label}</option>
                    ))}
                  </select>
                </label>
              )}
            </li>
          );
        })}
      </ol>

      {error && (
        <p role="alert" className="flex items-start gap-2 text-sm font-medium text-danger">
          <Icon name="alert" size={16} className="mt-0.5 shrink-0" /><span><span className="font-semibold">Error:</span> {error}</span>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" size="lg" onClick={() => void draft(false)}>
          {answered ? `Draft my resume with ${answered} answer${answered === 1 ? "" : "s"}` : "Draft my resume"}
          <Icon name="arrow-right" />
        </Button>
        {answered > 0 && <Button size="lg" onClick={() => void draft(true)}>Skip the answers</Button>}
      </div>
    </section>
  );
}
