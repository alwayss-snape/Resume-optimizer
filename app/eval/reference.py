"""Reference eval (P11.10): Tailores against a resume made another way.

A private case folder (never committed, under data/eval/private/) holds:
  resume.(pdf|docx)     the owner's resume
  jd.txt                the job description
  reference.(pdf|docx)  a resume made for the same job another way (e.g. a Claude chat)
  bank.(docx|pdf|md|txt)   optional: the owner's project notes
  answers.json          optional: interview answers, keyed by the need ("Pricing analytics")
                        or by "figure:<project heading>"

The full pipeline runs as the web app would (notes, questions, drafting, every
proposal that passes the fact check accepted, the suggested projects, files),
then the P4.3 judge compares the result with the reference twice, positions
swapped. The reference may hold facts the tool was never given; answers.json
is how the owner gives them, and without it a loss says "missing facts" as
much as "worse writing".

    python -m app.eval reference data/eval/private/<case>
"""
import json
import os
from typing import Dict, Optional

from app.analysis.interview import InterviewAnswer


def _find(folder: str, stem: str, exts) -> Optional[str]:
    for ext in exts:
        path = os.path.join(folder, stem + ext)
        if os.path.exists(path):
            return path
    return None


def _text(service, path: str) -> str:
    raw = service.read_file(path)
    return "\n".join(b.text for b in raw.blocks) if getattr(raw, "blocks", None) else raw.raw_text


def match_answers(questions, given: Dict[str, str]):
    """answers.json keys -> this run's questions: a need by its name, a
    figure by "figure:<project>" (case-insensitive)."""
    lowered = {k.strip().lower(): v for k, v in (given or {}).items() if (v or "").strip()}
    out = []
    for q in questions:
        key = (f"figure:{q.project}" if q.kind == "figure" else q.competency).strip().lower()
        if key in lowered:
            out.append(InterviewAnswer(id=q.id, answer=lowered[key], experience_id=q.experience_id, project=q.project))
    return out


def run_reference(folder: str, service=None, judge=None, out_dir: Optional[str] = None) -> Dict:
    from app.eval.judge import ResumeJudge
    from app.services.profile_store import MemoryProfileStore
    from app.services.tailor import TailorService
    service = service or TailorService(keep_run=False)
    service.profile_store = MemoryProfileStore()  # a reference run never touches saved answers
    resume = _find(folder, "resume", (".pdf", ".docx", ".txt"))
    reference = _find(folder, "reference", (".pdf", ".docx", ".txt"))
    bank = _find(folder, "bank", (".docx", ".pdf", ".md", ".txt"))
    jd_path = os.path.join(folder, "jd.txt")
    if not (resume and reference and os.path.exists(jd_path)):
        raise FileNotFoundError(f"{folder} needs resume.*, reference.* and jd.txt")
    with open(jd_path, encoding="utf-8") as f:
        jd = f.read()
    given = {}
    if os.path.exists(os.path.join(folder, "answers.json")):
        with open(os.path.join(folder, "answers.json"), encoding="utf-8") as f:
            given = json.load(f)

    parsed = service.parse_resume(resume)
    notes = []
    if bank:
        parsed, notes, _ = service.apply_bank(parsed, bank_path=bank)
    prepared = service.prepare(parsed, jd)
    answers = match_answers(prepared["questions"], given)
    drafted_from, brief, _ = service.apply_answers(parsed, prepared["role_brief"], prepared["questions"], answers,
                                                   remember=False)
    generated = service.generate_proposals(resume, jd, parsed=drafted_from, job_desc=prepared["job_description"],
                                           brief=brief)
    # As an owner who accepts everything the fact check passes (the tailored summary too).
    accepted = [p.model_dump() for p in generated["proposals"] if p.validation != "REJECT"]
    out_dir = out_dir or os.path.join(folder, "out")
    os.makedirs(out_dir, exist_ok=True)
    result = service.tailor_resume(resume, jd, out_dir, parsed=drafted_from, preapproved_proposals=accepted,
                                   job_desc=prepared["job_description"], role_brief=brief, remember_answers=False,
                                   brief_edits={"title": brief.headline, "positioning": brief.positioning})
    tailored_path = result.get("pdf") or result["docx"]
    tailored, ref = _text(service, tailored_path), _text(service, reference)
    judge = judge or ResumeJudge()
    first = judge.prefer(jd, ref, tailored)     # Tailores is B
    second = judge.prefer(jd, tailored, ref)    # Tailores is A
    wins, losses = (first == "B") + (second == "A"), (first == "A") + (second == "B")
    report = {
        "tailores_wins": wins, "reference_wins": losses,
        "verdict": "tailores" if wins == 2 else "reference" if losses == 2 else "tie",
        "questions": [q.question for q in prepared["questions"]], "answered": len(answers),
        "notes": notes, "tailored": tailored_path, "keyword_match": result.get("alignment_score"),
        "projects_kept": [c.name for c in generated.get("projects") or [] if c.chosen],
        # Proposals the fact check threw out (never in the output): how often the AI overreached.
        "rejected_by_fact_check": [p.validation_note for p in generated["proposals"] if p.validation == "REJECT"],
        "llm_usage": generated.get("llm_usage"),
    }
    with open(os.path.join(out_dir, "reference_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return report
