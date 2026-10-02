import type { DiffSpan } from "../lib/types";

type ProofPiece = { text: string; kind: "same" | "del" | "ins"; keyword: boolean };

/** Weaves the two sides of a word diff into one editor's proof: removed words
 *  then inserted words at each change, shared words once. Null when the
 *  shared words don't line up (then show the two sides instead). */
export function mergeProof(original: DiffSpan[], proposed: DiffSpan[]): ProofPiece[] | null {
  const same = (spans: DiffSpan[]) => spans.filter((s) => !s.changed && s.text !== "\n").map((s) => s.text);
  const a = same(original);
  const b = same(proposed);
  if (a.length !== b.length || a.some((t, i) => t !== b[i])) return null;
  const out: ProofPiece[] = [];
  const isBreak = (x: DiffSpan | undefined) => x?.text === "\n";
  let i = 0;
  let j = 0;
  while (i < original.length || j < proposed.length) {
    // at each point: removed words, then inserted words, then a line break, then a shared word
    while (i < original.length && original[i].changed && !isBreak(original[i])) {
      out.push({ text: original[i].text, kind: "del", keyword: Boolean(original[i].keyword) });
      i++;
    }
    while (j < proposed.length && proposed[j].changed && !isBreak(proposed[j])) {
      out.push({ text: proposed[j].text, kind: "ins", keyword: Boolean(proposed[j].keyword) });
      j++;
    }
    if (isBreak(original[i]) || isBreak(proposed[j])) {
      // the proposal's line breaks stay (the reading is the proposed text); the original's are dropped
      if (isBreak(proposed[j])) {
        out.push({ text: "\n", kind: "same", keyword: false });
        j++;
      }
      if (isBreak(original[i])) i++;
      continue;
    }
    if (i < original.length && j < proposed.length) {
      out.push({ text: proposed[j].text, kind: "same", keyword: Boolean(proposed[j].keyword || original[i].keyword) });
      i++;
      j++;
    } else {
      break; // one side is used up; nothing shared is left to pair
    }
  }
  return quietPunctuation(out);
}

const bare = (t: string) => t.replace(/,+$/, "");

/** In a removed run followed by an inserted run, words at either end that
 *  differ only by a trailing comma ("stores" -> "stores,") are the same
 *  words, not a change; only the middle stays marked. Full stops and other
 *  punctuation stay marked (they can change a sentence). */
function quietPunctuation(pieces: ProofPiece[]): ProofPiece[] {
  const out: ProofPiece[] = [];
  let k = 0;
  while (k < pieces.length) {
    if (pieces[k].kind === "same") {
      out.push(pieces[k++]);
      continue;
    }
    let d = k;
    while (d < pieces.length && pieces[d].kind === "del") d++;
    let n = d;
    while (n < pieces.length && pieces[n].kind === "ins") n++;
    const dels = pieces.slice(k, d);
    const ins = pieces.slice(d, n);
    const same = (x: number, y: number) => bare(dels[x].text) === bare(ins[y].text);
    let head = 0;
    while (head < dels.length && head < ins.length && same(head, head)) head++;
    let tail = 0;
    while (tail < dels.length - head && tail < ins.length - head && same(dels.length - 1 - tail, ins.length - 1 - tail)) tail++;
    const keep = (p: ProofPiece, x: number) => ({ ...p, kind: "same" as const, keyword: p.keyword || dels[x].keyword });
    ins.slice(0, head).forEach((p, x) => out.push(keep(p, x)));
    out.push(...dels.slice(head, dels.length - tail), ...ins.slice(head, ins.length - tail));
    ins.slice(ins.length - tail).forEach((p, x) => out.push(keep(p, dels.length - tail + x)));
    k = n;
  }
  return out;
}

type Run = { kind: "same" | "del" | "ins" | "break"; words: { text: string; keyword: boolean }[] };

/** Consecutive words with the same mark become one run, so a removal or an
 *  insertion reads as one continuous mark, not one per word. */
function runs(pieces: { text: string; kind: "same" | "del" | "ins"; keyword: boolean }[]): Run[] {
  const out: Run[] = [];
  for (const p of pieces) {
    const kind = p.text === "\n" ? "break" : p.kind;
    const last = out[out.length - 1];
    if (last && last.kind === kind && kind !== "same" && kind !== "break") last.words.push(p);
    else out.push({ kind, words: [p] });
  }
  return out;
}

/** A job keyword: bold with the highlighter swipe, in ink (never coloured text on yellow). Inside a removal it
 *  stays bold only, since struck red text on yellow would fail contrast. */
function Word({ text, keyword, removed }: { text: string; keyword: boolean; removed?: boolean }) {
  if (!keyword) return <>{text}</>;
  return <strong className={removed ? "font-semibold" : "mark-hl font-semibold text-ink"}>{text}</strong>;
}

function Marked({ list }: { list: Run[] }) {
  return (
    <>
      {list.map((run, i) => {
        if (run.kind === "break") return <br key={i} />;
        const space = i > 0 && list[i - 1].kind !== "break" ? " " : "";
        const words = run.words.map((w, x) => (
          <span key={x}>{x > 0 ? " " : ""}<Word text={w.text} keyword={w.keyword} removed={run.kind === "del"} /></span>
        ));
        if (run.kind === "del") return <span key={i}>{space}<del className="mark-del">{words}</del></span>;
        if (run.kind === "ins") return <span key={i}>{space}<ins className="mark-ins">{words}</ins></span>;
        return <span key={i}>{space}{words}</span>;
      })}
    </>
  );
}

/** One side of a word diff, or the merged proof. Removed words are struck
 *  (<del>), added words underlined (<ins>), job keywords bold with the
 *  highlighter swipe. Marks never rely on colour alone. React escapes the text. */
export function DiffText({ spans, side, proposed }: {
  spans: DiffSpan[];
  side: "original" | "proposed" | "proof";
  proposed?: DiffSpan[]; // the proposed side, for "proof"
}) {
  if (side === "proof") {
    const pieces = mergeProof(spans, proposed ?? []);
    if (pieces) {
      return (
        <p className="m-0 break-words font-serif text-[17px] leading-[1.8] text-ink">
          <Marked list={runs(pieces)} />
        </p>
      );
    }
    return (
      <div className="grid gap-5 sm:grid-cols-2 sm:gap-6">
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold text-muted">Original</span>
          <DiffText spans={spans} side="original" />
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold text-pencil">Proposed</span>
          <DiffText spans={proposed ?? []} side="proposed" />
        </div>
      </div>
    );
  }
  const changedKind = side === "original" ? "del" : "ins";
  const pieces = spans.map((sp) => ({ text: sp.text, kind: sp.changed ? changedKind : "same", keyword: Boolean(sp.keyword) } as const));
  return (
    <p className={`m-0 break-words font-serif text-[16px] leading-[1.7] ${side === "original" ? "text-muted" : "text-ink"}`}>
      <Marked list={runs(pieces)} />
    </p>
  );
}
