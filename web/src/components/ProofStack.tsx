import { motion } from "motion/react";
import { type ReviewState, isEdited, willApply } from "../lib/review";
import type { Proposal } from "../lib/types";

type Mark = "in" | "edited" | "out" | "dropped";

const WIDTHS = [92, 78, 86, 70, 95, 82, 74, 88];

/** A small proof of the resume on the desk, one line per proposed change:
 *  going in (ink, with a pencil tick), in your words (pencil), rejected
 *  (struck, original kept) or failing the fact check (dashed). The lines
 *  re-mark themselves as the review changes. */
export function ProofStack({ proposals, review }: { proposals: Proposal[]; review: ReviewState }) {
  const marks: Mark[] = proposals.map((p) =>
    review.decisions[p.id] === "reject" ? "out" : !willApply(p, review) ? "dropped" : isEdited(p, review) ? "edited" : "in");
  const going = marks.filter((m) => m === "in" || m === "edited").length;

  return (
    <div className="flex flex-col gap-3">
      <p className="m-0 text-sm font-semibold">
        Your resume <span className="tabular font-normal text-muted">· {going} of {proposals.length} changes go in</span>
      </p>
      <div aria-hidden="true" className="relative mx-2 mb-2">
        {/* the sheets underneath */}
        <div className="absolute inset-0 translate-x-2 translate-y-2 rotate-[1.2deg] rounded-[2px] border border-line bg-panel shadow-sheet" />
        <div className="absolute inset-0 translate-x-1 translate-y-1 -rotate-[0.6deg] rounded-[2px] border border-line bg-panel" />
        <div className="relative flex flex-col gap-2.5 rounded-[2px] border border-line bg-paper px-5 py-4 shadow-sheet">
          <span className="h-2 w-2/5 rounded-[1px] bg-[#1b1b1f]" />
          <span className="mb-1 h-1 w-3/5 rounded-[1px] bg-[#c9c9c3]" />
          {marks.slice(0, 12).map((m, i) => (
            <span key={proposals[i].id} className="relative flex h-2 items-center">
              <motion.span layout initial={false}
                animate={{
                  backgroundColor: m === "edited" ? "#2f62d8" : m === "in" ? "#3a3b42" : "#d4d4ce",
                  opacity: m === "out" ? 0.7 : 1,
                }}
                transition={{ duration: 0.35 }}
                className={`h-1.5 rounded-[1px] ${m === "dropped" ? "outline-1 outline-offset-1 outline-dashed outline-[#b3261e]" : ""}`}
                style={{ width: `${WIDTHS[i % WIDTHS.length]}%` }} />
              {m === "out" && <span className="absolute inset-x-0 top-1/2 h-px bg-[#bf3328]" style={{ width: `${WIDTHS[i % WIDTHS.length]}%` }} />}
              {(m === "in" || m === "edited") && (
                <svg viewBox="0 0 12 12" className="absolute -right-4 size-3 text-[#2f62d8]">
                  <path d="M2 6.5 5 9l5-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              )}
            </span>
          ))}
          {marks.length > 12 && <span className="text-[11px] text-[#5f6068]">+ {marks.length - 12} more</span>}
        </div>
      </div>
      {/* the same fixed colours as the paper above, in both themes */}
      <ul aria-hidden="true" className="m-0 flex flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-muted">
        <li className="flex items-center gap-1.5"><span className="h-1.5 w-4 rounded-[1px] bg-[#3a3b42] ring-1 ring-[#e2e2dd]" />Going in</li>
        <li className="flex items-center gap-1.5"><span className="h-1.5 w-4 rounded-[1px] bg-[#2f62d8]" />Your words</li>
        <li className="flex items-center gap-1.5"><span className="relative h-1.5 w-4 rounded-[1px] bg-[#d4d4ce]"><span className="absolute inset-x-0 top-1/2 h-px bg-[#bf3328]" /></span>Rejected</li>
        <li className="flex items-center gap-1.5"><span className="h-1.5 w-4 rounded-[1px] bg-[#3a3b42] outline-1 outline-offset-1 outline-dashed outline-[#b3261e]" />Fails the fact check</li>
      </ul>
    </div>
  );
}
