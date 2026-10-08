import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { initialReview } from "../lib/review";
import { EMPTY_RUN, useApp } from "../lib/store";
import type { TailorResult } from "../lib/types";
import { DRAFTED, MATCH } from "../test/fixtures";
import type { KeywordMatch } from "../lib/types";
import { Results } from "./Results";

const RESULT: TailorResult = {
  success: true, alignment_score: 78.4, initial_alignment_score: 48.2, keyword_match: MATCH,
  content_lint: { bullets: 6, bullets_with_metrics: 2, issues: [{ check: "pronoun", where: "Northwind", message: "Drop personal pronouns." }] },
  addition_note: null, warnings: [], docx_warnings: [], pdf_warnings: [], target_pages: 1, pages: 2,
  applied: { bullets: 4, bullets_edited: 0, summary: true, skills: false, rejected: 0, strict_withheld: false },
  files: { docx: true, pdf: true, changes: true },
};

function show(result: Partial<TailorResult> = {}) {
  useApp.setState({ step: "results", reached: 3, run: { ...EMPTY_RUN, drafted: DRAFTED, review: initialReview(DRAFTED),
    results: { ...RESULT, ...result }, resultsVersion: 3 } });
  return render(<Results />);
}

beforeEach(() => useApp.setState({ running: false }));
afterEach(() => vi.unstubAllGlobals());

test("before and after, downloads, stats and page previews", () => {
  show();
  expect(screen.getByRole("heading", { name: "Your resume is ready." })).toHaveFocus();
  expect(screen.getByRole("img", { name: /48.2% before, 78.4% after/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download PDF" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download DOCX" })).toBeInTheDocument();
  expect(screen.getByText("Job keywords on your resume").previousSibling).toHaveTextContent("1 of 3");
  expect(screen.getByText(/Bullets rewritten/).previousSibling).toHaveTextContent("4"); // the server's count
  const pages = screen.getAllByRole("img", { name: /Page \d of your tailored resume/ });
  expect(pages.map((p) => p.getAttribute("src"))).toEqual(["/api/preview/1?v=3", "/api/preview/2?v=3"]);
});

test("no PDF: DOCX is the main download and the preview explains", () => {
  show({ files: { docx: true, pdf: false, changes: true }, pages: 0 });
  expect(screen.queryByRole("button", { name: "Download PDF" })).toBeNull();
  expect(screen.getByText(/needs LibreOffice/)).toBeInTheDocument();
  expect(screen.getByText(/No preview is available/)).toBeInTheDocument();
});

test("change log is fetched once and rendered as text", async () => {
  const fetchMock = vi.fn(async () => new Response("# Tailoring Report\n\n- Rewrote **bullet 1**\n- <img src=x onerror=alert(1)>"));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  show();
  await user.click(screen.getByRole("tab", { name: "Change log" }));
  expect(await screen.findByText("bullet 1")).toHaveProperty("tagName", "STRONG");
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument(); // shown as text, not markup
  expect(document.querySelector("img[src='x']")).toBeNull();
  await user.click(screen.getByRole("tab", { name: "Preview" }));
  await user.click(screen.getByRole("tab", { name: "Change log" }));
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("content and file checks; warnings change the headline", async () => {
  const user = userEvent.setup();
  // tailor_resume repeats file warnings inside `warnings`.
  show({ success: false, pdf_warnings: ["Name not found on page 1"],
    warnings: ["Name not found on page 1", "Kept your edited text as written (not fact-checked): Shipped X"] });
  expect(screen.getByRole("heading", { name: /ready, with warnings/ })).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: /Content checks/ }));
  expect(screen.getByText("Drop personal pronouns.")).toBeInTheDocument();
  expect(screen.getByText(/2 of 6 bullets include a number/)).toBeInTheDocument();
  const fileTab = screen.getByRole("tab", { name: /File checks/ });
  expect(within(fileTab).getByText("(1)")).toBeInTheDocument();
  await user.click(fileTab);
  expect(screen.getByText("PDF: Name not found on page 1")).toBeInTheDocument();
  expect(screen.queryByText(/Kept your edited text/)).toBeNull();
  await user.click(screen.getByRole("tab", { name: /Notes/ }));
  expect(screen.getByText(/Kept your edited text/)).toBeInTheDocument();
  expect(screen.queryByText("Name not found on page 1")).toBeNull();
});

test("strict mode withholding is said up front", () => {
  show({ applied: { ...RESULT.applied!, bullets: 0, strict_withheld: true },
    warnings: ["Strict Factual Mode: all rewrites withheld because at least one rewrite failed validation."] });
  expect(screen.getByRole("status")).toHaveTextContent(/withheld every rewrite/);
  expect(screen.getByText(/Bullets rewritten/).previousSibling).toHaveTextContent("0");
});

test("a download that fails says why instead of saving an error page", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Your session has expired. Please upload your resume again." }),
    { status: 404, headers: { "Content-Type": "application/json" } })));
  const user = userEvent.setup();
  show();
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your session has expired");
});

test("the change log renders its keyword table and nested warnings", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    "## Keyword Match\n\n| Keyword | Kind | Required | Found in |\n|---|---|---|---|\n| Python | hard | yes | skills |\n\n- DOCX warnings (1):\n  - Font fallback used")));
  const user = userEvent.setup();
  show();
  await user.click(screen.getByRole("tab", { name: "Change log" }));
  expect(await screen.findByRole("columnheader", { name: "Keyword" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Python" })).toBeInTheDocument();
  expect(screen.queryByText(/\|---/)).toBeNull();
  const nested = screen.getByText("Font fallback used");
  expect(nested.closest("ul")!.parentElement).toHaveTextContent("DOCX warnings (1):");
});

test("Back to review returns to the review step", async () => {
  const user = userEvent.setup();
  show();
  await user.click(screen.getByRole("button", { name: /Back to review/ }));
  expect(useApp.getState().step).toBe("review");
});

test("own-wording bullets aren't called fact-checked", () => {
  show({ applied: { ...RESULT.applied!, bullets: 3, bullets_edited: 1 } });
  expect(screen.getByText(/1 in your own words, the rest fact-checked/)).toBeInTheDocument();
});

test("a flat match names what's missing and leads to where it can be added", async () => {
  const user = userEvent.setup();
  show({ alignment_score: 48.2, initial_alignment_score: 48.2 });
  expect(screen.getByText(/the match didn't/)).toBeInTheDocument();
  const missing = screen.getByText("Still missing (2)").parentElement!;
  expect(within(missing).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Airflow · required", "teamwork"]);
  // Nothing was asked in review, so the own-words box is where they go.
  await user.click(screen.getByRole("button", { name: "Add the ones you have, in your own words" }));
  expect(useApp.getState().step).toBe("review");
  expect(useApp.getState().run.jumpTo).toBe("addition");
});

test("with questions asked in review, the button goes to them", async () => {
  const user = userEvent.setup();
  const drafted = { ...DRAFTED, gap_questions: [{ id: "q1", requirement: "Airflow", priority: "required" as const,
    keywords: ["Airflow"], question: "", saved_keywords: [], saved_answer: "" }] };
  useApp.setState({ step: "results", reached: 3, run: { ...EMPTY_RUN, drafted, review: initialReview(drafted),
    results: { ...RESULT, alignment_score: 48.2, initial_alignment_score: 48.2 }, resultsVersion: 3 } });
  render(<Results />);
  await user.click(screen.getByRole("button", { name: "Add the ones you have" }));
  expect(useApp.getState().run.jumpTo).toBe("gaps");
});

test("keywords gained by tailoring are named", () => {
  const after: KeywordMatch = { ...MATCH, rows: MATCH.rows.map((r) => (r.keyword === "Airflow" ? { ...r, found: true } : r)) };
  show({ keyword_match: after });
  expect(screen.getByText("Now on your resume:").parentElement).toHaveTextContent("Now on your resume: Airflow");
  expect(screen.getByText("Still missing (1)")).toBeInTheDocument();
});

test("a stretch match gets its guidance too, not only a different field (P9.5)", () => {
  const tips = ["Tick the job keywords you really have in Review, with a line saying where."];
  show({ keyword_match: { ...MATCH, guidance: { kind: "stretch", headline: "A stretch: the job asks for more.", text: "Why.", tips } } });
  expect(screen.getByText("A stretch: the job asks for more.")).toBeInTheDocument();
  expect(screen.getByText(tips[0])).toBeInTheDocument();
  // said once, by the guidance, not again above the missing keywords (P9.4)
  expect(screen.queryByText(/the match didn't/)).not.toBeInTheDocument();
  expect(screen.queryByText(/To go further/)).not.toBeInTheDocument();
});

test("kept projects that don't fit: keep the longer length or leave one out, re-rendered with no AI (P11.12)", async () => {
  const layout = { section_order: [], hidden_sections: [], entry_order: {}, bullet_order: {}, removed_bullets: ["x"],
    edits: {}, pinned: [], page_target: null, trim: true };
  const arrangement = { sections: [], layout, source_order: { bullets: {}, experience: [], projects: [], education: [] }, trimmed: [] };
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    new Response(JSON.stringify({ ...RESULT, pages: 1, page_overflow: null,
      arrangement: { ...arrangement, layout: JSON.parse(String(init?.body)).layout } })));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  show({ arrangement, page_overflow: { pages: 2, target: 1, projects: [
    { key: "j1::Route Pilot", name: "Route Pilot", owner: "Northwind", bullet_ids: ["b1", "b2"] }] } });
  expect(screen.getByText(/don't fit on 1 page/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Leave out “Route Pilot”" }));
  expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).layout.removed_bullets).toEqual(["x", "b1", "b2"]);
  expect(await screen.findByRole("heading", { name: "Your resume is ready." })).toBeInTheDocument();
  expect(screen.queryByText(/don't fit on 1 page/)).toBeNull();
});

test("kept projects that don't fit: choosing the longer length sends that page target (P11.12)", async () => {
  const layout = { section_order: [], hidden_sections: [], entry_order: {}, bullet_order: {}, removed_bullets: [],
    edits: {}, pinned: [], page_target: null, trim: true };
  const arrangement = { sections: [], layout, source_order: { bullets: {}, experience: [], projects: [], education: [] }, trimmed: [] };
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ ...RESULT, page_overflow: null, arrangement })));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  show({ arrangement, page_overflow: { pages: 2, target: 1, projects: [
    { key: "j1::Route Pilot", name: "Route Pilot", owner: "Northwind", bullet_ids: ["b1"] }] } });
  await user.click(screen.getByRole("button", { name: "Use 2 pages" }));
  const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).layout;
  expect([sent.page_target, sent.trim]).toEqual([2, true]);
});

test("a run that ends at 4 pages offers 3, the longest Arrange allows (P11.12 review)", () => {
  const layout = { section_order: [], hidden_sections: [], entry_order: {}, bullet_order: {}, removed_bullets: [],
    edits: {}, pinned: [], page_target: 2, trim: true };
  const arrangement = { sections: [], layout, source_order: { bullets: {}, experience: [], projects: [], education: [] }, trimmed: [] };
  show({ arrangement, page_overflow: { pages: 4, target: 2, projects: [
    { key: "j1::Route Pilot", name: "Route Pilot", owner: "Northwind", bullet_ids: ["b1"] }] } });
  expect(screen.getByRole("button", { name: "Use 3 pages" })).toBeInTheDocument();
});
