import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import type { UploadValues } from "./components/UploadForm";
import { type AppConfig, analyze, friendlyError, getConfig, parseResume, resetSession } from "./lib/api";
import { beginStep, cancelSteps, isAbort } from "./lib/inflight";
import { type Intent, resolveModel, useApp } from "./lib/store";
import { useTheme } from "./lib/useTheme";
import { Details } from "./pages/Details";
import { Landing } from "./pages/Landing";
import { Report } from "./pages/Report";
import { Review } from "./pages/Review";
import { Results } from "./pages/Results";

export function App() {
  const { step, settings, run, updateRun, advance, restart } = useApp();
  // undefined while loading, null if the server can't be reached
  const [config, setConfig] = useState<AppConfig | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState(0);
  useTheme(settings.theme);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  const model = resolveModel(settings.model, config?.models);

  /** Run one step; a result that arrives after the user left is dropped. */
  const run_ = async (task: (isCurrent: () => boolean) => Promise<void>) => {
    const step = beginStep();
    setBusy(true);
    setError(null);
    try {
      await task(step.isCurrent);
    } catch (e) {
      if (isAbort(e) || !step.isCurrent()) return;
      setError(friendlyError(e));
      setErrorKey((n) => n + 1);
    } finally {
      if (step.isCurrent()) setBusy(false);
      step.end();
    }
  };

  /** A new upload is a new run: earlier results and steps are gone at once,
   *  even if this one fails (the server has already reset its side). */
  const freshRun = (intent: Intent, file: File, jdText: string, template = run.template, notes = run.notes) => {
    updateRun({ intent, file, notes, jdText, template, report: null, details: null, parseIssues: [], parseNotes: [], unplaced: [],
      toVerify: [], drafted: null, review: null, results: null });
    useApp.setState({ reached: 0 });
  };

  const readResume = async (file: File, jdText: string, isCurrent: () => boolean) => {
    const parsed = await parseResume(file, jdText, model, useApp.getState().run.notes);
    if (!isCurrent()) return;
    updateRun({ details: parsed.details, parseIssues: parsed.parse_issues, parseNotes: parsed.parse_notes ?? [],
      unplaced: parsed.unplaced ?? [], toVerify: parsed.to_verify ?? [] });
    advance("details");
  };

  const onStart = (intent: Intent, values: UploadValues) =>
    run_(async (isCurrent) => {
      freshRun(intent, values.file, values.jdText, values.template, values.notes ?? null);
      if (intent === "check") {
        const report = await analyze(values.file, values.jdText, model);
        if (!isCurrent()) return;
        updateRun({ report });
        advance("report");
      } else {
        await readResume(values.file, values.jdText, isCurrent);
      }
    });

  const startOver = () => {
    cancelSteps();
    resetSession().catch(() => undefined); // the server forgets this visitor's files (after a running step ends)
    restart();
    setBusy(false);
    setError(null);
  };

  let page;
  switch (step) {
    case "details":
      page = run.details ? <Details /> : null;
      break;
    case "review":
      page = run.drafted ? <Review /> : null;
      break;
    case "results":
      page = run.results ? <Results /> : null;
      break;
    case "report":
      page = run.report ? (
        <Report report={run.report} busy={busy} error={error} onStartOver={startOver}
          onTailor={() => run_(async (isCurrent) => {
            const report = run.report;
            freshRun("tailor", run.file!, run.jdText);
            updateRun({ report }); // stays visible until the details arrive
            await readResume(run.file!, run.jdText, isCurrent);
          })} />
      ) : null;
      break;
    default:
      page = null;
  }
  // A step whose data is gone (e.g. after a reload) falls back to the start.
  page ??= <Landing onStart={onStart} busy={busy} run={run} maxUploadMb={config?.max_upload_mb} error={error}
    errorKey={errorKey} config={config} />;

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-screen flex-col bg-bg text-ink">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-pencil focus:px-4 focus:py-2 focus:text-on-pencil">
          Skip to content
        </a>
        <Header config={config} />
        <main id="main" className="flex-1">
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25, ease: "easeOut" }}>
              {page}
            </motion.div>
          </AnimatePresence>
        </main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-[1240px] flex-col justify-between gap-2 px-4 py-6 text-xs text-muted sm:flex-row md:px-8">
            <span>Every rewrite comes from your own resume.</span>
            {step !== "upload" ? (
              <button type="button" onClick={startOver} className="min-h-11 w-fit text-left text-muted hover:text-ink sm:min-h-0">
                Start over
              </button>
            ) : (
              <span>Tailores · Resume Studio</span>
            )}
          </div>
        </footer>
      </div>
    </MotionConfig>
  );
}
