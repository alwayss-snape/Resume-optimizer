import { afterEach, expect, test, vi } from "vitest";
import { DRAFTED, jsonResponse, sseResponse } from "../test/fixtures";
import { ApiError, draftProposals, errorMessage, parseSse, request } from "./api";

afterEach(() => vi.unstubAllGlobals());

test("parseSse keeps an unfinished block for the next chunk", () => {
  const { events, rest } = parseSse('event: progress\ndata: {"message":"a"}\n\nevent: res');
  expect(events).toEqual([{ event: "progress", data: { message: "a" } }]);
  expect(rest).toBe("event: res");
});

test("streamStep reports progress, then resolves with the result", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => sseResponse([["progress", { message: "Reading" }], ["result", DRAFTED]])));
  const progress: string[] = [];
  const result = await draftProposals(null, (m) => progress.push(m));
  expect(progress).toEqual(["Reading"]);
  expect(result.proposals[0].id).toBe("p1");
});

test("streamStep rejects on an error event or a refused request", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => sseResponse([["error", { message: "Something went wrong on our side." }]])));
  await expect(draftProposals(null, () => undefined)).rejects.toThrow("Something went wrong on our side.");
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Your session has expired." }, 404)));
  await expect(draftProposals(null, () => undefined)).rejects.toMatchObject({ status: 404, message: "Your session has expired." });
});

test("request turns network failures and validation errors into readable messages", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
  await expect(request("/api/x")).rejects.toBeInstanceOf(ApiError);
  expect(errorMessage(422, { detail: [{ msg: "Field required" }] })).toBe("Please check your input: Field required.");
  expect(errorMessage(502, null)).toMatch(/on our side/);
});

test("parseSse accepts CRLF line endings", () => {
  const { events } = parseSse('event: result\r\ndata: {"ok":true}\r\n\r\n');
  expect(events).toEqual([{ event: "result", data: { ok: true } }]);
});

test("a stream that ends without a result rejects", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => sseResponse([["progress", { message: "Reading" }]])));
  await expect(draftProposals(null, () => undefined)).rejects.toThrow(/closed before the step finished/);
});
