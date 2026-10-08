/** Arrange and edit (P8.13–P8.16): pure changes to a Layout. The server
 *  applies a layout to the tailored resume and re-renders; nothing here
 *  talks to it. A bullet only ever moves within its own job or project. */
import type { ArrangeBullet, ArrangeEntry, ArrangeSection, Arrangement, Layout, TrimmedItem } from "./types";

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

/** Moves a section past its neighbour among the shown ones (empty sections
 *  the screen doesn't list never absorb a click). */
export function moveSection(layout: Layout, key: string, delta: number, shown?: string[]): Layout {
  const l = clone(layout);
  const visible = shown ?? l.section_order;
  const at = visible.indexOf(key);
  const neighbour = visible[at + delta];
  if (at < 0 || !neighbour) return l;
  const order = l.section_order.includes(key) ? [...l.section_order] : [...l.section_order, key];
  if (!order.includes(neighbour)) order.push(neighbour);
  const without = order.filter((k) => k !== key);
  const n = without.indexOf(neighbour);
  without.splice(delta < 0 ? n : n + 1, 0, key);
  l.section_order = without;
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

/** A project inside a job ("Scalable MLOps Framework") and its bullets, or
 *  the job's bullets without a sub-heading (`name` null). A group moves as
 *  one block, and its bullets stay together and inside it (R3). */
export interface BulletGroup {
  key: string;
  name: string | null;
  bullets: ArrangeBullet[];
}

/** The entry's bullets in layout order, kept together by sub-heading: a
 *  group sits where its first bullet is. */
export function orderedGroups(entry: ArrangeEntry, layout: Layout): BulletGroup[] {
  const groups = new Map<string, BulletGroup>();
  for (const b of orderedBullets(entry, layout)) {
    const key = b.group ?? "";
    if (!groups.has(key)) groups.set(key, { key, name: b.group, bullets: [] });
    groups.get(key)!.bullets.push(b);
  }
  return [...groups.values()];
}

const flatten = (groups: BulletGroup[]) => groups.flatMap((g) => g.bullets.map((b) => b.id));

/** Moves a bullet within its own group (so within its own job) only. */
export function moveBullet(layout: Layout, entry: ArrangeEntry, bulletId: string, delta: number): Layout {
  const l = clone(layout);
  const groups = orderedGroups(entry, layout).map((g) => {
    const ids = g.bullets.map((b) => b.id);
    if (!ids.includes(bulletId)) return g;
    const byId = new Map(g.bullets.map((b) => [b.id, b]));
    return { ...g, bullets: moveId(ids, bulletId, delta).map((id) => byId.get(id)!) };
  });
  l.bullet_order[entry.id] = flatten(groups);
  return l;
}

/** Moves a project (a group and all its bullets) past its neighbour. */
export function moveGroup(layout: Layout, entry: ArrangeEntry, key: string, delta: number): Layout {
  const l = clone(layout);
  const groups = orderedGroups(entry, layout);
  const byKey = new Map(groups.map((g) => [g.key, g]));
  l.bullet_order[entry.id] = flatten(moveId(groups.map((g) => g.key), key, delta).map((k) => byKey.get(k)!));
  return l;
}

export function dropBullet(layout: Layout, entry: ArrangeEntry, bulletId: string, beforeId: string): Layout {
  const moving = entry.bullets.find((b) => b.id === bulletId);
  const target = entry.bullets.find((b) => b.id === beforeId);
  // never across jobs, and never out of its own project
  if (!moving || !target || (moving.group ?? "") !== (target.group ?? "")) return layout;
  const l = clone(layout);
  const placed = placeBefore(orderedBullets(entry, layout).map((b) => b.id), bulletId, beforeId);
  l.bullet_order[entry.id] = flatten(orderedGroups(entry, { ...layout, bullet_order: { ...layout.bullet_order, [entry.id]: placed } }));
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

export function setRegion(layout: Layout, region: string): Layout {
  const l = clone(layout);
  l.region = region;
  return l;
}

export function setCvMode(layout: Layout, mode: string): Layout {
  const l = clone(layout);
  l.cv_mode = mode;
  return l;
}

export function setStyle(layout: Layout, style: string): Layout {
  const l = clone(layout);
  l.style = style;
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
