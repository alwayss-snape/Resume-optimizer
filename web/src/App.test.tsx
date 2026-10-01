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
    const handler = routes[url];
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
  await user.click(screen.getByRole("button", { name: /Read my resume/ }));

  expect(await screen.findByRole("heading", { name: "Check your details" })).toHaveFocus();
  expect(screen.getByText(/No phone number found/)).toBeInTheDocument();
  const name = screen.getByLabelText("Name");
  await user.clear(name);
  await user.type(name, "Avery J. Lee");
  // A job with no role read from the file still keeps a typed title.
  await user.type(screen.getAllByLabelText("Title")[1], "Engineer");
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));

  expect(await screen.findByRole("heading", { name: "Review changes" })).toBeInTheDocument();
  const sent = JSON.parse(String(calls.find((c) => c.url === "/api/proposals")!.init!.body));
  expect(sent.corrections.candidate.name).toBe("Avery J. Lee");
  expect(sent.corrections.candidate.links).toEqual(["github.com/avery"]);
  expect(sent.corrections.experience[1].roles).toEqual([{ title: "Engineer", start_date: "", end_date: "" }]);
  expect(useApp.getState().run.drafted?.proposals).toHaveLength(1);
});

test("check my match: shows the report, then can go on to tailor with the same files", async () => {
  stubApi({
    "/api/config": () => jsonResponse(CONFIG),
    "/api/analyze": () => jsonResponse(REPORT),
    "/api/parse": () => jsonResponse({ details: DETAILS, parse_issues: [] }),
  });
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: "Just check my match" }));
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /Check my match/ }));

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
  await user.click(screen.getByRole("button", { name: /Read my resume/ }));
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
  await user.click(screen.getByRole("button", { name: /Read my resume/ }));
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
    url === "/api/proposals" ? new Promise<Response>((resolve) => { finish = resolve; }) : base(url, init));

  const user = userEvent.setup();
  render(<App />);
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /Read my resume/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  expect(await screen.findByRole("heading", { name: "Drafting your rewrites" })).toHaveFocus();

  await user.click(screen.getByRole("button", { name: "Start over" }));
  finish(sseResponse([["result", DRAFTED]]));
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
  await user.click(screen.getByRole("button", { name: /Read my resume/ }));
  await screen.findByRole("heading", { name: "Check your details" });
  await user.click(screen.getByRole("button", { name: /draft rewrites/ }));
  await screen.findByRole("heading", { name: "Review changes" });
  expect(JSON.parse(String(calls.find((c) => c.url === "/api/proposals")!.init!.body))).toEqual({ corrections: null });
});

test("report tabs move with the arrow keys", async () => {
  stubApi({ "/api/config": () => jsonResponse(CONFIG), "/api/analyze": () => jsonResponse(REPORT) });
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: "Just check my match" }));
  await fillUpload(user);
  await user.click(screen.getByRole("button", { name: /Check my match/ }));
  const first = await screen.findByRole("tab", { name: /Must have/ });
  first.focus();
  await user.keyboard("{ArrowLeft}");
  expect(screen.getByRole("tab", { name: /Not on your resume/ })).toHaveFocus();
  expect(screen.getByText("Airflow experience")).toBeInTheDocument();
  expect(first).toHaveAttribute("tabindex", "-1");
});
