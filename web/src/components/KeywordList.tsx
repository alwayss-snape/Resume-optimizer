import type { KeywordMatch, KeywordRow } from "../lib/types";

const KIND_LABELS: Record<string, string> = {
  hard: "Hard skills", title: "Job title", education: "Education", certification: "Certifications", soft: "Soft skills",
};

function Chip({ row }: { row: KeywordRow }) {
  return (
    <li className={`flex items-center gap-1.5 border px-2.5 py-1 text-xs ${
      row.found ? "border-success-line text-success" : "border-dashed border-field text-muted"}`}
      title={row.found && row.where.length ? `Found in: ${row.where.join(", ")}` : undefined}>
      <span className="sr-only">{row.found ? "Found:" : "Missing:"}</span>
      {row.keyword}
      {row.required && !row.found && <span className="text-[10px] tracking-[0.1em] text-danger">REQ</span>}
    </li>
  );
}

/** JD keywords grouped by kind: found ones solid, missing ones dashed, the
 *  required missing ones flagged. */
export function KeywordList({ match, compact = false }: { match: KeywordMatch; compact?: boolean }) {
  const kinds = Object.keys(KIND_LABELS).filter((k) => match.rows.some((r) => r.kind === k));
  const found = match.rows.filter((r) => r.found).length;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11px] tracking-[0.2em] text-muted">KEYWORDS · {found} OF {match.rows.length} FOUND</p>
      {kinds.map((kind) => {
        const rows = match.rows
          .filter((r) => r.kind === kind)
          .sort((a, b) => Number(a.found) - Number(b.found) || Number(b.required) - Number(a.required) || b.weight - a.weight);
        return (
          <div key={kind} className="flex flex-col gap-2">
            {!compact && <h3 className="text-sm text-ink">{KIND_LABELS[kind]}</h3>}
            <ul className="flex flex-wrap gap-1.5">
              {rows.map((r) => (
                <Chip key={r.keyword} row={r} />
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export function Breakdown({ match }: { match: KeywordMatch }) {
  if (!match.breakdown.length) return null;
  return (
    <table className="w-full text-left text-sm">
      <caption className="mb-3 text-left text-[11px] tracking-[0.2em] text-muted">WHERE THE SCORE COMES FROM</caption>
      <thead className="text-xs text-muted">
        <tr className="border-b border-line">
          <th scope="col" className="py-2 font-normal">Kind</th>
          <th scope="col" className="py-2 font-normal">Found</th>
          <th scope="col" className="py-2 text-right font-normal">Points</th>
        </tr>
      </thead>
      <tbody>
        {match.breakdown.map((row) => (
          <tr key={row.Kind} className="border-b border-line">
            <td className="py-2.5">{row.Kind}</td>
            <td className="py-2.5 text-muted">{row.Found}</td>
            <td className="py-2.5 text-right text-muted">{row.Points}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
