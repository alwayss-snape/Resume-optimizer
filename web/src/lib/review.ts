// What the review screen keeps (P5.4) and how it becomes API requests.
// Plain functions so the rules are tested apart from the UI.
import type { AddedJob, Selection, TailorRequest } from "./api";
import type { Proposal, ProposalsResult } from "./types";

export type Decision = "accept" | "reject";

export interface GapInput {
  ticked: string[];
  answer: string;
  target: string; // "auto" | "new_project" | an experience id
}

export interface NewJob {
  company: string;
  title: string;
  location: string;
  current: boolean;
  start: string; // "YYYY-MM" from <input type="month">, or ""
  end: string;
  description: string;
}

export interface ReviewState {
  decisions: Record<string, Decision>;
  edits: Record<string, string>; // proposal id -> the user's text
  gaps: Record<string, GapInput>;
  addition: { text: string; target: string };
  newJob: NewJob;
  conditions?: string[]; // job conditions the user meets (P8.20)
  region?: string | null; // paper and dates, suggested from the JD (P10.3)
  cvMode?: string | null; // standard / academic / federal, suggested from the resume and JD (P10.5)
  leftOut?: string[]; // project keys left out (P10.13), starting with the ones not suggested
  brief?: { title: string; positioning: string }; // P11.3: the owner's edits to the role brief
  style?: string; // P11.9: "standard" or "classic"
}

export const EMPTY_JOB: NewJob = { company: "", title: "", location: "", current: false, start: "", end: "", description: "" };

/** Every proposal starts accepted (as the old Streamlit page did), except an opt-in one such as
 *  a tailored summary replacing the user's own; saved answers pre-tick their keywords and
 *  pre-fill the answer. */
export function initialReview(drafted: ProposalsResult): ReviewState {
  return {
    decisions: Object.fromEntries(drafted.proposals.map((p) => [p.id, (p.opt_in ? "reject" : "accept") as Decision])),
    edits: {},
    gaps: Object.fromEntries(drafted.gap_questions.map((q) => [q.id, { ticked: [...q.saved_keywords], answer: q.saved_answer, target: "auto" }])),
    addition: { text: "", target: "auto" },
    newJob: EMPTY_JOB,
    conditions: [],
    region: drafted.region?.region ?? null,
    cvMode: drafted.cv_mode?.mode ?? null,
    leftOut: (drafted.projects ?? []).filter((p) => !p.chosen).map((p) => p.key),
    brief: { title: drafted.role_brief?.headline ?? "", positioning: drafted.role_brief?.positioning ?? "" },
  };
}

/** Bullet ids of the projects left out: their cards hide and they don't count. */
export function leftOutBullets(drafted: ProposalsResult, review: ReviewState): Set<string> {
  const keys = new Set(review.leftOut ?? []);
  // The project's bullets, and its key (a heading card's target).
  return new Set((drafted.projects ?? []).filter((p) => keys.has(p.key)).flatMap((p) => [p.key, ...p.bullet_ids]));
}

/** Proposals still on the page: not those of a left-out project. */
export function visibleProposals(drafted: ProposalsResult, review: ReviewState): Proposal[] {
  const gone = leftOutBullets(drafted, review);
  return drafted.proposals.filter((p) => !p.target || !gone.has(p.target));
}

export const textOf = (p: Proposal, review: ReviewState) => review.edits[p.id] ?? p.proposed;
export const isEdited = (p: Proposal, review: ReviewState) =>
  review.edits[p.id] !== undefined && review.edits[p.id].trim() !== p.proposed.trim();

/** The accepted proposals, with edited text where the user changed it. */
export function selection(proposals: Proposal[], review: ReviewState): Selection[] {
  return proposals
    .filter((p) => review.decisions[p.id] !== "reject")
    .map((p) => (isEdited(p, review) ? { id: p.id, text: review.edits[p.id] } : { id: p.id }));
}

/** Will this proposal actually be used? A fact-check failure is dropped
 *  unless the user rewrote it themselves. */
export function willApply(p: Proposal, review: ReviewState): boolean {
  if (review.decisions[p.id] === "reject") return false;
  return p.state !== "dropped" || isEdited(p, review);
}

export const anyJobField = (j: NewJob) =>
  [j.company, j.title, j.location, j.description, j.start, j.end].some((v) => v.trim()) || j.current;

/** Problems with the "add a job" form, as the server would report them;
 *  null when it's empty or complete. */
export function newJobProblem(j: NewJob, otherwise = "clear the job fields"): string | null {
  if (!anyJobField(j)) return null;
  const missing = [
    ["company", j.company.trim()], ["job title", j.title.trim()], ["start date", j.start],
    ['end date (or tick "I currently work here")', j.end || j.current], ["what you did there", j.description.trim()],
  ].filter(([, ok]) => !ok).map(([label]) => label);
  if (missing.length) return `To add the job, fill in: ${missing.join(", ")}. Or ${otherwise}.`;
  if (!j.current && j.end < j.start) return "The new job's end date is before its start date.";
  return null;
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
  "October", "November", "December"];

/** "2023-05" -> "May 2023", the way dates read on a resume. */
export const monthLabel = (ym: string) => (ym ? `${MONTH_NAMES[Number(ym.slice(5, 7)) - 1]} ${ym.slice(0, 4)}` : "");

/** A job added on the "check details" step, as the server's corrections take it. */
export const addedJob = (j: NewJob): AddedJob => ({
  company: j.company.trim(), title: j.title.trim(), location: j.location.trim(), current: j.current,
  start_date: monthLabel(j.start), end_date: j.current ? "Present" : monthLabel(j.end), description: j.description,
});

export function tailorRequest(proposals: Proposal[], review: ReviewState, options: {
  keepLayout: boolean;
  strictFactual: boolean;
  rememberAnswers: boolean;
}): TailorRequest {
  const j = review.newJob;
  return {
    selection: selection(proposals, review),
    gap_answers: review.gaps,
    addition: review.addition,
    new_role: anyJobField(j)
      ? { company: j.company, title: j.title, location: j.location, current: j.current,
          start: j.start ? `${j.start}-01` : null, end: j.end && !j.current ? `${j.end}-01` : null,
          description: j.description }
      : null,
    keep_layout: options.keepLayout,
    strict_factual: options.strictFactual,
    remember_answers: options.rememberAnswers,
    conditions: review.conditions ?? [],
    region: review.region ?? null,
    cv_mode: review.cvMode ?? null,
    left_out: review.leftOut ?? null,
    role_brief: review.brief ?? null,
    style: review.style ?? null,
  };
}

/** Cards in reading order: summary, skills, then bullets by job/project. */
export function groupProposals(proposals: Proposal[]): { key: string; label: string; items: Proposal[] }[] {
  const groups: { key: string; label: string; items: Proposal[] }[] = [];
  const find = (key: string, label: string) => {
    let g = groups.find((x) => x.key === key);
    if (!g) groups.push((g = { key, label, items: [] }));
    return g;
  };
  for (const p of proposals.filter((x) => x.kind === "summary")) find("summary", "Professional summary").items.push(p);
  for (const p of proposals.filter((x) => x.kind === "skills")) find("skills", "Skills").items.push(p);
  // A job's project headings first, then its bullets (P10.13).
  const order = { heading: 0, project: 1, bullet: 2 } as Record<string, number>;
  for (const p of proposals.filter((x) => x.kind in order).sort((a, b) => order[a.kind] - order[b.kind])) {
    find(p.section?.id ?? "other", p.section?.label ?? "Other bullets").items.push(p);
  }
  return groups;
}
