import copy
import os
import re
import shutil
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from app.analysis.checklist import build_checklist
from app.analysis.language import english_only_note, other_language
from app.analysis.experience import future_dates, is_ongoing, parse_month, target_pages
from app.analysis.gap_questions import GapAnswer, build_questions, infer_kind
from app.analysis.jd_analyzer import JDAnalyzer
from app.analysis.keyword_match import KeywordMatcher, _contains_seq, reconcile, resume_sections, tokens
from app.analysis.matcher import EvidenceMatcher
from app.analysis.project_select import left_out_ids, remove_bullets
from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.rewriter import FAILED_STATUSES, LLMRewriter, RewriteProposal
from app.analysis.scoring import AlignmentScorer
from app.analysis.semantic_matcher import SemanticMatcher
from app.analysis.structure_extractor import StructureExtractor
from app.analysis.skills_tailor import SkillsTailor, is_trait, jd_spelling, parse_skills, skill_category
from app.analysis.summary_writer import SummaryWriter
from app.analysis.tailor_planner import TailoringPlanner
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import TailoringReport
from app.domain.resume import Experience, OtherSection, Project, Resume, ResumeBullet, Role, SectionLine
from app.domain.resume_document import ResumeDocument, ResumeSource
from app.domain.tailoring import TailoringPlan
from app.ingestion.docx import DocxParser
from app.ingestion.linkedin import LAYOUT as LINKEDIN_LAYOUT, NOTE as LINKEDIN_NOTE
from app.ingestion.pdf import PdfParser
from app.llm.client import LLMClient
from app.rendering.docx_patcher import DocxPatcher
from app.rendering.html_renderer import HtmlResumeRenderer
from app.rendering.layout import output_basename, section_order_for
from app.rendering.page_fit import PageFitter
from app.rendering.pdf_converter import PdfConverter
from app.rendering.template_renderer import TemplateRenderer
from app.services.arrange import Layout, apply_layout, default_layout, emptied, notes_for, trimmed_items
from app.services.arrange import section_order as arranged_order
from app.services.profile_store import ProfileStore
from app.services.run_manager import RunManager
from app.validation.content_lint import lint as content_lint
from app.analysis.region import apply_region
from app.analysis.cv_mode import (CV_MODES, NO_PAGE_CAP, academic_section_order, apply_cv_mode,
                                  move_appointments_from_education, suggest_cv_mode)
from app.validation.coverage import content_coverage, docx_text
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
    def __init__(self, llm_client: Optional[LLMClient] = None, keep_run: bool = True):
        """`keep_run=False` (the web app): nothing is written to data/runs, so
        an upload lives only in the visitor's session files (P9.8)."""
        self.llm_client = llm_client or LLMClient()
        self.docx_parser = DocxParser()
        self.pdf_parser = PdfParser()
        self.resume_normalizer = ResumeNormalizer()
        self.structure_extractor = StructureExtractor(self.llm_client, self.resume_normalizer)
        # Problems left in the last parse (empty = looks right). Shown by the UI.
        self.last_parse_issues: List[str] = []
        self.last_parse_notes: List[str] = []
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
        self.run_manager: Optional[RunManager] = RunManager() if keep_run else None

    def _save_run(self, run_dir: Optional[str], filename: str, data) -> None:
        """A run artifact for the CLI / eval; nothing when no run is kept (P9.8)."""
        if run_dir and self.run_manager:
            self.run_manager.save_json(run_dir, filename, data)

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
            if getattr(p, "kind", "bullet") in ("skills", "heading"):
                continue  # skills order and project headings can't be patched in place; the template shows them
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

    def _apply_gap_answers(self, resume: Resume, evidence_list: List, job_desc: JobDescription,
                           answers: List, questions: Optional[List] = None) -> List[str]:
        """Ticked keywords join the skills section; a typed answer becomes a
        bullet drafted only from the candidate's words (P3.1). Returns notes
        for the change log."""
        notes: List[str] = []
        known = {k.lower() for items in resume.skills.values() for k in items}
        # What each keyword is (P8.12): a licence goes under Certifications,
        # a degree isn't a skill.
        kinds = {r.keyword.lower(): infer_kind(r.keyword, r.kind) for r in self.keyword_matcher.match(job_desc, resume).rows} \
            if job_desc else {}
        for q in questions or []:  # the kinds the questions were asked with win
            kinds.update({k.lower(): v for k, v in (getattr(q, "kinds", None) or {}).items()})
        held = {c.get("name", "").lower() for c in resume.certifications}
        for raw in answers:
            ans = raw if isinstance(raw, GapAnswer) else GapAnswer(**raw)
            confirmed = [k for k in ans.confirmed_keywords if k.strip()]
            certs = [k for k in confirmed if kinds.get(k.lower()) == "certification" and k.lower() not in held]
            degrees = [k for k in confirmed if kinds.get(k.lower()) == "education"]
            # A trait or soft skill shows through an example, never as a skill (P9.12).
            traits = [k for k in confirmed if k not in certs and k not in degrees
                      and is_trait(k, kinds.get(k.lower(), ""))]
            if traits:
                notes.append(f"Not listed under Skills: {', '.join(traits)}. A trait shows through your work"
                             + (" (your example was added as a bullet)." if ans.answer.strip()
                                else "; write a line with a real example to include it."))
            for k in certs:
                resume.certifications.append({"name": k})
                held.add(k.lower())
                evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="certification",
                                              source_id="user_confirmed", text=k))
            if certs:
                notes.append(f"You confirmed: {', '.join(certs)} (added to Certifications)")
            if degrees:
                notes.append(f"You have {', '.join(degrees)}: if it isn't listed, add it under Education on "
                             "Check your details (a degree isn't added to Skills).")
            unexplained = [k for k in confirmed if k not in certs and k not in degrees and k not in traits]
            if unexplained and not ans.answer.strip():
                notes.append(f"Ticked without a line saying where: {', '.join(unexplained)}. A recruiter or "
                             "interviewer will ask where you used it.")
            jd_text = job_desc.raw_text if job_desc else ""
            added = [jd_spelling(k, jd_text) for k in confirmed
                     if k.lower() not in known and k not in certs and k not in degrees and k not in traits]
            placed: Dict[str, List[str]] = {}
            for k in added:  # each under a category of its own type (P9.12)
                category = skill_category(resume.skills, k)
                resume.skills.setdefault(category, []).append(k)
                placed.setdefault(category, []).append(k)
                known.add(k.lower())
                evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="skill",
                                              source_id="user_confirmed", text=k))
            if placed:
                notes.append("You confirmed: " + "; ".join(f"{', '.join(v)} (added to {c})" for c, v in placed.items()))
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
    MAX_PROJECT_BANK_LINES = 40  # a job added on Check details: notes to choose from (P10.13)
    _ACHIEVEMENT_HEADING = re.compile(r"^(?:key\s+)?(?:achievements?|awards?(?:\s+and\s+recognition)?|honou?rs|recognition)$", re.I)

    @classmethod
    def _project_lines(cls, text: str) -> List[Tuple[Optional[str], str]]:
        """An added job's notes -> (project, line) pairs. A short line ending
        in ":" or starting with "#" names a project; the lines under it are
        its bullets. Lines before any heading sit directly under the job."""
        out: List[Tuple[Optional[str], str]] = []
        group = None
        for raw in (text or "").splitlines():
            line = raw.strip()
            heading = re.match(r"^#+\s*(.+)$", line) or re.match(r"^(.{2,80}):$", line)
            if heading and len(heading.group(1).split()) <= 10:
                group = heading.group(1).strip().rstrip(":").strip()
                continue
            for chunk in cls._split_description(line):
                out.append((group, chunk))
        if not any(g for g, _ in out):  # no headings: the old behaviour (one paragraph splits into sentences)
            out = [(None, chunk) for chunk in cls._split_description(text)]
        return out

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

    @classmethod
    def _new_experience(cls, role_data: Dict, description_text: str) -> Experience:
        """An empty job from the "add a job" fields, validated."""
        company, title, start, end = cls.validate_new_role(role_data, description_text)
        return Experience(id=f"exp_user_{uuid4().hex[:6]}", company=company, title=title,
                          location=(role_data.get("location") or "").strip() or None,
                          start_date=start, end_date=end, roles=[Role(title=title, start_date=start, end_date=end)])

    @staticmethod
    def _insert_by_date(resume: Resume, exp: Experience) -> None:
        """Place a job in date order: current jobs first, then most recent start."""
        today = date.today()

        def sort_key(e: Experience):
            first = (e.all_roles() or [Role(title="")])[0]
            ongoing = is_ongoing(first.end_date)
            started = parse_month(first.start_date, is_end=False, today=today) or (0, 0)
            return (not ongoing, (-started[0], -started[1]))
        new_key = sort_key(exp)
        position = next((i for i, e in enumerate(resume.experience) if sort_key(e) > new_key), len(resume.experience))
        resume.experience.insert(position, exp)

    def add_new_role(self, resume: Resume, evidence_list: List, job_desc: JobDescription,
                     role_data: Dict, description_text: str) -> Tuple[Resume, List, List[str]]:
        """Add a job the resume doesn't have yet (P3.3). Each chunk of the
        user's description is polished into a bullet that may use only JD
        keywords already in that chunk, then fact-checked against it; if the
        polish adds anything, the user's own wording is used. The job goes
        in date order (current jobs first, then most recent start).
        Mutates `resume`; returns (resume, evidence_list, notes)."""
        exp = self._new_experience(role_data, description_text)
        company, title, start, end = exp.company, exp.title, exp.start_date, exp.end_date

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

        self._insert_by_date(resume, exp)
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

    COVERAGE_PREFIX = "Content coverage:"

    @staticmethod
    def _coverage(raw_doc, resume_doc: ResumeDocument, original: Resume, before_fit: Resume, docx_path: str,
                  extra_removed: str = ""):
        """Content coverage of the rendered DOCX against the uploaded file (P8.2)."""
        final = resume_doc.resume
        original_text = {b.source_location_id: b.text for s in [*original.experience, *original.projects]
                         for b in s.bullets if b.source_location_id}
        final_bullets = {b.source_location_id: b.text for s in [*final.experience, *final.projects]
                         for b in s.bullets if b.source_location_id}
        fit_bullets = {b.source_location_id for s in [*before_fit.experience, *before_fit.projects]
                       for b in s.bullets if b.source_location_id}
        reworded = {sid for sid, text in final_bullets.items() if text != original_text.get(sid, text)}
        reworded |= set(resume_doc.user_changed_blocks)
        if (final.summary or "") != (original.summary or ""):
            reworded |= {b.id for b in raw_doc.blocks if b.text.strip() and b.text.strip() in (original.summary or "")}
        trimmed = fit_bullets - set(final_bullets)
        final_groups = {b.group for e in final.experience for b in e.bullets if b.group}
        dropped_interests = [i for i in before_fit.interests if i not in final.interests]
        removed = [*dropped_interests,
                   # a one-line "Interests: Chess • Cycling" takes its label along
                   *(["Interests"] if dropped_interests else []),
                   *[t for p in before_fit.projects if p not in final.projects
                     for t in [p.name, *(b.text for b in p.bullets)]],
                   # a job sub-section page-fit removed takes its heading along
                   *{b.group for e in before_fit.experience for b in e.bullets if b.group} - final_groups,
                   extra_removed]
        return content_coverage(raw_doc.blocks, docx_text(docx_path), heading_texts=resume_doc.section_headings,
                                reworded_blocks=reworded, trimmed_blocks=trimmed, removed_text="\n".join(removed),
                                ignore_words=list(original.skills))

    @staticmethod
    def _rename_headings(resume: Resume, resume_doc: ResumeDocument, raw_doc, approved: List, kept_projects: set,
                         note: Callable[[str], None]) -> set:
        """Rename each project the user accepted a new heading for; the old
        heading line of the file counts as reworded, not lost. Returns the
        kept-project keys under their new names."""
        renamed = 0
        for p in approved:
            if getattr(p, "kind", "bullet") != "heading":
                continue
            exp_id, _, old = (getattr(p, "target_semantic_id", "") or "").partition("::")
            new = (getattr(p, "proposed_text", None) or "").strip()
            exp = next((e for e in resume.experience if e.id == exp_id), None)
            if not exp or not new or not old:
                continue
            hits = [b for b in exp.bullets if b.group == old]
            for b in hits:
                b.group = new
            if hits:
                renamed += 1
                if f"{exp_id}::{old}" in kept_projects:
                    kept_projects = (kept_projects - {f"{exp_id}::{old}"}) | {f"{exp_id}::{new}"}
                if raw_doc is not None:
                    resume_doc.user_changed_blocks.extend(
                        b.id for b in raw_doc.blocks if re.sub(r"\s+", " ", b.text).strip() == old)
        if renamed:
            note(f"Renamed {renamed} project heading(s) to plain, searchable titles")
        return kept_projects

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
        raw_doc = self.read_file(resume_path)
        return (raw_doc, *self.normalize_raw(raw_doc))

    def read_file(self, resume_path: str):
        """The uploaded file as raw blocks, or UnreadableFile with a message
        the person can act on (P8.22) instead of a crash."""
        import zipfile
        from docx.opc.exceptions import PackageNotFoundError
        from app.ingestion import errors
        from app.ingestion.text import TextParser
        lower = resume_path.lower()
        if os.path.getsize(resume_path) == 0:
            raise errors.UnreadableFile(errors.NO_TEXT)
        if lower.endswith(".txt"):
            return TextParser().parse(resume_path)
        if lower.endswith(".pdf"):
            import pymupdf
            try:
                with pymupdf.open(resume_path) as pdf:
                    if pdf.needs_pass or pdf.is_encrypted:
                        raise errors.UnreadableFile(errors.LOCKED_PDF)
                    has_images = any(page.get_images() for page in pdf)
            except errors.UnreadableFile:
                raise
            except Exception:
                raise errors.UnreadableFile(errors.DAMAGED_PDF)
            raw_doc = self.pdf_parser.parse(resume_path)
            if len(raw_doc.raw_text.strip()) < 40:
                raise errors.UnreadableFile(errors.SCANNED_PDF if has_images else errors.NO_TEXT)
            return raw_doc
        try:
            raw_doc = self.docx_parser.parse(resume_path)
        except (PackageNotFoundError, zipfile.BadZipFile, KeyError):
            raise errors.UnreadableFile(errors.DAMAGED_DOCX)
        if not raw_doc.raw_text.strip():
            raise errors.UnreadableFile(errors.NO_TEXT)
        return raw_doc

    def apply_bank(self, parsed, bank_path: Optional[str] = None, bank_text: Optional[str] = None):
        """Read the owner's project notes (P11.1) and merge them into the
        parsed resume. Returns (parsed, notes for Check details, lines held
        back to verify). Without the AI the notes aren't read, and the note
        says so."""
        from app.analysis.project_bank import bank_lines, merge_bank, read_bank
        text = bank_text or ""
        if bank_path:
            raw = self.read_file(bank_path)
            text = "\n".join(b.text for b in raw.blocks) if getattr(raw, "blocks", None) else raw.raw_text
        lines = bank_lines(text)
        if not lines:
            return parsed, [], []
        bank = read_bank(lines, self.llm_client)
        if bank is None:
            return parsed, ["Your project notes couldn't be read just now (the AI is needed for that). "
                            "You can paste them under a job on this page instead."], []
        raw_doc, resume_doc, evidence = self._copy_parsed(parsed)
        resume = resume_doc.resume

        def new_job(role):
            return self._new_experience(role, "notes")
        notes = merge_bank(resume, evidence, bank, new_experience=new_job)
        # Jobs from the notes go in date order, like any added job.
        added = [e for e in resume.experience if e.id.startswith("exp_user_")]
        for exp in added:
            resume.experience.remove(exp)
            self._insert_by_date(resume, exp)
        return (raw_doc, resume_doc, evidence), notes, list(bank.to_verify)

    def normalize_raw(self, raw_doc):
        resume_doc, evidence_list = self.resume_normalizer.normalize(raw_doc)
        # Information about how the file was read, shown apart from the
        # problems on Check details (P10.11).
        self.last_parse_notes: List[str] = []
        if raw_doc.layout:
            # Structure read from a known layout (the LinkedIn export, P10.1):
            # an LLM re-label can't improve it, and a role with no description
            # is normal there, so it isn't called a reading problem (P10.11;
            # the content checks on Results still suggest bullets for it).
            self.last_parse_issues = [
                issue for issue in self.structure_extractor.problems(resume_doc.resume, evidence_list, raw_doc)
                if not issue.startswith("experience without bullets")]
            if raw_doc.layout == LINKEDIN_LAYOUT:
                self.last_parse_notes.append(LINKEDIN_NOTE)
        else:
            resume_doc, evidence_list, self.last_parse_issues = self.structure_extractor.improve(
                raw_doc, resume_doc, evidence_list,
            )
        # Shown on "Check your details"; not a reason to ask the LLM (P8.6).
        self.last_parse_issues = list(self.last_parse_issues) + future_dates(resume_doc.resume)
        language = other_language(raw_doc.raw_text)
        if language:  # P8.25
            self.last_parse_issues.append(english_only_note("resume", language))
        return resume_doc, evidence_list

    @staticmethod
    def _copy_parsed(parsed):
        """Deep copies, so a parse kept in UI session state is never mutated."""
        raw_doc, resume_doc, evidence_list = parsed
        return raw_doc, resume_doc.model_copy(deep=True), [e.model_copy(deep=True) for e in evidence_list]

    def preview_keyword_match(self, parsed, job_desc: JobDescription, proposals: List[Dict],
                              left_out: Optional[List[str]] = None):
        """Match rate if these proposals were applied (P3.4 "recalculate"):
        no LLM, no files. `proposals` are dicts with kind, target_semantic_id
        and proposed_text, i.e. the ticked (and possibly edited) ones.
        `left_out`: bullet ids of projects left out (P10.13)."""
        resume = parsed[1].resume.model_copy(deep=True)
        if left_out:
            remove_bullets(resume, left_out)
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
        start_date, end_date}, ...]}], "removed_jobs": [id, ...], "added_jobs":
        [{company, title, location, current, start_date, end_date, description}]}.
        Existing bullet text is never touched here; an added job's bullets are
        the user's own lines, verbatim, so the draft step can tailor them like
        any other. Raises ValueError (user-facing) for an incomplete added job.
        Returns (parsed, changed)."""
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
        if any(c.startswith("candidate.") for c in changed):
            resume_doc.user_changed_blocks.extend(resume_doc.header_blocks)  # P8.2: the user's edit, not a loss

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
                         # A role read with dates but no title is kept.
                         for r in fix["roles"] if any((r.get(k) or "").strip()
                                                      for k in ("title", "start_date", "end_date"))]
                if [r.model_dump() for r in roles] != [r.model_dump() for r in exp.all_roles()]:
                    first = roles[0] if roles else Role(title="")
                    exp.title, exp.start_date, exp.end_date = first.title, first.start_date, first.end_date
                    exp.roles = roles if len(roles) > 1 else []
                    changed.append(f"{exp.id}.roles")
            if any(c.startswith(f"{exp.id}.") for c in changed):
                resume_doc.user_changed_blocks.extend(exp.source_blocks)
            # Experience evidence reads "<company>: <bullet>"; keep it in step.
            new_context = exp.company or exp.title or "Experience"
            if new_context != old_context:
                bullet_ids = {b.id for b in exp.bullets}
                for ev in evidence_list:
                    if ev.source_id in bullet_ids and ev.text.startswith(old_context):
                        ev.text = new_context + ev.text[len(old_context):]

        removed = set(corrections.get("removed_jobs") or [])
        if resume.experience and set(by_id) <= removed and not corrections.get("added_jobs"):
            raise ValueError("Keep at least one job, or add the right one.")
        if removed & set(by_id):
            for e in resume.experience:
                if e.id in removed:  # removed by the user: not counted as lost (P8.2)
                    resume_doc.user_changed_blocks.extend(e.source_blocks)
                    resume_doc.user_changed_blocks.extend(b.source_location_id for b in e.bullets
                                                          if b.source_location_id)
            gone = {b.id for e in resume.experience if e.id in removed for b in e.bullets}
            resume.experience = [e for e in resume.experience if e.id not in removed]
            evidence_list = [ev for ev in evidence_list if ev.source_id not in gone]
            changed.extend(f"{i}.removed" for i in sorted(removed & set(by_id)))

        # Validate every added job before changing anything.
        added = [(job, self._new_experience(job, job.get("description", "")))
                 for job in corrections.get("added_jobs") or []]
        for job, exp in added:
            lines = self._project_lines(job.get("description", ""))[:self.MAX_PROJECT_BANK_LINES]
            for n, (group, line) in enumerate(lines, start=1):
                if group and self._ACHIEVEMENT_HEADING.match(group):
                    # "Achievements:" in the notes: a win or award, not a project
                    # under the job (P10.13). It goes to Achievements as written.
                    resume.achievements.append(line)
                    evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="achievement",
                                                  source_id=f"{exp.id}_a{n:02d}", text=line))
                    continue
                exp.bullets.append(ResumeBullet(id=f"{exp.id}_b{n:02d}", text=line, group=group))
                evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="experience",
                                              source_id=f"{exp.id}_b{n:02d}", text=f"{exp.company}: {line}"))
            if not exp.bullets:
                raise ValueError(f"Describe at least one thing you did at {exp.company}, not only achievements.")
            self._insert_by_date(resume, exp)
            changed.append(f"{exp.id}.added")

        # Lines the parse placed nowhere, assigned by the user (P8.26).
        blocks = {b.id: b for b in raw_doc.blocks} if raw_doc is not None else {}
        jobs = {e.id: e for e in resume.experience}
        for item in corrections.get("placed") or []:
            block, target = blocks.get(item.get("id")), item.get("target")
            text = re.sub(r"\s+", " ", block.text).strip() if block else ""
            if not text or not target:
                continue
            if target == "summary":
                resume.summary = f"{resume.summary} {text}".strip() if resume.summary else text
                evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="summary",
                                              source_id=block.id, source_location_id=block.id, text=text))
            elif target == "skills":
                items = [i.strip() for i in re.split(r"[,;|]", text) if i.strip()]
                resume.skills.setdefault("Skills", []).extend(items)
            elif target in jobs:
                exp = jobs[target]
                bid = f"{exp.id}_bp{len(exp.bullets) + 1:02d}"
                exp.bullets.append(ResumeBullet(id=bid, text=text, source_location_id=block.id))
                evidence_list.append(Evidence(id=f"ev_user_{uuid4().hex[:6]}", source_type="experience", source_id=bid,
                                              source_location_id=block.id, text=f"{exp.company or exp.title}: {text}"))
            else:  # "other": kept as written under its own heading
                section = next((s for s in resume.other_sections if s.id == "sec_placed"), None)
                if section is None:
                    section = OtherSection(id="sec_placed", heading="Additional information")
                    resume.other_sections.append(section)
                section.lines.append(SectionLine(text=text, source_location_id=block.id))
            changed.append(f"placed.{block.id}")

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
        matches = reconcile(matches, self.keyword_matcher.match(job_desc, resume))
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
            conditions=[c.model_dump() for c in build_checklist(job_desc, resume)],
            warnings=[english_only_note(what, lang) for what, lang in (
                ("resume", other_language(raw_doc.raw_text)), ("job description", other_language(jd_text))) if lang],
        )

    def generate_proposals(self, resume_path: str, jd_text: str, suggestion_limit: int = 5,
                           parsed=None, progress: Optional[Callable[[str], None]] = None) -> Dict:
        """Generate rewrite proposals without applying them, plus questions
        about JD keywords the resume doesn't show (P3.1).

        Returns {"proposals": [...], "gap_questions": [...],
        "alignment_score": float, ...}. Useful for UI review flows.
        """
        step = _progress(progress)
        if self.llm_client is not None and progress is not None:
            self.llm_client.on_wait = step  # say why a step pauses (P8.23)
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
        matches = reconcile(matches, self.keyword_matcher.match(job_desc, resume))
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
            res = self.validator.validate_proposal(prop, evidence_list, jd_keywords=job_desc.keywords,
                                                 jd_text=job_desc.raw_text)
            prop.validation = res.verdict
            prop.validation_note = "; ".join(res.warnings) or None

        # Suggest-and-confirm (P3.1): ask about what the JD wants and the
        # resume doesn't show, instead of drafting experience the candidate
        # may not have. Built in code, no LLM call.
        gap_questions = build_questions(
            job_desc, keyword_report, limit=suggestion_limit,
            resume_text="\n".join(text for _label, text in resume_sections(resume)),
            education_text=" ".join(f"{e.degree} {e.institution} {' '.join(e.details)}" for e in resume.education))
        self._prefill_from_profile(gap_questions)

        llm_available = bool(self.llm_client and self.llm_client.is_available())
        failed = [p for p in proposals if getattr(p, "status", None) in FAILED_STATUSES]
        return {
            "proposals": proposals,
            "gap_questions": gap_questions,
            "conditions": build_checklist(job_desc, resume),
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
            # P10.13: projects kept and left out per job, with the reason.
            "projects": list(plan.projects),
            "projects_ranked_by_impact": plan.ranked_by_impact,
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
        conditions_confirmed: Optional[List[str]] = None,
        region: Optional[str] = None,
        cv_mode: Optional[str] = None,
        left_out_projects: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """`region` ("us", "uk_eu", "india", "other", P10.3) sets the paper
        and date style; None keeps the template's default (A4, "Jan 2022").
        `cv_mode` ("standard", "academic", "federal", P10.5): None takes the
        one the resume and JD suggest (the CLI and eval have no one to ask).
        `left_out_projects` (P10.13): project keys the user left out on Review;
        None leaves out the ones the planner didn't choose."""
        run_dir = self.run_manager.create_run(resume_path, jd_text) if self.run_manager else None
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
        if self.llm_client is not None and progress is not None:
            self.llm_client.on_wait = step  # say why a step pauses (P8.23)

        def _append_progress(msg: str) -> None:
            step(msg)
            ts = datetime.utcnow().isoformat() + "Z"
            try:
                with open(report_md_path, "a", encoding="utf-8") as pf:
                    pf.write(f"- [{ts}] {msg}\n")
            except Exception:
                # Never fail tailoring flow due to progress logging
                pass
        
        if run_dir:  # the CLI log; the web keeps no run folder (P9.8)
            _append_progress("Run created: " + run_dir)

        is_pdf = resume_path.lower().endswith((".pdf", ".txt"))  # nothing to patch in place
        if is_pdf:
            mode = "ATS_DEFAULT"  # Force ATS reconstruction for PDF and text inputs
        if parse_corrected and mode == "PRESERVE":
            # Header/role corrections have no place to go in an in-place
            # patch of the original file; only the template shows them.
            mode = "ATS_DEFAULT"
        if parsed is None:
            raw_doc = self.read_file(resume_path)

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
        if mode == "PRESERVE" and any(b.id.startswith("txb_") for b in raw_doc.blocks):
            # Text in text boxes can't be patched in place (P8.7).
            mode = "ATS_DEFAULT"
            _append_progress("Your file keeps some text in text boxes, so the standard template is used")
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
        matches = reconcile(matches, self.keyword_matcher.match(job_desc, resume))
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
            # Nobody reviewed these: an opt-in proposal (a summary replacing
            # the user's own) stays out unless chosen (Stage I review).
            proposals = [p for p in proposals if not getattr(p, "opt_in", False)]
            _append_progress(f"Planner created plan with {len(plan.actions)} actions; generated {len(proposals)} proposals")

        approved_proposals: List[RewriteProposal] = []
        warnings: List[str] = []

        # Keep copies of the pre-tailoring state: for structural validation,
        # and to roll back if Strict Factual Mode withholds the rewrites.
        import copy
        original_resume = copy.deepcopy(resume)
        original_evidence = copy.deepcopy(evidence_list)

        rejected_count = 0
        strict_withheld = False
        for prop in proposals:
            if getattr(prop, "user_edited", False):
                # The user wrote or changed this text themselves in the
                # review form: accept it as user-attested, and say so.
                approved_proposals.append(prop)
                warnings.append(
                    f"Kept your edited text as written (not fact-checked): {getattr(prop, 'proposed_text', '')[:80]}"
                )
                continue
            res = self.validator.validate_proposal(prop, evidence_list, jd_keywords=job_desc.keywords,
                                                 jd_text=job_desc.raw_text)
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
            strict_withheld = True
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

        # Choose projects, not lines (P10.13): a job keeps its best few
        # projects. Only the template can drop them; a DOCX patch keeps all.
        left_out_text: List[str] = []
        leave_out = left_out_ids(plan.projects, left_out_projects)
        # Kept projects stay through page-fit, shortened at most (P10.13).
        kept_projects = {c.key for c in plan.projects if not set(c.bullet_ids) <= set(leave_out)}
        # Accepted project headings (plain, searchable titles, P10.13).
        if mode != "PRESERVE" or is_pdf:
            kept_projects = self._rename_headings(resume, resume_doc, raw_doc, approved_proposals, kept_projects,
                                                  _append_progress)
        if leave_out and (mode != "PRESERVE" or is_pdf):
            left_out_text = remove_bullets(resume, leave_out)
            gone = set(leave_out)
            evidence_list[:] = [ev for ev in evidence_list if ev.source_id not in gone]
            names = [c.name for c in plan.projects if set(c.bullet_ids) <= gone]
            _append_progress(f"Left out {len(names)} project(s) as less "
                             f"{'impactful' if plan.ranked_by_impact else 'relevant'} for this job: "
                             f"{', '.join(names)}. Bring any back on Review")

        # Most relevant bullets first within each sub-heading (P1.3). Only the
        # template can move bullets; an in-place DOCX patch keeps the order.
        # Never silently (P8.14): only when the user accepted changes, and the
        # Arrange step shows it ("sorted by job relevance") and can undo it.
        if (mode != "PRESERVE" or is_pdf) and approved_proposals:
            reordered = self._apply_bullet_order(resume, plan.bullet_order)
            if reordered:
                _append_progress(f"Sorted bullets by job relevance in {reordered} role(s); "
                                 "change or restore the order in Arrange")

        # Fold in any free-text content the candidate typed in the UI (a
        # project, an achievement, a skill) as one more polished, evidence-
        # grounded bullet, then recompute the alignment score so it reflects
        # everything just applied — the rewrites above and this addition.
        # Answers to the gap questions (P3.1): only what the candidate
        # confirmed, in their own words.
        gap_notes = self._apply_gap_answers(resume, evidence_list, job_desc, gap_answers or [], gap_questions)
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
        matches = reconcile(matches, self.keyword_matcher.match(job_desc, resume))
        keyword_report = self.keyword_matcher.match(job_desc, resume)
        score = keyword_report.rate
        evidence_score = self.scorer.calculate_score(matches, job_desc.requirements)
        _append_progress(f"Recomputed keyword match rate after applying changes: {score:.1f}% (was {initial_score:.1f}%)")

        # Education goes first for someone early in their career (P2.1).
        resume_doc.presentation.section_order = section_order_for(resume)
        if region:
            apply_region(resume_doc.presentation, region)
        apply_cv_mode(resume_doc.presentation,
                      cv_mode if cv_mode in CV_MODES else suggest_cv_mode(resume, clean_jd_text).mode)
        capped = resume_doc.presentation.cv_mode not in NO_PAGE_CAP
        if resume_doc.presentation.cv_mode == "academic":  # P10.6: CV order, appointments as jobs
            for note in move_appointments_from_education(resume):
                _append_progress(note)
                warnings.append(note)
            resume_doc.presentation.section_order = academic_section_order(resume)
        fit = None

        if mode == "PRESERVE" and not is_pdf:
            self.docx_patcher.patch(resume_path, raw_doc.document_map,
                                    self._patchable(approved_proposals, original_evidence), docx_output_path)
            _append_progress(f"DOCX preserve-mode patch applied to {docx_output_path}")
        else:
            # Render, count pages and trim the least relevant content until
            # it fits the page target (P2.4). This also produces the PDF.
            page_target = target_pages(resume)
            before_fit = copy.deepcopy(resume)
            full_doc = resume_doc.model_copy(deep=True)  # for Arrange (P8.13): nothing trimmed yet
            relevance = self._fit_relevance(resume, plan)
            trim_candidates = {a.source_id for a in plan.actions if a.trim_candidate}
            fit = PageFitter(self._render_template).fit(
                resume_doc, docx_output_path, output_dir, page_target,
                relevance=relevance, trim_candidates=trim_candidates, trim=capped, kept_projects=kept_projects,
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
        content_report = content_lint(resume, region=region)

        # Did every line of the uploaded file reach the output? (P8.2) Only
        # the template rebuilds the document; a PRESERVE patch keeps it all.
        coverage = None
        if fit:
            coverage = self._coverage(raw_doc, resume_doc, original_resume, before_fit, docx_output_path,
                                      extra_removed="\n".join(left_out_text))
            if coverage.lost:
                shown = "; ".join(f"\"{line[:70]}\"" for line in coverage.lost[:5])
                more = f" and {len(coverage.lost) - 5} more" if len(coverage.lost) > 5 else ""
                warnings.append(f"{self.COVERAGE_PREFIX} {len(coverage.lost)} line(s) from your resume are missing "
                                f"from the output: {shown}{more}")
            _append_progress(f"Content coverage: {coverage.pct}% of {coverage.counted} source lines kept "
                             f"({coverage.reworded} reworded, {coverage.trimmed} trimmed to fit, "
                             f"{len(coverage.lost)} lost)")

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
            self._save_run(run_dir, "resume_document.json", resume_doc)
        except Exception:
            pass
        # Also save the legacy resume.json for compatibility
        self._save_run(run_dir, "resume.json", resume)
        # (Note: `resume_doc` already saved above as resume_document canonical SOT)
        self._save_run(run_dir, "jd.json", job_desc)
        self._save_run(run_dir, "plan.json", plan)
        self._save_run(run_dir, "rewrites.json", approved_proposals)

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
            self._save_run(run_dir, "llm_usage.json", usage_summary)
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
                # Only real changes are listed; a bullet the AI left as it was is
                # counted, not shown as a "rewrite" with the same text twice (P9.19).
                reworded = [p for p in approved_proposals
                            if " ".join(_prop_text(p).split()) != " ".join((p.original_text or "").split())]
                f.write(f"## Accepted Rewrites ({len(reworded)})\n\n")
                kept = len(approved_proposals) - len(reworded)
                if kept:
                    f.write(f"Kept as written ({kept}): the AI found nothing to improve.\n\n")
                for prop in reworded:
                    f.write(f"### Bullet ({_prop_key(prop) or 'unknown'})\n")
                    f.write(f"- **Original:** {prop.original_text}\n")
                    f.write(f"- **Tailored:** {_prop_text(prop)}\n")
                    f.write(f"- **Rationale:** {prop.rationale}\n\n")
                if conditions_confirmed:
                    # P8.20: the user's own word; not on the resume, not in the score.
                    f.write("## Job conditions you confirmed\n\n")
                    for line in conditions_confirmed:
                        f.write(f"- {line}\n")
                    f.write("\n")
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
        ]

        def has_critical(warnings_list):
            return any(any(sig in w for sig in critical_signals) or OutputQAValidator.is_serious(w)
                       for w in warnings_list)

        # Content lost from the uploaded file fails the run, however clean
        # the file reads back (P8.2).
        success = not (coverage and coverage.lost)
        if has_critical(docx_warnings):
            success = False
        if pdf_res and has_critical(pdf_warnings):
            success = False

        applied = {
            "bullets": sum(1 for p in approved_proposals if getattr(p, "kind", "bullet") == "bullet"
                           and _prop_text(p).strip() != (getattr(p, "original_text", "") or "").strip()),
            "bullets_edited": sum(1 for p in approved_proposals if getattr(p, "kind", "bullet") == "bullet"
                                  and getattr(p, "user_edited", False)),
            "summary": any(getattr(p, "kind", "") == "summary" for p in approved_proposals),
            "skills": any(getattr(p, "kind", "") == "skills" for p in approved_proposals),
            "rejected": rejected_count,
            "strict_withheld": strict_withheld,
        }
        arrange_state = None
        if fit:
            layout = default_layout(full_doc.resume, full_doc.presentation.section_order)
            layout.region = full_doc.presentation.region
            layout.cv_mode = full_doc.presentation.cv_mode
            arrange_state = {
                "full_doc": full_doc, "original": original_resume, "raw_doc": raw_doc, "job_desc": job_desc,
                "relevance": relevance, "trim_candidates": trim_candidates, "initial_score": initial_score,
                "applied": applied, "changes_md": report_md_path, "default_layout": layout,
                "trimmed": trimmed_items(before_fit, resume),
                "left_out_text": left_out_text,  # P10.13: left out on Review, not lost
                "kept_projects": kept_projects,
            }

        return {
            "arrange": arrange_state,
            "docx": docx_output_path,
            "pdf": pdf_output_path if pdf_res else "",
            "html": html_output_path,
            "target_pages": target_pages(resume) if capped else None,
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
            "coverage": coverage.as_dict() if coverage else None,
            # What really went into the files (P5.5), for an honest summary.
            "applied": applied,
        }

    def arrange(self, state: Dict, layout: "Layout", output_dir: str,
                progress: Optional[Callable[[str], None]] = None) -> Dict:
        """Re-render the tailored resume as the user arranged it (P8.13–P8.16):
        section and entry order, bullet order within each job, hidden
        sections, removed or restored bullets, their own wording, the page
        target. No LLM call. Runs page-fit (unless "don't trim"), the ATS
        round-trip and the content coverage check like a tailoring run."""
        step = _progress(progress)
        full_doc, original, raw_doc, job_desc = state["full_doc"], state["original"], state["raw_doc"], state["job_desc"]
        resume = apply_layout(full_doc.resume, layout)
        doc = full_doc.model_copy(deep=True)
        doc.resume = resume
        doc.presentation.section_order = arranged_order(layout, resume)
        doc.presentation.compact = False
        if layout.region:  # switched in Arrange (P10.3); otherwise the run's
            apply_region(doc.presentation, layout.region)
        if layout.cv_mode:  # P10.5
            apply_cv_mode(doc.presentation, layout.cv_mode)
        # Academic and federal CVs run to their full length unless the user picks a page target.
        uncapped = doc.presentation.cv_mode in NO_PAGE_CAP and layout.page_target is None
        # The user's removals and edits are theirs, not losses (P8.2).
        full = full_doc.resume
        removed_ids = set(layout.removed_bullets)
        hidden = set(layout.hidden_sections)
        gone_owners = set(emptied(full, layout))
        changed = list(full_doc.user_changed_blocks)
        for key in ("experience", "projects"):
            for o in getattr(full, key):
                whole = key in hidden or o.id in gone_owners  # the whole entry is out, header lines too
                if whole:
                    changed += getattr(o, "source_blocks", [])
                changed += [b.source_location_id for b in o.bullets if b.source_location_id and (
                    whole or b.id in removed_ids or (layout.edits.get(b.id) or "").strip())]
        doc.user_changed_blocks = changed
        # Sub-headings the user emptied go with their bullets.
        kept_groups = {b.group for e in resume.experience for b in e.bullets if b.group}
        hidden_text = "\n".join([_hidden_text(full, layout), *state.get("left_out_text", []),
                                 *({b.group for e in full.experience for b in e.bullets if b.group} - kept_groups)])

        base_name = output_basename(resume, job_desc.company) or "tailored_resume"
        docx_path = os.path.join(output_dir, f"{base_name}.docx")
        html_path = os.path.join(output_dir, f"{base_name}.html")
        page_target = layout.page_target or target_pages(resume)
        before_fit = copy.deepcopy(resume)
        step("Rendering your arrangement")
        fit = PageFitter(self._render_template).fit(
            doc, docx_path, output_dir, page_target, relevance=state["relevance"],
            trim_candidates=state["trim_candidates"],
            pinned=set(layout.pinned) | {b for b, t in layout.edits.items() if (t or "").strip()},  # your words stay
            trim=layout.trim and not uncapped, kept_projects=state.get("kept_projects"))
        warnings: List[str] = list(fit.notes)
        if not layout.trim and fit.pages and fit.pages > page_target:
            warnings.append(f"{fit.pages} pages (not trimmed, as you chose).")
        try:
            self.html_renderer.write_html(doc, html_path)
        except Exception:
            pass
        step("Checking the files read back")
        docx_warnings = self.qa_validator.validate_docx(docx_path, expected_candidate_name=resume.candidate.name)
        docx_warnings += self.qa_validator.round_trip(docx_path, resume)
        pdf_warnings: List[str] = []
        if fit.pdf_path:
            pdf_warnings = self.qa_validator.validate_pdf(fit.pdf_path, expected_candidate_name=resume.candidate.name)
            pdf_warnings += self.qa_validator.round_trip(fit.pdf_path, resume)
        coverage = self._coverage(raw_doc, doc, original, before_fit, docx_path, extra_removed=hidden_text)
        if coverage.lost:
            shown = "; ".join(f"\"{line[:70]}\"" for line in coverage.lost[:5])
            warnings.append(f"{self.COVERAGE_PREFIX} {len(coverage.lost)} line(s) from your resume are missing "
                            f"from the output: {shown}")
        notes = notes_for(layout, full, original)
        warnings = notes + warnings + docx_warnings + pdf_warnings
        keyword_report = self.keyword_matcher.match(job_desc, resume)
        try:
            # The tailoring log plus this arrangement only, rewritten each time.
            if "changes_base" not in state:
                with open(state["changes_md"], encoding="utf-8") as f:
                    state["changes_base"] = f.read()
            with open(state["changes_md"], "w", encoding="utf-8") as f:
                f.write(state["changes_base"])
                f.write("\n## Arranged by you\n\n")
                f.write(f"- Section order: {', '.join(doc.presentation.section_order)}\n")
                for label, items in (("Hidden", layout.hidden_sections), ("Bullets removed", layout.removed_bullets),
                                     ("Kept in (never trimmed)", layout.pinned), ("Your own wording", list(layout.edits))):
                    if items:
                        f.write(f"- {label}: {', '.join(items)}\n")
                for w in warnings:
                    f.write(f"- {w}\n")
        except Exception:
            pass
        critical = any(OutputQAValidator.is_serious(w) for w in docx_warnings + pdf_warnings)
        state["trimmed"] = trimmed_items(before_fit, resume)
        return {
            "docx": docx_path, "pdf": fit.pdf_path or "", "html": html_path, "changes_md": state["changes_md"],
            "target_pages": None if uncapped else page_target, "content_lint": content_lint(resume, region=doc.presentation.region),
            "alignment_score": f"{keyword_report.rate:.1f}",
            "initial_alignment_score": f"{state['initial_score']:.1f}", "keyword_match": keyword_report,
            "warnings": warnings, "docx_warnings": docx_warnings, "pdf_warnings": pdf_warnings,
            "success": not coverage.lost and not critical, "coverage": coverage.as_dict(),
            "applied": state["applied"], "addition_note": None, "pages": fit.pages, "arrange": state,
        }


def _hidden_text(full: Resume, layout) -> str:
    """Text of the sections the user hid, so coverage counts it as their choice."""
    parts: List[str] = [k for k in layout.hidden_sections if not k.startswith("other:")]  # "Interests: ..."
    hidden = set(layout.hidden_sections)
    if "summary" in hidden and full.summary:
        parts.append(full.summary)
    for key in ("certifications",):
        if key in hidden:
            parts += [" ".join(v for v in c.values() if v) for c in full.certifications]
    for key in ("achievements", "interests"):
        if key in hidden:
            parts += list(getattr(full, key))
    if "skills" in hidden:
        parts += [f"{c}: {', '.join(v)}" for c, v in full.skills.items()]
    if "education" in hidden:
        parts += [f"{e.degree} {e.institution} {e.dates or ''} {' '.join(e.details)}" for e in full.education]
    for key in ("experience", "projects"):
        if key in hidden:
            for o in getattr(full, key):
                parts.append(" ".join([getattr(o, "company", "") or getattr(o, "name", ""), getattr(o, "title", "") or "",
                                       getattr(o, "location", "") or "", *(b.text for b in o.bullets), *getattr(o, "details", [])]))
    for sec in full.other_sections:
        if f"other:{sec.id}" in hidden:
            parts += [sec.heading, *(l.text for l in sec.lines)]
    return "\n".join(parts)


def _merge_usage(first: Dict, second: Dict) -> Dict:
    """Combine two LLMClient.get_usage_summary() dicts into one. When one
    client made both steps (the CLI and the eval), both summaries hold the same
    calls: each call is counted once (P9.17: the nurse run's changes.md showed
    8 calls / 20.4K tokens for 4 / 10.2K)."""
    calls = list(second.get("calls") or [])
    seen = {id(c) for c in calls}
    calls = [c for c in first.get("calls") or [] if id(c) not in seen] + calls
    ok = [c for c in calls if c.get("success")]
    merged = dict(second)
    merged.update({
        "call_count": len(calls), "success_count": len(ok), "failure_count": len(calls) - len(ok),
        "total_prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in ok),
        "total_completion_tokens": sum(c.get("completion_tokens") or 0 for c in ok),
        "total_duration_seconds": round(sum(c.get("duration_seconds") or 0 for c in ok), 3),
        "calls": calls,
    })
    merged["total_tokens"] = merged["total_prompt_tokens"] + merged["total_completion_tokens"]
    return merged
