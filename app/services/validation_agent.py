import os
from typing import List, Optional
from app.domain.resume_document import ResumeDocument
from app.validation.factual import FactualValidator
from app.validation.structural import StructuralValidator
from app.validation.output import OutputQAValidator

class ValidationAgent:
    def __init__(self):
        self.factual = FactualValidator()
        self.struct = StructuralValidator()
        self.output = OutputQAValidator()

    def validate_run(self, run_dir: str, output_dir: Optional[str] = None) -> dict:
        results = {
            "factual": [],
            "structural": [],
            "output": [],
        }

        resume_doc_path = os.path.join(run_dir, "resume_document.json")
        resume_path = os.path.join(run_dir, "resume.json")

        resume_doc = None
        resume = None
        if os.path.exists(resume_doc_path):
            try:
                resume_doc = ResumeDocument.model_validate_json(open(resume_doc_path, "r", encoding="utf-8").read())
            except Exception:
                resume_doc = None
        if os.path.exists(resume_path):
            try:
                import json
                resume = json.load(open(resume_path, "r", encoding="utf-8"))
            except Exception:
                resume = None

        # Structural: if both original and tailored resume exist in resume.json, skip; otherwise best-effort
        if resume and isinstance(resume, dict):
            # attempt to find original vs tailored from run artifacts
            # This is a best-effort check: StructuralValidator expects Resume models, so we only run when both are present.
            results["structural"].append("Structural validation requires original and tailored Resume models; run-time check skipped if unavailable.")

        # Output QA: check DOCX and PDF in output_dir if provided
        if output_dir:
            docx_path = os.path.join(output_dir, "tailored_resume.docx")
            pdf_path = os.path.join(output_dir, "tailored_resume.pdf")
            results["output"].extend(self.output.validate_docx(docx_path, expected_candidate_name=(resume_doc.resume.candidate.name if resume_doc else None)))
            results["output"].extend(self.output.validate_pdf(pdf_path, expected_candidate_name=(resume_doc.resume.candidate.name if resume_doc else None)))

        # Factual: if there are rewrites stored as rewrites.json, validate each
        rewrites_path = os.path.join(run_dir, "rewrites.json")
        if os.path.exists(rewrites_path):
            import json
            try:
                rewrites = json.load(open(rewrites_path, "r", encoding="utf-8"))
                # rewrites may be list of dicts or pydantic models
                for r in rewrites:
                    # Minimal mapping to expected shape
                    from app.analysis.rewriter import RewriteProposal
                    try:
                        proposal = RewriteProposal(**r) if isinstance(r, dict) else r
                        # No evidence_list available here; skip deep factual checks
                        res = self.factual.validate_proposal(proposal, evidence_list=[])
                        results["factual"].append(res.model_dump() if hasattr(res, "model_dump") else str(res))
                    except Exception:
                        results["factual"].append(f"Failed to validate rewrite: {r}")
            except Exception as e:
                results["factual"].append(f"Failed to read rewrites.json: {e}")

        return results
