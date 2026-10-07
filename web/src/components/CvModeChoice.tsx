import { CV_MODE_LABELS, type CvModeInfo } from "../lib/types";

/** "CV type: [Academic CV] · suggested by a “Professor” role, …" (P10.5).
 *  The suggestion comes from the resume and the JD; the user decides. */
export function CvModeChoice({ id, value, suggested, onChange, className = "" }: {
  id: string;
  value: string;
  suggested?: CvModeInfo | null;
  onChange: (mode: string) => void;
  className?: string;
}) {
  const why = suggested && suggested.mode !== "standard" && suggested.evidence.length
    ? `Suggested as ${suggested.label}: ${suggested.evidence.join(", ")}.` : "";
  return (
    <div className={`flex flex-col gap-1.5 text-xs text-muted ${className}`}>
      <label htmlFor={id} className="font-medium text-ink">CV type</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink">
        {Object.entries(CV_MODE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      <span>{why} An Academic CV or a US Federal resume runs to its full length, with no page cap.</span>
    </div>
  );
}
