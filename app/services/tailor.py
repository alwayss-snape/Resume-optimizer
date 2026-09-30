import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.analysis.jd_analyzer import JDAnalyzer
from app.analysis.matcher import EvidenceMatcher
from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.rewriter import FAILED_STATUSES, LLMRewriter, RewriteProposal
from app.analysis.scoring import AlignmentScorer
from app.analysis.semantic_matcher import SemanticMatcher
from app.analysis.tailor_planner import TailoringPlanner
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.report import TailoringReport
from app.domain.resume import Project, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument, ResumeSource
from app.domain.tailoring import TailoringPlan
from app.ingestion.docx import DocxParser
from app.ingestion.pdf import PdfParser
from app.llm.client import LLMClient
from app.rendering.docx_patcher import DocxPatcher
from app.rendering.html_renderer import HtmlResumeRenderer
from app.rendering.pdf_converter import PdfConverter
from app.rendering.template_renderer import TemplateRenderer
from app.services.run_manager import RunManager
from app.validation.factual import FactualValidator
from app.validation.output import OutputQAValidator
from app.validation.structural import StructuralValidator
from app.validation.safety import SafetyGuard

class TailorService:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.docx_parser = DocxParser()
        self.pdf_parser = PdfParser()
        self.resume_normalizer = ResumeNormalizer()
        self.jd_analyzer = JDAnalyzer(self.llm_client)
        self.matcher = EvidenceMatcher(self.llm_client)
        # A single reused instance: the embedding model (if enabled) is
        # lazy-loaded on first use and cached here, rather than reloaded on
        # every analyze_only/generate_proposals/tailor_resume call.
        self.semantic_matcher = SemanticMatcher()
        self.scorer = AlignmentScorer()
        self.planner = TailoringPlanner(self.llm_client)
        self.rewriter = LLMRewriter(self.llm_client)
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
        contact = []
        if resume.candidate.email:
            contact.append(f"📧 {resume.candidate.email}")
        if resume.candidate.phone:
            contact.append(f"📞 {resume.candidate.phone}")
        if resume.candidate.location:
            contact.append(f"📍 {resume.candidate.location}")
        if contact:
            lines.append(" | ".join(contact) + "\n")

        if resume.summary:
            lines.append("## Professional Summary\n" + resume.summary + "\n")

        if resume.experience:
            lines.append("## Work Experience\n")
            for exp in resume.experience:
                lines.append(f"### {exp.company} — *{exp.title}*\n")
                for bullet in exp.bullets:
                    lines.append(f"- {bullet.text}")
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

    def analyze_only(self, resume_path: str, jd_text: str) -> TailoringReport:
        clean_jd_text = self.safety_guard.sanitize(jd_text)
        
        if resume_path.endswith(".pdf"):
            raw_doc = self.pdf_parser.parse(resume_path)
        else:
            raw_doc = self.docx_parser.parse(resume_path)

        resume_doc, evidence_list = self.resume_normalizer.normalize(raw_doc)
        resume = resume_doc.resume
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        score = self.scorer.calculate_score(matches, job_desc.requirements)
        score_components = self.scorer.calculate_components(matches, job_desc.requirements)

        required_m = [m for m in matches if any(r.id == m.requirement_id and r.priority == "required" for r in job_desc.requirements)]
        preferred_m = [m for m in matches if any(r.id == m.requirement_id and r.priority == "preferred" for r in job_desc.requirements)]
        missing_m = [m for m in matches if m.status == "MISSING"]

        return TailoringReport(
            alignment_score=score,
            required_matches=required_m,
            preferred_matches=preferred_m,
            missing_requirements=missing_m,
            score_components=dict(score_components),
        )

    def generate_proposals(self, resume_path: str, jd_text: str, suggestion_limit: int = 5) -> Dict:
        """Generate rewrite proposals without applying them, plus advisory
        suggestions for JD requirements the résumé doesn't address at all.

        Returns {"proposals": [...], "missing_suggestions": [...],
        "alignment_score": float}. Useful for UI review flows.
        """
        clean_jd_text = self.safety_guard.sanitize(jd_text)

        if resume_path.endswith(".pdf"):
            raw_doc = self.pdf_parser.parse(resume_path)
        else:
            raw_doc = self.docx_parser.parse(resume_path)

        resume_doc, evidence_list = self.resume_normalizer.normalize(raw_doc)
        resume = resume_doc.resume
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        score = self.scorer.calculate_score(matches, job_desc.requirements)
        plan = self.planner.create_plan(resume, job_desc, evidence_list, matches)
        proposals = self.rewriter.execute_plan(resume, plan, evidence_list, job_desc)
        # Fact-check now so the review UI can show each proposal's verdict
        # (and what would be dropped) before the user applies anything.
        for prop in proposals:
            res = self.validator.validate_proposal(prop, evidence_list, jd_keywords=job_desc.keywords)
            prop.validation = res.verdict
            prop.validation_note = "; ".join(res.warnings) or None

        missing_matches = [m for m in matches if m.status == "MISSING"]
        ranked_missing = self.planner.rank_missing_requirements(missing_matches, job_desc, limit=suggestion_limit)
        missing_suggestions = []
        for m in ranked_missing:
            suggestion = self.rewriter.suggest_for_missing_requirement(m.requirement_text, job_desc.keywords)
            if suggestion:
                missing_suggestions.append(suggestion)

        llm_available = bool(self.llm_client and self.llm_client.is_available())
        failed = [p for p in proposals if getattr(p, "status", None) in FAILED_STATUSES]
        return {
            "proposals": proposals,
            "missing_suggestions": missing_suggestions,
            "alignment_score": score,
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
            "experience_options": [{"id": e.id, "label": f"{e.company} — {e.title}"} for e in resume.experience],
        }

    def incorporate_user_addition(
        self,
        resume: Resume,
        evidence_list: List["object"],
        job_desc: JobDescription,
        addition_text: str,
        target: str = "auto",
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
        polished_text, rationale = self.rewriter.rewrite_bullet(
            addition_text,
            evidence=[user_evidence],
            jd_requirements=jd_req_texts,
            target_keywords=job_desc.keywords,
        )
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
                return self.incorporate_user_addition(resume, evidence_list, job_desc, addition_text, target="new_project")

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
        mode: str = "PRESERVE",
        strict_factual: bool = False,
        preapproved_proposals: Optional[List] = None,
        addition_text: Optional[str] = None,
        addition_target: str = "auto",
        proposal_usage: Optional[Dict] = None,
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
        
        def _append_progress(msg: str) -> None:
            ts = datetime.utcnow().isoformat() + "Z"
            try:
                with open(report_md_path, "a", encoding="utf-8") as pf:
                    pf.write(f"- [{ts}] {msg}\n")
            except Exception:
                # Never fail tailoring flow due to progress logging
                pass
        
        _append_progress("Run created: " + run_dir)

        is_pdf = resume_path.endswith(".pdf")
        if is_pdf:
            raw_doc = self.pdf_parser.parse(resume_path)
            mode = "ATS_DEFAULT"  # Force ATS reconstruction for PDF inputs
        else:
            raw_doc = self.docx_parser.parse(resume_path)

        if addition_text and (addition_text or "").strip() and mode == "PRESERVE":
            # A brand-new bullet has no corresponding block in the original
            # layout, so it cannot be positionally patched in place — fall
            # back to the reconstructed ATS template so the addition
            # actually shows up in the output.
            mode = "ATS_DEFAULT"

        # Normalizer returns a canonical ResumeDocument and the extracted evidence
        resume_doc, evidence_list = self.resume_normalizer.normalize(raw_doc)
        resume = resume_doc.resume
        _append_progress("Imported and normalized resume")
        # Record import as a revision (best-effort)
        try:
            resume_doc.record_revision("Imported uploaded résumé", ["resume", "source"], actor="import")
        except Exception:
            pass
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        matches = self.semantic_matcher.match(job_desc.requirements, evidence_list, matches)
        initial_score = self.scorer.calculate_score(matches, job_desc.requirements)
        _append_progress(f"Analyzed JD and computed initial alignment score: {initial_score:.1f}")

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
            proposals = self.rewriter.execute_plan(resume, plan, evidence_list, job_desc)
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
        docx_output_path = os.path.join(output_dir, "tailored_resume.docx")
        pdf_output_path = os.path.join(output_dir, "tailored_resume.pdf")
        html_output_path = os.path.join(output_dir, "tailored_resume.html")

        def _prop_key(p):
            return getattr(p, "semantic_id", None) or getattr(p, "target_semantic_id", None) or getattr(p, "source_id", None)

        def _prop_text(p):
            return getattr(p, "rewritten_text", None) or getattr(p, "proposed_text", None) or ""

        # Apply approved rewrites to the canonical resume model (semantic ids).
        prop_dict = {_prop_key(p): _prop_text(p) for p in approved_proposals}
        for exp in resume.experience:
            for b in exp.bullets:
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
            original_text = {b.id: b.text for e in original_resume.experience for b in e.bullets}
            for exp in resume.experience:
                for b in exp.bullets:
                    if b.id in original_text:
                        b.text = original_text[b.id]
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

        # Fold in any free-text content the candidate typed in the UI (a
        # project, an achievement, a skill) as one more polished, evidence-
        # grounded bullet, then recompute the alignment score so it reflects
        # everything just applied — the rewrites above and this addition.
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
        score = self.scorer.calculate_score(matches, job_desc.requirements)
        _append_progress(f"Recomputed alignment score after applying changes: {score:.1f} (was {initial_score:.1f})")

        if mode == "PRESERVE" and not is_pdf:
            self.docx_patcher.patch(resume_path, raw_doc.document_map, approved_proposals, docx_output_path)
            _append_progress(f"DOCX preserve-mode patch applied to {docx_output_path}")
        else:
            # Pass the ResumeDocument so renderers can access revisions and metadata
            self.template_renderer.render_ats_default(resume_doc, docx_output_path)
            _append_progress(f"DOCX reconstructed via template renderer at {docx_output_path}")

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
            warnings.extend(docx_warnings)
        except Exception:
            # Never fail the tailoring flow due to QA check exceptions
            warnings.append("Output QA DOCX validation failed unexpectedly.")

        # PDF Conversion and QA
        pdf_warnings = []
        pdf_res = self.pdf_converter.convert_docx_to_pdf(docx_output_path, output_dir)
        if not pdf_res:
            warnings.append("LibreOffice not available or PDF conversion failed; DOCX rendered successfully.")
            _append_progress("PDF conversion failed or LibreOffice unavailable")
        else:
            try:
                pdf_warnings = self.qa_validator.validate_pdf(pdf_res, expected_candidate_name=resume.candidate.name)
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
                f.write(f"**Alignment Score:** {score:.1f} / 100 (was {initial_score:.1f})\n\n")
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
            "changes_md": report_md_path,
            "alignment_score": f"{score:.1f}",
            "initial_alignment_score": f"{initial_score:.1f}",
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
