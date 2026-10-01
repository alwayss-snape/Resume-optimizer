import { useApp } from "../lib/store";
import { useFocusHeading } from "../lib/useFocusHeading";

/** Placeholder until the review screen lands (P5.4). */
export function Review() {
  const { run } = useApp();
  const heading = useFocusHeading();
  return (
    <section className="mx-auto max-w-[1240px] px-4 py-14 md:px-8">
      <h1 ref={heading} tabIndex={-1} className="font-display text-5xl outline-none">Review changes</h1>
      <p className="mt-4 text-muted">{run.drafted?.proposals.length ?? 0} proposals drafted.</p>
    </section>
  );
}
