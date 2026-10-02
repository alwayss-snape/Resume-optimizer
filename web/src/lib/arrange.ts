/** Arrange and edit (P8.13–P8.16): pure changes to a Layout. The server
 *  applies a layout to the tailored resume and re-renders; nothing here
 *  talks to it. A bullet only ever moves within its own job or project. */
import type { ArrangeEntry, ArrangeSection, Arrangement, Layout, TrimmedItem } from "./types";

const clone = (l: Layout): Layout => JSON.parse(JSON.stringify(l)) as Layout;

/** `ids` with `id` moved by `delta` (clamped); unchanged if absent. */
export function moveId(ids: string[], id: string, delta: number): string[] {
  const from = ids.indexOf(id);
  if (from < 0) return ids;
  const to = Math.max(0, Math.min(ids.length - 1, from + delta));
  if (to === from) return ids;
  const out = [...ids];
  out.splice(from, 1);
  out.splice(to, 0, id);
  return out;
}

/** `ids` with `id` placed before `target` (drag and drop). */
export function placeBefore(ids: string[], id: string, target: string): string[] {
  if (id === target || !ids.includes(id) || !ids.includes(target)) return ids;
  const out = ids.filter((x) => x !== id);
  out.splice(out.indexOf(target), 0, id);
  return out;
}

export function orderedSections(a: Arrangement, layout: Layout): ArrangeSection[] {
  const rank = new Map(layout.section_order.map((k, i) => [k, i]));
  return [...a.sections].sort((x, y) => (rank.get(x.key) ?? 99) - (rank.get(y.key) ?? 99));
}

export function orderedEntries(section: ArrangeSection, layout: Layout): ArrangeEntry[] {
  const order = layout.entry_order[section.key] ?? [];
  const rank = new Map(order.map((k, i) => [k, i]));
  return [...(section.entries ?? [])].sort((x, y) => (rank.get(x.id) ?? 99) - (rank.get(y.id) ?? 99));
}

export function orderedBullets(entry: ArrangeEntry, layout: Layout) {
  const order = layout.bullet_order[entry.id] ?? entry.bullets.map((b) => b.id);
  const rank = new Map(order.map((k, i) => [k, i]));
  return [...entry.bullets].sort((x, y) => (rank.get(x.id) ?? 99) - (rank.get(y.id) ?? 99));
}

export function moveSection(layout: Layout, key: string, delta: number): Layout {
  const l = clone(layout);
  l.section_order = moveId(l.section_order, key, delta);
  return l;
}

export function toggleSection(layout: Layout, key: string): Layout {
  const l = clone(layout);
  l.hidden_sections = l.hidden_sections.includes(key) ? l.hidden_sections.filter((k) => k !== key) : [...l.hidden_sections, key];
  return l;
}

export function moveEntry(layout: Layout, section: ArrangeSection, id: string, delta: number): Layout {
  const l = clone(layout);
  const order = l.entry_order[section.key]?.length ? l.entry_order[section.key] : (section.entries ?? []).map((e) => e.id);
  l.entry_order[section.key] = moveId(order, id, delta);
  return l;
}

/** Moves a bullet within its own entry only. */
export function moveBullet(layout: Layout, entry: ArrangeEntry, bulletId: string, delta: number): Layout {
  const l = clone(layout);
  const order = orderedBullets(entry, layout).map((b) => b.id);
  l.bullet_order[entry.id] = moveId(order, bulletId, delta);
  return l;
}

export function dropBullet(layout: Layout, entry: ArrangeEntry, bulletId: string, beforeId: string): Layout {
  if (!entry.bullets.some((b) => b.id === bulletId)) return layout; // never across jobs
  const l = clone(layout);
  l.bullet_order[entry.id] = placeBefore(orderedBullets(entry, layout).map((b) => b.id), bulletId, beforeId);
  return l;
}

export function toggleBullet(layout: Layout, bulletId: string): Layout {
  const l = clone(layout);
  l.removed_bullets = l.removed_bullets.includes(bulletId)
    ? l.removed_bullets.filter((b) => b !== bulletId) : [...l.removed_bullets, bulletId];
  return l;
}

/** The user's own wording; blank or unchanged removes the edit. */
export function editBullet(layout: Layout, bulletId: string, text: string, current: string): Layout {
  const l = clone(layout);
  const t = text.trim();
  if (!t || t === current.trim()) delete l.edits[bulletId];
  else l.edits[bulletId] = t;
  return l;
}

/** Bring back something page-fit trimmed: it is pinned, so it stays in. */
export function keepTrimmed(layout: Layout, item: TrimmedItem): Layout {
  const l = clone(layout);
  if (!l.pinned.includes(item.id)) l.pinned = [...l.pinned, item.id];
  l.removed_bullets = l.removed_bullets.filter((b) => b !== item.id);
  return l;
}

export function setPageTarget(layout: Layout, target: number | null, trim: boolean): Layout {
  const l = clone(layout);
  l.page_target = target;
  l.trim = trim;
  return l;
}

/** Jobs, projects, degrees and every bullet back in the file's order. */
export function restoreOriginalOrder(layout: Layout, a: Arrangement): Layout {
  const l = clone(layout);
  for (const key of ["experience", "projects", "education"] as const) {
    if (a.source_order[key]?.length) l.entry_order[key] = [...a.source_order[key]];
  }
  for (const [owner, ids] of Object.entries(a.source_order.bullets)) {
    const own = new Set((layout.bullet_order[owner] ?? []).concat(ids));
    l.bullet_order[owner] = [...ids.filter((id) => own.has(id)), ...(layout.bullet_order[owner] ?? []).filter((id) => !ids.includes(id))];
  }
  return l;
}

/** True when an entry's bullets aren't in the file's order (sorted by job relevance or by the user). */
export function reordered(entry: ArrangeEntry, layout: Layout, a: Arrangement): boolean {
  const source = a.source_order.bullets[entry.id];
  if (!source) return false;
  const now = orderedBullets(entry, layout).map((b) => b.id).filter((id) => source.includes(id));
  return now.join() !== source.filter((id) => now.includes(id)).join();
}

export const sameLayout = (a: Layout, b: Layout) => JSON.stringify(a) === JSON.stringify(b);
