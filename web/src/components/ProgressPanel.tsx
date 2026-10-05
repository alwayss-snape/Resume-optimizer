import { AnimatePresence, motion } from "motion/react";
import { type Dispatch, type SetStateAction, useEffect, useState } from "react";
import { Icon } from "./Icon";

/** The AI service asked us to wait this long (P9.7); `id` restarts the countdown. */
export interface Wait {
  seconds: number;
  id: number;
}

let waitCount = 0;

/** The streaming callback for a page: a new step ends any wait, a wait
 *  replaces the countdown and never becomes a step of its own. */
export function progressHandler(setMessages: Dispatch<SetStateAction<string[] | null>>,
  setWait: Dispatch<SetStateAction<Wait | null>>) {
  return (message: string, waitSeconds?: number) => {
    if (waitSeconds !== undefined) {
      setWait({ seconds: waitSeconds, id: ++waitCount });
      return;
    }
    setWait(null);
    setMessages((p) => [...(p ?? []), message]);
  };
}

function Countdown({ wait }: { wait: Wait }) {
  const [left, setLeft] = useState(wait.seconds);
  useEffect(() => {
    setLeft(wait.seconds);
    const id = window.setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(id);
  }, [wait.id, wait.seconds]);
  return (
    <p className="m-0 ml-5 flex items-center gap-2 text-sm text-muted" data-testid="wait">
      <Icon name="clock" size={14} className="shrink-0" />
      {/* Said once to screen readers; the ticking number is visual only. */}
      <span className="sr-only">The free AI service asked us to wait about {wait.seconds} seconds, then we try again.</span>
      <span aria-hidden="true">
        The free AI service asked us to wait · {left > 0 ? `trying again in ${left} s` : "trying again now…"}
      </span>
    </p>
  );
}

/** Live progress of a long step: each message the server sends, the last
 *  one still running (with a countdown under it while the AI service makes
 *  us wait), a pencil stroke drawing across and the time so far. */
export function ProgressPanel({ title, messages, wait }: { title: string; messages: string[]; wait?: Wait | null }) {
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
                <span className="flex flex-col gap-1.5">
                  {m}
                  {running && wait && <Countdown wait={wait} />}
                </span>
                <span className="sr-only">{running ? " (in progress)" : " (done)"}</span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
    </div>
  );
}
