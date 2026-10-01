"""What the review form sends, turned into what TailorService takes (P5.1).

Moved out of the Streamlit page so the web API and Streamlit share one
tested copy: which proposals are applied (with the user's edits), which gap
answers count, where an addition goes, and the "add a job" form's checks.
Plain functions, no web framework imports.
"""
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from app.config.settings import settings

PROVIDER_LABELS = {"anthropic": "Claude (Anthropic API)", "groq": "Groq (cloud)", "ollama": "Ollama (local)"}
PROVIDER_FIX_HINTS = {
    "anthropic": "Check ANTHROPIC_API_KEY in your .env (a pay-as-you-go key from console.anthropic.com).",
    "groq": "Check GROQ_API_KEY and GROQ_MODEL in your .env.",
    "ollama": "Start Ollama (`ollama serve`) and pull the model (`ollama pull <model>`).",
}


def current_provider() -> str:
    return (settings.llm_provider or "ollama").strip().lower()


def model_options(provider: str) -> List[str]:
    """Models offered for the configured provider. The configured default
    always comes first; a model name from one provider must never be sent
    to another (an Ollama tag sent to Groq made every rewrite fail silently)."""
    if provider == "anthropic":
        options = [settings.anthropic_model, "claude-opus-5-5", "claude-sonnet-5-5"]
    elif provider == "groq":
        options = [settings.groq_model, "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    else:
        options = [settings.llm_model, "qwen3:4b", "qwen3:8b", "qwen3.5:4b"]
    return list(dict.fromkeys(o for o in options if o))


def proposal_text(p) -> str:
    return getattr(p, "proposed_text", None) or getattr(p, "rewritten_text", None) or ""


def preapproved(selected: Iterable, edits: Optional[Dict[str, str]] = None) -> List[Dict]:
    """The ticked proposals as dicts, carrying the user's edits. `edits`
    maps a proposal id to the text in its edit box; a missing or empty edit
    keeps the proposed text."""
    edits = edits or {}
    out = []
    for p in selected:
        original_proposed = proposal_text(p)
        edited_text = edits.get(getattr(p, "id", None)) or original_proposed
        base = p.model_dump() if hasattr(p, "model_dump") else dict(p)
        base["user_edited"] = edited_text.strip() != original_proposed.strip()
        base["proposed_text"] = edited_text
        base.pop("rewritten_text", None)  # model_dump mirrors it; the edit must win
        out.append(base)
    return out


def resolve_target(target: Optional[str], experience_ids: Iterable[str]) -> str:
    """"auto", "new_project" or a known experience id; anything else is
    treated as "auto" so a stale or forged id can't reach the service."""
    if target in ("auto", "new_project") or target in set(experience_ids):
        return target
    return "auto"


def answer_counts(question, ticked: List[str], answer: Optional[str]) -> bool:
    """Unticking every keyword also withdraws a pre-filled answer the user
    didn't change: nothing is added without their confirmation."""
    answer = (answer or "").strip()
    return bool(ticked) or bool(answer and answer != (question.saved_answer or "").strip())


def gap_answers(questions: List, inputs: Dict[str, Dict], experience_ids: Iterable[str]) -> List[Dict]:
    """The answers that count. `inputs` maps a question id to {"ticked":
    [...], "answer": str, "target": str}; ticked keywords the question
    didn't ask about are ignored."""
    experience_ids = list(experience_ids)
    out = []
    for q in questions:
        given = inputs.get(q.id) or {}
        ticked = [k for k in given.get("ticked") or [] if k in q.keywords]
        answer = given.get("answer") or ""
        if answer_counts(q, ticked, answer):
            out.append({"question_id": q.id, "confirmed_keywords": ticked, "answer": answer,
                        "target": resolve_target(given.get("target"), experience_ids)})
    return out


def new_role(company: Optional[str] = None, title: Optional[str] = None, location: Optional[str] = None,
             current: bool = False, start: Optional[date] = None, end: Optional[date] = None,
             description: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
    """The "add a job" form (P3.3) -> (role dict for tailor_resume, error).
    All fields empty: (None, None), nothing to add. Company, title, start,
    end (or current) and a description are required once any is given."""
    if not (any((v or "").strip() for v in (company, title, description, location)) or start or end or current):
        return None, None
    missing = [label for label, ok in (
        ("company", (company or "").strip()), ("job title", (title or "").strip()),
        ("start date", start), ("end date (or tick \"I currently work here\")", end or current),
        ("what you did there", (description or "").strip())) if not ok]
    if missing:
        return None, "To add the job, fill in: " + ", ".join(missing) + ". Or clear the job fields."
    if end and not current and end < start:
        return None, "The new job's end date is before its start date."
    return {"company": company, "title": title, "location": location or "", "current": current,
            "description": description, "start_date": start.strftime("%b %Y") if start else "",
            "end_date": end.strftime("%b %Y") if (end and not current) else ""}, None
