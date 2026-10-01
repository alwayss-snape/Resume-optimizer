import { type MotionValue, motion, useReducedMotion, useSpring, useTransform } from "motion/react";
import { type ReactNode, useEffect, useRef, useState } from "react";

// The demo's script: how long each phase holds (ms). Marks for phase k show once phase >= k.
const STEPS = [900, 800, 800, 900, 1300, 800, 800, 900, 3200];
const FINAL = STEPS.length - 1;

const DESCRIPTION =
  "Example, not your resume: a job description and a resume side by side. On the resume, 'Was responsible for building' " +
  "is struck and 'Built' written above it, 'Worked with the marketing team on' becomes 'Partnered with marketing on', " +
  "and the job's keywords SQL, Tableau and A/B tests are highlighted on both sheets. Python is in the job but not on " +
  "the resume, so it is left open.";

/** Runs the mark-up loop while the sheets are on screen; holds the finished proof under reduced motion. */
function usePhase(still: boolean, target: React.RefObject<HTMLElement | null>) {
  const [phase, setPhase] = useState(still ? FINAL : 0);
  const [onScreen, setOnScreen] = useState(true);
  const [tabShown, setTabShown] = useState(true);
  const visible = onScreen && tabShown;

  useEffect(() => {
    const el = target.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([e]) => setOnScreen(e.isIntersecting));
    io.observe(el);
    const onHide = () => setTabShown(!document.hidden);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [target]);

  useEffect(() => {
    if (still) {
      setPhase(FINAL);
      return;
    }
    if (!visible) return;
    const id = window.setTimeout(() => setPhase((p) => (p >= FINAL ? -1 : p + 1)), phase < 0 ? 450 : STEPS[phase]);
    return () => window.clearTimeout(id);
  }, [phase, still, visible]);

  return phase;
}

function Del({ on, children }: { on: boolean; children: ReactNode }) {
  return <span className="pm-del" data-on={on || undefined}>{children}</span>;
}

/** An editor's insertion: the new words written above the line, a caret where they go. */
function Ins({ on, word }: { on: boolean; word: string }) {
  return (
    <span className="pm-ins" data-on={on || undefined}>
      <span className="pm-ins-word">{word}</span>
      <svg viewBox="0 0 10 8" className="pm-caret"><path d="M1 7.5 5 1l4 6.5" /></svg>
    </span>
  );
}

function Hl({ on, children }: { on: boolean; children: ReactNode }) {
  return <span className="pm-hl" data-on={on || undefined}>{children}</span>;
}

function Bar({ w }: { w: string }) {
  return <span className="block h-[0.42em] rounded-[1px] bg-[#e4e4df]" style={{ width: w }} />;
}

function Chip({ on, found, children }: { on: boolean; found: boolean; children: ReactNode }) {
  return (
    <span className={`flex items-center gap-[0.35em] rounded-[0.25em] border px-[0.5em] py-[0.15em] transition-colors duration-300 ${
      on ? (found ? "border-[#8fc4a5] text-[#1e7a4c]" : "border-[#85868e] text-[#5f6068]") : "border-[#e2e2dd] text-[#85868e]"}`}>
      <span aria-hidden="true" className={`inline-flex size-[0.9em] items-center justify-center rounded-full ${
        on && found ? "bg-[#1e7a4c] text-white" : "border border-current"}`}>
        {on && found && (
          <svg viewBox="0 0 12 12" className="size-[0.6em]"><path d="M2.5 6.2 5 8.5l4.5-5" fill="none" stroke="currentColor" strokeWidth="1.8" /></svg>
        )}
      </span>
      {children}
    </span>
  );
}

function Note({ on, children, className }: { on: boolean; children: ReactNode; className: string }) {
  return (
    <span className={`pm-note absolute ${className}`} data-on={on || undefined}>
      <span className="block font-serif italic">{children}</span>
    </span>
  );
}

/** The landing's demonstration: a job description and a resume as two sheets on the desk, tilting
 *  toward the pointer, while proof marks draw themselves. Papers stay white in both themes, like real
 *  paper under a lamp. Decorative for assistive tech beyond its one description. */
export function ProofSheet({ tiltX, tiltY }: { tiltX: MotionValue<number>; tiltY: MotionValue<number> }) {
  const reduce = useReducedMotion() ?? false;
  const stage = useRef<HTMLDivElement>(null);
  const phase = usePhase(reduce, stage);
  const at = (k: number) => phase >= k;

  const spring = { stiffness: 70, damping: 18, mass: 0.6 };
  const rotateY = useSpring(useTransform(tiltX, (x) => -16 + (reduce ? 0 : x * 12)), spring);
  const rotateX = useSpring(useTransform(tiltY, (y) => 10 + (reduce ? 0 : y * -9)), spring);

  return (
    <div ref={stage} role="img" aria-label={DESCRIPTION}
      className="relative mx-auto w-[40em] max-w-full text-[clamp(7.5px,2.2vw,13px)] [perspective:1700px] lg:text-[clamp(9px,0.95vw,13.5px)]">
      <motion.div aria-hidden="true" style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
        className={`relative h-[37em] transition-opacity duration-500 ${phase < 0 ? "opacity-60" : "opacity-100"}`}>
        {/* contact shadow on the desk */}
        <div className="absolute inset-x-[8%] bottom-[2%] h-[22%] rounded-[50%] bg-black/25 blur-2xl [transform:translateZ(-90px)] dark:bg-black/60" />

        {/* the job description, underneath */}
        <div className="absolute left-0 top-[1.4em] flex h-[27em] w-[22em] flex-col gap-[0.8em] border border-[#e2e2dd] bg-white p-[1.6em] font-serif text-[#1b1b1f] shadow-[0_2px_6px_rgb(0_0_0/0.08),0_24px_48px_-20px_rgb(0_0_0/0.3)] [transform:translateZ(-70px)_rotateZ(-5deg)]">
          <span className="font-sans text-[0.78em] font-semibold uppercase tracking-[0.08em] text-[#5f6068]">Job description</span>
          <span className="text-[1.35em] font-semibold leading-tight">Data Analyst</span>
          <span className="text-[0.95em] leading-[1.7]">
            You will build dashboards in <Hl on={at(3)}>SQL</Hl> and <Hl on={at(3)}>Tableau</Hl> for the sales team.
          </span>
          <span className="text-[0.95em] leading-[1.7]">
            Design and read <Hl on={at(7)}>A/B tests</Hl> with marketing.
          </span>
          <span className="text-[0.95em] leading-[1.7]">
            {/* in the job, not on the resume: left open, never highlighted as a match */}
            <span className={`decoration-[#5f6068] decoration-dotted decoration-2 underline-offset-[0.25em] ${at(7) ? "underline" : ""}`}>Python</span> is a plus.
          </span>
          <span className="mt-auto flex flex-col gap-[0.5em]"><Bar w="92%" /><Bar w="74%" /><Bar w="83%" /></span>
        </div>

        {/* the resume, on top */}
        <div className="absolute right-0 top-0 flex w-[29em] flex-col gap-[0.75em] border border-[#e2e2dd] bg-white px-[2em] pb-[1.6em] pt-[1.8em] font-serif text-[#1b1b1f] shadow-[0_2px_6px_rgb(0_0_0/0.08),0_30px_60px_-24px_rgb(0_0_0/0.35)] [transform:rotateZ(1.5deg)]">
          <span className="absolute right-[1.2em] top-[1.1em] rounded-[0.25em] border border-[#85868e] px-[0.5em] py-[0.1em] font-sans text-[0.75em] font-semibold text-[#5f6068]">Example</span>
          <span className="text-[1.6em] font-semibold leading-none tracking-[-0.01em]">Alex Morgan</span>
          <span className="font-sans text-[0.82em] text-[#5f6068]">Data Analyst · Lisbon</span>
          <span className="mt-[0.4em] border-b border-[#1b1b1f] pb-[0.2em] font-sans text-[0.78em] font-semibold uppercase tracking-[0.08em]">Experience</span>
          <span className="flex items-baseline justify-between gap-[1em] text-[0.95em]">
            <span className="font-semibold">Analyst, Northwind Traders</span>
            <span className="font-sans text-[0.85em] text-[#5f6068]">2021 – now</span>
          </span>
          <ul className="flex flex-col gap-[0.15em] text-[0.95em] leading-[2.1]">
            <li className="relative pl-[1em] before:absolute before:left-0 before:content-['•']">
              <Ins on={at(2)} word="Built" /><Del on={at(1)}>Was responsible for building</Del> weekly sales dashboards
              in <Hl on={at(3)}>SQL</Hl> and <Hl on={at(3)}>Tableau</Hl>.
            </li>
            <li className="relative pl-[1em] before:absolute before:left-0 before:content-['•']">
              <Ins on={at(6)} word="Partnered with marketing on" /><Del on={at(5)}>Worked with the marketing team on</Del>{" "}
              <Hl on={at(7)}>A/B tests</Hl> of the checkout page.
            </li>
            <li className="relative pl-[1em] before:absolute before:left-0 before:content-['•']">
              Cleaned and documented the regional sales data.
            </li>
          </ul>
          <span className="flex flex-col gap-[0.5em] pt-[0.2em]"><Bar w="88%" /><Bar w="70%" /></span>
          <span className="mt-[0.5em] border-b border-[#1b1b1f] pb-[0.2em] font-sans text-[0.78em] font-semibold uppercase tracking-[0.08em]">Education</span>
          <span className="flex flex-col gap-[0.5em]"><Bar w="64%" /><Bar w="46%" /></span>
          <span className="mt-[0.8em] flex flex-wrap items-center gap-[0.45em] border-t border-dashed border-[#c9c9c3] pt-[0.8em] font-sans text-[0.78em]">
            <span className="font-semibold text-[#5f6068]">Job keywords</span>
            <Chip on={at(3)} found>SQL</Chip>
            <Chip on={at(3)} found>Tableau</Chip>
            <Chip on={at(7)} found>A/B tests</Chip>
            <Chip on={at(7)} found={false}>Python</Chip>
          </span>

          {/* margin notes, lifted off the page */}
          <Note on={at(4)} className="-right-[6.2em] top-[11.4em] hidden w-[8.2em] rotate-[2deg] sm:block">Stronger verb, same facts.</Note>
          <Note on={at(8)} className="-right-[5.6em] top-[18.4em] hidden w-[7.6em] -rotate-[1.5deg] sm:block">Tighter. Nothing added.</Note>
        </div>
      </motion.div>
    </div>
  );
}
