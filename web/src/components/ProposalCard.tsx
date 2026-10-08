import { type KeyboardEvent, forwardRef, useEffect, useId, useRef, useState } from "react";

/** Text to keep from the edit box: null (= the proposal) when it matches the
 *  proposal or is blank, which the server would ignore anyway. */
export function normalizeEdit(draft: string, proposed: string): string | null {
  return !draft.trim() || draft.trim() === proposed.trim() ? null : draft;
}
import type { Decision } from "../lib/review";
import type { Proposal, ProposalState } from "../lib/types";
import { Button } from "./Button";
import { DiffText } from "./DiffText";
import { Icon } from "./Icon";

const STATE_TONE: Record<ProposalState, string> = {
  pass: "text-success border-success-line",
  unchanged: "text-muted border-field",
  check: "text-warning border-warning",
  dropped: "text-danger border-danger",
  failed: "text-danger border-danger",
};

export type ProofView = "proof" | "split";

const TITLES: Record<Proposal["kind"], string> = {
  summary: "Professional summary",
  skills: "Skills (only what your own work names)",
  bullet: "Bullet",
  heading: "Project heading",
  project: "Project, rewritten whole",
};

/** One proposed rewrite. Keys while the card has focus: A accept, R reject,
 *  E edit, ↑/↓ previous/next card (handled by the parent). */
export const ProposalCard = forwardRef<HTMLElement, {
  proposal: Proposal;
  index: number;
  decision: Decision;
  text: string;
  edited: boolean;
  onDecide: (d: Decision) => void;
  onEdit: (text: string | null) => void; // null: back to the proposed text
  onNavigate: (step: 1 | -1) => void;
  shortcutsHintId?: string;
  view?: ProofView; // one marked-up line, or original and proposal side by side
}>(function ProposalCard({ proposal: p, index, decision, text, edited, onDecide, onEdit, onNavigate, shortcutsHintId, view = "proof" }, ref) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);
  // What to restore on Cancel: the text and decision from before editing.
  const before = useRef<{ text: string | null; decision: Decision }>({ text: null, decision });
  const box = useRef<HTMLTextAreaElement>(null);
  const self = useRef<HTMLElement | null>(null);
  const editId = useId();
  const rejected = decision === "reject";

  const setRefs = (el: HTMLElement | null) => {
    self.current = el;
    if (typeof ref === "function") ref(el);
    else if (ref) ref.current = el;
  };
  // The button or box that had focus is replaced by these actions, so focus
  // goes back to the card instead of falling to <body>.
  const refocus = () => setTimeout(() => self.current?.focus(), 0);

  useEffect(() => {
    if (editing) box.current?.focus();
  }, [editing]);

  const startEdit = () => {
    before.current = { text: edited ? text : null, decision };
    setDraft(text);
    setEditing(true);
  };
  // Saving (also on leaving the box, so nothing typed is lost) keeps the
  // user's wording and accepts the card.
  const save = (close: boolean) => {
    onEdit(normalizeEdit(draft, p.proposed));
    if (rejected) onDecide("accept");
    if (close) {
      setEditing(false);
      refocus();
    }
  };
  const cancel = () => {
    onEdit(before.current.text);
    onDecide(before.current.decision);
    setEditing(false);
    refocus();
  };
  const decideAndFocus = (d: Decision) => {
    onDecide(d);
    refocus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.target !== e.currentTarget || e.metaKey || e.ctrlKey || e.altKey) return;
    const key = e.key.toLowerCase();
    if (key === "a") decideAndFocus("accept");
    else if (key === "r") decideAndFocus("reject");
    else if (key === "e") startEdit();
    else if (e.key === "ArrowDown" || key === "j") onNavigate(1);
    else if (e.key === "ArrowUp" || key === "k") onNavigate(-1);
    else return;
    e.preventDefault();
  };

  const label = p.kind === "bullet" ? `${TITLES.bullet} ${index + 1}` : TITLES[p.kind];

  if (rejected && !editing) {
    return (
      <article ref={setRefs} tabIndex={0} onKeyDown={onKeyDown} aria-label={`${label}, rejected`}
        aria-keyshortcuts="A R E ArrowUp ArrowDown" aria-describedby={shortcutsHintId}
        className="flex flex-col gap-3 rounded-[3px] border border-dashed border-field bg-bg p-4 outline-offset-2 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
        <span className="shrink-0 text-[13px] font-semibold text-muted">{label}</span>
        <p className="m-0 flex-1 break-words font-serif text-[16px] leading-relaxed text-ink">{p.original}</p>
        <span className="flex items-center gap-2 text-[13px] text-muted">
          {/* an editor's "stet": let it stand */}
          <span aria-hidden="true" className="font-serif text-[15px] italic text-pencil underline decoration-dotted decoration-2 underline-offset-4">stet</span>
          Rejected: your original is kept
        </span>
        <Button variant="ghost" onClick={() => decideAndFocus("accept")} className="text-pencil hover:text-pencil-hover">Undo</Button>
      </article>
    );
  }

  return (
    <article ref={setRefs} tabIndex={0} onKeyDown={onKeyDown} aria-label={label}
      aria-keyshortcuts="A R E ArrowUp ArrowDown" aria-describedby={shortcutsHintId}
      className="sheet flex flex-col gap-4 rounded-[3px] p-5 outline-offset-2 transition-[box-shadow,translate,border-color] duration-200 hover:shadow-sheet-lift focus-visible:border-pencil focus-visible:shadow-sheet-lift focus-visible:outline-2 focus-visible:outline-pencil motion-safe:hover:-translate-y-0.5 motion-safe:focus-visible:-translate-y-0.5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold">{label}</span>
        <span className={`rounded-[3px] border px-2 py-0.5 text-xs font-medium ${STATE_TONE[edited ? "pass" : p.state]}`}>
          {edited ? "Your wording" : p.state_label}
        </span>
      </div>

      {editing ? (
        <div className="flex flex-col gap-3">
          <label htmlFor={editId} className="text-sm font-semibold text-pencil">Your version</label>
          <textarea id={editId} ref={box} value={draft} rows={p.kind === "skills" || p.kind === "project" ? 6 : 3}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => save(false)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save(true);
            }}
            className="resize-y rounded-[3px] border border-field bg-panel p-3.5 font-serif text-[16px] leading-relaxed text-ink focus-visible:border-pencil" />
          <p className="m-0 break-words text-xs text-muted">Your own wording is used as you write it. Original: {p.original || "(none)"}</p>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="primary" onMouseDown={(e) => e.preventDefault()} onClick={() => save(true)}>Save edit</Button>
            <Button onMouseDown={(e) => e.preventDefault()} onClick={cancel}>Cancel</Button>
            <Button variant="ghost" onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onEdit(null); setEditing(false); refocus(); }}>Use the proposal</Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-x-8 gap-y-3 md:grid-cols-[minmax(0,1fr)_200px]">
          {edited ? (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-pencil">Your version</span>
              <p className="m-0 whitespace-pre-line break-words font-serif text-[17px] leading-[1.8]">{text}</p>
            </div>
          ) : p.kind === "project" ? (
            /* P11.5: a project written whole: your lines, then the new bullets */
            <div className="grid gap-5 sm:grid-cols-2 sm:gap-6">
              {([["Your lines", p.original, "text-muted"], ["Proposed", text, "text-pencil"]] as const).map(([title, body, tone]) => (
                <div key={title} className="flex flex-col gap-1.5">
                  <span className={`text-xs font-semibold ${tone}`}>{title}</span>
                  <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5 font-serif text-[16px] leading-relaxed">
                    {body.split("\n").filter((l) => l.trim()).map((l, i) => <li key={i}>{l}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          ) : view === "proof" ? (
            p.diff.original.length || p.diff.proposed.length
              ? <DiffText spans={p.diff.original} proposed={p.diff.proposed} side="proof" />
              : <p className="m-0 text-[15px] text-muted">(none)</p>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 sm:gap-6">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-muted">Original</span>
                {p.diff.original.length ? <DiffText spans={p.diff.original} side="original" />
                  : <p className="m-0 text-[15px] text-muted">(none)</p>}
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-pencil">Proposed</span>
                <DiffText spans={p.diff.proposed} side="proposed" />
              </div>
            </div>
          )}
          {/* the editor's margin: why this change, and anything to check */}
          {(p.rationale || p.note || p.state !== "pass") && (
            <p className="m-0 border-line font-serif text-[14px] italic leading-relaxed text-muted md:border-l md:pl-4">
              {p.state === "failed" && !edited ? <span className="not-italic text-danger">Not rewritten: the AI call failed, so your original is shown. </span> : null}
              {p.note && !edited && p.state !== "failed"
                ? <span className={`not-italic ${p.state === "check" ? "text-warning" : "text-danger"}`}>{p.note}. </span> : null}
              {p.state === "dropped" && !edited ? <span className="not-italic">Edit it, or it won't be used. </span> : null}
              {p.rationale ? `Why: ${p.rationale}` : !p.note ? `${p.state_meaning.charAt(0).toUpperCase()}${p.state_meaning.slice(1)}.` : null}
            </p>
          )}
        </div>
      )}

      {!editing && (
        <div className="flex flex-wrap gap-2.5 border-t border-line pt-4">
          <Button variant={decision === "accept" ? "primary" : "secondary"} aria-pressed={decision === "accept"}
            onClick={() => decideAndFocus("accept")}>
            {decision === "accept" && <Icon name="check" size={16} strokeWidth={2.2} />}
            {decision === "accept" ? "Accepted" : "Accept"}
          </Button>
          <Button onClick={() => decideAndFocus("reject")}>Reject</Button>
          <Button onClick={startEdit}>Edit</Button>
        </div>
      )}
    </article>
  );
});
