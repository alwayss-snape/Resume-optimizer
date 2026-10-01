import os
import re
from typing import List, Optional
import docx
import pymupdf as fitz  # PyMuPDF

class OutputQAValidator:
    def validate_docx(self, docx_path: str, expected_candidate_name: Optional[str] = None) -> List[str]:
        warnings: List[str] = []
        if not os.path.exists(docx_path):
            warnings.append(f"DOCX output file does not exist: {docx_path}")
            return warnings

        if os.path.getsize(docx_path) == 0:
            warnings.append("DOCX output file is 0 bytes.")
            return warnings

        try:
            doc = docx.Document(docx_path)
            full_text = "\n".join([p.text for p in doc.paragraphs]).strip()
            if not full_text:
                warnings.append("DOCX document contains no text.")
            elif expected_candidate_name and expected_candidate_name.lower() not in full_text.lower():
                warnings.append(f"Expected candidate name '{expected_candidate_name}' not found in DOCX.")
        except Exception as e:
            warnings.append(f"Failed to parse rendered DOCX: {e}")

        return warnings

    def validate_pdf(self, pdf_path: str, expected_candidate_name: Optional[str] = None) -> List[str]:
        warnings: List[str] = []
        if not os.path.exists(pdf_path):
            warnings.append(f"PDF output file does not exist: {pdf_path}")
            return warnings

        if os.path.getsize(pdf_path) == 0:
            warnings.append("PDF output file is 0 bytes.")
            return warnings

        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                warnings.append("PDF output file contains 0 pages.")

            extracted_text = ""
            for page in doc:
                extracted_text += page.get_text()

            if not extracted_text.strip():
                warnings.append("PDF contains no readable text.")
            elif expected_candidate_name and expected_candidate_name.lower() not in extracted_text.lower():
                warnings.append(f"Expected candidate name '{expected_candidate_name}' not found in PDF.")
            doc.close()
        except Exception as e:
            warnings.append(f"Failed to parse rendered PDF: {e}")

        return warnings

    # -- ATS round trip (P2.5) ------------------------------------------------

    ROUND_TRIP_PREFIX = "ATS round-trip"

    def round_trip(self, path: str, expected) -> List[str]:
        """Re-parse a rendered DOCX / PDF the way an ATS would (our own
        parser, no LLM) and compare it with the Resume that was rendered:
        name, email, phone, links, sections, companies, role titles and
        dates, education, skills and every bullet. Returns one warning per
        problem, each starting with ROUND_TRIP_PREFIX."""
        from app.analysis.resume_normalizer import ResumeNormalizer
        from app.ingestion.docx import DocxParser
        from app.ingestion.pdf import PdfParser
        from app.rendering.layout import date_range, display_skills, format_date_text

        kind = "PDF" if path.lower().endswith(".pdf") else "DOCX"
        prefix = f"{self.ROUND_TRIP_PREFIX} ({kind}):"
        try:
            raw = (PdfParser() if kind == "PDF" else DocxParser()).parse(path)
            got = ResumeNormalizer().normalize(raw)[0].resume
        except Exception as e:
            return [f"{prefix} the file could not be re-parsed: {e}"]

        norm = lambda t: re.sub(r"\s+", " ", (t or "")).strip().lower()
        digits = lambda t: re.sub(r"\D", "", t or "")
        problems: List[str] = []
        exp_c, got_c = expected.candidate, got.candidate
        if norm(exp_c.name) != norm(got_c.name):
            problems.append(f"name read as \"{got_c.name}\"")
        if exp_c.email and norm(exp_c.email) != norm(got_c.email):
            problems.append("email not found")
        if exp_c.phone and digits(exp_c.phone) != digits(got_c.phone):
            problems.append("phone not found")
        raw_text = norm(raw.raw_text)
        missing_links = [l for l in exp_c.display_links() if norm(l) not in raw_text]
        if missing_links:
            problems.append(f"link(s) not found: {', '.join(missing_links)}")

        sections = {"summary": (expected.summary, got.summary), "work experience": (expected.experience, got.experience),
                    "skills": (expected.skills, got.skills), "education": (expected.education, got.education),
                    "projects": (expected.projects, got.projects),
                    "certifications": (expected.certifications, got.certifications)}
        for name, (want, have) in sections.items():
            if want and not have:
                problems.append(f"the {name} section was not recognised")

        if expected.experience and got.experience:
            want_jobs = [(norm(e.company), [(norm(r.title), date_range(r.start_date, r.end_date))
                                            for r in e.all_roles()]) for e in expected.experience]
            have_jobs = [(norm(e.company), [(norm(r.title), date_range(r.start_date, r.end_date))
                                            for r in e.all_roles()]) for e in got.experience]
            if len(want_jobs) != len(have_jobs):
                problems.append(f"{len(have_jobs)} job entries read, {len(want_jobs)} rendered")
            for (w_co, w_roles), (h_co, h_roles) in zip(want_jobs, have_jobs):
                if w_co and w_co != h_co:
                    problems.append(f"company read as \"{h_co}\" instead of \"{w_co}\"")
                if w_roles != h_roles:
                    problems.append("role titles or dates differ: "
                                    + "; ".join(f"{t} {d}".strip() for t, d in h_roles))

        want_bullets = [norm(b.text) for s in [*expected.experience, *expected.projects] for b in s.bullets]
        have_bullets = {norm(b.text) for s in [*got.experience, *got.projects] for b in s.bullets}
        lost = [b for b in want_bullets if b and b not in have_bullets]
        if lost:
            problems.append(f"{len(lost)} of {len(want_bullets)} bullets not read back intact "
                            f"(e.g. \"{lost[0][:60]}\")")

        have_skills = {norm(v) for values in got.skills.values() for v in values}
        lost_skills = [v for values in display_skills(expected.skills).values() for v in values
                       if norm(v) not in have_skills]
        if lost_skills:
            problems.append(f"skill(s) not read back: {', '.join(lost_skills[:5])}")

        have_edu = {(norm(e.degree), norm(e.institution), format_date_text(e.dates), norm(e.location))
                    for e in got.education}
        for e in expected.education:
            if (norm(e.degree), norm(e.institution), format_date_text(e.dates), norm(e.location)) not in have_edu:
                problems.append(f"education entry \"{e.degree or e.institution}\" not read back")

        return [f"{prefix} {p}" for p in problems]
