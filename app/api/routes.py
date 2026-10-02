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
from app.rendering.review_view import PROPOSAL_STATES, diff_spans, gap_table, proposal_state, score_breakdown

logger = logging.getLogger(__name__)

SESSION_COOKIE = "rt_session"
ALLOWED_TYPES = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}

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


async def _save_upload(request: Request, file: UploadFile) -> str:
    """The upload as a temp file, after checking its type and size."""
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in ALLOWED_TYPES:
        raise HTTPException(415, "Please upload a .docx or .pdf file.")
    limit = request.app.state.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"The file is larger than {limit // (1024 * 1024)} MB.")
    if not data.startswith(ALLOWED_TYPES[suffix]):
        raise HTTPException(415, f"That file doesn't look like a real {suffix} file.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        return tmp.name


def _check_jd(jd_text: str) -> None:
    if not jd_text.strip():
        raise HTTPException(422, "Please paste the job description.")


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
            "max_upload_mb": request.app.state.max_upload_bytes / (1024 * 1024)}


def _model(model: Optional[str]) -> Optional[str]:
    if model and model not in forms.model_options(forms.current_provider()):
        raise HTTPException(422, "Unknown model for this provider.")
    return model or None


@router.post("/analyze", dependencies=[Depends(rate_limited)])
async def analyze(request: Request, file: UploadFile = File(...), jd_text: str = Form(...),
                  model: Optional[str] = Form(None)) -> Dict:
    """"Just check my match": score only, nothing kept."""
    _check_jd(jd_text)
    model = _model(model)
    path = await _save_upload(request, file)
    try:
        report = await run_in_threadpool(_service(request, model=model).analyze_only, path, jd_text)
    finally:
        os.remove(path)
    return {**report.model_dump(), "keyword_match": _match_out(report.keyword_match)}


@router.post("/parse", dependencies=[Depends(rate_limited)])
async def parse(request: Request, response: Response, file: UploadFile = File(...), jd_text: str = Form(...),
                model: Optional[str] = Form(None)) -> Dict:
    """Step 1: read the resume and start a fresh session for this run."""
    _check_jd(jd_text)
    model = _model(model)
    path = await _save_upload(request, file)
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
        session.data.update(parsed=parsed, jd_text=jd_text, model=model,
                            parse_issues=list(service.last_parse_issues))
    except BaseException:
        session.busy.release()
        if is_new:  # no cookie was sent, so nobody could reach it again
            store.drop(session)
        raise
    session.busy.release()
    response.set_cookie(SESSION_COOKIE, session.id, httponly=True, samesite="lax",
                        max_age=store.ttl_seconds)
    return {"details": _details(parsed[1].resume), "parse_issues": session.data["parse_issues"]}


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
        )
        session.data["results"] = results
        pdf = results.get("pdf")
        try:
            pages = len(pdf_page_images(pdf, zoom=0.2)) if pdf and os.path.exists(pdf) else 0
        except Exception:
            pages = 0
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
            "pages": pages,
            "files": {kind: bool(results.get(key)) and os.path.exists(results[key])
                      for kind, key in FILE_KINDS.items()},
        }

    return _stream(session, work)


FILE_KINDS = {"docx": "docx", "pdf": "pdf", "changes": "changes_md"}
MEDIA_TYPES = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               "pdf": "application/pdf", "changes": "text/markdown"}


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
