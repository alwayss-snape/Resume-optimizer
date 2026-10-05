// Thin client for the FastAPI backend (app/api/routes.py). Same origin:
// Vite proxies /api in development and FastAPI serves this app in
// production, so the session cookie just works.

import type { AnalysisReport, Details, Layout, MatchPreview, ParseResult, ProposalsResult, TailorResult } from "./types";

export interface AppConfig {
  provider: string;
  provider_label: string;
  models: string[];
  max_upload_mb: number;
  cloud?: boolean; // resume text goes to a cloud AI service (P8.24)
  session_minutes?: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** The server's message: FastAPI sends `detail` as a string for our own
 *  errors and as a list for request validation errors. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return `Please check your input: ${detail[0].msg}.`;
  if (status === 429) return "Too many requests. Please try again later.";
  return status >= 500 ? "Something went wrong on our side. Please try again." : `Request failed (${status}).`;
}

/** What to tell the user about a failed step. The server's own message is
 *  shown, except a busy session gets "try again in a moment". */
export function friendlyError(e: unknown): string {
  if (e instanceof ApiError && e.status === 409 && /still working/i.test(e.message)) {
    return "Your previous request is still finishing. Please try again in a moment.";
  }
  return (e as Error)?.message || "Something went wrong. Please try again.";
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...init });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* not JSON */
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body));
  return body as T;
}

export const getConfig = () => request<AppConfig>("/api/config");

function uploadForm(file: File, jdText: string, model: string | null): FormData {
  const form = new FormData();
  form.append("file", file);
  form.append("jd_text", jdText);
  if (model) form.append("model", model);
  return form;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const analyze = (file: File, jdText: string, model: string | null) =>
  request<AnalysisReport>("/api/analyze", { method: "POST", body: uploadForm(file, jdText, model) });

export const parseResume = (file: File, jdText: string, model: string | null) =>
  request<ParseResult>("/api/parse", { method: "POST", body: uploadForm(file, jdText, model) });

export const resetSession = () => request<{ ok: boolean }>("/api/reset", { method: "POST" });

/** Split an SSE body into (event, data) pairs; `rest` is an unfinished block. */
export function parseSse(buffer: string): { events: { event: string; data: unknown }[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const events = blocks
    .map((block) => {
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      try {
        return { event, data: data.length ? JSON.parse(data.join("\n")) : null };
      } catch {
        return null;
      }
    })
    .filter((e): e is { event: string; data: unknown } => e !== null);
  return { events, rest };
}

/** A step's progress line; `waitSeconds` is set when the AI service asked us
 *  to wait (P9.7), shown as a countdown rather than a finished step. */
export type OnProgress = (message: string, waitSeconds?: number) => void;

/** POST a JSON body to a streaming step: calls onProgress for each progress
 *  message and resolves with the final result (rejects on an error event). */
export async function streamStep<T>(path: string, body: unknown, onProgress: OnProgress,
  signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...json(body), signal });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (!response.ok || !response.body) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, errorMessage(response.status, detail));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const { events, rest } = parseSse(done ? buffer + "\n\n" : buffer);
    buffer = rest;
    for (const { event, data } of events) {
      const payload = data as { message?: string; seconds?: number } | null;
      if (event === "progress" && payload?.message) onProgress(payload.message);
      if (event === "wait" && payload?.message) onProgress(payload.message, payload.seconds ?? 0);
      if (event === "error") throw new ApiError(500, payload?.message || "Something went wrong. Please try again.");
      if (event === "result") return data as T;
    }
    if (done) throw new ApiError(500, "The connection closed before the step finished. Please try again.");
  }
}

/** The "check details" form: fixed fields plus jobs removed or added. */
export interface AddedJob {
  company: string;
  title: string;
  location: string;
  current: boolean;
  start_date: string;
  end_date: string;
  description: string;
}
export type Corrections = Details & { removed_jobs?: string[]; added_jobs?: AddedJob[];
  placed?: { id: string; target: string }[] }; // unplaced lines -> summary / skills / a job id / "other" (P8.26)

export const draftProposals = (corrections: Corrections | null, onProgress: OnProgress, signal?: AbortSignal) =>
  streamStep<ProposalsResult>("/api/proposals", { corrections }, onProgress, signal);

export interface Selection {
  id: string;
  text?: string | null;
}

export const matchPreview = (selection: Selection[], signal?: AbortSignal) =>
  request<MatchPreview>("/api/match-preview", { ...json({ selection }), signal });

export interface TailorRequest {
  selection: Selection[];
  gap_answers: Record<string, { ticked: string[]; answer: string; target: string }>;
  addition: { text: string; target: string };
  new_role: null | {
    company: string;
    title: string;
    location: string;
    current: boolean;
    start: string | null; // YYYY-MM-DD
    end: string | null;
    description: string;
  };
  keep_layout: boolean;
  strict_factual: boolean;
  conditions?: string[];
  remember_answers: boolean;
}

export const tailorResume = (body: TailorRequest, onProgress: OnProgress, signal?: AbortSignal) =>
  streamStep<TailorResult>("/api/tailor", body, onProgress, signal);

/** Re-render with the user's arrangement (P8.13). No AI call. */
export const arrangeResume = (layout: Layout, signal?: AbortSignal) =>
  request<TailorResult>("/api/arrange", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ layout }), signal,
  });

export const fileUrl = (kind: "docx" | "pdf" | "changes" | "html") => `/api/files/${kind}`;
export const previewUrl = (page: number, version: string | number) => `/api/preview/${page}?v=${version}`;

/** Fetch a result file and hand it to the browser as a download; throws
 *  ApiError (e.g. an expired session) instead of saving an error page. */
export async function downloadFile(kind: "docx" | "pdf" | "changes"): Promise<void> {
  let response: Response;
  try {
    response = await fetch(fileUrl(kind), { credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, errorMessage(response.status, body));
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const name = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name ? decodeURIComponent(name) : `resume.${kind === "changes" ? "md" : kind}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** The change log (changes.md) as text. */
export async function getChangeLog(): Promise<string> {
  const response = await fetch(fileUrl("changes"), { credentials: "same-origin" });
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, null));
  return response.text();
}
