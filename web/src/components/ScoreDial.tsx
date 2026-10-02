import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect } from "react";

const clamp = (v: number) => Math.max(0, Math.min(100, v));

/** A number that counts to its value; shows the value at once under reduced
 *  motion or when the preference is unknown. */
export function CountUp({ value, from = 0, decimals = 0 }: { value: number; from?: number; decimals?: number }) {
  const reduce = useReducedMotion();
  const shown = useMotionValue(reduce === false ? from : value);
  const text = useTransform(shown, (v) => v.toFixed(decimals));
  useEffect(() => {
    if (reduce !== false) {
      shown.set(value);
      return;
    }
    const controls = animate(shown, value, { duration: 0.9, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [shown, value, reduce]);
  return <motion.span>{text}</motion.span>;
}

/** An editor's rule from 0 to 100: ticks, the target band, the earlier rate
 *  as a ghost mark and the current rate as the pencil mark. */
export function ScoreRule({ value, before, band }: { value: number; before?: number | null; band?: [number, number] }) {
  const reduce = useReducedMotion();
  return (
    <div aria-hidden="true" className="flex w-full flex-col gap-1">
      {band && (
        <div className="relative h-4 text-xs font-medium text-success">
          <span className="absolute whitespace-nowrap"
            style={(band[0] + band[1]) / 2 > 70 ? { right: `${Math.max(0, 100 - band[1])}%` } : { left: `${band[0]}%` }}>
            Target {band[0].toFixed(0)}–{band[1].toFixed(0)}%
          </span>
        </div>
      )}
      <div className="relative h-9">
        {/* target band */}
        {band && (
          <div className="absolute bottom-3 top-1 rounded-[2px] bg-success/15 ring-1 ring-success-line ring-inset"
            style={{ left: `${band[0]}%`, width: `${band[1] - band[0]}%` }} />
        )}
        {/* ticks */}
        <div className="absolute inset-x-0 bottom-3 h-px bg-field" />
        {Array.from({ length: 21 }, (_, i) => (
          <span key={i} className={`absolute bottom-3 w-px bg-field ${i % 2 === 0 ? "h-3" : "h-1.5"}`} style={{ left: `${i * 5}%` }} />
        ))}
        {before != null && (
          <span className="absolute bottom-3 top-0 w-0.5 -translate-x-1/2 bg-line-strong" style={{ left: `${clamp(before)}%` }} />
        )}
        <motion.span className="absolute bottom-1 top-0 w-[3px] -translate-x-1/2 rounded-full bg-pencil"
          initial={reduce === false ? { left: `${clamp(before ?? 0)}%` } : false}
          animate={{ left: `${clamp(value)}%` }}
          transition={reduce === false ? { duration: 0.9, ease: [0.22, 1, 0.36, 1] } : { duration: 0 }}>
          <span className="absolute -bottom-2 left-1/2 size-0 -translate-x-1/2 border-x-[6px] border-b-[7px] border-x-transparent border-b-pencil" />
        </motion.span>
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>0</span>
        <span>100</span>
      </div>
    </div>
  );
}

/** The keyword match rate: the number, the change since tailoring started,
 *  and the rule with the target band. */
export function ScoreDial({ value, before, band, label = "Keyword match", size = "md" }: {
  value: number;
  before?: number | null;
  band?: [number, number];
  label?: string;
  size?: "md" | "lg";
}) {
  const delta = before != null ? value - before : null;
  return (
    <div className="flex w-full flex-col gap-4">
      <div role="img" aria-label={`${label}: ${value.toFixed(1)}%${before != null ? `, was ${before.toFixed(1)}%` : ""}`}
        className="flex items-end justify-between gap-3">
        <span aria-hidden="true" className={`tabular font-display font-bold leading-none tracking-[-0.04em] ${size === "lg" ? "text-[76px]" : "text-[60px]"}`}>
          <CountUp value={value} from={before ?? 0} /><span className="text-[0.45em] text-pencil">%</span>
        </span>
        {delta != null && Math.abs(delta) >= 0.05 && (
          <span aria-hidden="true" className={`mb-1.5 rounded-[3px] border px-2 py-0.5 text-[13px] font-semibold ${
            delta >= 0 ? "border-success-line text-success" : "border-danger text-danger"}`}>
            {delta >= 0 ? "+" : "−"}{Math.abs(delta).toFixed(1)} pts
          </span>
        )}
      </div>
      {band && <ScoreRule value={value} before={before} band={band} />}
    </div>
  );
}

/** Plain-language reading of the rate against the target band. */
export function verdict(rate: number, band: [number, number]): { text: string; tone: "low" | "good" | "high" } {
  const [low, high] = band;
  if (rate < low) return { text: `Below the ${low.toFixed(0)}–${high.toFixed(0)}% target.`, tone: "low" };
  if (rate > high) return { text: `Above ${high.toFixed(0)}%: check the resume doesn't read as keyword-stuffed.`, tone: "high" };
  return { text: "Inside the target band.", tone: "good" };
}
