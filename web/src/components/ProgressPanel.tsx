import { AnimatePresence, motion } from "motion/react";
import { Icon } from "./Icon";

/** Live progress of a long step: each message the server sends, the last
 *  one still running. */
export function ProgressPanel({ title, messages }: { title: string; messages: string[] }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-4 border border-line bg-panel p-6">
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-line-strong border-t-gold motion-reduce:animate-none" />
        <span className="font-display text-2xl">{title}</span>
      </div>
      <ol className="flex flex-col gap-2 text-sm">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => {
            const running = i === messages.length - 1;
            return (
              <motion.li key={`${i}-${m}`} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                className={`flex items-start gap-2.5 ${running ? "text-ink" : "text-muted"}`}>
                {running ? (
                  <span aria-hidden="true" className="mt-1.5 size-1.5 shrink-0 rounded-full bg-gold" />
                ) : (
                  <Icon name="check" size={14} strokeWidth={2} className="mt-0.5 shrink-0 text-success" />
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
