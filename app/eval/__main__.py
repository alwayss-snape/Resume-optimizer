"""python -m app.eval run [--live] [--tailor] [--case NAME] [--compare BASELINE] [--save PATH]

Examples:
    python -m app.eval run                                   # offline, committed + private cases
    python -m app.eval run --compare data/eval/baseline.json # show changes vs the committed baseline
    python -m app.eval run --live --tailor --case real-fox \\
        --compare data/eval/private/baseline.json            # full live run of the private case
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.eval.harness import compare, load_cases, run, summary_lines  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.eval")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run evaluation cases")
    r.add_argument("--live", action="store_true", help="call the configured LLM (Groq free tier)")
    r.add_argument("--tailor", action="store_true", help="also draft rewrites and render the output")
    r.add_argument("--case", action="append", help="only these case names (repeatable)")
    r.add_argument("--no-private", action="store_true", help="skip data/eval/private cases")
    r.add_argument("--compare", help="baseline JSON to compare against")
    r.add_argument("--save", help="write the report JSON here (e.g. to record a new baseline)")
    r.add_argument("--out-dir", help="where tailored outputs go (default: a temp dir)")
    r.add_argument("--check", action="store_true",
                   help="exit 1 if any case misses its expected.json (for CI / the stage gate)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    cases = load_cases(include_private=not args.no_private)
    if args.case:
        cases = [c for c in cases if c.name in args.case]
    if not cases:
        print("No cases to run.")
        return 1

    report = run(cases, live=args.live, tailor=args.tailor, out_dir=args.out_dir)
    print("\n".join(summary_lines(report)))
    misses = {name: m["expected"]["failed"] for name, m in report["cases"].items()
              if m.get("expected") and m["expected"]["failed"]}
    for name, failed in misses.items():
        print(f"\n{name} misses its expected.json:")
        print("\n".join(f"  - {f}" for f in failed))
    if args.compare:
        if os.path.exists(args.compare):
            with open(args.compare, encoding="utf-8") as f:
                print("\nCompared with " + args.compare + ":")
                print("\n".join(compare(report, json.load(f))))
        else:
            print(f"\n(no baseline at {args.compare})")
    if args.save:
        # Private case results never go into a committed file.
        if not args.save.startswith("data/eval/private"):
            report = {**report, "cases": {k: v for k, v in report["cases"].items() if not v.get("private")}}
        os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {args.save}")
    if any("error" in m for m in report["cases"].values()):
        return 1
    return 1 if (args.check and misses) else 0


if __name__ == "__main__":
    sys.exit(main())
