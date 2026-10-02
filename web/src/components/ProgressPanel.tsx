import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Icon } from "./Icon";

/** Live progress of a long step: each message the server sends, the last
 *  one still running, a pencil stroke drawing across and the time so far. */
export function ProgressPanel({ title, messages }: { title: string; messages: string[] }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div role="status" aria-live="polite" className="sheet flex flex-col gap-5 overflow-hidden rounded-[3px] p-6 md:p-7">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-display text-2xl font-bold tracking-[-0.025em]">{title}</span>
        <span aria-hidden="true" className="tabular text-sm text-muted">{seconds} s</span>
      </div>
      <div aria-hidden="true" className="relative h-[3px] overflow-hidden rounded-full bg-line">
        <span className="pencil-run absolute inset-y-0 left-0 w-2/5 rounded-full bg-pencil" />
      </div>
      <ol className="flex flex-col gap-2.5 text-[15px]">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => {
            const running = i === messages.length - 1;
            return (
              <motion.li key={`${i}-${m}`} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                className={`flex items-start gap-3 ${running ? "font-medium text-ink" : "text-muted"}`}>
                {running ? (
                  <span aria-hidden="true" className="mt-[7px] size-2 shrink-0 rounded-full bg-pencil motion-safe:animate-pulse" />
                ) : (
                  <Icon name="check" size={16} strokeWidth={2.2} className="mt-0.5 shrink-0 text-success" />
                )}
                {m}
                <span className="sr-only">{running ? " (in progress)" : " (done)"}</span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
    </div>
  );
}
