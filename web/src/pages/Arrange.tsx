import { type DragEvent, useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { arrangeResume, friendlyError, previewUrl } from "../lib/api";
import {
  dropBullet, editBullet, keepTrimmed, moveBullet, moveEntry, moveSection, orderedBullets, orderedEntries,
  orderedSections, placeBefore, reordered, restoreOriginalOrder, sameLayout, setPageTarget, toggleBullet, toggleSection,
} from "../lib/arrange";
import type { ArrangeBullet, ArrangeEntry, ArrangeSection, Arrangement, Layout, TailorResult } from "../lib/types";
import { useFocusHeading } from "../lib/useFocusHeading";

const UPDATE_DELAY_MS = 900;

function MoveButtons({ id, label, first, last, onMove }: {
  id: string; label: string; first: boolean; last: boolean; onMove: (delta: number) => void;
}) {
  return (
    <span className="flex shrink-0 gap-1">
      <button type="button" data-move={`${id}:up`} aria-label={`Move ${label} up`} disabled={first} onClick={() => onMove(-1)}
        className="grid size-11 place-items-center rounded-[4px] border border-field text-ink hover:border-pencil hover:text-pencil disabled:cursor-not-allowed disabled:opacity-40">
        <Icon name="arrow-right" size={16} className="-rotate-90" />
      </button>
      <button type="button" data-move={`${id}:down`} aria-label={`Move ${label} down`} disabled={last} onClick={() => onMove(1)}
        className="grid size-11 place-items-center rounded-[4px] border border-field text-ink hover:border-pencil hover:text-pencil disabled:cursor-not-allowed disabled:opacity-40">
        <Icon name="arrow-right" size={16} className="rotate-90" />
      </button>
    </span>
  );
}

const short = (t: string, n = 48) => (t.length > n ? `${t.slice(0, n).trimEnd()}…` : t);

/** After a move React re-orders the DOM and the pressed button loses focus;
 *  the Arrange screen puts it back (Stage J review). */
let focusAfterMove: { id: string; dir: "up" | "down" } | null = null;
const rememberMove = (id: string, delta: number) => { focusAfterMove = { id, dir: delta < 0 ? "up" : "down" }; };

/** One bullet: its text in the document serif, struck when taken out. */
function BulletRow({ bullet, entry, index, count, layout, onChange, onAnnounce, drag, trimmed }: {
  bullet: ArrangeBullet; entry: ArrangeEntry; index: number; count: number; layout: Layout;
  onChange: (l: Layout) => void; onAnnounce: (m: string) => void;
  drag: { start: (e: DragEvent, id: string) => void; drop: (e: DragEvent, id: string) => void; end: () => void };
  trimmed?: boolean;
}) {
  const removed = layout.removed_bullets.includes(bullet.id);
  const edit = layout.edits[bullet.id];
  const text = edit ?? bullet.text;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);
  const editRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (editing) editRef.current?.focus();
  }, [editing]);
  const label = `"${short(text, 40)}"`;
  return (
    <li draggable={!editing} onDragStart={(e) => { e.stopPropagation(); drag.start(e, bullet.id); }}
      onDragOver={(e) => e.preventDefault()} onDragEnd={(e) => { e.stopPropagation(); drag.end(); }}
      onDrop={(e) => { e.stopPropagation(); drag.drop(e, bullet.id); }}
      className={`flex flex-col gap-2 border-t border-line py-3 first:border-t-0 ${removed ? "opacity-80" : ""}`}>
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="mt-1 cursor-grab select-none text-muted">⋮⋮</span>
        {editing ? (
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <label htmlFor={`edit-${bullet.id}`} className="text-sm font-medium">Your wording</label>
            <textarea id={`edit-${bullet.id}`} ref={editRef} rows={3} value={draft} onChange={(e) => setDraft(e.target.value)}
              maxLength={600}
              className="resize-y rounded-[3px] border border-field bg-panel px-3.5 py-2.5 font-serif text-[16px] leading-relaxed text-ink focus-visible:border-pencil" />
            {bullet.file_text && bullet.file_text !== text && (
              <p className="m-0 text-xs text-muted">In your file: <span className="font-serif">{bullet.file_text}</span></p>
            )}
            <div className="flex gap-2.5">
              <Button variant="primary" onClick={() => {
                onChange(editBullet(layout, bullet.id, draft, bullet.text));
                setEditing(false);
                onAnnounce("Your wording saved.");
              }}>Save</Button>
              <Button onClick={() => { setDraft(text); setEditing(false); }}>Cancel</Button>
            </div>
          </div>
        ) : (
          <p className={`m-0 min-w-0 flex-1 font-serif text-[16px] leading-relaxed ${removed ? "mark-del" : ""}`}>
            {text}
            {edit !== undefined && <span className="ml-2 font-sans text-xs text-pencil">your words</span>}
            {trimmed && !removed && <span className="ml-2 font-sans text-xs text-muted">trimmed to fit · not in the file</span>}
          </p>
        )}
      </div>
      {!editing && (
        <div className="flex flex-wrap items-center gap-2 pl-7">
          {!removed && <MoveButtons id={bullet.id} label={label} first={index === 0} last={index === count - 1}
            onMove={(d) => { rememberMove(bullet.id, d); onChange(moveBullet(layout, entry, bullet.id, d)); onAnnounce(`Moved ${label} ${d < 0 ? "up" : "down"}.`); }} />}
          {!removed && <Button onClick={() => { setDraft(text); setEditing(true); }}>Edit</Button>}
          <Button variant="ghost" onClick={() => {
            onChange(toggleBullet(layout, bullet.id));
            onAnnounce(removed ? `Put back ${label}.` : `Took out ${label}.`);
          }}>{removed ? "Put it back" : "Take out"}</Button>
        </div>
      )}
    </li>
  );
}

function EntryBlock({ section, entry, index, count, layout, arrangement, trimmedIds, onChange, onAnnounce }: {
  section: ArrangeSection; entry: ArrangeEntry; index: number; count: number; layout: Layout; arrangement: Arrangement;
  trimmedIds: Set<string>; onChange: (l: Layout) => void; onAnnounce: (m: string) => void;
}) {
  const bullets = orderedBullets(entry, layout);
  const dragged = useRef<string | null>(null);
  const drag = {
    start: (e: DragEvent, id: string) => { dragged.current = id; e.dataTransfer.effectAllowed = "move"; },
    drop: (e: DragEvent, id: string) => {
      e.preventDefault();
      if (dragged.current) onChange(dropBullet(layout, entry, dragged.current, id)); // own bullets only
      dragged.current = null;
    },
    end: () => { dragged.current = null; },
  };
  const moved = reordered(entry, layout, arrangement);
  return (
    <li className="flex flex-col gap-2 rounded-[3px] border border-line bg-panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="m-0 font-semibold">{entry.title || "Untitled"}</p>
          {entry.subtitle && <p className="m-0 text-sm text-muted">{entry.subtitle}</p>}
          {moved && <p className="m-0 mt-1 text-xs text-muted">Bullets sorted by job relevance or by you, not as in your file.</p>}
        </div>
        {count > 1 && <MoveButtons id={entry.id} label={`"${short(entry.title)}"`} first={index === 0} last={index === count - 1}
          onMove={(d) => { rememberMove(entry.id, d); onChange(moveEntry(layout, section, entry.id, d)); onAnnounce(`Moved "${short(entry.title)}" ${d < 0 ? "up" : "down"}.`); }} />}
      </div>
      {bullets.length > 0 && (
        <ul className="m-0 flex flex-col p-0" aria-label={`Bullets of ${entry.title}`}>
          {bullets.map((b, i) => (
            <BulletRow key={b.id} bullet={b} entry={entry} index={i} count={bullets.length} layout={layout}
              onChange={onChange} onAnnounce={onAnnounce} drag={drag} trimmed={trimmedIds.has(b.id)} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** Arrange and edit (P8.15): the tailored resume's structure, owned by the user. */
export function Arrange({ result, onResult, onBack }: {
  result: TailorResult;
  onResult: (r: TailorResult) => void;
  onBack: () => void;
}) {
  const arrangement = result.arrangement!;
  const heading = useFocusHeading();
  const [aiVersion] = useState<Layout>(arrangement.default_layout ?? arrangement.layout);
  const [layout, setLayout] = useState<Layout>(arrangement.layout);
  const [history, setHistory] = useState<Layout[]>([]);
  const [status, setStatus] = useState<"idle" | "waiting" | "updating" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  const [version, setVersion] = useState(0);
  const sent = useRef<Layout>(arrangement.layout);
  const inFlight = useRef(false);
  const latest = useRef<Layout>(layout);
  const sectionDrag = useRef<string | null>(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  const change = (next: Layout) => {
    if (sameLayout(next, layout)) return;
    setHistory((h) => [...h.slice(-49), layout]);
    setLayout(next);
  };

  const send = async () => {
    if (inFlight.current || sameLayout(latest.current, sent.current)) return;
    inFlight.current = true;
    const target = latest.current;
    setStatus("updating");
    setError(null);
    try {
      const r = await arrangeResume(target);
      sent.current = target;
      onResult(r);
      setVersion((v) => v + 1);
      setStatus("idle");
      setAnnounce(`Updated: ${r.pages || "?"} page${r.pages === 1 ? "" : "s"}.`);
    } catch (e) {
      setStatus("error");
      setError(friendlyError(e));
    } finally {
      inFlight.current = false;
      if (!sameLayout(latest.current, sent.current) && latest.current !== target) void send();
    }
  };

  useEffect(() => {
    latest.current = layout;
    if (sameLayout(layout, sent.current)) {
      if (!inFlight.current) setStatus("idle"); // e.g. undone back to what the files already show
      return;
    }
    setStatus("waiting");
    const timer = window.setTimeout(() => void send(), UPDATE_DELAY_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout]);

  // Leaving during the pause still applies the last change (Stage J review).
  useEffect(() => () => {
    if (!inFlight.current && !sameLayout(latest.current, sent.current)) {
      arrangeResume(latest.current).then((r) => onResultRef.current(r)).catch(() => undefined);
    }
  }, []);

  // Keep focus on the moved item's button (or its other one at an end).
  useEffect(() => {
    if (!focusAfterMove) return;
    const { id, dir } = focusAfterMove;
    focusAfterMove = null;
    const esc = (v: string) => (typeof CSS !== "undefined" && typeof CSS.escape === "function" ? CSS.escape(v) : v.replace(/"/g, '\\"'));
    const btn = document.querySelector<HTMLButtonElement>(`[data-move="${esc(id)}:${dir}"]`);
    const other = document.querySelector<HTMLButtonElement>(`[data-move="${esc(id)}:${dir === "up" ? "down" : "up"}"]`);
    (btn && !btn.disabled ? btn : other)?.focus();
  }, [layout]);

  const sections = orderedSections(arrangement, layout);
  const trimmed = result.arrangement?.trimmed ?? arrangement.trimmed;
  const trimmedIds = new Set(trimmed.filter((t) => !layout.pinned.includes(t.id)).map((t) => t.id));
  const notes = result.warnings.filter((w) => /newest first|isn't elsewhere|pages \(not trimmed|Removed .* to fit|Still \d+ pages/.test(w));
  const target = layout.trim ? (layout.page_target ?? 0) : -1;

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-8 px-4 py-12 md:px-8 md:py-16">
      <div className="flex flex-col gap-4">
        <h1 ref={heading} tabIndex={-1} className="font-display text-[40px] font-bold leading-[1.04] tracking-[-0.03em] outline-none md:text-[48px]">
          Arrange and edit
        </h1>
        <p className="m-0 max-w-[62ch] text-base leading-relaxed text-muted">
          Put sections, jobs and bullets in the order you want, hide what you don't need, reword a bullet in your own words,
          and bring back anything trimmed to fit the page. The files update as you go; no AI is involved. A bullet stays
          with its own job.
        </p>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button onClick={onBack}><Icon name="arrow-right" size={16} className="rotate-180" /> Back to results</Button>
          <Button disabled={!history.length} onClick={() => {
            setLayout(history[history.length - 1]);
            setHistory((h) => h.slice(0, -1));
            setAnnounce("Undone.");
          }}>Undo</Button>
          <Button onClick={() => { change(restoreOriginalOrder(layout, arrangement)); setAnnounce("Back to your file's order."); }}>
            Restore my original order
          </Button>
          <Button variant="ghost" disabled={sameLayout(layout, aiVersion)}
            onClick={() => { change(aiVersion); setAnnounce("Back to the tailored version."); }}>Reset to the tailored version</Button>
        </div>
        <p role="status" aria-live="polite" className="m-0 min-h-5 text-sm text-muted">
          {status === "updating" ? "Updating your files…" : status === "waiting" ? "Changes will apply in a moment…"
            : status === "error" ? "" : `Up to date · ${result.pages || "?"} page${result.pages === 1 ? "" : "s"}`}
          <span className="sr-only"> {announce}</span>
        </p>
        {error && (
          <p role="alert" className="m-0 flex items-start gap-2 text-sm font-medium text-danger">
            <Icon name="alert" size={16} className="mt-0.5 shrink-0" />
            <span><span className="font-semibold">Error:</span> {error}{" "}
              <button type="button" className="underline" onClick={() => void send()}>Try again</button></span>
          </p>
        )}
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)]">
        <div className="flex min-w-0 flex-col gap-6">
          <fieldset className="sheet flex flex-col gap-3 rounded-[3px] p-5 md:p-6">
            <legend className="float-left mb-2 text-[15px] font-bold">Page length</legend>
            <div className="clear-both flex flex-wrap gap-2.5">
              {([[0, "Automatic"], [1, "1 page"], [2, "2 pages"], [3, "3 pages"], [-1, "Don't trim"]] as const).map(([value, label]) => (
                <label key={value} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-[3px] border px-4 text-sm font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pencil ${
                  target === value ? "border-pencil bg-pencil-soft" : "border-field hover:border-ink"}`}>
                  <input type="radio" name="page-length" className="size-4" checked={target === value}
                    onChange={() => change(setPageTarget(layout, value > 0 ? value : null, value !== -1))} />
                  {label}
                </label>
              ))}
            </div>
            <p className="m-0 text-xs text-muted">
              Automatic fits 1 page under 8 years of experience and 2 from 8 years. Don't trim keeps everything, however long.
              Lines you keep or reword are never trimmed; to make room, something less relevant may be.
            </p>
          </fieldset>

          {trimmed.length > 0 && (
            <section className="sheet flex flex-col gap-3 rounded-[3px] p-5 md:p-6" aria-labelledby="trimmed-h">
              <h2 id="trimmed-h" className="m-0 text-[15px] font-bold">Trimmed to fit the page <span className="tabular font-normal text-muted">({trimmed.length})</span></h2>
              <ul className="m-0 flex flex-col p-0">
                {trimmed.map((item) => (
                  <li key={item.id} className="flex flex-col gap-2 border-t border-line py-3 first:border-t-0 sm:flex-row sm:items-start sm:justify-between">
                    <span className="min-w-0">
                      {item.owner_label && <span className="block text-xs text-muted">{item.owner_label}</span>}
                      <span className="font-serif text-[15px] leading-relaxed">{item.kind === "interests" ? `Interests: ${item.text}` : item.text}</span>
                    </span>
                    <Button className="shrink-0" disabled={layout.pinned.includes(item.id)}
                      onClick={() => { change(keepTrimmed(layout, item)); setAnnounce("It will stay in; something less relevant may be trimmed instead."); }}>
                      {layout.pinned.includes(item.id) ? "Kept" : "Keep it"}
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <ol className="m-0 flex flex-col gap-4 p-0" aria-label="Sections, in order">
            {sections.map((section, i) => {
              const hidden = layout.hidden_sections.includes(section.key);
              const entries = orderedEntries(section, layout);
              return (
                <li key={section.key} draggable onDragStart={(e) => { sectionDrag.current = section.key; e.dataTransfer.effectAllowed = "move"; }}
                  onDragOver={(e) => e.preventDefault()} onDragEnd={() => { sectionDrag.current = null; }}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (sectionDrag.current) change({ ...layout, section_order: placeBefore(layout.section_order, sectionDrag.current, section.key) });
                    sectionDrag.current = null;
                  }}
                  className={`list-none rounded-[3px] p-5 md:p-6 ${hidden ? "border border-dashed border-field bg-bg" : "sheet"}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className={`m-0 text-[17px] font-bold ${hidden ? "text-muted" : ""}`}>
                      <span aria-hidden="true" className="mr-2 cursor-grab select-none text-muted">⋮⋮</span>{section.title}
                      {hidden && <span className="ml-2 text-sm font-normal">· hidden</span>}
                    </h2>
                    <span className="flex items-center gap-2">
                      <MoveButtons id={section.key} label={section.title} first={i === 0} last={i === sections.length - 1}
                        onMove={(d) => {
                          rememberMove(section.key, d);
                          change(moveSection(layout, section.key, d, sections.map((x) => x.key)));
                          setAnnounce(`Moved ${section.title} ${d < 0 ? "up" : "down"}.`);
                        }} />
                      <label className="flex min-h-11 cursor-pointer items-center gap-2 px-2 text-sm">
                        <input type="checkbox" className="size-4" checked={!hidden}
                          onChange={() => { change(toggleSection(layout, section.key)); setAnnounce(`${section.title} ${hidden ? "shown" : "hidden"}.`); }} />
                        Show<span className="sr-only"> {section.title}</span>
                      </label>
                    </span>
                  </div>
                  {!hidden && section.kind === "entries" && (
                    <ul className="m-0 mt-4 flex flex-col gap-3 p-0">
                      {entries.map((entry, j) => (
                        <EntryBlock key={entry.id} section={section} entry={entry} index={j} count={entries.length}
                          layout={layout} arrangement={arrangement} trimmedIds={trimmedIds} onChange={change}
                          onAnnounce={setAnnounce} />
                      ))}
                    </ul>
                  )}
                  {!hidden && section.kind !== "entries" && section.lines && (
                    <div className="mt-3 flex flex-col gap-1">
                      {section.lines.slice(0, 6).map((line, j) => <p key={j} className="m-0 font-serif text-[15px] leading-relaxed">{line}</p>)}
                      {section.lines.length > 6 && <p className="m-0 text-xs text-muted">+{section.lines.length - 6} more lines</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
          {notes.length > 0 && (
            <ul className="m-0 flex flex-col p-0 text-sm" aria-label="Notes on your arrangement">
              {notes.map((n, i) => <li key={i} className="list-none border-t border-line py-2.5 leading-relaxed">{n}</li>)}
            </ul>
          )}
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start" aria-label="Preview">
          <h2 className="m-0 text-[15px] font-bold">Preview</h2>
          {result.pages > 0 ? (
            <div className={`flex flex-col gap-4 ${status === "updating" ? "opacity-60" : ""}`}>
              {Array.from({ length: result.pages }, (_, i) => (
                <img key={`${version}-${i}`} src={previewUrl(i + 1, `a${version}`)} alt={`Page ${i + 1} as arranged`}
                  className="w-full border border-line bg-paper shadow-sheet" />
              ))}
            </div>
          ) : <p className="m-0 text-sm text-muted">No preview is available (the PDF couldn't be made).</p>}
        </aside>
      </div>
    </div>
  );
}
