import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { DEFAULT_SETTINGS, EMPTY_RUN, useApp } from "./lib/store";
import { DETAILS, DRAFTED, REPORT, jsonResponse, sseResponse } from "./test/fixtures";

const CONFIG = { provider: "groq", provider_label: "Groq (cloud)", models: ["m1", "m2"], max_upload_mb: 5 };

function stubApi(routes: Record<string, () => Response>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    // P11.2: drafting starts with /api/prepare; by default nothing to ask, so it goes straight on.
    const handler = routes[url] ?? (url === "/api/prepare"
      ? () => sseResponse([["result", { role_brief: null, questions: [] }]]) : undefined);
    if (!handler) return jsonResponse({ detail: "not found" }, 404);
    return handler();
  }));
  return calls;
}

beforeEach(() => useApp.setState({ step: "upload", reached: 0, run: EMPTY_RUN, settings: DEFAULT_SETTINGS }));
afterEach(() => vi.unstubAllGlobals());

async function fillUpload(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText(/Drop your resume here/), new File(["x"], "cv.docx"));
  await user.type(screen.getByLabelText("The job description"), "Data Scientist");
}

test("tailor: upload -> check details -> drafting with progress -> review", async () => {
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: ["No phone number found"] }),
    "/api/proposals": () => sseResponse([["progress", { message: "Analysing the job description" }], ["result", DRAFTED]]),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));

  expect(await screen.findByRole("heading", { name: "Check your details" })).toHaveFocus();
  expect(screen.getByText(/No phone number found/)).toBeInTheDocument();
  const name = screen.getByLabelText("Name");
  await user.clear(name);
  await user.type(name, "Avery J. Lee");
  // A job with no role read from the file still keeps a typed title.
  await user.type(screen.getAllByLabelText("Title")[1], "Engineer");
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));

  expect(await screen.findByRole("heading", { name: "Review changes" })).toBeInTheDocument();
  const sent = JSON.parse(String(calls.find((c) => c.url === "/api/prepare")!.init!.body));
  expect(sent.corrections.candidate.name).toBe("Avery J. Lee");
  expect(sent.corrections.candidate.links).toEqual(["github.com/avery"]);
  expect(sent.corrections.experience[1].roles).toEqual([{ title: "Engineer", start_date: "", end_date: "" }]);
  expect(useApp.getState().run.drafted?.proposals).toHaveLength(1);
});

test("a note on how the file was read is not called a reading problem (P10.11)", async () => {
  const note = "Read as a LinkedIn profile (Save to PDF): please check the details below.";
  stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: ["No phone number found"], parse_notes: [note] }),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));

  expect(await screen.findByRole("heading", { name: "Check your details" })).toBeInTheDocument();
  const shown = screen.getByText(note);
  expect(shown.closest("li")).not.toHaveTextContent("Possible reading problem");
  expect(screen.getByText(/No phone number found/).closest("li")).toHaveTextContent("Possible reading problem");
  expect(screen.getAllByText(/Possible reading problem/)).toHaveLength(1);
});

test("check my match: shows the report, then can go on to tailor with the same files", async () => {
  stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/analyze": () => jsonResponse(REPORT),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: "Just check my match" }));

  expect(await screen.findByRole("heading", { name: /How your resume reads/ })).toBeInTheDocument();
  expect(screen.getByText(/1 of 3 keywords found/)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Keyword match: 48.2%/ })).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: /Not on your resume/ }));
  expect(screen.getByText("Airflow experience")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Tailor my resume for this job/ }));
  expect(await screen.findByRole("heading", { name: "Check your details" })).toBeInTheDocument();
});

test("a server error stays on the upload form with its message", async () => {
  stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ detail: "That file doesn't look like a real .docx file." }, 415),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("doesn't look like a real .docx");
  expect(useApp.getState().step).toBe("upload");
});

test("the chosen model is sent only if the provider offers it", async () => {
  useApp.setState({ settings: { ...DEFAULT_SETTINGS, model: "m2" } });
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
  });
  const user = userEvent.setup();
  render(<App />);
  await waitFor(() => expect(calls.some((c) => c.url === "/api/config")).toBe(true));
  await screen.findByText(/Tailor my resume/);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  expect((calls.find((c) => c.url === "/api/parse")!.init!.body as FormData).get("model")).toBe("m2");
});


test("Start over while drafting: the late result is ignored and the server is told", async () => {
  let finish: (r: Response) => void = () => undefined;
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/reset": () => jsonResponse({ ok: true, pending: true }),
  });
  const fetchMock = globalThis.fetch as ReturnType<typeof vi.fn>;
  const base = fetchMock.getMockImplementation() as (url: string, init?: RequestInit) => Promise<Response>;
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) =>
    url === "/api/prepare" ? new Promise<Response>((resolve) => { finish = resolve; }) : base(url, init));

  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  expect(await screen.findByRole("heading", { name: "Reading the job" })).toHaveFocus();

  await user.click(screen.getByRole("button", { name: "Start over" }));
  finish(sseResponse([["result", { role_brief: null, questions: [] }]]));
  await new Promise((r) => setTimeout(r, 20));
  expect(useApp.getState().step).toBe("upload");
  expect(useApp.getState().run.drafted).toBeNull();
  expect(calls.some((c) => c.url === "/api/reset")).toBe(true);
});

test("an untouched details form sends no corrections", async () => {
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  await screen.findByRole("heading", { name: "Review changes" });
  expect(JSON.parse(String(calls.find((c) => c.url === "/api/prepare")!.init!.body))).toEqual({ corrections: null });
  expect(JSON.parse(String(calls.find((c) => c.url === "/api/proposals")!.init!.body))).toEqual({ corrections: null, answers: [] });
});

test("details: a missed job is added, a misread one removed, and both are sent", async () => {
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  // Remove and Undo keep focus on the control that replaced the one clicked.
  await user.click(screen.getByRole("button", { name: "Remove job 1, Northwind" }));
  expect(screen.getByRole("button", { name: "Undo removing job 1" })).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Undo removing job 1" }));
  expect(screen.getByRole("button", { name: "Remove job 1, Northwind" })).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Remove job 2, Contoso" }));
  expect(screen.getByText(/won't be on your resume/)).toBeInTheDocument();
  // A blank card is skipped but still numbered as shown; deleting one hands focus back to "Add".
  await user.click(screen.getByRole("button", { name: "Add a job we missed" }));
  await user.click(screen.getByRole("button", { name: "Add a job we missed" }));
  await user.click(screen.getByRole("button", { name: "Remove new job 2" }));
  expect(screen.getByRole("button", { name: "Add a job we missed" })).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Add a job we missed" }));
  expect(screen.getAllByLabelText("Company *")[1]).toHaveFocus();
  await user.type(screen.getAllByLabelText("Company *")[1], "Acme");
  // Incomplete: explained, nothing sent.
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  expect(screen.getByRole("alert")).toHaveTextContent(/New job 2: To add the job, fill in: job title.*Or remove it/);
  await user.click(screen.getByRole("button", { name: "Remove new job 1" }));
  expect(calls.some((c) => c.url === "/api/prepare" || c.url === "/api/proposals")).toBe(false);
  await user.type(screen.getByLabelText("Job title *"), "Engineer");
  await user.selectOptions(screen.getByLabelText("Start *: month"), "03");
  await user.selectOptions(screen.getByLabelText("Start *: year"), "2019");
  await user.selectOptions(screen.getByLabelText("End *: month"), "12");
  await user.selectOptions(screen.getByLabelText("End *: year"), "2021");
  // P10.13: a whole project bank fits (the next step chooses), up to 40 lines.
  await user.click(screen.getByLabelText(/What did you do there/));
  await user.paste(Array.from({ length: 41 }, (_, i) => `point ${i}`).join("\n"));
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("New job 1: Keep it to 40 lines (one per bullet point); it has 41.");
  await user.clear(screen.getByLabelText(/What did you do there/));
  await user.type(screen.getByLabelText(/What did you do there/), "Built the billing service");
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  await screen.findByRole("heading", { name: "Review changes" });
  const { corrections } = JSON.parse(String(calls.find((c) => c.url === "/api/prepare")!.init!.body));
  expect(corrections.removed_jobs).toEqual(["exp_2"]);
  expect(corrections.experience.map((e: { id: string }) => e.id)).toEqual(["exp_1"]);
  expect(corrections.added_jobs).toEqual([{ company: "Acme", title: "Engineer", location: "", current: false,
    start_date: "March 2019", end_date: "December 2021", description: "Built the billing service" }]);
});

test("report tabs move with the arrow keys", async () => {
  stubApi({ "/api/config": () => jsonResponse(CONFIG), "/api/analyze": () => jsonResponse(REPORT) });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: "Just check my match" }));
  const first = await screen.findByRole("tab", { name: /Must have/ });
  first.focus();
  await user.keyboard("{ArrowLeft}");
  expect(screen.getByRole("tab", { name: /Not on your resume/ })).toHaveFocus();
  expect(screen.getByText("Airflow experience")).toBeInTheDocument();
  expect(first).toHaveAttribute("tabindex", "-1");
});


async function toReview(user: ReturnType<typeof userEvent.setup>) {
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  return screen.findByRole("heading", { name: "Review changes" });
}

test("review: live match follows decisions; generate sends them and opens results", async () => {
  const drafted = { ...DRAFTED, gap_questions: [{ id: "gap_1", requirement: "Experience with Airflow", priority: "required" as const,
    keywords: ["Airflow"], question: "?", saved_keywords: [], saved_answer: "" }] };
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", drafted]]),
    "/api/match-preview": () => jsonResponse({ ...drafted.keyword_match, rate: 61.5, delta: 13.3 }),
    "/api/tailor": () => sseResponse([["progress", { message: "Rendering" }], ["result", {
      success: true, alignment_score: 61.5, initial_alignment_score: 48.2, keyword_match: null, content_lint: null,
      addition_note: null, warnings: [], docx_warnings: [], pdf_warnings: [], target_pages: 1, pages: 1,
      files: { docx: true, pdf: true, changes: true } }]]),
  });
  const user = userEvent.setup();
  await toReview(user);
  expect(await screen.findByRole("img", { name: /Keyword match: 61.5%, was 48.2%/ }, { timeout: 2000 })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Reject" }));
  await waitFor(() => {
    const previews = calls.filter((c) => c.url === "/api/match-preview");
    expect(JSON.parse(String(previews.at(-1)!.init!.body))).toEqual({ selection: [], left_out: [] });
  }, { timeout: 2000 });

  await user.click(screen.getByRole("checkbox", { name: "Airflow" }));
  await user.click(screen.getAllByRole("button", { name: "Generate my resume" })[0]);
  expect(await screen.findByRole("heading", { name: "Your resume is ready." })).toBeInTheDocument();
  const body = JSON.parse(String(calls.find((c) => c.url === "/api/tailor")!.init!.body));
  expect(body.selection).toEqual([]);
  expect(body.gap_answers.gap_1).toEqual({ ticked: ["Airflow"], answer: "", target: "auto" });
  expect(body.new_role).toBeNull();
});

test("review: a half-filled new job is explained before anything is sent", async () => {
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
    "/api/match-preview": () => jsonResponse({ ...DRAFTED.keyword_match, delta: 0 }),
  });
  const user = userEvent.setup();
  await toReview(user);
  await user.click(screen.getByText("Add a job that isn't on your resume"));
  await user.type(screen.getByLabelText("Company *"), "Acme");
  await user.click(screen.getAllByRole("button", { name: "Generate my resume" })[0]);
  expect(await screen.findByRole("alert")).toHaveTextContent(/fill in: job title/);
  expect(calls.some((c) => c.url === "/api/tailor")).toBe(false);
});

test("review: decisions survive going back to details and returning", async () => {
  stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
    "/api/match-preview": () => jsonResponse({ ...DRAFTED.keyword_match, delta: 0 }),
  });
  const user = userEvent.setup();
  await toReview(user);
  await user.click(screen.getByRole("button", { name: "Reject" }));
  await user.click(screen.getAllByRole("button", { name: /Check details/ })[0]);
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getAllByRole("button", { name: /Review/ })[0]);
  await screen.findByRole("heading", { name: "Review changes" });
  expect(screen.getByRole("article", { name: /rejected/ })).toBeInTheDocument();
});


test("review: text typed but not saved is still sent when generating", async () => {
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
    "/api/match-preview": () => jsonResponse({ ...DRAFTED.keyword_match, delta: 0 }),
    "/api/tailor": () => sseResponse([["error", { message: "stop here" }]]),
  });
  const user = userEvent.setup();
  await toReview(user);
  await user.click(screen.getByRole("button", { name: "Edit" }));
  const box = screen.getByLabelText("Your version");
  await user.clear(box);
  await user.type(box, "Shipped forecasting dashboards in Python");
  await user.click(screen.getAllByRole("button", { name: "Generate my resume" })[0]);
  await screen.findByText("stop here");
  const body = JSON.parse(String(calls.find((c) => c.url === "/api/tailor")!.init!.body));
  expect(body.selection).toEqual([{ id: "p1", text: "Shipped forecasting dashboards in Python" }]);
});

test("review: new job dates come from month and year selects", async () => {
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
    "/api/match-preview": () => jsonResponse({ ...DRAFTED.keyword_match, delta: 0 }),
    "/api/tailor": () => sseResponse([["error", { message: "stop here" }]]),
  });
  const user = userEvent.setup();
  await toReview(user);
  await user.click(screen.getByText("Add a job that isn't on your resume"));
  await user.type(screen.getByLabelText("Company *"), "Acme");
  await user.type(screen.getByLabelText("Job title *"), "Engineer");
  await user.selectOptions(screen.getByLabelText("Start *: month"), "03");
  await user.selectOptions(screen.getByLabelText("Start *: year"), "2020");
  await user.click(screen.getByLabelText("I currently work here"));
  await user.type(screen.getByLabelText(/What did you do there/), "Built the billing service");
  await user.click(screen.getAllByRole("button", { name: "Generate my resume" })[0]);
  await screen.findByText("stop here");
  const body = JSON.parse(String(calls.find((c) => c.url === "/api/tailor")!.init!.body));
  expect(body.new_role).toMatchObject({ company: "Acme", start: "2020-03-01", end: null, current: true });
});

test("review: an expired session says so instead of retrying forever", async () => {
  stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
    "/api/match-preview": () => jsonResponse({ detail: "Your session has expired. Please upload your resume again." }, 404),
  });
  const user = userEvent.setup();
  await toReview(user);
  expect(await screen.findByText(/Your session has expired. Use Start over/, {}, { timeout: 2000 })).toBeInTheDocument();
});

test("review: the CV type and paper choices show once, outside the sticky aside, and go with the request (P10.12)", async () => {
  const drafted = { ...DRAFTED, region: { region: "us", label: "US (Letter)", evidence: "Austin, TX" },
    cv_mode: { mode: "standard", label: "Standard resume", evidence: [] } };
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/proposals": () => sseResponse([["result", drafted]]),
    "/api/match-preview": () => jsonResponse({ ...DRAFTED.keyword_match, delta: 0 }),
    "/api/tailor": () => sseResponse([["result", {
      success: true, alignment_score: 50, initial_alignment_score: 40, keyword_match: null, content_lint: null,
      addition_note: null, warnings: [], docx_warnings: [], pdf_warnings: [], target_pages: 1, pages: 1,
      files: { docx: true, pdf: true, changes: true } }]]),
  });
  const user = userEvent.setup();
  await toReview(user);
  const formatted = screen.getAllByLabelText("Formatted for");
  expect(formatted).toHaveLength(1);
  expect(formatted[0].closest("aside")).toBeNull();
  expect(screen.getAllByLabelText("CV type")).toHaveLength(1);
  await user.selectOptions(formatted[0], "uk_eu");
  await user.selectOptions(screen.getByLabelText("CV type"), "academic");
  await user.click(screen.getAllByRole("button", { name: "Generate my resume" })[0]);
  expect(await screen.findByRole("heading", { name: "Your resume is ready." })).toBeInTheDocument();
  const body = JSON.parse(String(calls.find((c) => c.url === "/api/tailor")!.init!.body));
  expect([body.region, body.cv_mode]).toEqual(["uk_eu", "academic"]);
});


test("questions (P11.2): asked before drafting, answers go with the draft, any can be skipped", async () => {
  const question = { id: "need_0", kind: "need", competency: "Pricing analytics", experience_id: "exp_1",
    project: "Membership Analytics", job: "Acme", question: "The job needs pricing analytics. Did it involve prices?",
    hint: "e.g. Tuned the discount tiers.", saved_answer: "" };
  const calls = stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
    "/api/prepare": () => sseResponse([["result", { role_brief: null, questions: [question] }]]),
    "/api/proposals": () => sseResponse([["result", DRAFTED]]),
  });
  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /^Tailor my resume$/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  await screen.findByRole("heading", { name: "A few questions" });
  expect(calls.some((c) => c.url === "/api/proposals")).toBe(false);  // nothing written yet
  await user.type(screen.getByLabelText("Your answer (optional)"), "Set the membership fee tiers");
  await user.click(screen.getByRole("button", { name: "Draft my resume with 1 answer" }));
  await screen.findByRole("heading", { name: "Review changes" });
  const sent = JSON.parse(String(calls.find((c) => c.url === "/api/proposals")!.init!.body));
  expect(sent).toEqual({ corrections: null, answers: [{ id: "need_0", answer: "Set the membership fee tiers",
    experience_id: "exp_1", project: "Membership Analytics" }] });
});
