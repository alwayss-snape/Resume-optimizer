"""HTTP endpoints, one per step of the review flow (P5.1).

Upload -> check details -> draft proposals -> review (live match rate) ->
tailor -> download / preview. Each endpoint is a thin call into
TailorService; the two long steps stream their progress messages as
Server-Sent Events and end with one "result" (or "error") event.
"""
import json
import logging
import os
import queue
import re
import shutil
import tempfile
import threading
import time
from collections import defaultdict, deque
from datetime import date
from typing import Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api import forms
from app.api.sessions import Session, remove_path
from app.rendering.pdf_converter import pdf_page_images
from app.ingestion import errors
from app.ingestion.errors import UnreadableFile
from app.validation.output import OutputQAValidator
from app.services.arrange import Layout
from app.services.arrange import view as arrange_view
from app.rendering.review_view import PROPOSAL_STATES, diff_spans, gap_table, proposal_state, score_breakdown

logger = logging.getLogger(__name__)

SESSION_COOKIE = "rt_session"
ALLOWED_TYPES = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}
# Read after conversion to .docx with LibreOffice (P8.22); a ".doc" that is
# really a .docx (renamed) is read as one.
CONVERTED_TYPES = {".doc": b"\xd0\xcf\x11\xe0", ".odt": b"PK\x03\x04", ".rtf": b"{\\rtf"}
MAX_PASTED_CHARS = 60_000

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class ProposalsIn(BaseModel):
    # The "check details" form: {"candidate": {...}, "experience": [...],
    # "removed_jobs": [...], "added_jobs": [...]}, as
    # TailorService.apply_parse_corrections takes it. None = no changes.
    corrections: Optional[Dict] = None


class SelectionItem(BaseModel):
    id: str
    text: Optional[str] = None  # the edit box; None or empty keeps the proposal


class MatchPreviewIn(BaseModel):
    selection: List[SelectionItem] = Field(default_factory=list)


class GapInput(BaseModel):
    ticked: List[str] = Field(default_factory=list)
    answer: str = ""
    target: str = "auto"


class AdditionIn(BaseModel):
    text: str = ""
    target: str = "auto"


class NewRoleIn(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    current: bool = False
    start: Optional[date] = None
    end: Optional[date] = None
    description: str = ""


class TailorIn(BaseModel):
    selection: List[SelectionItem] = Field(default_factory=list)
    gap_answers: Dict[str, GapInput] = Field(default_factory=dict)
    addition: AdditionIn = Field(default_factory=AdditionIn)
    new_role: Optional[NewRoleIn] = None
    keep_layout: bool = False
    strict_factual: bool = False
    remember_answers: bool = True
    conditions: List[str] = Field(default_factory=list)  # ids of job conditions the user meets (P8.20)


# ---------------------------------------------------------------------------
# Plumbing: sessions, rate limit, uploads, streaming
# ---------------------------------------------------------------------------
class RateLimiter:
    """At most `limit` calls per `window` seconds per key (visitor IP)."""

    def __init__(self, limit: int, window: float = 3600.0):
        self.limit, self.window = limit, window
        self._calls: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            calls = self._calls[key]
            while calls and now - calls[0] > self.window:
                calls.popleft()
            if len(calls) >= self.limit:
                raise HTTPException(429, "Too many requests from this address. Please try again later.")
            calls.append(now)


def rate_limited(request: Request) -> None:
    request.app.state.rate_limiter.check(request.client.host if request.client else "unknown")


def current_session(request: Request) -> Session:
    session = request.app.state.sessions.get(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise HTTPException(404, "Your session has expired. Please upload your resume again.")
    return session


def _require(session: Session, *keys: str) -> None:
    if any(session.data.get(k) is None for k in keys):
        raise HTTPException(409, "That step isn't available yet. Please start from the upload step.")


def _claim(session: Session) -> None:
    if not session.busy.acquire(blocking=False):
        raise HTTPException(409, "Still working on your previous request.")


async def _save_upload(request: Request, file: Optional[UploadFile], resume_text: Optional[str] = None) -> str:
    """The upload (or pasted text) as a temp file, after checking its type
    and size. .doc / .odt / .rtf are converted to .docx (P8.22)."""
    if file is None or not (file.filename or "").strip():
        text = (resume_text or "").strip()
        if not text:
            raise HTTPException(422, "Please upload your resume or paste it as text.")
        if len(text) > MAX_PASTED_CHARS:
            raise HTTPException(413, "That's too much text for a resume. Paste just the resume.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp:
            tmp.write(text)
            return tmp.name
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in ALLOWED_TYPES and suffix not in CONVERTED_TYPES and suffix != ".txt":
        raise HTTPException(415, "Please upload a .docx, .pdf, .doc, .odt, .rtf or .txt file, or paste your resume.")
    limit = request.app.state.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"The file is larger than {limit // (1024 * 1024)} MB.")
    if not data.strip():
        raise HTTPException(422, errors.EMPTY_FILE)
    if suffix == ".doc" and data.startswith(ALLOWED_TYPES[".docx"]):
        suffix = ".docx"  # a .docx renamed to .doc
    elif suffix == ".doc" and data.startswith(CONVERTED_TYPES[".rtf"]):
        suffix = ".rtf"  # Word's "save as .doc" can write RTF
    if suffix == ".txt":
        if (b"\x00" in data[:4096] and not data.startswith((b"\xff\xfe", b"\xfe\xff"))) or _mostly_binary(data):
            raise HTTPException(415, "That file doesn't look like plain text.")
    elif suffix == ".rtf" and _mostly_binary(data):
        raise HTTPException(422, errors.DAMAGED_FILE)  # RTF is plain text, so LibreOffice would read the garbage
    elif not data.startswith({**ALLOWED_TYPES, **CONVERTED_TYPES}[suffix]):
        raise HTTPException(415, f"That file doesn't look like a real {suffix} file.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        path = tmp.name
    if suffix in CONVERTED_TYPES:
        from app.rendering.pdf_converter import convert_to_docx
        out_dir = tempfile.mkdtemp(prefix="convert_")
        converted = await run_in_threadpool(convert_to_docx, path, out_dir)
        os.remove(path)
        if not converted:
            from app.ingestion.errors import CONVERT_FAILED
            raise HTTPException(422, CONVERT_FAILED)
        final = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
        shutil.move(converted, final)
        shutil.rmtree(out_dir, ignore_errors=True)
        return final
    return path


def _mostly_binary(data: bytes) -> bool:
    """Control characters (other than tabs and line breaks) in more than 2% of
    the first 64 KB: random bytes have ~10%, real text and RTF none (P9.2)."""
    head = data[:65536]
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False  # UTF-16 text
    return sum(b < 32 and b not in (9, 10, 12, 13) for b in head) > 0.02 * max(len(head), 1)


def _check_jd(jd_text: str) -> None:
    if not jd_text.strip():
        raise HTTPException(422, "Please paste the job description.")
    from app.analysis.jd_analyzer import JDAnalyzer
    if JDAnalyzer.too_short(JDAnalyzer.clean_text(jd_text)):
        raise HTTPException(422, "That job description is very short. Paste the whole posting, so the match "
                                 "compares your resume with what the job really asks for.")


def _event(kind: str, payload) -> str:
    return f"event: {kind}\ndata: {json.dumps(jsonable_encoder(payload))}\n\n"


def _stream(session: Session, work: Callable[[Callable[[str], None]], Dict]) -> StreamingResponse:
    """Run `work(progress)` in a thread (the session must already be
    claimed) and stream its progress, then its result, as SSE."""
    events: "queue.Queue" = queue.Queue()

    def run():
        try:
            events.put(("result", work(lambda message: events.put(("progress", {"message": message})))))
        except HTTPException as e:
            events.put(("error", {"message": e.detail}))
        except Exception:
            # Details go to the server log, not to the visitor.
            logger.exception("Streaming step failed")
            events.put(("error", {"message": "Something went wrong on our side. Please try again."}))
        finally:
            if session.reset_pending:
                session.reset_pending = False
                session.reset()
            session.busy.release()
            events.put(None)

    try:
        threading.Thread(target=run, daemon=True).start()
    except BaseException:
        session.busy.release()
        raise

    def body():
        while (item := events.get()) is not None:
            yield _event(*item)

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _service(request: Request, session: Optional[Session] = None, model: Optional[str] = None):
    """A TailorService for one step. With a session, saved gap answers come
    from (and go to) that visitor's own in-memory profile."""
    service = request.app.state.make_service(model)
    if session is not None:
        service.profile_store = session.profile
    return service


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------
_ISSUE_RULES = [
    (r"^no candidate name$", "We couldn't find your name. Type it below."),
    (r"^name looks wrong: '?(.*?)'?$", "Is \u201c{0}\u201d your name? If not, correct it below."),
    (r"^bullets found but no experience or projects$",
     "We found bullet points but couldn't tell which job they belong to. Check the jobs below, or add the job."),
    (r"^experience without a company \((.*)\)$", "We couldn't find the employer for \u201c{0}\u201d. Add it below."),
    (r"^experience without a title \((.*)\)$", "We couldn't find the job title for \u201c{0}\u201d. Add it below."),
    (r"^experience without bullets \((.*)\)$",
     "\u201c{0}\u201d has no bullet points under it. If it isn't a job, remove it."),
    (r"^(\d+) lines outside any known section$",
     "{0} lines didn't fit any section; see \u201cLines we couldn't place\u201d below."),
]


def plain_issue(issue: str) -> str:
    """A parse issue in plain words (P8.26: "experience without a company
    (exp_001)" was developer language)."""
    for pattern, text in _ISSUE_RULES:
        m = re.match(pattern, issue)
        if m:
            return text.format(*m.groups())
    return issue


def unplaced_lines(raw_doc, resume) -> List[Dict]:
    """Lines of the file that ended up in no field the resume shows (P8.26),
    for the user to assign on Check details."""
    from app.validation.coverage import words
    have = words(" ".join(_resume_texts(resume)))
    out = []
    for b in raw_doc.blocks:
        line_words = words(b.text)
        if line_words and len(line_words & have) / len(line_words) < 0.6:
            out.append({"id": b.id, "text": b.text.strip()})
    return out[:30]


def _resume_texts(resume) -> List[str]:
    c = resume.candidate
    out = [c.name, c.headline or "", c.email or "", c.phone or "", c.location or "", *c.links, *c.details,
           resume.summary or ""]
    for e in resume.experience:
        out += [e.company, e.location or "", *(f"{r.title} {r.start_date or ''} {r.end_date or ''}" for r in e.all_roles()),
                *(b.text for b in e.bullets), *(b.group or "" for b in e.bullets), *e.details]
    for p in resume.projects:
        out += [p.name, p.description, *(b.text for b in p.bullets)]
    out += [f"{e.degree} {e.institution} {e.location or ''} {e.dates or ''} {' '.join(e.details)}" for e in resume.education]
    out += [f"{k} {' '.join(v)}" for k, v in resume.skills.items()]
    out += [" ".join(str(x) for x in c.values()) for c in resume.certifications]
    out += [*resume.achievements, *resume.interests]
    out += [f"{s.heading} {' '.join(l.text for l in s.lines)}" for s in resume.other_sections]
    return out


def _details(resume) -> Dict:
    """What the "check details" step shows and edits (P3.5)."""
    cand = resume.candidate
    return {
        "candidate": {"name": cand.name if cand.name != "Candidate" else "", "headline": cand.headline or "",
                      "email": cand.email or "", "phone": cand.phone or "", "location": cand.location or "",
                      "links": list(cand.links)},
        "experience": [{
            "id": exp.id, "company": exp.company, "location": exp.location or "",
            "bullets": len(exp.bullets), "groups": len({b.group for b in exp.bullets if b.group}),
            "roles": [{"title": r.title, "start_date": r.start_date or "", "end_date": r.end_date or ""}
                      for r in (exp.all_roles() or [])],
        } for exp in resume.experience],
        # Everything else read from the file, shown so nothing is hidden (P8.26).
        "also_read": [sec for sec in (
            {"title": "Other header details", "lines": list(cand.details)},
            {"title": "Summary", "lines": [resume.summary] if resume.summary else []},
            {"title": "Education", "lines": [" · ".join(v for v in (e.degree, e.institution, e.dates or "") if v)
                                              + "".join(f" ({d})" for d in e.details) for e in resume.education]},
            {"title": "Skills", "lines": [f"{k}: {', '.join(v)}" for k, v in resume.skills.items()]},
            {"title": "Projects", "lines": [f"{p.name} ({len(p.bullets)} bullet{'s' if len(p.bullets) != 1 else ''})"
                                             for p in resume.projects]},
            {"title": "Certifications and licences", "lines": [c.get("name", "") for c in resume.certifications]},
            {"title": "Achievements", "lines": list(resume.achievements)},
            {"title": "Interests", "lines": list(resume.interests)},
            *({"title": s.heading, "lines": [l.text for l in s.lines]} for s in resume.other_sections),
        ) if sec["lines"]],
    }


def _sections(resume) -> Dict[str, Dict]:
    """Bullet id -> the job or project it belongs to, for grouping cards."""
    out = {}
    for kind, items in (("experience", resume.experience), ("project", resume.projects)):
        for item in items:
            name = getattr(item, "company", None) or getattr(item, "name", None) or getattr(item, "title", None)
            label = " — ".join(v for v in (name, getattr(item, "title", None) if kind == "experience" else None) if v)
            for b in item.bullets:
                out[b.id] = {"id": item.id, "kind": kind, "label": label or item.id}
    return out


def _proposal_out(p, keywords: List[str], sections: Dict[str, Dict]) -> Dict:
    original, proposed = p.original_text or "", forms.proposal_text(p)
    state = proposal_state(p.status, p.validation, proposed.strip() != original.strip())
    _, label, meaning = PROPOSAL_STATES[state]
    left, right = diff_spans(original, proposed, keywords)
    note = p.error if state == "failed" else (p.validation_note if state in ("dropped", "check") else None)
    return {"id": p.id, "kind": p.kind, "section": sections.get(p.target_semantic_id),
            "original": original, "proposed": proposed, "rationale": p.rationale,
            "state": state, "state_label": label, "state_meaning": meaning, "note": note,
            "opt_in": bool(getattr(p, "opt_in", False)),
            "diff": {"original": left, "proposed": right}}


def _match_out(report) -> Optional[Dict]:
    if report is None:
        return None
    return {**report.model_dump(), "rate": report.rate, "breakdown": score_breakdown(report)}


def _selected(session: Session, selection: List[SelectionItem]) -> List[Dict]:
    by_id = {p.id: p for p in session.data["proposals"]}
    chosen = [by_id[s.id] for s in selection if s.id in by_id]
    return forms.preapproved(chosen, {s.id: s.text for s in selection if s.text})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/health")
def health() -> Dict:
    return {"ok": True}


@router.get("/config")
def config(request: Request) -> Dict:
    provider = forms.current_provider()
    return {"provider": provider, "provider_label": forms.PROVIDER_LABELS.get(provider, provider),
            "models": forms.model_options(provider),
            "max_upload_mb": request.app.state.max_upload_bytes / (1024 * 1024),
            # For the privacy note (P8.24): where resume text goes, how long files live.
            "cloud": provider != "ollama",
            "session_minutes": request.app.state.sessions.ttl_seconds // 60}


def _model(model: Optional[str]) -> Optional[str]:
    if model and model not in forms.model_options(forms.current_provider()):
        raise HTTPException(422, "Unknown model for this provider.")
    return model or None


@router.post("/analyze", dependencies=[Depends(rate_limited)])
async def analyze(request: Request, file: Optional[UploadFile] = File(None), jd_text: str = Form(...),
                  model: Optional[str] = Form(None), resume_text: Optional[str] = Form(None)) -> Dict:
    """"Just check my match": score only, nothing kept."""
    _check_jd(jd_text)
    model = _model(model)
    path = await _save_upload(request, file, resume_text)
    service = _service(request, model=model)
    try:
        report = await run_in_threadpool(service.analyze_only, path, jd_text)
    except UnreadableFile as e:
        raise HTTPException(422, str(e))
    finally:
        os.remove(path)
    used = bool(report.keyword_match and not report.keyword_match.approximate)
    # Whether the AI read the JD, and why not (P8.23): the score is then approximate.
    ai = {"used": used, "reason": None if used else getattr(service.llm_client, "last_error", None)}
    return {**report.model_dump(), "keyword_match": _match_out(report.keyword_match), "ai": ai}


@router.post("/parse", dependencies=[Depends(rate_limited)])
async def parse(request: Request, response: Response, file: Optional[UploadFile] = File(None),
                jd_text: str = Form(...), model: Optional[str] = Form(None),
                resume_text: Optional[str] = Form(None)) -> Dict:
    """Step 1: read the resume and start a fresh session for this run."""
    _check_jd(jd_text)
    model = _model(model)
    path = await _save_upload(request, file, resume_text)
    store = request.app.state.sessions
    session = store.get(request.cookies.get(SESSION_COOKIE))
    is_new = session is None
    session = session or store.create()
    try:
        _claim(session)
    except HTTPException:
        os.remove(path)
        raise
    try:
        session.reset({"resume_path": path})
        service = _service(request, session, model)
        parsed = await run_in_threadpool(service.parse_resume, path)
        issues = list(service.last_parse_issues)
        from app.analysis.language import english_only_note, other_language
        jd_language = other_language(jd_text)
        if jd_language:  # P8.25
            issues.append(english_only_note("job description", jd_language))
        session.data.update(parsed=parsed, jd_text=jd_text, model=model, parse_issues=issues)
    except BaseException as e:
        session.busy.release()
        if is_new:  # no cookie was sent, so nobody could reach it again
            store.drop(session)
        if isinstance(e, UnreadableFile):
            raise HTTPException(422, str(e))
        raise
    session.busy.release()
    response.set_cookie(SESSION_COOKIE, session.id, httponly=True, samesite="lax",
                        max_age=store.ttl_seconds)
    return {"details": _details(parsed[1].resume), "parse_issues": [plain_issue(i) for i in session.data["parse_issues"]],
            "unplaced": unplaced_lines(parsed[0], parsed[1].resume)}


@router.post("/proposals", dependencies=[Depends(rate_limited)])
def proposals(request: Request, body: ProposalsIn, session: Session = Depends(current_session)):
    """Step 2: apply the user's fixes, then draft rewrites and gap
    questions. Streams progress."""
    _require(session, "parsed")
    service = _service(request, session, session.data.get("model"))
    _claim(session)

    def work(progress):
        parsed, changed = session.data["parsed"], False
        if body.corrections:
            try:
                parsed, changed = service.apply_parse_corrections(parsed, body.corrections)
            except ValueError as e:  # an added job is incomplete
                raise HTTPException(422, str(e))
        # Drafting again after going back: fixes applied the first time count too.
        changed = changed or bool(session.data.get("parse_corrected"))
        generated = service.generate_proposals(session.data["resume_path"], session.data["jd_text"],
                                               parsed=parsed, progress=progress)
        session.data.update(
            parsed=parsed, parse_corrected=changed, proposals=generated["proposals"],
            gap_questions=generated.get("gap_questions") or [], keyword_match=generated.get("keyword_match"),
            job_description=generated.get("job_description"), proposal_usage=generated.get("llm_usage"),
            pre_score=generated["alignment_score"], experience_options=generated["experience_options"],
        )
        session.data.pop("results", None)
        session.data["conditions"] = generated.get("conditions") or []
        report = generated.get("keyword_match")
        keywords = [r.keyword for r in getattr(report, "rows", [])]
        sections = _sections(parsed[1].resume)
        questions = session.data["gap_questions"]
        status = generated.get("llm_status") or {}
        provider = status.get("provider") or forms.current_provider()
        return {
            # What the server now holds, so going back shows added jobs as ordinary ones.
            "details": _details(parsed[1].resume),
            "proposals": [_proposal_out(p, keywords, sections) for p in generated["proposals"]],
            "gap_questions": [q.model_dump() for q in questions],
            "conditions": [c.model_dump() for c in generated.get("conditions") or []],
            "keyword_match": _match_out(report),
            "gaps": gap_table(report, asked=[k for q in questions for k in q.keywords]),
            "pre_score": generated["alignment_score"],
            "experience_options": generated["experience_options"],
            "llm": {**status, "available": generated["llm_available"],
                    "provider_label": forms.PROVIDER_LABELS.get(provider, provider),
                    "fix_hint": forms.PROVIDER_FIX_HINTS.get(provider, "")},
        }

    return _stream(session, work)


@router.post("/match-preview")
def match_preview(request: Request, body: MatchPreviewIn, session: Session = Depends(current_session)) -> Dict:
    """The match rate if the selected (and edited) proposals were applied.
    No LLM, no files."""
    _require(session, "proposals", "job_description")
    report = _service(request, session).preview_keyword_match(
        session.data["parsed"], session.data["job_description"], _selected(session, body.selection))
    return {**_match_out(report), "delta": report.rate - (session.data.get("pre_score") or 0)}


@router.post("/tailor", dependencies=[Depends(rate_limited)])
def tailor(request: Request, body: TailorIn, session: Session = Depends(current_session)):
    """Step 3: apply the review and generate the files. Streams progress."""
    _require(session, "proposals")
    role = body.new_role or NewRoleIn()
    new_role, error = forms.new_role(role.company, role.title, role.location, role.current,
                                     role.start, role.end, role.description)
    if error:
        raise HTTPException(422, error)
    exp_ids = [o["id"] for o in session.data.get("experience_options") or []]
    questions = session.data.get("gap_questions") or []
    answers = forms.gap_answers(questions, {k: v.model_dump() for k, v in body.gap_answers.items()}, exp_ids)
    preapproved = _selected(session, body.selection)
    service = _service(request, session, session.data.get("model"))
    _claim(session)

    def work(progress):
        session.data.pop("results", None)  # downloads stop pointing at the old files first
        session.data.pop("arrange", None)  # and Arrange at the old run (Stage J review)
        session.data.pop("layout", None)
        remove_path(session.data.pop("output_dir", None))
        output_dir = session.data["output_dir"] = tempfile.mkdtemp(prefix="tailor_")
        results = service.tailor_resume(
            session.data["resume_path"], session.data["jd_text"], output_dir,
            mode="PRESERVE" if body.keep_layout else "ATS_DEFAULT",
            strict_factual=body.strict_factual, preapproved_proposals=preapproved,
            addition_text=body.addition.text, addition_target=forms.resolve_target(body.addition.target, exp_ids),
            proposal_usage=session.data.get("proposal_usage"), parsed=session.data["parsed"],
            parse_corrected=bool(session.data.get("parse_corrected")),
            job_desc=session.data.get("job_description"), gap_answers=answers, new_role=new_role,
            gap_questions=questions, remember_answers=body.remember_answers, progress=progress,
            conditions_confirmed=[c.text for c in session.data.get("conditions") or [] if c.id in set(body.conditions)],
        )
        session.data["arrange"] = results.pop("arrange", None)
        session.data.pop("layout", None)  # a new run starts from its own arrangement
        session.data["results"] = results
        return _results_out(session, results)

    return _stream(session, work)


def _results_out(session: Session, results: Dict) -> Dict:
    """What the Results (and Arrange) screen gets after a run."""
    pdf = results.get("pdf")
    try:
        pages = len(pdf_page_images(pdf, zoom=0.2)) if pdf and os.path.exists(pdf) else 0
    except Exception:
        pages = 0
    state = session.data.get("arrange")
    return {
        "success": bool(results.get("success")),
        "alignment_score": float(results["alignment_score"]),
        "initial_alignment_score": float(results.get("initial_alignment_score") or 0),
        "keyword_match": _match_out(results.get("keyword_match")),
        "content_lint": results.get("content_lint"),
        "addition_note": results.get("addition_note"),
        "warnings": results.get("warnings") or [],
        "docx_warnings": results.get("docx_warnings") or [],
        "pdf_warnings": results.get("pdf_warnings") or [],
        "target_pages": results.get("target_pages"),
        "applied": results.get("applied"),
        "coverage": results.get("coverage"),
        # Read-back checks split by weight (P8.26): serious ones fail the run.
        "file_checks": {
            "serious": [w for w in (results.get("docx_warnings") or []) + (results.get("pdf_warnings") or [])
                        if OutputQAValidator.is_serious(w)],
            "minor": [w for w in (results.get("docx_warnings") or []) + (results.get("pdf_warnings") or [])
                      if w.startswith(OutputQAValidator.ROUND_TRIP_PREFIX) and not OutputQAValidator.is_serious(w)],
        },
        "pages": pages,
        "files": {kind: bool(results.get(key)) and os.path.exists(results[key])
                  for kind, key in FILE_KINDS.items()},
        # P8.13: what the Arrange screen edits; None for "keep my layout".
        "arrangement": arrange_view(state["full_doc"].resume, state["original"],
                                    session.data.get("layout") or state["default_layout"], state["trimmed"],
                                    default=state["default_layout"])
        if state else None,
    }


class ArrangeIn(BaseModel):
    layout: Layout


MAX_EDIT_CHARS = 600


@router.post("/arrange")
def arrange(request: Request, body: ArrangeIn, session: Session = Depends(current_session)) -> Dict:
    """Re-render the tailored resume as the user arranged it (P8.13). No LLM
    call, so no rate limit; one render (or a few, to fit the page)."""
    state = session.data.get("arrange")
    if not state or not session.data.get("output_dir"):
        raise HTTPException(409, "Generate your resume first, then arrange it.")
    layout = body.layout
    if layout.page_target not in (None, 1, 2, 3):
        raise HTTPException(422, "Choose 1, 2 or 3 pages.")
    if any(len(t) > MAX_EDIT_CHARS for t in layout.edits.values()):
        raise HTTPException(422, f"Keep each bullet under {MAX_EDIT_CHARS} characters.")
    if sum(len(v) for v in (layout.section_order, layout.hidden_sections, layout.removed_bullets, layout.pinned,
                             layout.edits)) > 5000 or sum(len(v) for v in layout.bullet_order.values()) > 5000:
        raise HTTPException(422, "That arrangement is too large.")
    _claim(session)
    try:
        try:
            results = _service(request, session).arrange(state, layout, session.data["output_dir"])
        except HTTPException:
            raise
        except Exception:
            logger.exception("Arrange failed")
            raise HTTPException(500, "Couldn't update your files. Please try again.")
        session.data["arrange"] = results.pop("arrange")
        session.data["layout"] = layout
        session.data["results"] = results
        return _results_out(session, results)
    finally:
        if session.reset_pending:
            session.reset_pending = False
            session.reset()
        session.busy.release()


FILE_KINDS = {"docx": "docx", "pdf": "pdf", "changes": "changes_md", "html": "html"}
MEDIA_TYPES = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               "pdf": "application/pdf", "changes": "text/markdown", "html": "text/html"}


def _result_path(session: Session, key: str) -> str:
    path = (session.data.get("results") or {}).get(key)
    if not path or not os.path.exists(path):
        raise HTTPException(404, "That file isn't available.")
    return path


@router.get("/files/{kind}")
def download(kind: str, session: Session = Depends(current_session)) -> FileResponse:
    if kind not in FILE_KINDS:
        raise HTTPException(404, "Unknown file.")
    path = _result_path(session, FILE_KINDS[kind])
    return FileResponse(path, media_type=MEDIA_TYPES[kind], filename=os.path.basename(path))


@router.get("/preview/{page}")
def preview(page: int, session: Session = Depends(current_session)) -> Response:
    """One page of the tailored PDF as a PNG (Chrome blocks embedded PDFs)."""
    pages = pdf_page_images(_result_path(session, "pdf"))
    if not 1 <= page <= len(pages):
        raise HTTPException(404, "No such page.")
    return Response(pages[page - 1], media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/reset")
def reset(request: Request) -> Dict:
    """Start over: delete this visitor's files and state. If a step is still
    running, that happens as soon as it ends."""
    session = request.app.state.sessions.get(request.cookies.get(SESSION_COOKIE))
    if session is not None:
        if not session.busy.acquire(blocking=False):
            session.reset_pending = True
            return {"ok": True, "pending": True}
        try:
            session.reset()
        finally:
            session.busy.release()
    return {"ok": True}
