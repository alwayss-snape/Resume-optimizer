import argparse
import os
import sys

# Ensure project root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.tailor import TailorService


def check_llm(provider=None, model=None) -> int:
    """One live, structured call to the configured provider. Returns an exit
    code: 0 if the model answered with valid structured output, else 1."""
    import time

    from app.llm.client import LLMClient
    from app.llm.schemas import BulletRewriteResult

    client = LLMClient(provider=provider, model=model)
    print(f"Provider: {client.provider}")
    print(f"Model:    {client.model}")
    if not client.is_available():
        print(f"FAILED: not available: {client.last_error}")
        return 1
    start = time.time()
    try:
        result = client.generate_json(
            messages=[
                {"role": "system", "content": "You rewrite resume bullets. Keep every fact; add nothing."},
                {"role": "user", "content": "Rewrite with a stronger verb: 'Did data pipelines in Python for 2M events a day.'"},
            ],
            schema_model=BulletRewriteResult,
            effort="low",
        )
    except Exception as e:
        print(f"FAILED: call error: {e}")
        return 1
    usage = client.get_usage_summary()
    print(f"OK in {time.time() - start:.1f}s: {usage['total_prompt_tokens']} prompt + "
          f"{usage['total_completion_tokens']} completion tokens")
    print(f"Sample output: {result.rewritten}")
    return 0

PROPOSALS_HELP = """Edit this file, then run:
  python -m app.cli tailor --resume <resume> --jd <jd> --proposals <this file>
- proposals: set "apply" to false to reject one; edit "proposed_text" to change it
  (your own edits are kept as written, not fact-checked). "draft_text" is the
  tool's original draft, for reference only.
- gap_questions: list in "confirmed_keywords" only what you have really used;
  "answer" (your own words) becomes a bullet; "target" is "auto", "new_project"
  or a job id from "jobs".
- addition: optional free text and where it goes (same targets).
- new_role: optional job that isn't on the resume (company, title, start_date,
  end_date or current: true, location, description)."""


def write_proposals(service: TailorService, resume_path: str, jd_text: str, out_path: str, progress=None) -> dict:
    """Draft proposals and gap questions into an editable JSON file (P3.6),
    the CLI's version of the UI review step."""
    import json

    generated = service.generate_proposals(resume_path, jd_text, progress=progress)
    data = {
        "_help": PROPOSALS_HELP,
        "keyword_match_rate": generated["alignment_score"],
        "jobs": [{"id": o["id"], "label": o["label"]} for o in generated["experience_options"]],
        "proposals": [
            {**p.model_dump(mode="json"), "apply": getattr(p, "validation", None) != "REJECT",
             "draft_text": p.proposed_text or ""}
            for p in generated["proposals"]
        ],
        "gap_questions": [
            {"question_id": q.id, "requirement": q.requirement, "priority": q.priority, "keywords": q.keywords,
             "confirmed_keywords": list(q.saved_keywords), "answer": q.saved_answer, "target": "auto"}
            for q in generated["gap_questions"]
        ],
        "addition": {"text": "", "target": "auto"},
        "new_role": None,
        # Reused by `tailor`, so the JD isn't analysed (and paid for) twice.
        "job_description": generated["job_description"].model_dump(mode="json"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def read_proposals(path: str) -> dict:
    """The edited proposals file -> tailor_resume keyword arguments."""
    import json

    from app.domain.job import JobDescription

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    preapproved = []
    for p in data.get("proposals", []):
        if not p.get("apply", True):
            continue
        p = dict(p)
        draft = p.pop("draft_text", p.get("proposed_text") or "")
        p.pop("apply", None)
        p["user_edited"] = (p.get("proposed_text") or "").strip() != (draft or "").strip()
        preapproved.append(p)
    gap_answers = [
        {"question_id": q.get("question_id", ""), "confirmed_keywords": q.get("confirmed_keywords") or [],
         "answer": q.get("answer") or "", "target": q.get("target") or "auto"}
        for q in data.get("gap_questions", []) if q.get("confirmed_keywords") or (q.get("answer") or "").strip()
    ]
    addition = data.get("addition") or {}
    job = data.get("job_description")
    return {
        "preapproved_proposals": preapproved,
        "gap_answers": gap_answers,
        "addition_text": addition.get("text") or None,
        "addition_target": addition.get("target") or "auto",
        "new_role": data.get("new_role") or None,
        "job_desc": JobDescription.model_validate(job) if job else None,
    }


def _print_progress(message: str) -> None:
    print(f"  · {message}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Local Resume Tailor CLI — Privacy-first, evidence-based AI resume tailoring.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check-llm
    check_parser = subparsers.add_parser(
        "check-llm", help="Make one live structured call to the configured LLM and report the result.")
    check_parser.add_argument("--provider", choices=["anthropic", "groq", "ollama"], help="Override LLM_PROVIDER")
    check_parser.add_argument("--model", help="Override the provider's configured model")

    # Subcommand: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze resume alignment against JD without generating files.")
    analyze_parser.add_argument("--resume", required=True, help="Path to input resume (.docx or .pdf)")
    analyze_parser.add_argument("--jd", required=True, help="Path to JD text file")

    # Subcommand: propose (the UI's review step, as an editable file)
    propose_parser = subparsers.add_parser(
        "propose", help="Draft rewrites and gap questions into an editable JSON file for `tailor --proposals`.")
    propose_parser.add_argument("--resume", required=True, help="Path to input resume (.docx or .pdf)")
    propose_parser.add_argument("--jd", required=True, help="Path to JD text file")
    propose_parser.add_argument("--out", default="data/output/proposals.json", help="Where to write the proposals file")

    # Subcommand: tailor
    tailor_parser = subparsers.add_parser("tailor", help="Tailor resume to JD and produce DOCX/PDF output.")
    tailor_parser.add_argument("--resume", required=True, help="Path to input resume (.docx or .pdf)")
    tailor_parser.add_argument("--jd", required=True, help="Path to JD text file")
    tailor_parser.add_argument("--output", default="data/output", help="Output directory path")
    tailor_parser.add_argument("--mode", choices=["PRESERVE", "ATS_DEFAULT"], default="ATS_DEFAULT", help="Rendering mode (PRESERVE patches a DOCX in place)")
    tailor_parser.add_argument("--proposals", help="Reviewed file from `propose`: apply exactly what it says")
    tailor_parser.add_argument("--strict", action="store_true",
                               help="Strict Factual Mode: withhold all rewrites if any fails the fact check")
    tailor_parser.add_argument("--no-remember", action="store_true",
                               help="Don't save confirmed gap answers for future jobs")

    args = parser.parse_args()

    if args.command == "check-llm":
        sys.exit(check_llm(args.provider, args.model))

    if not os.path.exists(args.resume):
        print(f"Error: Resume file not found: {args.resume}")
        sys.exit(1)
    if not os.path.exists(args.jd):
        print(f"Error: JD file not found: {args.jd}")
        sys.exit(1)

    with open(args.jd, "r", encoding="utf-8") as f:
        jd_text = f.read()

    service = TailorService()

    if args.command == "analyze":
        print("Analyzing resume against job description...")
        report = service.analyze_only(args.resume, jd_text)
        print("\n" + "=" * 50)
        print(f"KEYWORD MATCH RATE: {report.alignment_score:.1f}% (aim for 75-85%)")
        print("=" * 50)
        if report.keyword_match:
            missing = [r.keyword for r in report.keyword_match.missing]
            print(f"Keywords found: {len(report.keyword_match.matched)} of {len(report.keyword_match.rows)}")
            if missing:
                print(f"Missing keywords: {', '.join(missing)}")
        print(f"Required Matches: {len(report.required_matches)}")
        print(f"Preferred Matches: {len(report.preferred_matches)}")
        print(f"Missing Requirements: {len(report.missing_requirements)}")
        for m in report.missing_requirements:
            print(f"  - [MISSING] {m.requirement_text}")

    elif args.command == "propose":
        print("Drafting proposals...")
        data = write_proposals(service, args.resume, jd_text, args.out, progress=_print_progress)
        print(f"\nKeyword match rate now: {data['keyword_match_rate']:.1f}%")
        print(f"{len(data['proposals'])} proposal(s), {len(data['gap_questions'])} gap question(s).")
        print(f"Review and edit: {args.out}")
        print(f"Then: python -m app.cli tailor --resume {args.resume} --jd {args.jd} --proposals {args.out}")

    elif args.command == "tailor":
        print(f"Tailoring resume ({args.mode} mode)...")
        extra = read_proposals(args.proposals) if args.proposals else {}
        results = service.tailor_resume(args.resume, jd_text, args.output, mode=args.mode,
                                        strict_factual=args.strict, remember_answers=not args.no_remember,
                                        progress=_print_progress, **extra)
        print("\n" + "=" * 50)
        print("TAILORING COMPLETE")
        print("=" * 50)
        print(f"Keyword match rate: {results['alignment_score']}% (was {results['initial_alignment_score']}%)")
        for warning in results.get("warnings") or []:
            print(f"  ! {warning}")
        print(f"DOCX Output: {results['docx']}")
        if results['pdf']:
            print(f"PDF Output: {results['pdf']}")
        print(f"Change Log: {results['changes_md']}")
        print(f"Run Directory: {results['run_dir']}")

if __name__ == "__main__":
    main()
