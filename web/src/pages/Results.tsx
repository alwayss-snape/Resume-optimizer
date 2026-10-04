import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { MatchGuidance } from "../components/MatchGuidance";
import { MiniMarkdown } from "../components/MiniMarkdown";
import { CountUp, ScoreRule, verdict } from "../components/ScoreDial";
import { downloadFile, fileUrl, friendlyError, getChangeLog, previewUrl } from "../lib/api";
import { useApp } from "../lib/store";
import type { KeywordRow, TailorResult } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";
import { Arrange } from "./Arrange";

const CHECK_LABELS: Record<string, string> = {
  bullets_per_role: "Bullets per role", length: "Length", pronoun: "Pronouns", buzzword: "Buzzwords",
  tense: "Tense", dates: "Dates", repeated_verb: "Repeated verbs", metrics: "Numbers",
};

/** Fetches the file first, so an expired session shows a message instead
 *  of a broken download. */
function Download({ kind, label, primary, onError }: {
  kind: "docx" | "pdf" | "changes";
  label: string;
  primary?: boolean;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Button variant={primary ? "primary" : "secondary"} size="lg" disabled={busy} aria-busy={busy}
      onClick={() => {
        setBusy(true);
        downloadFile(kind).catch((e) => onError(friendlyError(e))).finally(() => setBusy(false));
      }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"
        strokeLinejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>
      {label}
    </Button>
  );
}

/** Whole percent, unless rounding would hide a real change. */
function pair(before: number, after: number): [string, string] {
  const hidden = Math.round(before) === Math.round(after) && Math.abs(after - before) >= 0.05;
  return hidden ? [before.toFixed(1), after.toFixed(1)] : [String(Math.round(before)), String(Math.round(after))];
}

/** One line of the proof sign-off: the figure, then what it counts. */
function SignOffLine({ value, unit, label }: { value: string | number; unit?: string; label: string }) {
  return (
    <li className="flex items-baseline gap-3 border-t border-line py-3 first:border-t-0 sm:[&:nth-child(2)]:border-t-0">
      <span className="tabular min-w-[4.5rem] shrink-0 font-serif text-xl font-semibold">
        {value}{unit && <span className="text-[15px] font-normal text-muted"> {unit}</span>}
      </span>
      <span className="text-sm text-muted">{label}</span>
    </li>
  );
}

/** Required first, then the heaviest: the keywords most worth adding. */
const byImportance = (a: KeywordRow, b: KeywordRow) => Number(b.required) - Number(a.required) || b.weight - a.weight;

/** Before -> after on the rule; then what moved it, or what would. */
function ScoreReveal({ result, beforeRows, asked, onAddKeywords }: {
  result: TailorResult;
  beforeRows: KeywordRow[];
  asked: boolean; // review has tick boxes for some of these
  onAddKeywords: () => void;
}) {
  const before = result.initial_alignment_score;
  const after = result.alignment_score;
  const band = result.keyword_match?.target_band ?? [75, 85];
  const v = verdict(after, band);
  const [b, a] = pair(before, after);
  const flat = Math.abs(after - before) < 0.5;
  const rows = result.keyword_match?.rows ?? [];
  const foundBefore = new Set(beforeRows.filter((r) => r.found).map((r) => r.keyword));
  const gained = beforeRows.length ? rows.filter((r) => r.found && !foundBefore.has(r.keyword)) : [];
  const missing = rows.filter((r) => !r.found).sort(byImportance);
  const shown = missing.slice(0, 8);
  return (
    <div className="sheet flex flex-col gap-6 rounded-[3px] p-6 md:p-8">
      <div role="img" aria-label={`Keyword match: ${before.toFixed(1)}% before, ${after.toFixed(1)}% after tailoring. ${v.text}`}
        className="flex flex-col gap-6">
        <span aria-hidden="true" className="text-sm font-semibold">Keyword match</span>
        <div aria-hidden="true" className="flex items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-muted">Before</span>
            <span className="tabular font-display text-5xl font-bold leading-[0.9] tracking-[-0.04em] text-muted sm:text-7xl">
              {b}<span className="text-[0.45em]">%</span>
            </span>
          </div>
          <svg width="72" height="24" viewBox="0 0 80 24" fill="none" stroke="var(--pencil)" strokeWidth="1.6" strokeLinecap="round"
            className="mb-4 w-12 shrink sm:mb-6 sm:w-[72px]">
            <path d="M2 12h72M66 5l8 7-8 7" />
          </svg>
          <div className="flex flex-col items-end gap-1">
            <span className="text-[13px] font-semibold text-pencil">After</span>
            <span className="tabular font-display text-5xl font-bold leading-[0.9] tracking-[-0.04em] text-pencil sm:text-7xl">
              {Number.isInteger(Number(a)) ? <CountUp value={Number(a)} from={Number(b)} /> : a}<span className="text-[0.45em] text-pencil">%</span>
            </span>
          </div>
        </div>
        <ScoreRule value={after} before={before} band={band} />
        <span aria-hidden="true" className={`text-sm ${v.tone === "good" ? "font-medium text-success" : "text-muted"}`}>{v.text}</span>
      </div>
      {result.keyword_match?.approximate && (
        <p className="m-0 flex items-start gap-2 text-[13px] leading-relaxed text-warning">
        <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
        <span>Approximate: the AI couldn't read this job description, so its keywords were picked by simple rules.</span>
        </p>
      )}
      {gained.length > 0 && (
        <p className="m-0 border-t border-line pt-4 text-sm leading-relaxed">
          <span className="text-muted">Now on your resume: </span>
          {gained.map((r, i) => (
            <span key={r.keyword}>{i > 0 && ", "}<ins className="mark-ins">{r.keyword}</ins></span>
          ))}
        </p>
      )}
      {result.keyword_match?.guidance && <MatchGuidance guidance={result.keyword_match.guidance} />}
      {missing.length > 0 && (
        <div className="flex flex-col gap-3 border-t border-line pt-4">
          <p className="m-0 font-serif text-[15px] italic leading-relaxed text-muted">
            {flat
              ? "The wording changed, but the match didn't: rewrites only reword what's already on your resume, so it moves when you add a job keyword you really have."
              : "To go further, add the job keywords you really have."}
          </p>
          <div>
            <span className="text-[13px] font-semibold">Still missing ({missing.length})</span>
            <ul className="m-0 mt-2 flex flex-wrap gap-1.5 p-0">
              {shown.map((r) => (
                <li key={r.keyword} className="list-none rounded-[3px] border border-dashed border-field px-2.5 py-1 text-xs">
                  {r.keyword}{r.required ? <span className="text-muted"> · required</span> : null}
                </li>
              ))}
              {missing.length > shown.length && (
                <li className="list-none px-1 py-1 text-xs text-muted">+{missing.length - shown.length} more</li>
              )}
            </ul>
          </div>
          <div>
            <Button onClick={onAddKeywords}>
              {asked ? "Add the ones you have" : "Add the ones you have, in your own words"} <Icon name="arrow-right" size={16} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

const TABS = ["Preview", "Change log", "Content checks", "Notes", "File checks"] as const;
type Tab = (typeof TABS)[number];

/** Step 4: the finished files, how the match moved, and what changed. */
export function Results() {
  const { run, updateRun } = useApp();
  const [arranging, setArranging] = useState(false);
  if (arranging && run.results?.arrangement) {
    return <Arrange result={run.results} onBack={() => setArranging(false)}
      onResult={(r) => updateRun({ results: r, resultsVersion: run.resultsVersion + 1 })} />;
  }
  return <ResultsView onArrange={() => setArranging(true)} />;
}

function ResultsView({ onArrange }: { onArrange: () => void }) {
  const { run, goTo, updateRun } = useApp();
  const result = run.results!;
  const heading = useFocusHeading();
  const [tab, setTab] = useState<Tab>("Preview");
  const [log, setLog] = useState<string | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<{ text: string; n: number } | null>(null);
  const onDownloadError = (text: string) => setDownloadError((e) => ({ text, n: (e?.n ?? 0) + 1 }));
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // A gentle parallax: the score sheet drifts a little slower than the page.
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const drift = useTransform(scrollY, [0, 500], [0, reduce === false ? -28 : 0]);

  useEffect(() => {
    if (tab !== "Change log" || log !== null || !result.files.changes) return;
    getChangeLog().then(setLog).catch((e) => setLogError(friendlyError(e)));
  }, [tab, log, result.files.changes]);

  const rows = result.keyword_match?.rows ?? [];
  const asked = (run.drafted?.gap_questions.length ?? 0) > 0;
  const applied = result.applied; // what the server really put in the files
  const issues = result.content_lint?.issues ?? [];
  const fileWarnings = [...result.docx_warnings.map((w) => `DOCX: ${w}`), ...result.pdf_warnings.map((w) => `PDF: ${w}`)];
  // Serious read-back problems vs minor differences (P8.26); older results have no split.
  const serious = result.file_checks ? result.file_checks.serious : fileWarnings;
  const minor = result.file_checks?.minor ?? [];
  const lost = result.coverage?.lost ?? [];
  const fileSet = new Set([...result.docx_warnings, ...result.pdf_warnings]);
  // tailor_resume repeats the file warnings in `warnings`; the rest are notes on the content.
  const notes = result.warnings.filter((w) => !fileSet.has(w) && !w.startsWith("Strict Factual Mode"));

  const onTabKey = (e: KeyboardEvent, i: number) => {
    const last = TABS.length - 1;
    const next = e.key === "ArrowRight" ? (i === last ? 0 : i + 1) : e.key === "ArrowLeft" ? (i === 0 ? last : i - 1)
      : e.key === "Home" ? 0 : e.key === "End" ? last : null;
    if (next === null) return;
    e.preventDefault();
    setTab(TABS[next]);
    tabRefs.current[next]?.focus();
  };

  return (
    <div className="mx-auto flex max-w-[1240px] flex-col gap-12 px-4 py-12 md:px-8 md:py-16">
      <section className="grid items-center gap-10 md:grid-cols-2 md:gap-12">
        <div className="flex flex-col gap-5">
          <h1 ref={heading} tabIndex={-1} className="font-display text-[44px] font-bold leading-[1.02] tracking-[-0.035em] outline-none md:text-[62px]">
            {result.success ? "Your resume is ready." : "Your resume is ready, with warnings."}
          </h1>
          <p className="max-w-[460px] text-base leading-relaxed text-muted">
            {result.success
              ? "Read back from the finished files to confirm nothing was lost. Every change is listed below."
              : "Some checks on the finished files raised problems. See File checks below before you send it."}
          </p>
          {applied?.strict_withheld && (
            <p role="status" className="m-0 rounded-[3px] border border-warning bg-panel p-4 text-sm leading-relaxed">
              Strict factual mode withheld every rewrite, because at least one failed the fact check. The files keep your
              original wording. Go back to review to edit or reject the failing rewrite, or turn strict mode off in settings.
            </p>
          )}
          <div className="flex flex-col gap-3 sm:flex-row">
            {result.files.pdf && <Download kind="pdf" label="Download PDF" primary onError={onDownloadError} />}
            {result.files.docx && <Download kind="docx" label="Download DOCX" primary={!result.files.pdf} onError={onDownloadError} />}
          </div>
          {downloadError && (
            <p key={downloadError.n} role="alert" className="m-0 flex items-start gap-2 text-sm font-medium text-danger">
              <Icon name="alert" size={16} className="mt-0.5 shrink-0" /><span><span className="font-semibold">Error:</span> {downloadError.text}</span>
            </p>
          )}
          {result.files.html && (
            <a href={fileUrl("html")} download className="w-fit text-sm text-pencil underline-offset-4 hover:underline">
              Download as a web page (HTML)
            </a>
          )}
          {!result.files.pdf && result.files.docx && (
            <p className="m-0 text-xs text-muted">A PDF couldn't be made on the server (it needs LibreOffice); the DOCX is ready.</p>
          )}
          {result.addition_note && <p className="m-0 text-sm text-muted">Your addition was included: {result.addition_note}</p>}
          {result.arrangement && (
            <div className="flex flex-col gap-1.5 border-t border-line pt-4 sm:flex-row sm:items-center sm:gap-4">
              <Button onClick={onArrange}>Arrange and edit</Button>
              <span className="text-sm text-muted">Reorder sections and bullets, hide what you don't need, reword a line, or bring back what was trimmed.</span>
            </div>
          )}
        </div>
        <motion.div style={{ y: drift }}>
          <ScoreReveal result={result} beforeRows={run.drafted?.keyword_match?.rows ?? []} asked={asked}
            onAddKeywords={() => { updateRun({ jumpTo: asked ? "gaps" : "addition" }); goTo("review"); }} />
        </motion.div>
      </section>

      <section aria-label="Summary" className="sheet flex flex-col gap-2 rounded-[3px] px-6 py-5 md:flex-row md:items-start md:gap-10 md:px-8">
        <div className="flex shrink-0 items-center gap-2.5 md:w-44 md:flex-col md:items-start md:pt-3">
          {/* the editor's sign-off, drawn in pencil */}
          <svg aria-hidden="true" viewBox="0 0 40 24" className={`h-6 w-10 ${serious.length || lost.length ? "text-warning" : "text-pencil"}`}>
            <path d="M3 13.5 12 21 37 3" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-serif text-[15px] italic text-muted">
            {lost.length ? "Content missing from the files: see File checks"
              : serious.length ? "Read back, with problems: see File checks"
              : minor.length ? "Checked: the files read back, with small differences" : "Checked: the files read back cleanly"}
          </span>
        </div>
        <ul className="m-0 grid flex-1 p-0 sm:grid-cols-2 sm:gap-x-10">
        <SignOffLine value={rows.filter((r) => r.found).length} unit={`of ${rows.length}`} label="Job keywords on your resume" />
        <SignOffLine value={applied?.bullets ?? "—"}
          label={applied?.bullets_edited
            ? `Bullets rewritten (${applied.bullets_edited} in your own words, the rest fact-checked)`
            : "Bullets rewritten, all fact-checked"} />
        <SignOffLine value={result.pages || "—"} unit={result.pages === 1 ? "page" : result.pages ? "pages" : undefined}
          label={run.template === "keep" ? "Your own layout" : "A4, ATS template"} />
        <SignOffLine value={issues.length} label={issues.length === 1 ? "Content suggestion to consider" : "Content suggestions to consider"} />
        </ul>
      </section>

      <section className="flex flex-col gap-6">
        <div role="tablist" aria-label="Details" className="flex gap-7 overflow-x-auto border-b border-line">
          {TABS.map((t, i) => (
            <button key={t} ref={(el) => { tabRefs.current[i] = el; }} role="tab" type="button" id={`rtab-${i}`}
              aria-selected={tab === t} aria-controls="results-panel" tabIndex={tab === t ? 0 : -1}
              onClick={() => setTab(t)} onKeyDown={(e) => onTabKey(e, i)}
              className={`min-h-11 whitespace-nowrap border-b-2 pb-2 text-[15px] transition-colors ${
                tab === t ? "border-pencil font-semibold text-ink" : "border-transparent text-muted hover:text-ink"}`}>
              {t}
              {t === "Content checks" && issues.length ? <span className="text-muted"> ({issues.length})</span> : null}
              {t === "Notes" && notes.length ? <span className="text-muted"> ({notes.length})</span> : null}
              {t === "File checks" && (serious.length + lost.length)
                ? <span className="text-danger"> ({serious.length + lost.length})</span>
                : t === "File checks" && minor.length ? <span className="text-muted"> ({minor.length})</span> : null}
            </button>
          ))}
        </div>

        <div id="results-panel" role="tabpanel" tabIndex={0} aria-labelledby={`rtab-${TABS.indexOf(tab)}`} className="outline-none">
          {tab === "Preview" && (
            result.pages > 0 ? (
              <div className="flex flex-col items-center gap-10 py-4">
                {Array.from({ length: result.pages }, (_, i) => (
                  <motion.img key={`${run.resultsVersion}-${i}`} src={previewUrl(i + 1, run.resultsVersion)} loading="lazy"
                    alt={`Page ${i + 1} of your tailored resume`}
                    initial={reduce === false ? { opacity: 0, y: 24 } : false}
                    whileInView={reduce === false ? { opacity: 1, y: 0 } : undefined}
                    viewport={{ once: true, margin: "-60px" }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                    className="w-full max-w-[820px] border border-line bg-paper shadow-sheet-lift" />
                ))}
                <p className="m-0 text-xs text-muted">This is the exact PDF you download.</p>
              </div>
            ) : (
              <p className="text-sm text-muted">
                {result.files.pdf ? "The preview couldn't be drawn. Download the PDF to view it."
                  : "No preview is available (the PDF couldn't be made). Download the DOCX to view it."}
              </p>
            )
          )}

          {tab === "Change log" && (
            <div className="max-w-[820px]">
              {log !== null ? <MiniMarkdown source={log} />
                : logError || !result.files.changes ? <p className="text-sm text-muted">{logError ?? "The change log isn't available."}</p>
                : <p className="text-sm text-muted">Loading…</p>}
              {result.files.changes && log !== null && (
                <a href={fileUrl("changes")} download className="mt-4 inline-block min-h-11 text-sm">Download the change log</a>
              )}
            </div>
          )}

          {tab === "Content checks" && (
            <div className="flex max-w-[820px] flex-col gap-4">
              {result.content_lint && (
                <p className="m-0 text-sm text-muted">
                  {result.content_lint.bullets_with_metrics} of {result.content_lint.bullets} bullets include a number.
                  These are suggestions only; nothing was changed automatically.
                </p>
              )}
              {issues.length ? (
                <ul className="flex flex-col">
                  {issues.map((issue, i) => (
                    <li key={i} className="flex flex-col gap-1 border-t border-line py-4">
                      <span className="text-xs text-pencil">{CHECK_LABELS[issue.check] ?? issue.check} · {issue.where}</span>
                      <span className="text-sm">{issue.message}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-success">All clear.</p>}
            </div>
          )}

          {tab === "Notes" && (
            <div className="flex max-w-[820px] flex-col gap-3 text-sm">
              {notes.length === 0 ? <p className="m-0 text-muted">No notes on this run.</p> : (
                <ul className="flex flex-col">
                  {notes.map((w, i) => <li key={i} className="break-words border-t border-line py-3 leading-relaxed">{w}</li>)}
                </ul>
              )}
            </div>
          )}

          {tab === "File checks" && (
            <div className="flex max-w-[820px] flex-col gap-3 text-sm">
              {lost.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="m-0 font-semibold text-danger">Lines from your resume missing from the files</p>
                  <ul className="flex flex-col">
                    {lost.map((w, i) => <li key={i} className="break-words border-t border-line py-3 font-serif leading-relaxed">{w}</li>)}
                  </ul>
                </div>
              )}
              {serious.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="m-0 font-semibold">Needs attention: an ATS may misread this</p>
                  <ul className="flex flex-col">
                    {serious.map((w, i) => <li key={i} className="break-words border-t border-line py-3 leading-relaxed">{w}</li>)}
                  </ul>
                </div>
              )}
              {minor.length > 0 && (
                <details className="rounded-[3px] border border-line bg-panel p-4">
                  <summary className="min-h-6 cursor-pointer font-medium text-muted hover:text-ink">
                    {minor.length} small difference{minor.length === 1 ? "" : "s"} when the files are read back (usually harmless)
                  </summary>
                  <ul className="mt-2 flex flex-col">
                    {minor.map((w, i) => <li key={i} className="break-words border-t border-line py-3 leading-relaxed">{w}</li>)}
                  </ul>
                </details>
              )}
              {!lost.length && !serious.length && !minor.length && (
                <p className="m-0 text-success">The files read back cleanly: no problems found.</p>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-3 border-t border-line pt-8 sm:flex-row sm:items-center">
        <Button onClick={() => goTo("review")}>
          <Icon name="arrow-right" size={16} className="rotate-180" /> Back to review
        </Button>
        <span className="text-sm text-muted">Change your choices and generate again.</span>
      </section>
    </div>
  );
}
