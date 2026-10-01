import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { MiniMarkdown } from "../components/MiniMarkdown";
import { verdict } from "../components/ScoreDial";
import { downloadFile, fileUrl, friendlyError, getChangeLog, previewUrl } from "../lib/api";
import { useApp } from "../lib/store";
import type { TailorResult } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";

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
    <button type="button" disabled={busy} aria-busy={busy}
      onClick={() => {
        setBusy(true);
        downloadFile(kind).catch((e) => onError(friendlyError(e))).finally(() => setBusy(false));
      }}
      className={`inline-flex h-13 items-center justify-center gap-2.5 rounded-[2px] px-6 text-[15px] transition-colors disabled:opacity-60 ${
        primary ? "bg-gold font-semibold text-on-gold hover:bg-gold-hover" : "border border-line-strong text-ink hover:border-gold"}`}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"
        strokeLinejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>
      {label}
    </button>
  );
}

/** Whole percent, unless rounding would hide a real change. */
function pair(before: number, after: number): [string, string] {
  const hidden = Math.round(before) === Math.round(after) && Math.abs(after - before) >= 0.05;
  return hidden ? [before.toFixed(1), after.toFixed(1)] : [String(Math.round(before)), String(Math.round(after))];
}

function StatTile({ value, unit, label }: { value: string | number; unit?: string; label: string }) {
  return (
    <div className="flex flex-col gap-2 bg-bg p-5 md:p-6">
      <span className="font-display text-[40px] leading-none">
        {value}{unit && <span className="text-[22px] text-muted"> {unit}</span>}
      </span>
      <span className="text-[13px] text-muted">{label}</span>
    </div>
  );
}

/** Before -> after, the Novoresume-style reveal. */
function ScoreReveal({ result }: { result: TailorResult }) {
  const before = result.initial_alignment_score;
  const after = result.alignment_score;
  const band = result.keyword_match?.target_band ?? [75, 85];
  const v = verdict(after, band);
  const [b, a] = pair(before, after);
  return (
    <div className="flex flex-col gap-6 border border-line bg-panel p-6 md:p-9"
      role="img" aria-label={`Keyword match: ${before.toFixed(1)}% before, ${after.toFixed(1)}% after tailoring. ${v.text}`}>
      <span aria-hidden="true" className="text-[11px] tracking-[0.2em] text-muted">KEYWORD MATCH</span>
      <div aria-hidden="true" className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[13px] text-muted">Before</span>
          <span className="font-display text-5xl leading-[0.9] text-muted sm:text-7xl md:text-[88px]">
            {b}<span className="text-[0.45em]">%</span>
          </span>
        </div>
        <svg width="72" height="24" viewBox="0 0 80 24" fill="none" stroke="var(--gold)" strokeWidth="1.2" className="mb-4 w-12 shrink sm:mb-6 sm:w-[72px]">
          <path d="M0 12h76M68 5l8 7-8 7" />
        </svg>
        <div className="flex flex-col items-end gap-1">
          <span className="text-[13px] text-gold">After</span>
          <span className="font-display text-5xl leading-[0.9] sm:text-7xl md:text-[88px]">
            {a}<span className="text-[0.45em] text-gold">%</span>
          </span>
        </div>
      </div>
      <div aria-hidden="true" className="flex flex-col gap-2.5">
        <div className="h-2 bg-line"><div className="h-full bg-line-strong" style={{ width: `${Math.min(100, before)}%` }} /></div>
        <div className="h-2 bg-line"><div className="h-full bg-gold" style={{ width: `${Math.min(100, after)}%` }} /></div>
      </div>
      <span aria-hidden="true" className={`text-[13px] ${v.tone === "good" ? "text-success" : "text-muted"}`}>{v.text}</span>
    </div>
  );
}

const TABS = ["Preview", "Change log", "Content checks", "Notes", "File checks"] as const;
type Tab = (typeof TABS)[number];

/** Step 4: the finished files, how the match moved, and what changed. */
export function Results() {
  const { run, goTo } = useApp();
  const result = run.results!;
  const heading = useFocusHeading();
  const [tab, setTab] = useState<Tab>("Preview");
  const [log, setLog] = useState<string | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<{ text: string; n: number } | null>(null);
  const onDownloadError = (text: string) => setDownloadError((e) => ({ text, n: (e?.n ?? 0) + 1 }));
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (tab !== "Change log" || log !== null || !result.files.changes) return;
    getChangeLog().then(setLog).catch((e) => setLogError(friendlyError(e)));
  }, [tab, log, result.files.changes]);

  const rows = result.keyword_match?.rows ?? [];
  const applied = result.applied; // what the server really put in the files
  const issues = result.content_lint?.issues ?? [];
  const fileWarnings = [...result.docx_warnings.map((w) => `DOCX: ${w}`), ...result.pdf_warnings.map((w) => `PDF: ${w}`)];
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
          <p className="text-xs tracking-[0.28em] text-gold">TAILORED RESUME</p>
          <h1 ref={heading} tabIndex={-1} className="font-display text-5xl font-medium leading-[1.02] outline-none md:text-[68px]">
            {result.success ? "Your resume is ready." : "Your resume is ready, with warnings."}
          </h1>
          <p className="max-w-[460px] text-base leading-relaxed text-muted">
            {result.success
              ? "Read back from the finished files to confirm nothing was lost. Every change is listed below."
              : "Some checks on the finished files raised problems. See File checks below before you send it."}
          </p>
          {applied?.strict_withheld && (
            <p role="status" className="m-0 border border-gold/60 bg-gold-soft p-4 text-sm leading-relaxed">
              Strict factual mode withheld every rewrite, because at least one failed the fact check. The files keep your
              original wording. Go back to review to edit or reject the failing rewrite, or turn strict mode off in settings.
            </p>
          )}
          <div className="flex flex-col gap-3 sm:flex-row">
            {result.files.pdf && <Download kind="pdf" label="Download PDF" primary onError={onDownloadError} />}
            {result.files.docx && <Download kind="docx" label="Download DOCX" primary={!result.files.pdf} onError={onDownloadError} />}
          </div>
          {downloadError && <p key={downloadError.n} role="alert" className="m-0 text-sm text-danger">{downloadError.text}</p>}
          {!result.files.pdf && result.files.docx && (
            <p className="m-0 text-xs text-muted">A PDF couldn't be made on the server (it needs LibreOffice); the DOCX is ready.</p>
          )}
          {result.addition_note && <p className="m-0 text-sm text-muted">Your addition was included: {result.addition_note}</p>}
        </div>
        <ScoreReveal result={result} />
      </section>

      <section aria-label="Summary" className="grid grid-cols-2 gap-px border border-line bg-line md:grid-cols-4">
        <StatTile value={rows.filter((r) => r.found).length} unit={`of ${rows.length}`} label="Job keywords now on your resume" />
        <StatTile value={applied?.bullets ?? "—"}
          label={applied?.bullets_edited
            ? `Bullets rewritten (${applied.bullets_edited} in your own words, the rest fact-checked)`
            : "Bullets rewritten, all fact-checked"} />
        <StatTile value={result.pages || "—"} unit={result.pages === 1 ? "page" : result.pages ? "pages" : undefined}
          label={run.template === "keep" ? "Your own layout" : "A4, ATS template"} />
        <StatTile value={issues.length} label={issues.length === 1 ? "Content suggestion to consider" : "Content suggestions to consider"} />
      </section>

      <section className="flex flex-col gap-6">
        <div role="tablist" aria-label="Details" className="flex gap-7 overflow-x-auto border-b border-line">
          {TABS.map((t, i) => (
            <button key={t} ref={(el) => { tabRefs.current[i] = el; }} role="tab" type="button" id={`rtab-${i}`}
              aria-selected={tab === t} aria-controls="results-panel" tabIndex={tab === t ? 0 : -1}
              onClick={() => setTab(t)} onKeyDown={(e) => onTabKey(e, i)}
              className={`min-h-11 whitespace-nowrap border-b-2 pb-2 text-[15px] transition-colors ${
                tab === t ? "border-gold text-ink" : "border-transparent text-muted hover:text-ink"}`}>
              {t}
              {t === "Content checks" && issues.length ? <span className="text-muted"> ({issues.length})</span> : null}
              {t === "Notes" && notes.length ? <span className="text-muted"> ({notes.length})</span> : null}
              {t === "File checks" && fileWarnings.length
                ? <span className="text-danger"> ({fileWarnings.length})</span> : null}
            </button>
          ))}
        </div>

        <div id="results-panel" role="tabpanel" tabIndex={0} aria-labelledby={`rtab-${TABS.indexOf(tab)}`} className="outline-none">
          {tab === "Preview" && (
            result.pages > 0 ? (
              <div className="flex flex-col items-center gap-8">
                {Array.from({ length: result.pages }, (_, i) => (
                  <img key={`${run.resultsVersion}-${i}`} src={previewUrl(i + 1, run.resultsVersion)} loading="lazy"
                    alt={`Page ${i + 1} of your tailored resume`}
                    className="w-full max-w-[820px] bg-paper shadow-[0_30px_60px_rgb(0_0_0/0.35)]" />
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
                      <span className="text-xs text-gold">{CHECK_LABELS[issue.check] ?? issue.check} · {issue.where}</span>
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
              {fileWarnings.length === 0 ? (
                <p className="m-0 text-success">The files read back cleanly: no problems found.</p>
              ) : (
                <ul className="flex flex-col">
                  {fileWarnings.map((w, i) => <li key={i} className="break-words border-t border-line py-3 leading-relaxed">{w}</li>)}
                </ul>
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
