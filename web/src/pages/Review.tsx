import { useEffect, useMemo, useRef, useState } from "react";
import { AddJobForm } from "../components/AddJobForm";
import { Button } from "../components/Button";
import { TextArea } from "../components/Field";
import { ConditionList } from "../components/ConditionList";
import { GapQuestionCard, type TargetOption, TargetSelect } from "../components/GapQuestionCard";
import { Icon } from "../components/Icon";
import { KeywordList } from "../components/KeywordList";
import { ProgressPanel, progressHandler, type Wait } from "../components/ProgressPanel";
import { type ProofView, ProposalCard } from "../components/ProposalCard";
import { ProofStack } from "../components/ProofStack";
import { ProjectChoices } from "../components/ProjectChoices";
import { RoleBriefPanel } from "../components/RoleBriefPanel";
import { ScoreDial, verdict } from "../components/ScoreDial";
import { ApiError, draftProject, friendlyError, matchPreview, tailorResume } from "../lib/api";
import { CvModeChoice } from "../components/CvModeChoice";
import { RegionChoice } from "../components/RegionChoice";
import { beginStep, isAbort } from "../lib/inflight";
import {
  type Decision, type ReviewState, anyJobField, groupProposals, initialReview, isEdited, newJobProblem, selection, tailorRequest,
  textOf, visibleProposals, willApply,
} from "../lib/review";
import { useApp } from "../lib/store";
import type { MatchPreview } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";


/** Step 3 (P3.4 / P5.4): accept, reject or edit each rewrite; answer the
 *  questions about what the job asks for; add anything else; then generate. */
export function Review() {
  const { run, settings, updateRun, advance } = useApp();
  const drafted = run.drafted!;
  // Sent here from the results page to add job keywords: open at that section instead of the top.
  const [jump] = useState(() => run.jumpTo);
  const heading = useFocusHeading(!jump);
  const gapsHeading = useRef<HTMLHeadingElement>(null);
  const additionBox = useRef<HTMLDetailsElement>(null);
  const review: ReviewState = run.review ?? initialReview(drafted);
  // Functional updates on the latest stored state: one action may make
  // several changes in a row (save an edit, then accept the card).
  const update = (fn: (r: ReviewState) => ReviewState) =>
    updateRun({ review: fn(useApp.getState().run.review ?? initialReview(drafted)) });
  const [live, setLive] = useState<MatchPreview | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[] | null>(null);
  const [wait, setWait] = useState<Wait | null>(null);
  const [error, setError] = useState<{ text: string; n: number } | null>(null);
  const [jobOpen, setJobOpen] = useState(() => anyJobField(review.newJob));
  const [view, setView] = useState<ProofView>("proof");
  const hintId = "review-shortcuts";
  const cards = useRef<(HTMLElement | null)[]>([]);
  const progressHeading = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (!run.review) updateRun({ review: initialReview(drafted) });
  }, [run.review, drafted, updateRun]);
  useEffect(() => {
    if (!jump) return;
    updateRun({ jumpTo: null });
    if (jump === "addition" && additionBox.current) additionBox.current.open = true;
    const target = jump === "gaps" && gapsHeading.current ? gapsHeading.current
      : additionBox.current?.querySelector("summary") ?? heading.current;
    target?.scrollIntoView?.({ block: "center" });
    target?.focus({ preventScroll: true });
  }, [jump, updateRun, heading]);

  // Paper and dates (P10.3): only the ATS template has them.
  // and the CV type (P10.5).
  const regionChoice = (id: string, className: string) => run.template !== "keep" && drafted.region ? (
    <div className={`grid gap-4 sm:grid-cols-2 ${className}`}>
      {drafted.cv_mode && (
        <CvModeChoice id={`${id}-mode`} value={review.cvMode ?? drafted.cv_mode.mode} suggested={drafted.cv_mode}
          onChange={(cvMode) => update((r) => ({ ...r, cvMode }))} />
      )}
      <RegionChoice id={id} value={review.region ?? drafted.region.region} suggested={drafted.region}
        onChange={(region) => update((r) => ({ ...r, region }))} />
      <label className="flex flex-col gap-1.5 text-xs text-muted">
        <span className="font-medium text-ink">Look</span>
        <select value={review.style ?? "standard"} onChange={(e) => { const style = e.target.value; update((r) => ({ ...r, style })); }}
          className="h-11 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink">
          <option value="standard">Standard</option>
          <option value="classic">Classic: company first, figures in bold, serif</option>
        </select>
        <span>Both read cleanly in applicant-tracking systems; change it later in Arrange.</span>
      </label>
    </div>
  ) : null;
  // P10.13: cards of a left-out project hide, and don't count.
  const leftOutKey = JSON.stringify(review.leftOut ?? []);
  const shown = useMemo(() => visibleProposals(drafted, { ...review, leftOut: JSON.parse(leftOutKey) }),
    [drafted, leftOutKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const groups = useMemo(() => groupProposals(shown), [shown]);
  const selectionKey = JSON.stringify(selection(shown, review));

  // Live match rate for the current choices (no AI, no files), debounced.
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      matchPreview(JSON.parse(selectionKey), controller.signal, JSON.parse(leftOutKey))
        .then((m) => { setLive(m); setLiveError(null); })
        .catch((e) => {
          if (isAbort(e)) return;
          setLiveError(e instanceof ApiError && (e.status === 404 || e.status === 409) && !/still working/i.test(e.message)
            ? "Your session has expired. Use Start over below." : "Couldn't update the rate just now.");
        });
    }, 450);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [selectionKey, leftOutKey]);

  useEffect(() => {
    if (progress !== null) progressHeading.current?.focus({ preventScroll: true });
  }, [progress !== null]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);
  const fail = (text: string) => setError((e) => ({ text, n: (e?.n ?? 0) + 1 }));

  const decide = (id: string, d: Decision) => update((r) => ({ ...r, decisions: { ...r.decisions, [id]: d } }));
  const edit = (id: string, text: string | null) =>
    update((r) => {
      const edits = { ...r.edits };
      if (text === null) delete edits[id];
      else edits[id] = text;
      return { ...r, edits };
    });
  const setAll = (d: Decision) =>
    update((r) => ({ ...r, decisions: { ...r.decisions, ...Object.fromEntries(shown.map((p) => [p.id, d])) } }));
  const [drafting, setDrafting] = useState<string | null>(null);
  const toggleProject = (key: string) => {
    const bringingBack = (useApp.getState().run.review?.leftOut ?? []).includes(key);
    update((r) => {
      const now = r.leftOut ?? [];
      return { ...r, leftOut: now.includes(key) ? now.filter((k) => k !== key) : [...now, key] };
    });
    // P11.11: a project brought back wasn't written while it was out; write it now.
    if (bringingBack && !drafted.proposals.some((p) => p.target === key && p.kind === "project")) {
      setDrafting(key);
      draftProject(key).then(({ proposals }) => {
        const run = useApp.getState().run;
        if (!run.drafted || !proposals.length) return;
        updateRun({ drafted: { ...run.drafted, proposals: [...run.drafted.proposals, ...proposals] } });
        update((r) => ({ ...r, decisions: { ...r.decisions, ...Object.fromEntries(proposals.map((p) => [p.id, "accept" as Decision])) } }));
      }).catch(() => undefined).finally(() => setDrafting(null));
    }
  };
  const navigate = (from: number, step: 1 | -1) => cards.current[from + step]?.focus();

  const targets: TargetOption[] = [
    { value: "auto", label: "Auto: my most recent job" },
    ...drafted.experience_options.map((o) => ({ value: o.id, label: o.label })),
    { value: "new_project", label: "A new project" },
  ];

  const counts = {
    accepted: shown.filter((p) => review.decisions[p.id] !== "reject").length,
    rejected: shown.filter((p) => review.decisions[p.id] === "reject").length,
    edited: shown.filter((p) => isEdited(p, review)).length,
    dropped: shown.filter((p) => review.decisions[p.id] !== "reject" && !willApply(p, review)).length,
  };

  const generate = async () => {
    const current = useApp.getState().run.review ?? review; // includes an edit saved on blur just now
    const problem = newJobProblem(current.newJob);
    if (problem) {
      setJobOpen(true);
      fail(problem);
      return;
    }
    setError(null);
    setProgress([]);
    setWait(null);
    // The server deletes the previous files before generating, so the old
    // results must not stay reachable if this run fails.
    updateRun({ results: null });
    useApp.setState((s) => ({ reached: Math.min(s.reached, 2) }));
    const step = beginStep();
    const onProgress = progressHandler(setProgress, setWait);
    try {
      const results = await tailorResume(
        tailorRequest(visibleProposals(drafted, current), current, {
          keepLayout: run.template === "keep", strictFactual: settings.strictFactual, rememberAnswers: settings.rememberAnswers,
        }),
        (m, w) => step.isCurrent() && onProgress(m, w),
        step.signal,
      );
      if (!step.isCurrent()) return;
      updateRun({ results, resultsVersion: run.resultsVersion + 1 });
      advance("results");
    } catch (e) {
      if (isAbort(e) || !step.isCurrent()) return;
      fail(friendlyError(e));
      setProgress(null);
    } finally {
      step.end();
    }
  };

  if (progress) {
    return (
      <section className="mx-auto flex max-w-[760px] flex-col gap-6 px-4 py-14 md:px-8">
        <h1 ref={progressHeading} tabIndex={-1} className="font-display text-[40px] font-bold leading-tight tracking-[-0.03em] outline-none">
          Generating your resume
        </h1>
        <p className="text-muted">Applying your choices, laying out the pages and checking the files read back cleanly.</p>
        <ProgressPanel title="Working…" messages={progress.length ? progress : ["Starting"]} wait={wait} />
      </section>
    );
  }

  const llm = drafted.llm;
  const preScore = drafted.pre_score;
  const rate = live?.rate ?? preScore;
  const band = (live ?? drafted.keyword_match)?.target_band ?? [75, 85];
  const v = verdict(rate, band);
  let cardIndex = 0;
  let bulletNumber = 0;

  return (
    <>
      <div className="mx-auto grid max-w-[1320px] items-start gap-10 px-4 pb-32 pt-10 md:px-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:pb-28">
        <div className="flex min-w-0 flex-col gap-5">
          <div className="flex flex-wrap items-end justify-between gap-5">
            <div className="flex flex-col gap-2">
              <h1 ref={heading} tabIndex={-1} className="font-display text-[44px] font-bold leading-none tracking-[-0.035em] outline-none">Review changes</h1>
              <p className="tabular text-sm text-muted">
                {shown.length} proposals · {counts.accepted} accepted · {counts.rejected} rejected
                {counts.edited ? ` · ${counts.edited} edited` : ""}
              </p>
            </div>
            {drafted.proposals.length > 0 && (
              <div className="flex flex-wrap items-center gap-2.5">
                <div role="radiogroup" aria-label="Show changes as" className="flex h-11 overflow-hidden rounded-[4px] border border-field text-sm">
                  {([["proof", "Marked up"], ["split", "Side by side"]] as const).map(([id, l]) => (
                    <label key={id} className={`flex cursor-pointer items-center px-3.5 has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-4 has-[:focus-visible]:outline-pencil ${
                      view === id ? "bg-pencil-soft font-semibold text-ink" : "text-muted hover:text-ink"}`}>
                      <input type="radio" name="proof-view" value={id} checked={view === id} onChange={() => setView(id)} className="sr-only" />
                      {l}
                    </label>
                  ))}
                </div>
                <Button onClick={() => setAll("accept")}>Accept all</Button>
                <Button onClick={() => setAll("reject")}>Reject all</Button>
              </div>
            )}
          </div>
          {drafted.role_brief && drafted.role_brief.competencies.length > 0 && (
            <RoleBriefPanel brief={drafted.role_brief}
              value={review.brief ?? { title: drafted.role_brief.headline ?? "", positioning: drafted.role_brief.positioning }}
              onChange={(brief) => update((r) => ({ ...r, brief }))} />
          )}
          {regionChoice("region", "sheet rounded-[3px] p-4")}
          <ProjectChoices projects={drafted.projects ?? []} rankedByImpact={Boolean(drafted.projects_ranked_by_impact)}
            leftOut={review.leftOut ?? []} onToggle={toggleProject} drafting={drafting} />
          {liveError && (
            <p role="status" className="m-0 flex items-start gap-2 rounded-[3px] border border-warning bg-panel p-3 text-sm font-medium">
              <Icon name="alert" size={16} className="mt-0.5 shrink-0 text-warning" />{liveError}
            </p>
          )}
          {drafted.proposals.length > 0 && view === "proof" && (
            <p className="m-0 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted">
              <span>How to read the marks:</span>
              <span><del className="mark-del">removed</del></span>
              <span><ins className="mark-ins">added</ins></span>
              <span><strong className="mark-hl font-semibold text-ink">job keyword</strong></span>
            </p>
          )}

          {!llm.available ? (
            <div role="alert" className="rounded-[3px] border-2 border-danger bg-panel p-4 text-sm leading-relaxed">
              The AI model isn't available ({llm.provider_label}{llm.model ? `, ${llm.model}` : ""}: {llm.reason || "unavailable"}).
              No rewrites could be drafted, so the cards show your original text.{llm.fix_hint ? ` ${llm.fix_hint} Then start over.` : ""}
            </div>
          ) : llm.failed ? (
            <div role="status" className="rounded-[3px] border border-warning bg-panel p-4 text-sm">
              {llm.failed} of {llm.attempted} rewrites failed and show your original text.
              {llm.errors?.[0] ? ` Reason: ${llm.errors[0]}` : ""}
            </div>
          ) : null}
          {counts.dropped > 0 && (
            <p className="m-0 flex items-start gap-2 text-sm font-medium text-danger">
              <Icon name="alert" size={16} className="mt-0.5 shrink-0" />
              <span>{counts.dropped} accepted {counts.dropped === 1 ? "rewrite fails" : "rewrites fail"} the fact check and won't be used unless you edit {counts.dropped === 1 ? "it" : "them"}.
              {settings.strictFactual ? " Strict factual mode is on, so this withholds every rewrite." : ""}</span>
            </p>
          )}

          {drafted.proposals.length === 0 && (
            <p className="text-muted">No existing bullets needed rewriting for this job description.</p>
          )}

          {groups.map((g) => (
            <section key={g.key} aria-label={g.label} className="flex flex-col gap-4">
              <div className="mt-4 flex items-center gap-3.5">
                <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{g.label}</h2>
                <span aria-hidden="true" className="h-px flex-1 bg-line" />
                <span className="tabular text-[13px] text-muted">{g.items.length}</span>
              </div>
              {g.items.map((p) => {
                const i = cardIndex++;
                const n = p.kind === "bullet" ? bulletNumber++ : 0;
                return (
                  <ProposalCard key={p.id} ref={(el) => { cards.current[i] = el; }} proposal={p} index={n}
                    decision={review.decisions[p.id] ?? "accept"} text={textOf(p, review)} edited={isEdited(p, review)}
                    onDecide={(d) => decide(p.id, d)} onEdit={(t) => edit(p.id, t)} onNavigate={(s) => navigate(i, s)}
                    shortcutsHintId={hintId} view={view} />
                );
              })}
            </section>
          ))}

          {drafted.gap_questions.length > 0 && (
            <section aria-labelledby="gaps-title" className="mt-8 flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <h2 id="gaps-title" ref={gapsHeading} tabIndex={-1} className="scroll-mt-6 font-display text-2xl font-bold tracking-[-0.025em] outline-none">What the job asks for</h2>
                <span className="text-sm text-muted">Not on your resume yet. Only what you confirm is added.</span>
              </div>
              {drafted.gap_questions.map((q) => (
                <GapQuestionCard key={q.id} question={q} targets={targets}
                  value={review.gaps[q.id] ?? { ticked: [], answer: "", target: "auto" }}
                  onChange={(value) => update((r) => ({ ...r, gaps: { ...r.gaps, [q.id]: value } }))} />
              ))}
            </section>
          )}

          {(drafted.conditions?.length ?? 0) > 0 && (
            <section aria-labelledby="conditions-title" className="mt-8 flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <h2 id="conditions-title" className="font-display text-2xl font-bold tracking-[-0.025em]">Job conditions</h2>
                <span className="text-sm text-muted">
                  Licences, schedule, physical demands and the like. Tick what you meet: it's for you and the change log,
                  never added to your resume or the match.
                </span>
              </div>
              <div className="sheet rounded-[3px] px-5 py-2 md:px-6">
                <ConditionList conditions={drafted.conditions ?? []} ticked={review.conditions ?? []}
                  onToggle={(id) => update((r) => {
                    const now = r.conditions ?? [];
                    return { ...r, conditions: now.includes(id) ? now.filter((x) => x !== id) : [...now, id] };
                  })} />
              </div>
            </section>
          )}

          {drafted.gaps.length > 0 && (
            <details className="rounded-[3px] border border-line bg-panel p-5 text-sm">
              <summary className="min-h-6 cursor-pointer font-medium text-muted hover:text-ink">
                {drafted.gaps.length} job keyword{drafted.gaps.length === 1 ? "" : "s"} not on your resume
              </summary>
              <p className="mt-3 text-xs text-muted">Rewrites never add these; they come in only through your answers above.</p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {drafted.gaps.map((g) => (
                  <li key={g["Missing keyword"]} className="rounded-[3px] border border-dashed border-field px-2.5 py-1 text-xs text-ink">
                    {g["Missing keyword"]}{g.Required === "yes" ? " · required" : ""}{g["Asked below"] === "yes" ? " · asked" : ""}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <section aria-label="Add more" className="mt-6 flex flex-col gap-4">
            <details ref={additionBox} className="group rounded-[3px] border border-dashed border-field bg-panel">
              <summary className="flex min-h-15 cursor-pointer list-none items-center gap-2.5 px-5 text-sm font-medium hover:text-pencil [&::-webkit-details-marker]:hidden">
                <Icon name="close" size={16} className="rotate-45 text-pencil transition-transform group-open:rotate-0" />
                Add anything else in your own words
              </summary>
              <div className="grid gap-4 border-t border-line p-5 md:grid-cols-[2fr_1fr]">
                <TextArea label="A project, achievement or skill" rows={3} value={review.addition.text}
                  placeholder="e.g. Trained 8 new staff on the scheduling system, or led a migration that cut costs by 20%."
                  onChange={(e) => { const text = e.target.value; update((r) => ({ ...r, addition: { ...r.addition, text } })); }} />
                <TargetSelect label="Where should it go?" value={review.addition.target} options={targets}
                  onChange={(target) => update((r) => ({ ...r, addition: { ...r.addition, target } }))} />
              </div>
            </details>
            <details open={jobOpen} onToggle={(e) => setJobOpen(e.currentTarget.open)}
              className="group rounded-[3px] border border-dashed border-field bg-panel">
              <summary className="flex min-h-15 cursor-pointer list-none items-center gap-2.5 px-5 text-sm font-medium hover:text-pencil [&::-webkit-details-marker]:hidden">
                <Icon name="close" size={16} className="rotate-45 text-pencil transition-transform group-open:rotate-0" />
                Add a job that isn't on your resume
              </summary>
              <div className="border-t border-line p-5">
                <AddJobForm value={review.newJob} onChange={(newJob) => update((r) => ({ ...r, newJob }))} />
              </div>
            </details>
          </section>

          {error && (
            <p key={error.n} ref={errorRef} tabIndex={-1} role="alert" className="flex items-start gap-2 text-sm font-medium text-danger outline-none">
              <Icon name="alert" size={16} className="mt-0.5 shrink-0" /><span><span className="font-semibold">Error:</span> {error.text}</span>
            </p>
          )}
          <p id={hintId} className="sr-only">
            Shortcuts on a selected card: A accept, R reject, E edit, up and down arrows for the previous or next card.
          </p>
        </div>

        <aside aria-label="Match and actions" className="order-first flex flex-col gap-4 lg:sticky lg:top-6 lg:order-none">
          <p aria-live="polite" className="sr-only">
            Match with your choices: {rate.toFixed(1)}%. Was {preScore.toFixed(1)}% before tailoring. {v.text}
          </p>
          <div className="sheet hidden flex-col gap-4 rounded-[3px] p-6 lg:flex">
            <span className="text-sm font-semibold">Keyword match</span>
            <ScoreDial value={rate} before={preScore} band={band} />
            <p className="m-0 text-[13px] leading-relaxed text-muted">
              Was {preScore.toFixed(1)}% before tailoring. {v.text}
              {liveError ? "" : " Updates as you review."}
            </p>
          </div>
          {drafted.proposals.length > 0 && (
            <div className="hidden px-1 pt-2 lg:block">
              <ProofStack proposals={shown} review={review} />
            </div>
          )}
          {(live ?? drafted.keyword_match) && (
            <div className="sheet hidden rounded-[3px] p-5 lg:block">
              <KeywordList match={(live ?? drafted.keyword_match)!} compact />
            </div>
          )}
          <p className="m-0 hidden text-xs text-muted lg:block">
            Output: {run.template === "keep" ? "your own DOCX layout" : "ATS template"}
            {settings.strictFactual ? " · strict factual mode" : ""}
          </p>
          <div className="hidden lg:flex lg:flex-col">
            <Button variant="primary" size="lg" onClick={() => void generate()}>Generate my resume</Button>
          </div>
        </aside>
      </div>

      {/* phones: the rate and the main action stay in reach */}
      <div className="sticky bottom-0 z-20 border-t border-line bg-bg lg:hidden">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-4 py-3">
          <span aria-hidden="true" className="flex flex-col leading-tight">
            <span className="tabular font-display text-2xl font-bold tracking-[-0.03em]">{rate.toFixed(0)}<span className="text-sm text-pencil">%</span></span>
            <span className="text-xs text-muted">keyword match · was {preScore.toFixed(0)}%</span>
          </span>
          <Button variant="primary" size="lg" onClick={() => void generate()}>Generate my resume</Button>
        </div>
      </div>

      <div aria-hidden="true" className="sticky bottom-0 hidden border-t border-line bg-bg lg:block">
        <div className="mx-auto flex max-w-[1320px] gap-6 px-8 py-3 text-[13px] text-muted">
          {[["A", "Accept"], ["R", "Reject"], ["E", "Edit"], ["↑ ↓", "Next / previous"]].map(([k, l]) => (
            <span key={k}><kbd className="mr-1.5 rounded-[3px] border border-field bg-panel px-2 py-0.5 font-sans text-ink shadow-[0_1px_0_var(--field)]">{k}</kbd>{l}</span>
          ))}
          <span className="ml-auto">Select a card first (click or Tab)</span>
        </div>
      </div>
    </>
  );
}
