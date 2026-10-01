import { useApp } from "../lib/store";
import { useFocusHeading } from "../lib/useFocusHeading";

/** Placeholder until the results screen lands (P5.5). */
export function Results() {
  const { run } = useApp();
  const heading = useFocusHeading();
  return (
    <section className="mx-auto max-w-[1240px] px-4 py-14 md:px-8">
      <h1 ref={heading} tabIndex={-1} className="font-display text-5xl outline-none">Your resume is ready.</h1>
      <p className="mt-4 text-muted">Keyword match: {run.results?.alignment_score.toFixed(1)}%</p>
    </section>
  );
}
