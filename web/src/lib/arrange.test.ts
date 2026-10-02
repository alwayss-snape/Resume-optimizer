import { expect, test } from "vitest";
import {
  dropBullet, editBullet, keepTrimmed, moveBullet, moveId, orderedBullets, placeBefore, reordered, restoreOriginalOrder,
  setPageTarget, toggleSection,
} from "./arrange";
import type { Arrangement, Layout } from "./types";

export const LAYOUT: Layout = {
  section_order: ["summary", "experience", "education"], hidden_sections: [],
  entry_order: { experience: ["exp_001", "exp_002"] },
  bullet_order: { exp_001: ["b3", "b1", "b2"], exp_002: ["c1"] },
  removed_bullets: [], edits: {}, pinned: [], page_target: null, trim: true,
};
const JOB = { id: "exp_001", title: "Nurse", subtitle: "Banner", bullets: [
  { id: "b1", text: "One", file_text: "One", group: null }, { id: "b2", text: "Two", file_text: "Two", group: null },
  { id: "b3", text: "Three", file_text: "Three", group: null }] };
const OTHER = { id: "exp_002", title: "Clerk", subtitle: "", bullets: [{ id: "c1", text: "C", file_text: "C", group: null }] };
export const ARRANGEMENT: Arrangement = {
  sections: [{ key: "experience", title: "Work Experience", kind: "entries", entries: [JOB, OTHER] },
    { key: "summary", title: "Summary", kind: "text", lines: ["A nurse."] }],
  layout: LAYOUT,
  source_order: { bullets: { exp_001: ["b1", "b2", "b3"], exp_002: ["c1"] }, experience: ["exp_001", "exp_002"], projects: [], education: [] },
  trimmed: [{ kind: "bullet", id: "b9", owner: "exp_001", owner_label: "Banner", text: "Nine" }],
};

test("moving ids is clamped and drag places before the target", () => {
  expect(moveId(["a", "b", "c"], "a", -1)).toEqual(["a", "b", "c"]);
  expect(moveId(["a", "b", "c"], "a", 1)).toEqual(["b", "a", "c"]);
  expect(placeBefore(["a", "b", "c"], "c", "a")).toEqual(["c", "a", "b"]);
});

test("a bullet moves within its own job only", () => {
  const l = moveBullet(LAYOUT, JOB, "b1", -1);
  expect(l.bullet_order.exp_001).toEqual(["b1", "b3", "b2"]);
  expect(dropBullet(LAYOUT, OTHER, "b1", "c1")).toBe(LAYOUT); // b1 isn't the clerk job's
  expect(orderedBullets(JOB, LAYOUT).map((b) => b.id)).toEqual(["b3", "b1", "b2"]);
});

test("original order, sorted marker, edits, hiding, keeping trimmed, page length", () => {
  expect(reordered(JOB, LAYOUT, ARRANGEMENT)).toBe(true);
  const restored = restoreOriginalOrder(LAYOUT, ARRANGEMENT);
  expect(restored.bullet_order.exp_001).toEqual(["b1", "b2", "b3"]);
  expect(reordered(JOB, restored, ARRANGEMENT)).toBe(false);
  expect(editBullet(LAYOUT, "b1", "  My words  ", "One").edits).toEqual({ b1: "My words" });
  expect(editBullet({ ...LAYOUT, edits: { b1: "x" } }, "b1", "One", "One").edits).toEqual({});
  expect(toggleSection(LAYOUT, "summary").hidden_sections).toEqual(["summary"]);
  expect(keepTrimmed(LAYOUT, ARRANGEMENT.trimmed[0]).pinned).toEqual(["b9"]);
  expect(setPageTarget(LAYOUT, null, false)).toMatchObject({ page_target: null, trim: false });
  expect(LAYOUT.hidden_sections).toEqual([]); // never mutated
});
