import os
import shutil
from typing import Dict, List, Optional, Tuple

from app.analysis.jd_analyzer import JDAnalyzer
from app.analysis.matcher import EvidenceMatcher
from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.rewriter import LLMRewriter, RewriteProposal
from app.analysis.scoring import AlignmentScorer
from app.analysis.tailor_planner import TailoringPlanner
from app.domain.job import JobDescription
from app.domain.report import TailoringReport
from app.domain.resume import Resume
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

        resume, evidence_list = self.resume_normalizer.normalize(raw_doc)
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        score = self.scorer.calculate_score(matches, job_desc.requirements)

        required_m = [m for m in matches if any(r.id == m.requirement_id and r.priority == "required" for r in job_desc.requirements)]
        preferred_m = [m for m in matches if any(r.id == m.requirement_id and r.priority == "preferred" for r in job_desc.requirements)]
        missing_m = [m for m in matches if m.status == "MISSING"]

        return TailoringReport(
            alignment_score=score,
            required_matches=required_m,
            preferred_matches=preferred_m,
            missing_requirements=missing_m,
        )

    def tailor_resume(
        self,
        resume_path: str,
        jd_text: str,
        output_dir: str,
        mode: str = "PRESERVE",
        strict_factual: bool = False,
    ) -> Dict[str, str]:
        run_dir = self.run_manager.create_run(resume_path, jd_text)
        clean_jd_text = self.safety_guard.sanitize(jd_text)

        is_pdf = resume_path.endswith(".pdf")
        if is_pdf:
            raw_doc = self.pdf_parser.parse(resume_path)
            mode = "ATS_DEFAULT"  # Force ATS reconstruction for PDF inputs
        else:
            raw_doc = self.docx_parser.parse(resume_path)

        resume, evidence_list = self.resume_normalizer.normalize(raw_doc)
        resume_document = ResumeDocument(
            resume=resume,
            source=ResumeSource(
                filename=os.path.basename(resume_path),
                file_type="pdf" if is_pdf else "docx",
                import_mode="template" if is_pdf else "preserve",
            ),
        )
        resume_document.record_revision(
            "Imported uploaded résumé", ["resume", "source"], actor="import"
        )
        job_desc = self.jd_analyzer.analyze(clean_jd_text)
        matches = self.matcher.match(job_desc, evidence_list)
        score = self.scorer.calculate_score(matches, job_desc.requirements)

        plan = self.planner.create_plan(resume, job_desc, evidence_list, matches)
        proposals = self.rewriter.execute_plan(resume, plan, evidence_list, job_desc)

        approved_proposals: List[RewriteProposal] = []
        warnings: List[str] = []

        # Keep a copy of the original resume model for structural validation
        import copy
        original_resume = copy.deepcopy(resume)

        for prop in proposals:
            res = self.validator.validate_proposal(prop, evidence_list)
            if res.approved:
                approved_proposals.append(prop)
            else:
                warnings.extend(res.warnings)

        # Output file generation
        os.makedirs(output_dir, exist_ok=True)
        docx_output_path = os.path.join(output_dir, "tailored_resume.docx")
        pdf_output_path = os.path.join(output_dir, "tailored_resume.pdf")
        html_output_path = os.path.join(output_dir, "tailored_resume.html")

        # Update resume model with approved rewrites for ATS & preview rendering
        prop_dict = {p.source_id: p.rewritten_text for p in approved_proposals}
        for exp in resume.experience:
            for b in exp.bullets:
                if b.id in prop_dict:
                    b.text = prop_dict[b.id]

        if approved_proposals:
            resume_document.record_revision(
                "Applied evidence-approved AI rewrites",
                [f"resume.experience.{proposal.source_id}" for proposal in approved_proposals],
                actor="ai",
                evidence_ids=[evidence_id for proposal in approved_proposals for evidence_id in proposal.evidence_ids],
            )

        if mode == "PRESERVE" and not is_pdf:
            self.docx_patcher.patch(resume_path, raw_doc.document_map, approved_proposals, docx_output_path)
        else:
            self.template_renderer.render_ats_default(resume, docx_output_path)

<<<<<<< HEAD
        # Canonical ATS HTML is available for browser preview and print workflows.
        self.html_renderer.write_html(resume_document, html_output_path)
=======
        # Structural validation: ensure tailoring didn't alter identity/content unexpectedly
        struct_warnings = self.struct_validator.validate(original_resume, resume)
        if struct_warnings:
            warnings.extend(struct_warnings)

        # Output QA validations (DOCX and PDF) to catch rendering issues
        try:
            docx_warnings = self.qa_validator.validate_docx(docx_output_path, expected_candidate_name=resume.candidate.name)
            warnings.extend(docx_warnings)
        except Exception:
            # Never fail the tailoring flow due to QA check exceptions
            warnings.append("Output QA DOCX validation failed unexpectedly.")
>>>>>>> 0587dcd (Phase1: wire StructuralValidator and OutputQAValidator into TailorService; collect validation warnings)

        # Respect strict factual mode: if enabled and any validation warnings exist,
        # withhold applying rewrites to avoid introducing potentially unsupported claims.
        if strict_factual and warnings:
            approved_proposals = []
            warnings.append("Strict Factual Mode enabled: rewrites withheld due to validation warnings.")

        # PDF Conversion
        pdf_res = self.pdf_converter.convert_docx_to_pdf(docx_output_path, output_dir)
        if not pdf_res:
            warnings.append("LibreOffice not available or PDF conversion failed; DOCX rendered successfully.")

        # Save artifacts to run folder
        self.run_manager.save_json(run_dir, "resume.json", resume)
        self.run_manager.save_json(run_dir, "resume_document.json", resume_document)
        self.run_manager.save_json(run_dir, "jd.json", job_desc)
        self.run_manager.save_json(run_dir, "plan.json", plan)
        self.run_manager.save_json(run_dir, "rewrites.json", approved_proposals)

        # Generate human-readable change log / report
        report_md_path = os.path.join(output_dir, "changes.md")
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Tailoring Report & Change Log\n\n")
            f.write(f"**Alignment Score:** {score:.1f} / 100\n\n")
            f.write(f"## Accepted Rewrites\n\n")
            for prop in approved_proposals:
                f.write(f"### Bullet ({prop.source_id})\n")
                f.write(f"- **Original:** {prop.original_text}\n")
                f.write(f"- **Tailored:** {prop.rewritten_text}\n")
                f.write(f"- **Rationale:** {prop.rationale}\n\n")
            if plan.unsupported_requirements:
                f.write(f"## Unsupported Missing Requirements\n\n")
                for req in plan.unsupported_requirements:
                    f.write(f"- {req}\n")
            if warnings:
                f.write("\n## Validation Warnings\n\n")
                for w in warnings:
                    f.write(f"- {w}\n")

        preview_md = self.generate_preview_md(resume)

        return {
            "docx": docx_output_path,
            "pdf": pdf_output_path if pdf_res else "",
            "html": html_output_path,
            "changes_md": report_md_path,
            "alignment_score": f"{score:.1f}",
            "run_dir": run_dir,
<<<<<<< HEAD
            "preview_md": preview_md,
=======
            "warnings": warnings,
>>>>>>> 0587dcd (Phase1: wire StructuralValidator and OutputQAValidator into TailorService; collect validation warnings)
        }
