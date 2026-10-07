import { REGION_LABELS, type RegionInfo } from "../lib/types";

/** "Formatted for US (Letter) · the job says "Austin, TX"" with a select to
 *  change it (P10.3). The suggestion comes from the JD; the user decides. */
export function RegionChoice({ id, value, suggested, onChange, className = "" }: {
  id: string;
  value: string;
  suggested?: RegionInfo | null;
  onChange: (region: string) => void;
  className?: string;
}) {
  const why = suggested?.evidence && suggested.region === value
    ? <>the job says “{suggested.evidence}”</>
    : suggested?.evidence ? <>the job says “{suggested.evidence}” ({REGION_LABELS[suggested.region]})</>
    : <>nothing in the job says where; A4 is the default</>;
  return (
    <div className={`flex flex-col gap-1.5 text-xs text-muted ${className}`}>
      <label htmlFor={id} className="font-medium text-ink">Formatted for</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-[3px] border border-field bg-panel px-3 text-sm text-ink">
        {Object.entries(REGION_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      <span>{why}. US uses Letter paper and 01/2022 dates; elsewhere A4 and Jan 2022.</span>
    </div>
  );
}
