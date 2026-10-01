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
  check: "text-pencil border-pencil/60",
  dropped: "text-danger border-danger/50",
  failed: "text-danger border-danger/50",
};

const TITLES: Record<Proposal["kind"], string> = {
  summary: "Professional summary",
  skills: "Skills (reordered only; nothing is added)",
  bullet: "Bullet",
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
}>(function ProposalCard({ proposal: p, index, decision, text, edited, onDecide, onEdit, onNavigate, shortcutsHintId }, ref) {
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
        className="flex flex-col gap-3 border border-line bg-bg p-4 outline-offset-2 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
        <Icon name="close" className="shrink-0 text-danger" />
        <p className="m-0 flex-1 break-words text-[15px] leading-relaxed text-muted line-through decoration-field">{p.original}</p>
        <span className="text-[13px] text-danger">Rejected, original kept</span>
        <Button variant="ghost" onClick={() => decideAndFocus("accept")} className="text-pencil hover:text-pencil-hover">Undo</Button>
      </article>
    );
  }

  return (
    <article ref={setRefs} tabIndex={0} onKeyDown={onKeyDown} aria-label={label}
      aria-keyshortcuts="A R E ArrowUp ArrowDown" aria-describedby={shortcutsHintId}
      className="flex flex-col gap-4 border border-line bg-panel p-5 outline-offset-2 transition-colors focus-visible:border-pencil focus-visible:outline-none md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] text-muted">{label}</span>
        <span className={`border px-2.5 py-1 text-xs ${STATE_TONE[edited ? "pass" : p.state]}`}>
          {edited ? "Your wording" : p.state_label}
        </span>
      </div>

      {editing ? (
        <div className="flex flex-col gap-3">
          <label htmlFor={editId} className="text-[11px] tracking-[0.18em] text-pencil">YOUR VERSION</label>
          <textarea id={editId} ref={box} value={draft} rows={p.kind === "skills" ? 6 : 3}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => save(false)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save(true);
            }}
            className="resize-y border border-field bg-panel-2 p-3.5 text-[15px] leading-relaxed text-ink" />
          <p className="m-0 break-words text-xs text-muted">Your own wording is used as you write it. Original: {p.original || "(none)"}</p>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="primary" onMouseDown={(e) => e.preventDefault()} onClick={() => save(true)}>Save edit</Button>
            <Button onMouseDown={(e) => e.preventDefault()} onClick={cancel}>Cancel</Button>
            <Button variant="ghost" onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onEdit(null); setEditing(false); refocus(); }}>Use the proposal</Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 md:gap-7">
          <div className="flex flex-col gap-2">
            <span className="text-[11px] tracking-[0.18em] text-muted">ORIGINAL</span>
            {p.diff.original.length ? <DiffText spans={p.diff.original} side="original" />
              : <p className="m-0 text-[15px] text-muted">(none)</p>}
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-[11px] tracking-[0.18em] text-pencil">{edited ? "YOUR VERSION" : "PROPOSED"}</span>
            {edited ? <p className="m-0 whitespace-pre-line break-words text-[15px] leading-relaxed">{text}</p>
              : <DiffText spans={p.diff.proposed} side="proposed" />}
          </div>
        </div>
      )}

      {!editing && (p.rationale || p.note || p.state !== "pass") && (
        <p className="m-0 text-[13px] leading-relaxed text-muted">
          {p.state === "failed" && !edited ? <span className="text-danger">Not rewritten: the AI call failed, so your original is shown. </span> : null}
          {p.note && !edited && p.state !== "failed"
            ? <span className={p.state === "check" ? "text-pencil" : "text-danger"}>{p.note}. </span> : null}
          {p.state === "dropped" && !edited ? "Edit it, or it won't be used. " : null}
          {p.rationale ? `Why: ${p.rationale}` : !p.note ? `${p.state_meaning.charAt(0).toUpperCase()}${p.state_meaning.slice(1)}.` : null}
        </p>
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
