import type { KeywordMatch } from "../lib/types";

/** What a low match means for this resume (P8.21): a different field gets a
 *  plain explanation and career-change steps, not "aim for 75-85%". */
export function MatchGuidance({ guidance }: { guidance: NonNullable<KeywordMatch["guidance"]> }) {
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-4">
      <p className="m-0 text-[15px] font-semibold">{guidance.headline}</p>
      <p className="m-0 font-serif text-[15px] italic leading-relaxed text-muted">{guidance.text}</p>
      <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed">
        {guidance.tips.map((t) => <li key={t}>{t}</li>)}
      </ul>
    </div>
  );
}
