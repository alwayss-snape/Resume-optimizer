import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useFocusHeading } from "../lib/useFocusHeading";
import { Button } from "../components/Button";
import { UploadForm, type UploadValues } from "../components/UploadForm";
import type { Intent, Run } from "../lib/store";

const HOW_IT_WORKS = [
  { title: "Upload and paste", text: "We read your resume and the job, and show your keyword match before anything changes." },
  { title: "Review every change", text: "Accept, reject or edit each rewrite next to your original. You decide what goes in." },
  { title: "Download DOCX and PDF", text: "An ATS-ready file, checked by reading it back, with a log of every change made." },
];

const rise = {
  hidden: { opacity: 0, y: 14 },
  shown: (i: number) => ({ opacity: 1, y: 0, transition: { duration: 0.6, delay: 0.08 * i, ease: [0.22, 1, 0.36, 1] as const } }),
};

/** First screen: hero, the upload form, and how it works. */
export function Landing({ onStart, busy, run, maxUploadMb, error, errorKey }: {
  onStart: (intent: Intent, values: UploadValues) => void;
  busy?: boolean;
  run: Run;
  maxUploadMb?: number;
  error?: string | null;
  errorKey?: number;
}) {
  const [intent, setIntent] = useState<Intent>(run.intent);
  // Coming back to this page (a run exists): put focus on its heading.
  const heading = useFocusHeading(Boolean(run.file));
  const start = useRef<HTMLElement>(null);

  const begin = (next: Intent) => {
    setIntent(next);
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    start.current?.scrollIntoView?.({ behavior: still ? "auto" : "smooth", block: "start" });
    start.current?.querySelector<HTMLElement>("input, textarea")?.focus({ preventScroll: true });
  };

  return (
    <>
      <section className="mx-auto flex max-w-[1240px] flex-col items-center gap-6 px-4 pb-14 pt-16 text-center md:px-8 md:pt-24">
        <motion.p variants={rise} initial="hidden" animate="shown" custom={0}
          className="flex items-center gap-3.5 text-xs tracking-[0.28em] text-gold">
          <span aria-hidden="true" className="h-px w-10 bg-gold" />
          RESUME TAILORING
          <span aria-hidden="true" className="h-px w-10 bg-gold" />
        </motion.p>
        <motion.h1 ref={heading} tabIndex={-1} variants={rise} initial="hidden" animate="shown" custom={1}
          className="max-w-[900px] outline-none font-display text-[44px] font-medium leading-[1.02] tracking-[-0.01em] sm:text-6xl md:text-[76px]">
          Your experience, presented for the role.
        </motion.h1>
        <motion.p variants={rise} initial="hidden" animate="shown" custom={2}
          className="max-w-[620px] text-base leading-relaxed text-muted md:text-lg">
          Upload your resume and paste the job description. Every rewrite is built from what is already on your
          resume. Nothing is invented.
        </motion.p>
        <motion.div variants={rise} initial="hidden" animate="shown" custom={3}
          className="mt-3 flex flex-col gap-3.5 sm:flex-row">
          <Button variant="primary" size="lg" onClick={() => begin("tailor")}>Tailor my resume</Button>
          <Button size="lg" onClick={() => begin("check")}>Just check my match</Button>
        </motion.div>
      </section>

      <section ref={start} id="start" aria-labelledby="start-title" className="mx-auto max-w-[1240px] scroll-mt-6 px-4 md:px-8">
        <h2 id="start-title" className="sr-only">
          {intent === "tailor" ? "Tailor your resume" : "Check your match"}
        </h2>
        <UploadForm intent={intent} busy={busy} onSubmit={(values) => onStart(intent, values)} initial={run}
          maxUploadMb={maxUploadMb} serverError={error} serverErrorKey={errorKey} />
      </section>

      <section aria-labelledby="how-title" className="mx-auto flex max-w-[1240px] flex-col gap-9 px-4 pb-20 pt-24 md:px-8">
        <div className="flex items-center gap-5">
          <h2 id="how-title" className="whitespace-nowrap font-display text-[40px] font-medium">How it works</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-line" />
        </div>
        <ol className="grid gap-8 md:grid-cols-3 md:gap-6">
          {HOW_IT_WORKS.map((item, i) => (
            <li key={item.title} className="flex flex-col gap-3 border-t border-gold pt-5">
              <span aria-hidden="true" className="font-display text-[44px] leading-none text-gold">0{i + 1}</span>
              <span className="text-lg font-medium">{item.title}</span>
              <span className="text-sm leading-relaxed text-muted">{item.text}</span>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
