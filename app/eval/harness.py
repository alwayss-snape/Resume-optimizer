"""Run evaluation cases through the pipeline and collect metrics (P4.1).

A case is a resume + JD (+ optional golden parse). Committed cases live in
data/eval/cases.json and use anonymized fixtures; private cases (the user's
real resume) live in data/eval/private/cases.json, which is gitignored.

Offline mode (default) uses no LLM, so its numbers are reproducible and
cheap: parsing, heuristic JD analysis, matching and scoring. --live uses the
configured provider (Groq free tier) and adds rewrite / suggestion metrics
and LLM cost when --tailor is given.
"""
import json
import logging
import os
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.analysis.jd_analyzer import JDAnalyzer
from app.eval.golden import golden_mismatches, project_resume

logger = logging.getLogger(__name__)

COMMITTED_MANIFEST = "data/eval/cases.json"
PRIVATE_MANIFEST = "data/eval/private/cases.json"


@dataclass
class Case:
    name: str
    resume: str
    jd: str
    golden: Optional[str] = None
    private: bool = False


class OfflineLLM:
    """Stands in for LLMClient when no model should be called: every
    component sees "unavailable" and takes its deterministic path."""
    provider = "offline"
    model = None
    last_error = "offline evaluation (no LLM)"

    def is_available(self, refresh: bool = False) -> bool:
        return False

    def get_usage_summary(self) -> Dict:
        return {"provider": "offline", "model": None, "call_count": 0, "success_count": 0,
                "failure_count": 0, "total_prompt_tokens": 0, "total_completion_tokens": 0,
                "total_tokens": 0, "total_duration_seconds": 0.0}


class _RetryCounter(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record):
        if "429" in record.getMessage():
            self.count += 1


def load_cases(include_private: bool = True) -> List[Case]:
    cases: List[Case] = []
    manifests = [(COMMITTED_MANIFEST, False)]
    if include_private:
        manifests.append((PRIVATE_MANIFEST, True))
    for path, private in manifests:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                case = Case(private=private, **item)
                if os.path.exists(case.resume) and os.path.exists(case.jd):
                    cases.append(case)
                else:
                    logger.warning("Skipping case %s: input file missing", case.name)
    return cases


def keyword_coverage(keywords: List[str], resume_text: str) -> Dict:
    """Share of the JD's keywords found verbatim (whole term, any case) in
    the resume text. A plain measure that doesn't depend on the matcher."""
    found = [k for k in keywords if JDAnalyzer.count_occurrences(k, resume_text) > 0]
    missing = [k for k in keywords if k not in found]
    pct = round(100.0 * len(found) / len(keywords), 1) if keywords else None
    return {"pct": pct, "found": len(found), "total": len(keywords), "missing": missing}


def run_case(case: Case, *, live: bool = False, tailor: bool = False, out_dir: Optional[str] = None) -> Dict:
    from app.llm.client import LLMClient
    from app.services.tailor import TailorService

    llm = LLMClient() if live else OfflineLLM()
    service = TailorService(llm_client=llm)
    counter = _RetryCounter()
    logging.getLogger("app.llm.client").addHandler(counter)
    started = time.time()
    try:
        with open(case.jd, encoding="utf-8") as f:
            jd_text = f.read()
        parsed = service.parse_resume(case.resume)
        raw_doc, resume_doc, evidence = parsed
        resume = resume_doc.resume
        metrics: Dict = {"private": case.private}

        parse = {
            "issues": list(service.last_parse_issues),
            "experience": len(resume.experience),
            "roles": sum(len(e.all_roles()) for e in resume.experience),
            "bullets": sum(len(e.bullets) for e in resume.experience) + sum(len(p.bullets) for p in resume.projects),
            "skills": sum(len(v) for v in resume.skills.values()),
        }
        if case.golden and os.path.exists(case.golden):
            with open(case.golden, encoding="utf-8") as f:
                mismatches = golden_mismatches(project_resume(resume), json.load(f))
            parse["golden"] = "match" if not mismatches else "mismatch"
            parse["golden_mismatches"] = mismatches
        metrics["parse"] = parse

        # With --tailor, use the JD analysis generate_proposals makes (as the
        # UI does), so the metrics and the tailored output share one analysis
        # and the run makes exactly the pipeline's LLM calls.
        generated = service.generate_proposals(case.resume, jd_text, parsed=parsed) if tailor else None
        job = generated["job_description"] if generated else service.jd_analyzer.analyze(
            service.safety_guard.sanitize(jd_text))
        metrics["jd"] = {
            "source": job.analysis_source, "title": job.job_title, "company": job.company,
            "seniority": job.seniority, "years": [job.min_years, job.max_years],
            "requirements": len(job.requirements),
            "preferred": sum(r.priority == "preferred" for r in job.requirements),
            "keywords": len(job.keywords),
        }

        matches = service.matcher.match(job, evidence)
        matches = service.semantic_matcher.match(job.requirements, evidence, matches)
        keyword_report = service.keyword_matcher.match(job, resume)
        metrics["match"] = {
            "score": keyword_report.rate,  # headline: keyword match rate (P1.2)
            "evidence_score": round(service.scorer.calculate_score(matches, job.requirements), 1),
            "statuses": dict(Counter(m.status for m in matches)),
            "keywords_matched": len(keyword_report.matched),
            "keywords_missing": [r.keyword for r in keyword_report.missing],
            "keyword_coverage": keyword_coverage(job.keywords, raw_doc.raw_text),
        }

        if tailor:
            metrics["tailor"] = _tailor_metrics(service, case, jd_text, parsed, generated, out_dir)

        usage = llm.get_usage_summary()
        metrics["llm"] = {
            "calls": usage.get("call_count", 0), "failures": usage.get("failure_count", 0),
            "tokens": usage.get("total_tokens", 0),
            "llm_seconds": round(usage.get("total_duration_seconds") or 0.0, 1),
            "retries_429": counter.count,
        }
        metrics["elapsed_s"] = round(time.time() - started, 1)
        return metrics
    finally:
        logging.getLogger("app.llm.client").removeHandler(counter)


def _tailor_metrics(service, case: Case, jd_text: str, parsed, generated: Dict, out_dir: Optional[str]) -> Dict:
    proposals = generated["proposals"]
    approved = [p.model_dump() for p in proposals if getattr(p, "validation", None) != "REJECT"]
    case_dir = os.path.join(out_dir or tempfile.mkdtemp(prefix="eval_"), case.name)
    os.makedirs(case_dir, exist_ok=True)
    result = service.tailor_resume(
        case.resume, jd_text, case_dir, mode="ATS_DEFAULT", preapproved_proposals=approved,
        proposal_usage=generated.get("llm_usage"), parsed=parsed, job_desc=generated.get("job_description"),
    )
    pages = None
    if result.get("pdf") and os.path.exists(result["pdf"]):
        import pymupdf
        with pymupdf.open(result["pdf"]) as pdf:
            pages = pdf.page_count
    return {
        "proposals": len(proposals),
        "changed": sum(1 for p in proposals if (p.proposed_text or "").strip() != (p.original_text or "").strip()),
        "statuses": dict(Counter(getattr(p, "status", None) or "none" for p in proposals)),
        "verdicts": dict(Counter(getattr(p, "validation", None) or "none" for p in proposals)),
        "gap_questions": len(generated["gap_questions"]),
        "score_after": float(result.get("alignment_score") or 0.0),
        "pages": pages,
        "target_pages": result.get("target_pages"),
        # P2.5: problems found re-parsing the rendered DOCX / PDF (0 = passes)
        "ats_round_trip": [w for w in result.get("warnings", []) if w.startswith("ATS round-trip")],
        "output_dir": case_dir,
    }


def run(cases: List[Case], *, live: bool = False, tailor: bool = False, out_dir: Optional[str] = None) -> Dict:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "live" if live else "offline",
        "tailor": tailor,
        "cases": {},
    }
    for case in cases:
        logger.info("Evaluating %s", case.name)
        try:
            report["cases"][case.name] = run_case(case, live=live, tailor=tailor, out_dir=out_dir)
        except Exception as e:  # one broken case shouldn't hide the others
            report["cases"][case.name] = {"private": case.private, "error": f"{type(e).__name__}: {e}"}
    return report


def _flatten(d: Dict, prefix: str = "") -> Dict[str, object]:
    flat: Dict[str, object] = {}
    for key, value in d.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, path + "."))
        else:
            flat[path] = value
    return flat


# Metrics where a lower number is better; everything else numeric is
# reported as a plain delta.
LOWER_IS_BETTER = ("llm.calls", "llm.tokens", "llm.llm_seconds", "llm.retries_429", "llm.failures",
                   "elapsed_s", "tailor.pages", "statuses.MISSING", "verdicts.REJECT", "parse.issues")


def compare(report: Dict, baseline: Dict) -> List[str]:
    """Human-readable differences per case between a report and a baseline."""
    lines: List[str] = []
    for name, metrics in report.get("cases", {}).items():
        base = baseline.get("cases", {}).get(name)
        if base is None:
            lines.append(f"{name}: new case (no baseline)")
            continue
        now_flat, base_flat = _flatten(metrics), _flatten(base)
        changes = []
        for key in sorted(set(now_flat) | set(base_flat)):
            if key.endswith(("output_dir", "missing", "keywords_missing", "golden_mismatches")) or key == "elapsed_s":
                continue
            old, new = base_flat.get(key), now_flat.get(key)
            if old == new:
                continue
            if isinstance(old, (int, float)) and isinstance(new, (int, float)) and not isinstance(old, bool):
                delta = new - old
                better = (delta < 0) if any(key.endswith(k) for k in LOWER_IS_BETTER) else (delta > 0)
                mark = "↑" if delta > 0 else "↓"
                changes.append(f"  {key}: {old} → {new} ({mark}{abs(round(delta, 1))}{'' if better else ' ⚠'})")
            else:
                changes.append(f"  {key}: {old!r} → {new!r}")
        lines.append(f"{name}: " + ("no change" if not changes else f"{len(changes)} change(s)"))
        lines.extend(changes)
    return lines


def summary_lines(report: Dict) -> List[str]:
    lines = [f"Evaluation ({report['mode']}{', tailor' if report.get('tailor') else ''}) at {report['generated_at']}"]
    for name, m in report["cases"].items():
        if "error" in m:
            lines.append(f"- {name}: ERROR {m['error']}")
            continue
        kc = m["match"]["keyword_coverage"]
        parts = [
            f"parse={m['parse'].get('golden', 'n/a')}",
            f"jd={m['jd']['requirements']} req/{m['jd']['preferred']} pref ({m['jd']['source']})",
            f"score={m['match']['score']}",
            f"keywords={kc['found']}/{kc['total']}",
        ]
        if "tailor" in m:
            t = m["tailor"]
            parts += [f"rewrites={t['changed']}/{t['proposals']}", f"pages={t['pages']}"]
        parts.append(f"llm={m['llm']['calls']} calls/{m['llm']['tokens']} tok/{m['llm']['retries_429']}×429")
        lines.append(f"- {name}: " + ", ".join(parts))
    return lines
