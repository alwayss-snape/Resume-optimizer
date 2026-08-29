from typing import List
from app.domain.resume import Resume

class StructuralValidator:
    def validate(self, original_resume: Resume, tailored_resume: Resume) -> List[str]:
        warnings: List[str] = []

        # Check candidate identity preserved
        if original_resume.candidate.name != tailored_resume.candidate.name:
            warnings.append("Candidate name was altered during tailoring.")

        # Check experience entry count
        if len(original_resume.experience) != len(tailored_resume.experience):
            warnings.append("Number of work experience entries changed.")

        # Check company names preserved
        orig_companies = [e.company for e in original_resume.experience]
        tailored_companies = [e.company for e in tailored_resume.experience]
        if orig_companies != tailored_companies:
            warnings.append("Company names were altered during tailoring.")

        return warnings
