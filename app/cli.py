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

    # Subcommand: tailor
    tailor_parser = subparsers.add_parser("tailor", help="Tailor resume to JD and produce DOCX/PDF output.")
    tailor_parser.add_argument("--resume", required=True, help="Path to input resume (.docx or .pdf)")
    tailor_parser.add_argument("--jd", required=True, help="Path to JD text file")
    tailor_parser.add_argument("--output", default="data/output", help="Output directory path")
    tailor_parser.add_argument("--mode", choices=["PRESERVE", "ATS_DEFAULT"], default="PRESERVE", help="Rendering mode")

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
        print(f"ALIGNMENT SCORE: {report.alignment_score:.1f} / 100")
        print("=" * 50)
        print(f"Required Matches: {len(report.required_matches)}")
        print(f"Preferred Matches: {len(report.preferred_matches)}")
        print(f"Missing Requirements: {len(report.missing_requirements)}")
        for m in report.missing_requirements:
            print(f"  - [MISSING] {m.requirement_text}")

    elif args.command == "tailor":
        print(f"Tailoring resume ({args.mode} mode)...")
        results = service.tailor_resume(args.resume, jd_text, args.output, mode=args.mode)
        print("\n" + "=" * 50)
        print("TAILORING COMPLETE")
        print("=" * 50)
        print(f"Alignment Score: {results['alignment_score']} / 100")
        print(f"DOCX Output: {results['docx']}")
        if results['pdf']:
            print(f"PDF Output: {results['pdf']}")
        print(f"Change Log: {results['changes_md']}")
        print(f"Run Directory: {results['run_dir']}")

if __name__ == "__main__":
    main()
