import { type KeyboardEvent, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { Breakdown, KeywordList } from "../components/KeywordList";
import { ScoreDial, verdict } from "../components/ScoreDial";
import type { AnalysisReport, MatchStatus, RequirementMatch } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";

const STATUS: Record<MatchStatus, { label: string; tone: string }> = {
  EXPLICIT: { label: "Shown", tone: "text-success border-success-line" },
  SUPPORTED: { label: "Shown", tone: "text-success border-success-line" },
  PARTIAL: { label: "Partly", tone: "text-pencil border-pencil/60" },
  SEMANTIC_PARTIAL: { label: "Similar wording", tone: "text-pencil border-pencil/60" },
  UNCERTAIN: { label: "Unclear", tone: "text-muted border-field" },
  MISSING: { label: "Not shown", tone: "text-danger border-danger/50" },
};

const TABS = [
  { id: "required", label: "Must have" },
  { id: "preferred", label: "Nice to have" },
  { id: "missing", label: "Not on your resume" },
] as const;

function Requirement({ m }: { m: RequirementMatch }) {
  const s = STATUS[m.status];
  return (
    <li className="flex flex-col gap-1.5 border-b border-line py-3.5 sm:flex-row sm:items-start sm:gap-4">
      <span className={`w-fit shrink-0 border px-2 py-0.5 text-[11px] tracking-[0.06em] ${s.tone}`}>{s.label}</span>
      <span className="flex flex-col gap-1">
        <span className="text-sm leading-relaxed">{m.requirement_text}</span>
        {m.status === "SEMANTIC_PARTIAL" && m.explanation && <span className="text-xs text-muted">{m.explanation}</span>}
      </span>
    </li>
  );
}

/** "Just check my match": the score, what it's made of, and each JD
 *  requirement. Nothing is changed or kept. */
export function Report({ report, onTailor, onStartOver, busy, error }: {
  report: AnalysisReport;
  onTailor: () => void;
  onStartOver: () => void;
  busy?: boolean;
  error?: string | null;
}) {
  const heading = useFocusHeading();
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("required");
  const match = report.keyword_match;
  const band = match?.target_band ?? [75, 85];
  const v = verdict(report.alignment_score, band);
  const lists = { required: report.required_matches, preferred: report.preferred_matches, missing: report.missing_requirements };
  const similar = [...report.required_matches, ...report.preferred_matches].filter((m) => m.status === "SEMANTIC_PARTIAL").length;
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // Tabs pattern: arrows, Home and End move between tabs.
  const onTabKey = (e: KeyboardEvent, i: number) => {
    const last = TABS.length - 1;
    const next = e.key === "ArrowRight" ? (i === last ? 0 : i + 1) : e.key === "ArrowLeft" ? (i === 0 ? last : i - 1)
      : e.key === "Home" ? 0 : e.key === "End" ? last : null;
    if (next === null) return;
    e.preventDefault();
    setTab(TABS[next].id);
    tabRefs.current[next]?.focus();
  };

  return (
    <div className="mx-auto flex max-w-[1240px] flex-col gap-12 px-4 py-12 md:px-8 md:py-16">
      <section className="grid items-center gap-10 md:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-5">
          <p className="text-xs tracking-[0.28em] text-pencil">MATCH REPORT</p>
          <h1 ref={heading} tabIndex={-1} className="font-display text-5xl font-medium leading-[1.02] outline-none md:text-[64px]">
            How your resume reads for this job.
          </h1>
          <p className={`text-base ${v.tone === "good" ? "text-success" : "text-muted"}`}>
            {match ? `${match.rows.filter((r) => r.found).length} of ${match.rows.length} keywords found. ` : ""}{v.text}
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button variant="primary" size="lg" onClick={onTailor} disabled={busy} aria-busy={busy}>
              {busy ? "Reading your resume…" : "Tailor my resume for this job"} {!busy && <Icon name="arrow-right" />}
            </Button>
            <Button size="lg" onClick={onStartOver}>Check another</Button>
          </div>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        </div>
        <div className="border border-line bg-panel p-7">
          <ScoreDial value={report.alignment_score} band={band} />
        </div>
      </section>

      {match && (
        <section aria-label="Keywords" className="grid gap-10 border-t border-line pt-10 md:grid-cols-[1fr_360px]">
          <KeywordList match={match} />
          <div className="flex flex-col gap-4">
            <Breakdown match={match} />
            <p className="text-xs leading-relaxed text-muted">
              Weighted share of the job's keywords found in your resume. Hard skills count most, then the job title,
              education and certifications, then soft skills; required keywords count 1.5×.
            </p>
          </div>
        </section>
      )}

      <section aria-labelledby="reqs" className="flex flex-col gap-5 border-t border-line pt-10">
        <h2 id="reqs" className="font-display text-[32px] font-medium">What the job asks for</h2>
        <div role="tablist" aria-label="Requirements" className="flex gap-6 overflow-x-auto border-b border-line">
          {TABS.map((t, i) => (
            <button key={t.id} ref={(el) => { tabRefs.current[i] = el; }} role="tab" type="button" id={`tab-${t.id}`}
              aria-selected={tab === t.id} aria-controls="req-panel" tabIndex={tab === t.id ? 0 : -1}
              onClick={() => setTab(t.id)} onKeyDown={(e) => onTabKey(e, i)}
              className={`min-h-11 whitespace-nowrap border-b-2 pb-2 text-sm transition-colors ${
                tab === t.id ? "border-pencil text-ink" : "border-transparent text-muted hover:text-ink"}`}>
              {t.label} <span className="text-muted">({lists[t.id].length})</span>
            </button>
          ))}
        </div>
        <div id="req-panel" role="tabpanel" tabIndex={0} aria-labelledby={`tab-${tab}`}>
          {lists[tab].length ? (
            <ul>{lists[tab].map((m) => <Requirement key={m.requirement_id} m={m} />)}</ul>
          ) : (
            <p className="py-4 text-sm text-muted">Nothing here.</p>
          )}
        </div>
        {similar > 0 && (
          <p className="text-xs text-muted">
            {similar} requirement{similar === 1 ? "" : "s"} match only through similar wording, not the job's exact terms.
          </p>
        )}
      </section>
    </div>
  );
}
