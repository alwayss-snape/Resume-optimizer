import os
import re
import shutil
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from app.analysis.experience import is_ongoing, parse_month, target_pages
from app.analysis.gap_questions import GapAnswer, build_questions
from app.analysis.jd_analyzer import JDAnalyzer
from app.analysis.keyword_match import KeywordMatcher, _contains_seq, tokens
from app.analysis.matcher import EvidenceMatcher
from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.rewriter import FAILED_STATUSES, LLMRewriter, RewriteProposal
from app.analysis.scoring import AlignmentScorer
from app.analysis.semantic_matcher import SemanticMatcher
from app.analysis.structure_extractor import StructureExtractor
from app.analysis.skills_tailor import SkillsTailor, parse_skills
from app.analysis.summary_writer import SummaryWriter
from app.analysis.tailor_planner import TailoringPlanner
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import TailoringReport
from app.domain.resume import Experience, Project, Resume, ResumeBullet, Role
from app.domain.resume_document import ResumeDocument, ResumeSource
from app.domain.tailoring import TailoringPlan
from app.ingestion.docx import DocxParser
from app.ingestion.pdf import PdfParser
from app.llm.client import LLMClient
from app.rendering.docx_patcher import DocxPatcher
from app.rendering.html_renderer import HtmlResumeRenderer
from app.rendering.layout import output_basename, section_order_for
from app.rendering.page_fit import PageFitter
from app.rendering.pdf_converter import PdfConverter
from app.rendering.template_renderer import TemplateRenderer
from app.services.profile_store import ProfileStore
from app.services.run_manager import RunManager
from app.validation.content_lint import lint as content_lint
from app.validation.factual import FactualValidator
from app.validation.output import OutputQAValidator
from app.validation.structural import StructuralValidator
from app.validation.safety import SafetyGuard

def _progress(callback: Optional[Callable[[str], None]]) -> Callable[[str], None]:
    """A progress reporter that can never break a run (P3.6)."""
    def step(message: str) -> None:
        if callback is not None:
            try:
                callback(message)
            except Exception:
                pass
    return step


class TailorService:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.docx_parser = DocxParser()
        self.pdf_parser = PdfParser()
        self.resume_normalizer = ResumeNormalizer()
        self.structure_extractor = StructureExtractor(self.llm_client, self.resume_normalizer)
        # Problems left in the last parse (empty = looks right). Shown by the UI.
        self.last_parse_issues: List[str] = []
        self.jd_analyzer = JDAnalyzer(self.llm_client)
        self.matcher = EvidenceMatcher(self.llm_client)
        # A single reused instance: the embedding model (if enabled) is
        # lazy-loaded on first use and cached here, rather than reloaded on
        # every analyze_only/generate_proposals/tailor_resume call.
        self.semantic_matcher = SemanticMatcher()
        self.scorer = AlignmentScorer()
        # Headline score = keyword match rate (P1.2). The requirement-level
        # AlignmentScorer result is kept as the secondary "evidence_score".
        self.keyword_matcher = KeywordMatcher()
        self.planner = TailoringPlanner(self.llm_client, embedder=self._embed)
        self.rewriter = LLMRewriter(self.llm_client)
        self.summary_writer = SummaryWriter(self.llm_client)
        self.skills_tailor = SkillsTailor()
        self.profile_store = ProfileStore()
        self.validator = FactualValidator()
        self.struct_validator = StructuralValidator()
        self.docx_patcher = DocxPatcher()
        self.template_renderer = TemplateRenderer()
        self.html_renderer = HtmlResumeRenderer()
        self.pdf_converter = PdfConverter()
        self.qa_validator = OutputQAValidator()
        self.safety_guard = SafetyGuard()
        self.run_manager = RunManager()

    def generate_preview_md(self, resume: Resume) -> str:
        lines = [f"# {resume.candidate.name}\n"]
        if resume.candidate.headline:
            lines.append(f"**{resume.candidate.headline}**\n")
        contact = []
        if resume.candidate.email:
            contact.append(f"📧 {resume.candidate.email}")
        if resume.candidate.phone:
            contact.append(f"📞 {resume.candidate.phone}")
        if resume.candidate.location:
            contact.append(f"📍 {resume.candidate.location}")
        contact.extend(f"🔗 {link}" for link in resume.candidate.display_links())
        if contact:
            lines.append(" | ".join(contact) + "\n")

        if resume.summary:
            lines.append("## Professional Summary\n" + resume.summary + "\n")

        if resume.experience:
            lines.append("## Work Experience\n")
            for exp in resume.experience:
                lines.append(f"### {exp.company or exp.title}\n")
                for role in exp.all_roles():
                    dates = " – ".join(v for v in (role.start_date, role.end_date) if v)
                    lines.append(f"*{role.title}*" + (f" ({dates})" if dates else ""))
                lines.append("")
                for group, bullets in exp.bullet_groups():
                    if group:
                        lines.append(f"**{group}**")
                    lines.extend(f"- {bullet.text}" for bullet in bullets)
                lines.append("")

        if resume.skills:
            lines.append("## Technical Skills\n")
            for cat, s_list in resume.skills.items():
                lines.append(f"**{cat}:** {', '.join(s_list)}")
            lines.append("")

        if resume.education:
            lines.append("## Education\n")
            for edu in resume.education:
                lines.append(f"- **{edu.degree}** — {edu.institution}")

        return "\n".join(lines)

    @staticmethod
    def _patchable(proposals, evidence_list) -> List[RewriteProposal]:
        """Proposals as in-place DOCX patches. A summary proposal targets the
        summary paragraph(s): the first gets the new text, any others are
        emptied so the old summary doesn't remain."""
        out = []
        for p in proposals:
            if getattr(p, "kind", "bullet") == "skills":
                continue  # skills order can't be patched in place; the template shows it
            if getattr(p, "kind", "bullet") != "summary":
                out.append(p)
                continue
            blocks = [ev.source_location_id for ev in evidence_list
                      if ev.source_type == "summary" and ev.source_location_id]
            for i, block in enumerate(dict.fromkeys(blocks)):
                out.append(p.model_copy(update={
                    "target_source_location_id": block, "target_semantic_id": block,
                    "proposed_text": p.proposed_text if i == 0 else "",
                }))
        return out

    # Where a newly confirmed skill goes when the resume has such a category.
    SKILL_CATEGORY_RE = re.compile(r"tool|framework|librar|technolog|platform|skill", re.IGNORECASE)

    def _apply_gap_answers(self, resume: Resume, evidence_list: List, job_desc: JobDescription,
                           answers: List) -> List[str]:
        """Ticked keywords join the skills section; a typed answer becomes a
        bullet drafted only from the candidate's words (P3.1). Returns notes
        for the change log."""
        notes: List[str] = []
        known = {k.lower() for items in resume.skills.values() for k in items}
        for raw in answers:
            ans = raw if isinstance(raw, GapAnswer) else GapAnswer(**raw)
            added = [k for k in ans.confirmed_keywords if k.strip() and k.lower() not in known]
            if added:
                category = next((c for c in resume.skills if self.SKILL_CATEGORY_RE.search(c)), None) or "Skills"
                resume.skills.setdefault(category, []).extend(added)
                known.update(k.lower() for k in added)
                for k in added:
                    evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="skill",
                                                  source_id="user_confirmed", text=k))
                notes.append(f"You confirmed: {', '.join(added)} (added to {category})")
            if ans.answer.strip():
                _, updated, text = self._draft_from_answer(resume, evidence_list, ans)
                evidence_list[:] = updated
                notes.append(f"Added from your answer: {text}")
        return notes

    def _prefill_from_profile(self, questions: List) -> None:
        """Answers confirmed for an earlier JD pre-fill the same questions
        now (P3.2). Only a pre-fill: the user still sees and keeps them."""
        try:
            known = self.profile_store.known([k for q in questions for k in q.keywords])
        except Exception:
            return  # a profile problem must never block tailoring
        for q in questions:
            facts = [known[k] for k in q.keywords if k in known]
            q.saved_keywords = [k for k in q.keywords if k in known]
            q.saved_answer = next((f.answer for f in facts if f.answer), "")

    def _draft_from_answer(self, resume: Resume, evidence_list: List, ans: GapAnswer):
        """Polish the candidate's answer into one bullet that may use only
        the keywords they ticked, then fact-check it against the answer.
        If the polish adds anything, their own wording is used instead."""
        answer = ans.answer.strip()
        user_ev = Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="general", source_id="user_answer", text=answer)
        polished, _ = self.rewriter.rewrite_bullet(answer, evidence=[user_ev], jd_requirements=[],
                                                   target_keywords=ans.confirmed_keywords)
        check = RewriteProposal(target_semantic_id="user_answer", original_text=answer,
                                proposed_text=polished or answer, evidence_ids=[user_ev.id])
        verdict = self.validator.validate_proposal(check, [user_ev]).verdict
        text = polished if polished and verdict == "PASS" else answer
        resume, updated, _ = self.incorporate_user_addition(
            resume, evidence_list, JobDescription(), text, ans.target, polish=False)
        return resume, updated, text

    MAX_NEW_ROLE_BULLETS = 6

    @staticmethod
    def _split_description(text: str) -> List[str]:
        """Pasted role description -> bullet-sized chunks: one per line (list
        markers removed), or one per sentence for a single paragraph."""
        lines = [re.sub(r"^\s*(?:[-*•●▪◦]|\d+[.)])\s*", "", l).strip() for l in (text or "").splitlines()]
        lines = [l for l in lines if l]
        if len(lines) == 1:
            lines = [c.strip() for c in re.split(r"(?<=[.!?])\s+(?=[A-Z])", lines[0]) if c.strip()]
        return lines

    @classmethod
    def validate_new_role(cls, role_data: Dict, description_text: str) -> Tuple[str, str, str, str]:
        """Check a new job before any work is done; raises ValueError with a
        user-facing reason. Returns (company, title, start, end)."""
        company = (role_data.get("company") or "").strip()
        title = (role_data.get("title") or "").strip()
        if not company or not title:
            raise ValueError("A new job needs both a company and a job title.")
        start = (role_data.get("start_date") or "").strip() or None
        end = "Present" if role_data.get("current") else ((role_data.get("end_date") or "").strip() or None)
        # A job without dates or bullets reads back wrongly in an ATS (the
        # parser merges it into its neighbours), so these are required too.
        today = date.today()
        start_month = parse_month(start, is_end=False, today=today)
        end_month = parse_month(end, is_end=True, today=today)
        if start_month is None:
            raise ValueError("A new job needs a start date.")
        if end_month is None:
            raise ValueError("A new job needs an end date, or tick \"I currently work here\".")
        if end_month < start_month:
            raise ValueError("The new job's end date is before its start date.")
        if not cls._split_description(description_text):
            raise ValueError("Describe at least one thing you did in the new job.")
        return company, title, start, end

    def add_new_role(self, resume: Resume, evidence_list: List, job_desc: JobDescription,
                     role_data: Dict, description_text: str) -> Tuple[Resume, List, List[str]]:
        """Add a job the resume doesn't have yet (P3.3). Each chunk of the
        user's description is polished into a bullet that may use only JD
        keywords already in that chunk, then fact-checked against it; if the
        polish adds anything, the user's own wording is used. The job goes
        in date order (current jobs first, then most recent start).
        Mutates `resume`; returns (resume, evidence_list, notes)."""
        company, title, start, end = self.validate_new_role(role_data, description_text)
        today = date.today()
        exp = Experience(id=f"exp_user_{uuid4().hex[:6]}", company=company, title=title,
                         location=(role_data.get("location") or "").strip() or None,
                         start_date=start, end_date=end, roles=[Role(title=title, start_date=start, end_date=end)])

        notes = []
        chunks = self._split_description(description_text)
        if len(chunks) > self.MAX_NEW_ROLE_BULLETS:
            notes.append(f"Only the first {self.MAX_NEW_ROLE_BULLETS} of {len(chunks)} description lines were used.")
        for n, chunk in enumerate(chunks[:self.MAX_NEW_ROLE_BULLETS], start=1):
            user_ev = Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="general", source_id="new_role",
                               text=chunk)
            chunk_tokens = tokens(chunk)  # whole words: "R" doesn't match "Reduced"
            allowed = [k for k in job_desc.keywords if tokens(k) and _contains_seq(chunk_tokens, tokens(k))]
            polished, _ = self.rewriter.rewrite_bullet(chunk, evidence=[user_ev], jd_requirements=[],
                                                       target_keywords=allowed)
            check = RewriteProposal(target_semantic_id="new_role", original_text=chunk,
                                    proposed_text=polished or chunk, evidence_ids=[user_ev.id])
            verdict = self.validator.validate_proposal(check, [user_ev]).verdict
            text = polished if polished and verdict == "PASS" else chunk
            bullet = ResumeBullet(id=f"{exp.id}_b{n:02d}", text=text)
            exp.bullets.append(bullet)
            evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="experience",
                                          source_id=bullet.id, text=f"{company}: {text}"))

        def sort_key(e: Experience):
            first = (e.all_roles() or [Role(title="")])[0]
            ongoing = is_ongoing(first.end_date)
            started = parse_month(first.start_date, is_end=False, today=today) or (0, 0)
            return (not ongoing, (-started[0], -started[1]))
        new_key = sort_key(exp)
        position = next((i for i, e in enumerate(resume.experience) if sort_key(e) > new_key), len(resume.experience))
        resume.experience.insert(position, exp)
        dates = " – ".join(v for v in (start, end) if v)
        notes.insert(0, f"Added a new job: {title} at {company}" + (f" ({dates})" if dates else "")
                     + f" with {len(exp.bullets)} bullet(s) from your description.")
        return resume, evidence_list, notes

    def _skills_proposals(self, resume, keyword_report) -> List[RewriteProposal]:
        """The skills section with the JD's skills first, when that changes it (P1.6)."""
        proposal = self.skills_tailor.propose(resume, keyword_report)
        return [proposal] if proposal is not None else []

    def _summary_proposals(self, resume, job_desc, keyword_report, evidence_list) -> List[RewriteProposal]:
        """The tailored summary as a proposal, when one was written (P1.5)."""
        proposal = self.summary_writer.propose(resume, job_desc, keyword_report, evidence_list)
        return [proposal] if proposal is not None and proposal.status == "ok" else []

    def _embed(self, texts):
        """Sentence embeddings for the planner, loaded lazily; raises when the
        model isn't available so the planner falls back to token overlap."""
        encode = self.semantic_matcher._get_embedder()
        if encode is None:
            raise RuntimeError("embedding model unavailable")
        return encode(texts)

    @staticmethod
    def _fit_relevance(resume: Resume, plan: TailoringPlan) -> Dict[str, float]:
        """Planner relevance per bullet for the page-fit loop. Bullets the user
        added in this run (gap answers, additions, a new job) aren't in the
        plan; they count as fully relevant so they're never trimmed first."""
        relevance = {a.source_id: a.relevance for a in plan.actions if a.source_id}
        for section in [*resume.experience, *resume.projects]:
            for b in section.bullets:
                relevance.setdefault(b.id, 1.0)
        return relevance

    def _render_template(self, resume_doc: ResumeDocument, docx_path: str, output_dir: str) -> Optional[str]:
        """One template render plus PDF conversion (the page-fit loop's step)."""
        self.template_renderer.render_ats_default(resume_doc, docx_path)
        return self.pdf_converter.convert_docx_to_pdf(docx_path, output_dir)

    @staticmethod
    def _apply_bullet_order(resume: Resume, bullet_order: Dict[str, List[str]]) -> int:
        """Reorder bullets as planned (most relevant first within each
        sub-heading). Returns how many experience entries changed order."""
        changed = 0
        for exp in [*resume.experience, *resume.projects]:
            order = bullet_order.get(exp.id)
            if not order:
                continue
            rank = {bid: i for i, bid in enumerate(order)}
            new = sorted(exp.bullets, key=lambda b: rank.get(b.id, len(rank)))
            if [b.id for b in new] != [b.id for b in exp.bullets]:
                exp.bullets = new
                changed += 1
        return changed

    def parse_resume(self, resume_path: str):
        """File -> (raw document, ResumeDocument, evidence). The deterministic
        parse runs first; only if it looks wrong is the LLM asked to label
        lines by index (P1.13), which keeps every value verbatim."""
        if resume_path.lower().endswith(".pdf"):
            raw_doc = self.pdf_parser.parse(resume_path)
        else:
            raw_doc = self.docx_parser.parse(resume_path)
        return (raw_doc, *self.normalize_raw(raw_doc))

    def normalize_raw(self, raw_doc):
        resume_doc, evidence_list = self.resume_normalizer.normalize(raw_doc)
        resume_doc, evidence_list, self.last_parse_issues = self.structure_extractor.improve(
            raw_doc, resume_doc, evidence_list,
        )
        return resume_doc, evidence_list

    @staticmethod
    def _copy_parsed(parsed):
        """Deep copies, so a parse kept in UI session state is never mutated."""
        raw_doc, resume_doc, evidence_list = parsed
        return raw_doc, resume_doc.model_copy(deep=True), [e.model_copy(deep=True) for e in evidence_list]

    def preview_keyword_match(self, parsed, job_desc: JobDescription, proposals: List[Dict]):
        """Match rate if these proposals were applied (P3.4 "recalculate"):
        no LLM, no files. `proposals` are dicts with kind, target_semantic_id
        and proposed_text, i.e. the ticked (and possibly edited) ones."""
        resume = parsed[1].resume.model_copy(deep=True)
        for p in proposals:
            text = (p.get("proposed_text") or "").strip()
            if not text:
                continue
            if p.get("validation") == "REJECT" and not p.get("user_edited"):
                continue  # Apply drops these too (unless the user edited them)
            kind = p.get("kind", "bullet")
            if kind == "summary":
                resume.summary = text
            elif kind == "skills" and parse_skills(text):
                resume.skills = parse_skills(text)
            elif kind == "bullet":
                for section in [*resume.experience, *resume.projects]:
                    for b in section.bullets:
                        if b.id == p.get("target_semantic_id"):
                            b.text = text
        return self.keyword_matcher.match(job_desc, resume)

    def apply_parse_corrections(self, parsed, corrections: Dict):
        """Apply the user's fixes from the "Check parsed resume" step (P3.5).

        `corrections` = {"candidate": {name, headline, email, phone, location,
        links: [...]}, "experience": [{id, company, location, roles: [{title,
        start_date, end_date}, ...]}]}. Only header/structure fields change;
        bullet text is never touched here. Returns (parsed, changed)."""
        raw_doc, resume_doc, evidence_list = self._copy_parsed(parsed)
        resume = resume_doc.resume
        changed: List[str] = []

        cand = corrections.get("candidate") or {}
        for field in ("name", "headline", "email", "phone", "location"):
            if field in cand:
                value = (cand[field] or "").strip() or None
                if field == "name":
                    value = value or resume.candidate.name
                if value != getattr(resume.candidate, field):
                    setattr(resume.candidate, field, value)
                    changed.append(f"candidate.{field}")
        if "links" in cand:
            links = [l.strip() for l in cand["links"] if l and l.strip()]
            if links != resume.candidate.links:
                resume.candidate.links = links
                changed.append("candidate.links")

        by_id = {e.id: e for e in resume.experience}
        for fix in corrections.get("experience") or []:
            exp = by_id.get(fix.get("id"))
            if exp is None:
                continue
            old_context = exp.company or exp.title or "Experience"
            for field in ("company", "location"):
                if field in fix:
                    value = (fix[field] or "").strip()
                    value = value if field == "company" else (value or None)
                    if value != getattr(exp, field):
                        setattr(exp, field, value)
                        changed.append(f"{exp.id}.{field}")
            if "roles" in fix:
                roles = [Role(title=(r.get("title") or "").strip(),
                              start_date=(r.get("start_date") or "").strip() or None,
                              end_date=(r.get("end_date") or "").strip() or None)
                         for r in fix["roles"] if (r.get("title") or "").strip()]
                if [r.model_dump() for r in roles] != [r.model_dump() for r in exp.all_roles()]:
                    first = roles[0] if roles else Role(title="")
                    exp.title, exp.start_date, exp.end_date = first.title, first.start_date, first.end_date
                    exp.roles = roles if len(roles) > 1 else []
                    changed.append(f"{exp.id}.roles")
            # Experience evidence reads "<company>: <bullet>"; keep it in step.
            new_context = exp.company or exp.title or "Experience"
            if new_context != old_context:
                bullet_ids = {b.id for b in exp.bullets}
                for ev in evidence_list:
                    if ev.source_id in bullet_ids and ev.text.startswith(old_context):
                        ev.text = new_context + ev.text[len(old_context):]

        if changed:
            resume_doc.record_revision("Parsed resume corrected by the user", changed, actor="user")
        return (raw_doc, resume_doc, evidence_list), bool(changed)

    def analyze_only(self, resume_path: str, jd_text: str) -> TailoringReport:
        clean_jd_text = self.safety_guard.sanitize(jd_text)
        
        raw_doc, resume_doc, evidence_list = self.parse_resume(resume_path)
        resume = resume_doc.resume
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        keyword_report = self.keyword_matcher.match(job_desc, resume)
        score = keyword_report.rate
        score_components = dict(self.scorer.calculate_components(matches, job_desc.requirements))
        score_components["evidence_score"] = self.scorer.calculate_score(matches, job_desc.requirements)

        required_m = [m for m in matches if any(r.id == m.requirement_id and r.priority == "required" for r in job_desc.requirements)]
        preferred_m = [m for m in matches if any(r.id == m.requirement_id and r.priority == "preferred" for r in job_desc.requirements)]
        missing_m = [m for m in matches if m.status == "MISSING"]

        return TailoringReport(
            alignment_score=score,
            required_matches=required_m,
            preferred_matches=preferred_m,
            missing_requirements=missing_m,
            score_components=score_components,
            keyword_match=keyword_report,
        )

    def generate_proposals(self, resume_path: str, jd_text: str, suggestion_limit: int = 5,
                           parsed=None, progress: Optional[Callable[[str], None]] = None) -> Dict:
        """Generate rewrite proposals without applying them, plus questions
        about JD keywords the resume doesn't show (P3.1).

        Returns {"proposals": [...], "gap_questions": [...],
        "alignment_score": float, ...}. Useful for UI review flows.
        """
        step = _progress(progress)
        clean_jd_text = self.safety_guard.sanitize(jd_text)

        # `parsed`: the (raw, resume, evidence) the user checked in the UI.
        if parsed is None:
            step("Reading your resume")
        raw_doc, resume_doc, evidence_list = (
            self._copy_parsed(parsed) if parsed is not None else self.parse_resume(resume_path)
        )
        resume = resume_doc.resume
        step("Analysing the job description")
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        step("Matching your resume to the job's keywords")
        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        keyword_report = self.keyword_matcher.match(job_desc, resume)
        score = keyword_report.rate
        plan = self.planner.create_plan(resume, job_desc, evidence_list, matches)
        step("Writing a tailored summary")
        proposals = self._summary_proposals(resume, job_desc, keyword_report, evidence_list)
        proposals += self._skills_proposals(resume, keyword_report)
        proposals += self.rewriter.execute_plan(resume, plan, evidence_list, job_desc, progress=step)
        step("Fact-checking every proposal")
        # Fact-check now so the review UI can show each proposal's verdict
        # (and what would be dropped) before the user applies anything.
        for prop in proposals:
            res = self.validator.validate_proposal(prop, evidence_list, jd_keywords=job_desc.keywords)
            prop.validation = res.verdict
            prop.validation_note = "; ".join(res.warnings) or None

        # Suggest-and-confirm (P3.1): ask about what the JD wants and the
        # resume doesn't show, instead of drafting experience the candidate
        # may not have. Built in code, no LLM call.
        gap_questions = build_questions(job_desc, keyword_report, limit=suggestion_limit)
        self._prefill_from_profile(gap_questions)

        llm_available = bool(self.llm_client and self.llm_client.is_available())
        failed = [p for p in proposals if getattr(p, "status", None) in FAILED_STATUSES]
        return {
            "proposals": proposals,
            "gap_questions": gap_questions,
            "alignment_score": score,
            "keyword_match": keyword_report,
            "job_description": job_desc,
            "llm_available": llm_available,
            # Why rewrites didn't happen, so the UI can say so instead of
            # silently presenting the original text as the "proposal".
            "llm_status": {
                "provider": getattr(self.llm_client, "provider", None),
                "model": getattr(self.llm_client, "model", None),
                "available": llm_available,
                "reason": getattr(self.llm_client, "last_error", None),
                "attempted": len(proposals),
                "failed": len(failed),
                "errors": sorted({p.error for p in failed if p.error}),
            },
            "llm_usage": self.llm_client.get_usage_summary() if self.llm_client else None,
            "parse_issues": list(self.last_parse_issues),
            "experience_options": [{"id": e.id, "label": " — ".join(v for v in (e.company, e.title) if v) or e.id} for e in resume.experience],
        }

    def incorporate_user_addition(
        self,
        resume: Resume,
        evidence_list: List["object"],
        job_desc: JobDescription,
        addition_text: str,
        target: str = "auto",
        polish: bool = True,
    ) -> Tuple[Resume, List, Optional[str]]:
        """Fold a user-supplied free-text addition (a project, an
        achievement, a skill, anything they typed in) into the résumé as one
        polished, JD-keyword-aware bullet — grounded ONLY in what the user
        actually wrote (the LLM is explicitly told this text IS the
        evidence, so it may not invent facts beyond it).

        `target` is either "auto" (append to the most recent experience
        entry), "new_project" (create a new Project entry), or the `id` of
        a specific Experience entry to append to.

        Mutates `resume` in place and returns (resume, updated_evidence_list,
        rationale_or_None). If `addition_text` is blank, this is a no-op.
        """
        addition_text = (addition_text or "").strip()
        if not addition_text:
            return resume, evidence_list, None

        jd_req_texts = [r.text for r in job_desc.requirements]
        user_evidence = Evidence(
            id=f"ev_user_{uuid4().hex[:6]}",
            source_type="general",
            source_id="user_addition",
            text=addition_text,
        )
        if polish:
            polished_text, rationale = self.rewriter.rewrite_bullet(
                addition_text,
                evidence=[user_evidence],
                jd_requirements=jd_req_texts,
                target_keywords=job_desc.keywords,
            )
        else:  # already drafted and checked by the caller
            polished_text, rationale = addition_text, None
        polished_text = polished_text or addition_text

        if target == "new_project":
            proj_id = f"proj_user_{uuid4().hex[:6]}"
            bullet_id = f"{proj_id}_b01"
            bullet = ResumeBullet(id=bullet_id, text=polished_text)
            resume.projects.append(Project(id=proj_id, name="Additional Project", bullets=[bullet]))
            ev_text = f"Project (Additional Project): {polished_text}"
            ev_source_type = "project"
        else:
            exp = None
            if target and target not in ("auto", "new_project"):
                exp = next((e for e in resume.experience if e.id == target), None)
            if exp is None and resume.experience:
                exp = resume.experience[0]

            if exp is None:
                # No experience section to attach to at all — fall back to a
                # new project rather than silently dropping the addition.
                return self.incorporate_user_addition(resume, evidence_list, job_desc, addition_text,
                                                      target="new_project", polish=polish)

            bullet_id = f"{exp.id}_b_user_{uuid4().hex[:6]}"
            bullet = ResumeBullet(id=bullet_id, text=polished_text)
            exp.bullets.append(bullet)
            ev_text = f"{exp.company}: {polished_text}"
            ev_source_type = "experience"

        new_evidence = Evidence(
            id=f"ev_user_add_{uuid4().hex[:6]}",
            source_type=ev_source_type,
            source_id=bullet_id,
            text=ev_text,
        )
        updated_evidence_list = list(evidence_list) + [new_evidence]
        return resume, updated_evidence_list, rationale

    def tailor_resume(
        self,
        resume_path: str,
        jd_text: str,
        output_dir: str,
        mode: str = "ATS_DEFAULT",
        strict_factual: bool = False,
        preapproved_proposals: Optional[List] = None,
        addition_text: Optional[str] = None,
        addition_target: str = "auto",
        proposal_usage: Optional[Dict] = None,
        parsed=None,
        parse_corrected: bool = False,
        job_desc: Optional[JobDescription] = None,
        gap_answers: Optional[List] = None,
        new_role: Optional[Dict] = None,
        gap_questions: Optional[List] = None,
        remember_answers: bool = True,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, str]:
        run_dir = self.run_manager.create_run(resume_path, jd_text)
        clean_jd_text = self.safety_guard.sanitize(jd_text)
        
        # Prepare incremental change log so callers (and UI) can tail it in
        # near-real-time while processing proceeds.
        report_md_path = os.path.join(output_dir, "changes.md")
        os.makedirs(output_dir, exist_ok=True)
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Tailoring Report & Change Log\n\n")
            f.write(f"**Started:** {datetime.utcnow().isoformat()}Z\n\n")
            f.write("## Progress Log\n\n")
        
        step = _progress(progress)

        def _append_progress(msg: str) -> None:
            step(msg)
            ts = datetime.utcnow().isoformat() + "Z"
            try:
                with open(report_md_path, "a", encoding="utf-8") as pf:
                    pf.write(f"- [{ts}] {msg}\n")
            except Exception:
                # Never fail tailoring flow due to progress logging
                pass
        
        _append_progress("Run created: " + run_dir)

        is_pdf = resume_path.lower().endswith(".pdf")
        if is_pdf:
            mode = "ATS_DEFAULT"  # Force ATS reconstruction for PDF inputs
        if parse_corrected and mode == "PRESERVE":
            # Header/role corrections have no place to go in an in-place
            # patch of the original file; only the template shows them.
            mode = "ATS_DEFAULT"
        if parsed is None:
            raw_doc = self.pdf_parser.parse(resume_path) if is_pdf else self.docx_parser.parse(resume_path)

        if new_role and mode == "PRESERVE":
            mode = "ATS_DEFAULT"  # a new job has no place in the original layout
        if addition_text and (addition_text or "").strip() and mode == "PRESERVE":
            # A brand-new bullet has no corresponding block in the original
            # layout, so it cannot be positionally patched in place — fall
            # back to the reconstructed ATS template so the addition
            # actually shows up in the output.
            mode = "ATS_DEFAULT"

        # Normalizer returns a canonical ResumeDocument and the extracted evidence
        if parsed is not None:
            raw_doc, resume_doc, evidence_list = self._copy_parsed(parsed)
        else:
            resume_doc, evidence_list = self.normalize_raw(raw_doc)
        resume = resume_doc.resume
        _append_progress("Imported and normalized resume")
        # Record import as a revision (best-effort)
        try:
            resume_doc.record_revision("Imported uploaded résumé", ["resume", "source"], actor="import")
        except Exception:
            pass
        # Reuse the JD analysis from generate_proposals when given: a second LLM
        # analysis costs a call and can return a slightly different keyword list,
        # which made the before/after match rates disagree.
        job_desc = job_desc or self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        initial_keywords = self.keyword_matcher.match(job_desc, resume)
        initial_score = initial_keywords.rate
        _append_progress(f"Analyzed JD and computed initial keyword match rate: {initial_score:.1f}%")

        # The planner is deterministic (no LLM calls), so it always runs: its
        # plan feeds plan.json and the unsupported-requirements report.
        plan = self.planner.create_plan(resume, job_desc, evidence_list, matches)
        if preapproved_proposals is not None:
            # The user already reviewed proposals in the UI. Re-running the
            # rewriter here would repeat every LLM call and then throw the
            # result away, so use theirs. They may arrive as plain dicts.
            proposals = [RewriteProposal(**p) if isinstance(p, dict) else p for p in preapproved_proposals]
            _append_progress(f"Using {len(proposals)} user-approved proposals (rewriter skipped)")
        else:
            proposals = self._summary_proposals(resume, job_desc, initial_keywords, evidence_list)
            proposals += self._skills_proposals(resume, initial_keywords)
            proposals += self.rewriter.execute_plan(resume, plan, evidence_list, job_desc)
            _append_progress(f"Planner created plan with {len(plan.actions)} actions; generated {len(proposals)} proposals")

        approved_proposals: List[RewriteProposal] = []
        warnings: List[str] = []

        # Keep copies of the pre-tailoring state: for structural validation,
        # and to roll back if Strict Factual Mode withholds the rewrites.
        import copy
        original_resume = copy.deepcopy(resume)
        original_evidence = copy.deepcopy(evidence_list)

        rejected_count = 0
        for prop in proposals:
            if getattr(prop, "user_edited", False):
                # The user wrote or changed this text themselves in the
                # review form: accept it as user-attested, and say so.
                approved_proposals.append(prop)
                warnings.append(
                    f"Kept your edited text as written (not fact-checked): {getattr(prop, 'proposed_text', '')[:80]}"
                )
                continue
            res = self.validator.validate_proposal(prop, evidence_list, jd_keywords=job_desc.keywords)
            if res.approved:
                approved_proposals.append(prop)
                warnings.extend(res.warnings)  # NEEDS_CONFIRM notes: kept, but worth a look
            else:
                rejected_count += 1
                warnings.extend(res.warnings)
        _append_progress(f"Validation complete: {len(approved_proposals)} approved, {rejected_count} rejected")

        # Output file generation
        os.makedirs(output_dir, exist_ok=True)
        # First_Last_Resume_<Company>.docx/.pdf/.html (P2.1)
        base_name = output_basename(resume, job_desc.company) or "tailored_resume"
        docx_output_path = os.path.join(output_dir, f"{base_name}.docx")
        pdf_output_path = os.path.join(output_dir, f"{base_name}.pdf")
        html_output_path = os.path.join(output_dir, f"{base_name}.html")

        def _prop_key(p):
            return getattr(p, "semantic_id", None) or getattr(p, "target_semantic_id", None) or getattr(p, "source_id", None)

        def _prop_text(p):
            return getattr(p, "rewritten_text", None) or getattr(p, "proposed_text", None) or ""

        # The tailored summary (P1.5) replaces the summary text and its evidence.
        for p in approved_proposals:
            if getattr(p, "kind", "bullet") == "summary" and _prop_text(p).strip():
                resume.summary = _prop_text(p).strip()
                summary_ev = [ev for ev in evidence_list if ev.source_type == "summary"]
                if summary_ev:
                    summary_ev[0].text = resume.summary
                    for ev in summary_ev[1:]:
                        evidence_list.remove(ev)

        # Reordered / respelled skills (P1.6), from the (possibly edited) text.
        for p in approved_proposals:
            if getattr(p, "kind", "bullet") == "skills" and parse_skills(_prop_text(p)):
                resume.skills = parse_skills(_prop_text(p))

        # Apply approved rewrites to the canonical resume model (semantic ids).
        prop_dict = {_prop_key(p): _prop_text(p) for p in approved_proposals
                     if getattr(p, "kind", "bullet") == "bullet"}
        for section in [*resume.experience, *resume.projects]:  # project bullets too (P1.7)
            for b in section.bullets:
                if b.id in prop_dict:
                    b.text = prop_dict[b.id]

        # Keep the evidence ledger in sync with rewritten bullet text so that
        # rescoring below reflects the tailored wording, not the original.
        for b_id, new_text in prop_dict.items():
            for ev in evidence_list:
                if ev.source_id == b_id and ev.source_type in ("experience", "project"):
                    prefix = ev.text.split(":", 1)[0] if ":" in ev.text else None
                    ev.text = f"{prefix}: {new_text}" if prefix else new_text

        # Structural validation: tailoring must not alter identity/structure.
        struct_warnings = self.struct_validator.validate(original_resume, resume)
        warnings.extend(struct_warnings)

        # Strict Factual Mode is all-or-nothing, and it must be decided BEFORE
        # anything is rendered (it used to clear the list after the DOCX was
        # already written, so the output kept rewrites the report said were
        # withheld). If any rewrite was rejected or the structure changed,
        # roll back every rewrite.
        if strict_factual and approved_proposals and (rejected_count or struct_warnings):
            original_text = {b.id: b.text for e in [*original_resume.experience, *original_resume.projects]
                             for b in e.bullets}
            for section in [*resume.experience, *resume.projects]:
                for b in section.bullets:
                    if b.id in original_text:
                        b.text = original_text[b.id]
            resume.summary = original_resume.summary
            resume.skills = original_resume.skills
            evidence_list[:] = original_evidence
            approved_proposals = []
            warnings.append(
                "Strict Factual Mode: all rewrites withheld because at least one rewrite failed validation."
            )
            _append_progress("Strict factual mode triggered: all rewrites withheld")

        if approved_proposals:
            try:
                for prop in approved_proposals:
                    resume_doc.record_revision(
                        rev_id=f"ai_{_prop_key(prop)}", actor="ai", original=getattr(prop, "original_text", ""),
                        rewritten=_prop_text(prop), evidence_ids=getattr(prop, "evidence_ids", []) or [],
                        source="llm_rewriter",
                    )
            except Exception:
                pass  # revision history is best-effort; never fail the run for it
            _append_progress(f"Applied {len(approved_proposals)} approved rewrites to canonical resume model")

        # Most relevant bullets first within each sub-heading (P1.3). Only the
        # template can move bullets; an in-place DOCX patch keeps the order.
        if mode != "PRESERVE" or is_pdf:
            reordered = self._apply_bullet_order(resume, plan.bullet_order)
            if reordered:
                _append_progress(f"Reordered bullets by JD relevance in {reordered} role(s)")

        # Fold in any free-text content the candidate typed in the UI (a
        # project, an achievement, a skill) as one more polished, evidence-
        # grounded bullet, then recompute the alignment score so it reflects
        # everything just applied — the rewrites above and this addition.
        # Answers to the gap questions (P3.1): only what the candidate
        # confirmed, in their own words.
        gap_notes = self._apply_gap_answers(resume, evidence_list, job_desc, gap_answers or [])
        if remember_answers and gap_answers:
            try:
                saved = self.profile_store.record(gap_answers, gap_questions or [])
                if saved:
                    _append_progress(f"Saved for future applications: {', '.join(saved)}")
            except Exception as e:
                warnings.append(f"Could not save your answers for next time: {e}")
        for note in gap_notes:
            _append_progress(note)
            warnings.append(note)

        if new_role:  # "Add a job" (P3.3)
            resume, evidence_list, role_notes = self.add_new_role(
                resume, evidence_list, job_desc, new_role, new_role.get("description", ""))
            for note in role_notes:
                _append_progress(note)
                warnings.append(note)

        addition_note = None
        if addition_text and (addition_text or "").strip():
            resume, evidence_list, addition_note = self.incorporate_user_addition(
                resume, evidence_list, job_desc, addition_text, addition_target,
            )
            if addition_note:
                _append_progress(f"Incorporated user-supplied addition: {addition_note}")
            else:
                _append_progress("Incorporated user-supplied addition")

        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        keyword_report = self.keyword_matcher.match(job_desc, resume)
        score = keyword_report.rate
        evidence_score = self.scorer.calculate_score(matches, job_desc.requirements)
        _append_progress(f"Recomputed keyword match rate after applying changes: {score:.1f}% (was {initial_score:.1f}%)")

        # Education goes first for someone early in their career (P2.1).
        resume_doc.presentation.section_order = section_order_for(resume)
        fit = None

        if mode == "PRESERVE" and not is_pdf:
            self.docx_patcher.patch(resume_path, raw_doc.document_map,
                                    self._patchable(approved_proposals, original_evidence), docx_output_path)
            _append_progress(f"DOCX preserve-mode patch applied to {docx_output_path}")
        else:
            # Render, count pages and trim the least relevant content until
            # it fits the page target (P2.4). This also produces the PDF.
            page_target = target_pages(resume)
            fit = PageFitter(self._render_template).fit(
                resume_doc, docx_output_path, output_dir, page_target,
                relevance=self._fit_relevance(resume, plan),
                trim_candidates={a.source_id for a in plan.actions if a.trim_candidate},
            )
            _append_progress(f"DOCX reconstructed via template renderer at {docx_output_path} "
                             f"({fit.pages or '?'} page(s), target {page_target}, {fit.renders} render(s))")
            for note in fit.notes:
                _append_progress(note)
                warnings.append(note)
            if fit.trimmed and fit.pages is not None:
                keyword_report = self.keyword_matcher.match(job_desc, resume)
                score = keyword_report.rate
                _append_progress(f"Keyword match rate after page fit: {score:.1f}%")

        # Content checks on what was rendered (P2.6): advice, never auto-applied.
        content_report = content_lint(resume)

        # Canonical ATS HTML is available for browser preview and print workflows.
        try:
            self.html_renderer.write_html(resume_doc, html_output_path)
            _append_progress(f"HTML preview written to {html_output_path}")
        except Exception:
            pass

        # Output QA validations (DOCX and PDF) to catch rendering issues
        docx_warnings = []
        try:
            docx_warnings = self.qa_validator.validate_docx(docx_output_path, expected_candidate_name=resume.candidate.name)
            if fit:  # template output: it must read back exactly as rendered (P2.5)
                docx_warnings += self.qa_validator.round_trip(docx_output_path, resume)
            warnings.extend(docx_warnings)
        except Exception:
            # Never fail the tailoring flow due to QA check exceptions
            warnings.append("Output QA DOCX validation failed unexpectedly.")

        # PDF Conversion and QA
        pdf_warnings = []
        pdf_res = fit.pdf_path if fit else self.pdf_converter.convert_docx_to_pdf(docx_output_path, output_dir)
        if not pdf_res:
            warnings.append("LibreOffice not available or PDF conversion failed; DOCX rendered successfully.")
            _append_progress("PDF conversion failed or LibreOffice unavailable")
        else:
            try:
                pdf_warnings = self.qa_validator.validate_pdf(pdf_res, expected_candidate_name=resume.candidate.name)
                if fit:
                    pdf_warnings += self.qa_validator.round_trip(pdf_res, resume)
                warnings.extend(pdf_warnings)
            except Exception:
                warnings.append("Output QA PDF validation failed unexpectedly.")
            _append_progress(f"PDF conversion complete: {pdf_res}")

        # Save artifacts to run folder
        # Save the ResumeDocument as canonical SOT
        try:
            self.run_manager.save_json(run_dir, "resume_document.json", resume_doc)
        except Exception:
            pass
        # Also save the legacy resume.json for compatibility
        self.run_manager.save_json(run_dir, "resume.json", resume)
        # (Note: `resume_doc` already saved above as resume_document canonical SOT)
        self.run_manager.save_json(run_dir, "jd.json", job_desc)
        self.run_manager.save_json(run_dir, "plan.json", plan)
        self.run_manager.save_json(run_dir, "rewrites.json", approved_proposals)

        # Groq/Ollama token usage for this run (every LLMClient.generate()
        # call made anywhere in the pipeline is recorded on the client
        # instance) — lets us see real per-run token consumption instead of
        # guessing whether a single free-tier model is enough headroom.
        # proposal_usage covers the earlier generate_proposals step (a
        # separate client instance in the UI), which makes most of the calls.
        usage_summary = None
        try:
            usage_summary = self.llm_client.get_usage_summary()
            if proposal_usage:
                usage_summary = _merge_usage(proposal_usage, usage_summary)
            self.run_manager.save_json(run_dir, "llm_usage.json", usage_summary)
        except Exception:
            pass

        # Append the final report to changes.md, below the progress log that
        # was written incrementally during the run (which is kept as-is).
        # Everything listed here reflects what was actually rendered.
        try:
            with open(report_md_path, "a", encoding="utf-8") as f:
                f.write("\n## Final Summary\n\n")
                low, high = keyword_report.target_band
                f.write(f"**Keyword match rate:** {score:.1f}% (was {initial_score:.1f}%; "
                        f"aim for {low:.0f}-{high:.0f}%)  \n")
                f.write(f"**Evidence score (requirement level):** {evidence_score:.1f} / 100\n\n")
                f.write("## Keyword Match\n\n| Keyword | Kind | Required | Found in |\n|---|---|---|---|\n")
                for row in sorted(keyword_report.rows, key=lambda r: (not r.found, -r.weight)):
                    found_in = ", ".join(row.where) if row.found else "❌ missing"
                    f.write(f"| {row.keyword} | {row.kind} | {'yes' if row.required else 'no'} | {found_in} |\n")
                f.write("\n")
                f.write(f"## Content Checks\n\n{content_report.bullets_with_metrics} of {content_report.bullets} "
                        f"bullets include a number.\n\n")
                for issue in content_report.issues:
                    f.write(f"- **{issue.check}** ({issue.where}): {issue.message}\n")
                f.write("\n")
                f.write(f"## Accepted Rewrites ({len(approved_proposals)})\n\n")
                for prop in approved_proposals:
                    f.write(f"### Bullet ({_prop_key(prop) or 'unknown'})\n")
                    f.write(f"- **Original:** {prop.original_text}\n")
                    f.write(f"- **Tailored:** {_prop_text(prop)}\n")
                    f.write(f"- **Rationale:** {prop.rationale}\n\n")
                if plan.unsupported_requirements:
                    f.write("## Unsupported Missing Requirements\n\n")
                    for req in plan.unsupported_requirements:
                        f.write(f"- {req}\n")
                if warnings:
                    f.write("\n## Validation Warnings\n\n")
                    for w in warnings:
                        f.write(f"- {w}\n")
                if usage_summary:
                    f.write("\n## LLM Usage\n\n")
                    f.write(f"- Provider: {usage_summary['provider']}\n")
                    f.write(f"- Model: {usage_summary['model']}\n")
                    f.write(f"- Calls: {usage_summary['call_count']} "
                            f"({usage_summary['success_count']} succeeded, {usage_summary['failure_count']} failed)\n")
                    f.write(f"- Tokens: {usage_summary['total_prompt_tokens']} prompt + "
                            f"{usage_summary['total_completion_tokens']} completion = "
                            f"{usage_summary['total_tokens']} total\n")
                    f.write(f"- Time in LLM calls: {usage_summary['total_duration_seconds']}s\n")
                f.write("\n## Artifact Verification\n\n")
                f.write(f"- DOCX warnings ({len(docx_warnings)}):\n")
                for w in docx_warnings:
                    f.write(f"  - {w}\n")
                f.write(f"- PDF warnings ({len(pdf_warnings)}):\n")
                for w in pdf_warnings:
                    f.write(f"  - {w}\n")
        except Exception:
            pass  # non-fatal: the run's outputs don't depend on the report

        preview_md = self.generate_preview_md(resume)

        # Determine overall success: fail if any critical QA warnings present
        critical_signals = [
            "does not exist",
            "contains no text",
            "0 bytes",
            "contains 0 pages",
            "contains no readable text",
            "Failed to parse rendered DOCX",
            "Failed to parse rendered PDF",
            "Expected candidate name",
            OutputQAValidator.ROUND_TRIP_PREFIX,
        ]

        def has_critical(warnings_list):
            return any(any(sig in w for sig in critical_signals) for w in warnings_list)

        success = True
        if has_critical(docx_warnings):
            success = False
        if pdf_res and has_critical(pdf_warnings):
            success = False

        return {
            "docx": docx_output_path,
            "pdf": pdf_output_path if pdf_res else "",
            "html": html_output_path,
            "target_pages": target_pages(resume),
            "content_lint": content_report,
            "changes_md": report_md_path,
            "alignment_score": f"{score:.1f}",
            "initial_alignment_score": f"{initial_score:.1f}",
            "evidence_score": f"{evidence_score:.1f}",
            "keyword_match": keyword_report,
            "addition_note": addition_note,
            "run_dir": run_dir,
            "preview_md": preview_md,
            "warnings": warnings,
            "docx_warnings": docx_warnings,
            "pdf_warnings": pdf_warnings,
            "success": success,
        }


def _merge_usage(first: Dict, second: Dict) -> Dict:
    """Combine two LLMClient.get_usage_summary() dicts into one."""
    merged = dict(second)
    for key in ("call_count", "success_count", "failure_count",
                "total_prompt_tokens", "total_completion_tokens", "total_tokens"):
        merged[key] = (first.get(key) or 0) + (second.get(key) or 0)
    merged["total_duration_seconds"] = round(
        (first.get("total_duration_seconds") or 0) + (second.get("total_duration_seconds") or 0), 3)
    merged["calls"] = list(first.get("calls") or []) + list(second.get("calls") or [])
    return merged
