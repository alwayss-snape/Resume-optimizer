import { motion, useMotionValue } from "motion/react";
import { type PointerEvent, useRef } from "react";
import { useFocusHeading } from "../lib/useFocusHeading";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { FluidField } from "../components/hero/FluidField";
import { ProofSheet } from "../components/hero/ProofSheet";
import { UploadForm, type UploadValues } from "../components/UploadForm";
import type { AppConfig } from "../lib/api";
import type { Intent, Run } from "../lib/store";

const HOW_IT_WORKS = [
  { title: "Upload and paste", text: "We read your resume and the job, and show your keyword match before anything changes." },
  { title: "Review every change", text: "Accept, reject or edit each rewrite next to your original. You decide what goes in." },
  { title: "Download DOCX and PDF", text: "An ATS-ready file, checked by reading it back, with a log of every change made." },
];

const rise = {
  hidden: { opacity: 0, y: 14 },
  shown: (i: number) => ({ opacity: 1, y: 0, transition: { duration: 0.7, delay: 0.08 * i, ease: [0.22, 1, 0.36, 1] as const } }),
};

/** First screen: the proof demonstration, the upload form, and how it works. */
/** Where the resume goes (P8.24): said before anything is uploaded. */
export function PrivacyNote({ config }: { config?: AppConfig | null }) {
  const minutes = config?.session_minutes ?? 60;
  const ai = config?.provider_label ?? "an AI service";
  return (
    <p className="m-0 mt-6 max-w-[72ch] text-[13px] leading-relaxed text-muted">
      <span className="font-semibold text-ink">Privacy: </span>
      {config?.cloud === false
        ? `Your resume and the job description are processed on this server, by ${ai}; nothing is sent to an outside AI service. `
        : `To read the job description and draft rewrites, the text of your resume and the job description is sent to ${ai}, a cloud AI service. `}
      Your file and results are kept only for this visit and deleted when you start over or after {minutes} minutes
      without activity. Your browser keeps only your settings, never your resume.
    </p>
  );
}

export function Landing({ onStart, busy, run, maxUploadMb, error, errorKey, config }: {
  onStart: (intent: Intent, values: UploadValues) => void;
  busy?: boolean;
  run: Run;
  maxUploadMb?: number;
  error?: string | null;
  errorKey?: number;
  config?: AppConfig | null;
}) {
  // Coming back to this page (a run exists): put focus on its heading.
  const heading = useFocusHeading(Boolean(run.file));
  const start = useRef<HTMLElement>(null);
  // The pointer over the hero: -0.5..0.5 for the sheets' tilt, 0..1 for the ink.
  const tiltX = useMotionValue(0);
  const tiltY = useMotionValue(0);
  const pointer = useRef({ x: 0.7, y: 0.5 });

  // The hero only leads to the form; what to do with it (tailor or check) is
  // chosen by the form's own actions, once both inputs are filled in (P9.14).
  const begin = () => {
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    start.current?.scrollIntoView?.({ behavior: still ? "auto" : "smooth", block: "start" });
    start.current?.querySelector<HTMLElement>("input, textarea")?.focus({ preventScroll: true });
  };

  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - box.left) / box.width;
    const y = (e.clientY - box.top) / box.height;
    tiltX.set(x - 0.5);
    tiltY.set(y - 0.5);
    pointer.current = { x, y: 1 - y };
  };
  const onPointerLeave = () => {
    tiltX.set(0);
    tiltY.set(0);
  };

  return (
    <>
      <section onPointerMove={onPointerMove} onPointerLeave={onPointerLeave} className="relative isolate overflow-hidden">
        <FluidField pointer={pointer}
          className="absolute inset-0 -z-10 [mask-image:linear-gradient(180deg,transparent_0%,transparent_38%,black_72%,black_86%,transparent_100%)] lg:[mask-composite:intersect] lg:[mask-image:linear-gradient(90deg,transparent_0%,transparent_34%,black_66%),linear-gradient(180deg,black_0%,black_72%,transparent_100%)]" />
        <div className="mx-auto grid max-w-[1240px] items-center gap-12 px-4 pb-16 pt-12 md:px-8 lg:grid-cols-12 lg:gap-8 lg:pb-24 lg:pt-20">
          <div className="flex flex-col items-start gap-6 lg:col-span-6">
            <motion.h1 ref={heading} tabIndex={-1} variants={rise} initial="hidden" animate="shown" custom={0}
              className="font-display text-[42px] font-bold leading-[1.02] tracking-[-0.035em] outline-none sm:text-[56px] lg:text-[62px]">
              Your experience, presented for the role.
            </motion.h1>
            <motion.p variants={rise} initial="hidden" animate="shown" custom={1}
              className="max-w-[46ch] text-[17px] leading-relaxed text-muted lg:text-lg">
              Upload your resume and paste the job description. Every rewrite is built from what is already on your
              resume. Nothing is invented.
            </motion.p>
            <motion.div variants={rise} initial="hidden" animate="shown" custom={2} className="mt-2 w-full sm:w-auto">
              <Button variant="primary" size="lg" onClick={begin} className="w-full sm:w-auto">
                Get started <Icon name="arrow-right" />
              </Button>
            </motion.div>
          </div>
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.2, ease: [0.22, 1, 0.36, 1] }} className="lg:col-span-6">
            <ProofSheet tiltX={tiltX} tiltY={tiltY} />
          </motion.div>
        </div>
      </section>

      <section ref={start} id="start" aria-labelledby="start-title" className="mx-auto max-w-[1240px] scroll-mt-6 px-4 pt-4 md:px-8">
        <h2 id="start-title" className="sr-only">Your resume and the job</h2>
        <UploadForm busy={busy} onSubmit={(values, intent) => onStart(intent, values)} initial={run}
          maxUploadMb={maxUploadMb} serverError={error} serverErrorKey={errorKey} />
        <PrivacyNote config={config} />
      </section>

      <section aria-labelledby="how-title" className="mx-auto flex max-w-[1240px] flex-col gap-10 px-4 pb-24 pt-28 md:px-8">
        <h2 id="how-title" className="font-display text-[32px] font-bold tracking-[-0.025em] md:text-[40px]">How it works</h2>
        <ol className="relative grid gap-10 md:grid-cols-3 md:gap-8">
          {/* the route between the steps, drawn like a pencil rule */}
          <span aria-hidden="true" className="absolute left-[22px] top-[22px] hidden h-px w-[calc(100%-44px)] bg-[repeating-linear-gradient(90deg,var(--field)_0_6px,transparent_6px_12px)] md:block" />
          {HOW_IT_WORKS.map((item, i) => (
            <li key={item.title} className="relative flex flex-col gap-3">
              <span aria-hidden="true"
                className="tabular flex size-11 items-center justify-center rounded-full border-2 border-pencil bg-bg font-display text-lg font-bold text-pencil">
                {i + 1}
              </span>
              <span className="mt-2 text-xl font-semibold tracking-[-0.01em]">{item.title}</span>
              <span className="max-w-[38ch] text-[15px] leading-relaxed text-muted">{item.text}</span>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
