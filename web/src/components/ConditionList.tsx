import type { Condition } from "../lib/types";
import { Icon } from "./Icon";

/** Job conditions that aren't keywords (P8.20): a licence, shifts, lifting,
 *  a language, the right to work. Ticked once by the user, never added to the
 *  resume or the match rate. Read-only (the match report) when `ticked` is absent. */
export function ConditionList({ conditions, ticked, onToggle }: {
  conditions: Condition[];
  ticked?: string[];
  onToggle?: (id: string) => void;
}) {
  return (
    <ul className="m-0 flex flex-col p-0">
      {conditions.map((c) => {
        const met = c.auto === "met";
        const on = met || (ticked?.includes(c.id) ?? false);
        return (
          <li key={c.id} className="flex flex-col gap-1 border-t border-line py-3 first:border-t-0">
            <span className="text-xs text-muted">
              {c.label}{c.priority === "preferred" ? " · nice to have" : ""}
            </span>
            {onToggle && !c.auto ? (
              <label className="flex min-h-11 cursor-pointer items-start gap-3 text-[15px] leading-relaxed">
                <input type="checkbox" className="mt-1 size-4 shrink-0" checked={on} onChange={() => onToggle(c.id)} />
                <span><span className="font-serif">{c.text}</span> <span className="text-sm text-muted">· I meet this</span></span>
              </label>
            ) : (
              <p className="m-0 flex items-start gap-2 text-[15px] leading-relaxed">
                {c.auto === "met" ? <Icon name="check" size={16} strokeWidth={2.2} className="mt-1 shrink-0 text-success" />
                  : c.auto === "not_met" ? <Icon name="alert" size={16} className="mt-1 shrink-0 text-warning" />
                  : <span aria-hidden="true" className="mt-1.5 size-2.5 shrink-0 rounded-full border-[1.5px] border-field" />}
                <span className="font-serif">{c.text}</span>
              </p>
            )}
            {c.note && <span className="text-xs text-muted">{c.note}</span>}
          </li>
        );
      })}
    </ul>
  );
}
