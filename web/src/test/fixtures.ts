import type { AnalysisReport, Details, KeywordMatch, ProposalsResult } from "../lib/types";

export const DETAILS: Details = {
  candidate: { name: "Avery Lee", headline: "", email: "avery@example.com", phone: "", location: "Pune", links: ["github.com/avery"] },
  experience: [
    { id: "exp_1", company: "Northwind", location: "", bullets: 3, groups: 0,
      roles: [{ title: "Data Analyst", start_date: "Jan 2022", end_date: "Present" }] },
    { id: "exp_2", company: "Contoso", location: "Remote", bullets: 2, groups: 0, roles: [] },
  ],
};

export const MATCH: KeywordMatch = {
  rate: 48.2,
  target_band: [75, 85],
  rows: [
    { keyword: "Python", kind: "hard", required: true, weight: 3, found: true, credit: 1, where: ["skills"] },
    { keyword: "Airflow", kind: "hard", required: true, weight: 3, found: false, credit: 0, where: [] },
    { keyword: "teamwork", kind: "soft", required: false, weight: 1, found: false, credit: 0, where: [] },
  ],
  breakdown: [{ Kind: "Hard skills", Found: "1 of 2", Points: "42.9 of 85.7" }],
};

export const REPORT: AnalysisReport = {
  alignment_score: 48.2,
  required_matches: [{ requirement_id: "r1", requirement_text: "Strong Python", status: "EXPLICIT", explanation: "" }],
  preferred_matches: [],
  missing_requirements: [{ requirement_id: "r2", requirement_text: "Airflow experience", status: "MISSING", explanation: "" }],
  score_components: { semantic_coverage: 0 },
  keyword_match: MATCH,
};

export const DRAFTED: ProposalsResult = {
  proposals: [
    { id: "p1", kind: "bullet", section: { id: "exp_1", kind: "experience", label: "Northwind — Data Analyst" },
      original: "Built dashboards in Python", proposed: "Built forecasting dashboards in Python", rationale: "Adds forecasting",
      state: "pass", state_label: "Pass", state_meaning: "fact-checked against your resume", note: null,
      diff: {
        original: [{ text: "Built" }, { text: "dashboards" }, { text: "in" }, { text: "Python", keyword: true }].map((s) => ({ changed: false, keyword: false, ...s })),
        proposed: [{ text: "Built" }, { text: "forecasting", changed: true }, { text: "dashboards" }, { text: "in" }, { text: "Python", keyword: true }].map((s) => ({ changed: false, keyword: false, ...s })),
      } },
  ],
  gap_questions: [],
  keyword_match: MATCH,
  gaps: [],
  pre_score: 48.2,
  experience_options: [{ id: "exp_1", label: "Northwind — Data Analyst" }],
  llm: { available: true, provider_label: "Groq (cloud)", fix_hint: "", attempted: 1, failed: 0, errors: [] },
};

/** A fetch Response whose body streams these SSE events. */
export function sseResponse(events: [string, unknown][]): Response {
  const text = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
  const bytes = new TextEncoder().encode(text);
  const body = new ReadableStream({
    start(controller) {
      // Split mid-event to prove partial chunks are buffered.
      controller.enqueue(bytes.slice(0, 7));
      controller.enqueue(bytes.slice(7));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

export const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
