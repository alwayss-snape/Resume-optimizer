import type { DiffSpan } from "../lib/types";

/** One side of a word diff: removed words struck through on the original,
 *  added words highlighted on the proposal, JD keywords in bold. React
 *  escapes the text. */
export function DiffText({ spans, side }: { spans: DiffSpan[]; side: "original" | "proposed" }) {
  return (
    <p className={`m-0 whitespace-pre-line break-words text-[15px] leading-relaxed ${side === "original" ? "text-muted" : "text-ink"}`}>
      {spans.map((s, i) => {
        if (s.text === "\n") return "\n";
        let node: React.ReactNode = s.text;
        if (s.keyword) node = <strong className="font-semibold text-ink">{node}</strong>;
        if (s.changed) {
          node = side === "original"
            ? <del className="decoration-danger/70">{node}</del>
            : <ins className="bg-gold-soft no-underline">{node}</ins>;
        }
        const next = spans[i + 1];
        return (
          <span key={i}>
            {node}
            {next && next.text !== "\n" && s.text !== "\n" ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}
