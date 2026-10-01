import { animate, motion, useMotionValue, useTransform } from "motion/react";
import { useEffect } from "react";

const R = 74;
const CIRCUMFERENCE = 2 * Math.PI * R;

/** The keyword match rate as a ring, with the earlier rate as a faint arc
 *  and the target band under it. */
export function ScoreDial({ value, before, band, size = 180, label = "Keyword match" }: {
  value: number;
  before?: number | null;
  band?: [number, number];
  size?: number;
  label?: string;
}) {
  const shown = useMotionValue(before ?? 0);
  const text = useTransform(shown, (v) => Math.round(v).toString());
  const dash = useTransform(shown, (v) => `${(Math.max(0, Math.min(100, v)) / 100) * CIRCUMFERENCE} ${CIRCUMFERENCE}`);
  useEffect(() => {
    const controls = animate(shown, value, { duration: 0.9, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [shown, value]);

  const delta = before != null ? value - before : null;
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative" style={{ width: size, height: size }}
        role="img" aria-label={`${label}: ${value.toFixed(1)}%${before != null ? `, was ${before.toFixed(1)}%` : ""}`}>
        <svg width={size} height={size} viewBox="0 0 180 180" aria-hidden="true">
          <circle cx="90" cy="90" r={R} fill="none" stroke="var(--line)" strokeWidth="6" />
          {before != null && (
            <circle cx="90" cy="90" r={R} fill="none" stroke="var(--line-strong)" strokeWidth="6"
              strokeDasharray={`${(before / 100) * CIRCUMFERENCE} ${CIRCUMFERENCE}`} transform="rotate(-90 90 90)" />
          )}
          <motion.circle cx="90" cy="90" r={R} fill="none" stroke="var(--gold)" strokeWidth="6" strokeLinecap="round"
            style={{ strokeDasharray: dash }} transform="rotate(-90 90 90)" />
        </svg>
        <div aria-hidden="true" className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display leading-none" style={{ fontSize: size * 0.32 }}>
            <motion.span>{text}</motion.span>
            <span style={{ fontSize: size * 0.155 }}>%</span>
          </span>
          {delta != null && Math.abs(delta) >= 0.05 && (
            <span className={`mt-1 text-xs ${delta >= 0 ? "text-success" : "text-danger"}`}>
              {delta >= 0 ? "+" : ""}{delta.toFixed(1)} pts
            </span>
          )}
        </div>
      </div>
      {band && <BandBar value={value} band={band} />}
    </div>
  );
}

export function BandBar({ value, band }: { value: number; band: [number, number] }) {
  const [low, high] = band;
  return (
    <div className="flex w-full flex-col gap-1.5" aria-hidden="true">
      <div className="relative h-1.5 bg-line">
        <div className="absolute inset-y-0 bg-success/45" style={{ left: `${low}%`, width: `${high - low}%` }} />
        <div className="absolute -top-[5px] h-4 w-0.5 bg-gold" style={{ left: `${Math.min(99.5, value)}%` }} />
      </div>
      <div className="flex justify-between text-[11px] text-muted">
        <span>0</span>
        <span>Target {low.toFixed(0)}–{high.toFixed(0)}%</span>
        <span>100</span>
      </div>
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
