import { expect, test } from "vitest";
import { DRAFTED } from "../test/fixtures";
import type { Proposal } from "./types";
import { EMPTY_JOB, groupProposals, initialReview, newJobProblem, selection, tailorRequest, willApply } from "./review";

const p = (id: string, extra: Partial<Proposal> = {}): Proposal => ({ ...DRAFTED.proposals[0], id, ...extra });

test("everything starts accepted; saved answers pre-tick and pre-fill", () => {
  const drafted = { ...DRAFTED, gap_questions: [{ id: "gap_1", requirement: "Kafka", priority: "required" as const,
    keywords: ["Kafka"], question: "?", saved_keywords: ["Kafka"], saved_answer: "At Acme" }] };
  const r = initialReview(drafted);
  expect(r.decisions).toEqual({ p1: "accept" });
  expect(r.gaps.gap_1).toEqual({ ticked: ["Kafka"], answer: "At Acme", target: "auto" });
});

test("selection: rejected left out, edits sent only when they differ", () => {
  const props = [p("a"), p("b"), p("c")];
  const r = { ...initialReview({ ...DRAFTED, proposals: props }), decisions: { a: "accept", b: "reject", c: "accept" } as const,
    edits: { a: "My own words", c: props[2].proposed + "  " } };
  expect(selection(props, r)).toEqual([{ id: "a", text: "My own words" }, { id: "c" }]);
});

test("a fact-check failure is used only if the user edits it", () => {
  const bad = p("x", { state: "dropped" });
  const r = initialReview({ ...DRAFTED, proposals: [bad] });
  expect(willApply(bad, r)).toBe(false);
  expect(willApply(bad, { ...r, edits: { x: "Rewritten by me" } })).toBe(true);
});

test("new job: empty is fine, partial is explained, dates are checked", () => {
  expect(newJobProblem(EMPTY_JOB)).toBeNull();
  expect(newJobProblem({ ...EMPTY_JOB, company: "Acme" })).toMatch(/job title, start date, end date .*what you did there/);
  const full = { ...EMPTY_JOB, company: "Acme", title: "Engineer", start: "2023-05", end: "2022-01", description: "Built X" };
  expect(newJobProblem(full)).toMatch(/before its start/);
  expect(newJobProblem({ ...full, current: true })).toBeNull();
});

test("tailorRequest sends month inputs as dates and drops the end date when current", () => {
  const r = { ...initialReview(DRAFTED), newJob: { ...EMPTY_JOB, company: "Acme", title: "Eng", start: "2023-05",
    end: "2024-01", current: true, description: "Built X" } };
  const body = tailorRequest(DRAFTED.proposals, r, { keepLayout: true, strictFactual: false, rememberAnswers: true });
  expect(body.new_role).toMatchObject({ start: "2023-05-01", end: null, current: true });
  expect(body.keep_layout).toBe(true);
  expect(tailorRequest(DRAFTED.proposals, initialReview(DRAFTED), { keepLayout: false, strictFactual: false, rememberAnswers: true }).new_role).toBeNull();
});

test("cards are grouped: summary, skills, then each job", () => {
  const groups = groupProposals([
    p("b1"), p("s", { kind: "skills", section: null }), p("sum", { kind: "summary", section: null }),
    p("b2", { section: { id: "exp_2", kind: "experience", label: "Contoso" } }),
  ]);
  expect(groups.map((g) => g.label)).toEqual(["Professional summary", "Skills", "Northwind — Data Analyst", "Contoso"]);
});

test("an opt-in proposal (a summary replacing the user's own) starts unticked", () => {
  const props: Proposal[] = DRAFTED.proposals.map((p, i) => (i === 0 ? { ...p, opt_in: true } : p));
  const r = initialReview({ ...DRAFTED, proposals: props });
  expect(r.decisions[props[0].id]).toBe("reject");
  expect(props.slice(1).every((p) => r.decisions[p.id] === "accept")).toBe(true);
});

test("the region starts as the JD's suggestion and goes with the request (P10.3)", () => {
  const drafted = { ...DRAFTED, region: { region: "us", label: "US (Letter)", evidence: "Austin, TX" } };
  const r = initialReview(drafted);
  expect(r.region).toBe("us");
  const opts = { keepLayout: false, strictFactual: false, rememberAnswers: true };
  expect(tailorRequest(drafted.proposals, r, opts).region).toBe("us");
  expect(tailorRequest(drafted.proposals, { ...r, region: "uk_eu" }, opts).region).toBe("uk_eu");
  expect(tailorRequest(DRAFTED.proposals, initialReview(DRAFTED), opts).region).toBeNull();
});
