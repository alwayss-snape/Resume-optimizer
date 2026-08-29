import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.job import JobDescription, Requirement
from app.llm.client import LLMClient

class LLMJDAnalysisOutput(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

class JDAnalyzer:
    STOP_WORDS = {"and", "the", "with", "for", "such", "as", "that", "this", "should", "have", "must", "required", "knowledge", "experience", "familiarity"}

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def extract_keywords_from_text(self, text: str) -> List[str]:
        words = re.findall(r'\b[A-Za-z0-9\+#\.-]{2,}\b', text)
        keywords = []
        for w in words:
            w_clean = w.strip(".,()")
            if w_clean.lower() not in self.STOP_WORDS and len(w_clean) > 1:
                keywords.append(w_clean)
        return list(dict.fromkeys(keywords))

    def analyze(self, jd_text: str) -> JobDescription:
        lines = [line.strip() for line in jd_text.split("\n") if line.strip()]
        job_title = None
        company = None

        for line in lines[:5]:
            if line.lower().startswith("job title:") or line.lower().startswith("role:"):
                job_title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("company:"):
                company = line.split(":", 1)[1].strip()

        # Attempt LLM extraction if client available
        if self.llm_client and self.llm_client.is_available():
            try:
                prompt_path = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "jd_analysis.txt")
                system_prompt = "You are an expert technical recruiter."
                if os.path.exists(prompt_path):
                    with open(prompt_path, "r", encoding="utf-8") as f:
                        system_prompt = f.read()

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this Job Description:\n\n{jd_text}"},
                ]
                extracted = self.llm_client.generate_json(
                    messages=messages,
                    schema_model=LLMJDAnalysisOutput,
                    temperature=0.0,
                )
                
                req_counter = 0
                requirements: List[Requirement] = []

                for req_skill in extracted.required_skills:
                    req_counter += 1
                    requirements.append(Requirement(
                        id=f"req_{req_counter:03d}",
                        text=req_skill,
                        category="skill",
                        priority="required",
                    ))

                for pref_skill in extracted.preferred_skills:
                    req_counter += 1
                    requirements.append(Requirement(
                        id=f"req_{req_counter:03d}",
                        text=pref_skill,
                        category="skill",
                        priority="preferred",
                    ))

                for resp in extracted.responsibilities:
                    req_counter += 1
                    requirements.append(Requirement(
                        id=f"req_{req_counter:03d}",
                        text=resp,
                        category="responsibility",
                        priority="required",
                    ))

                for qual in extracted.qualifications:
                    req_counter += 1
                    requirements.append(Requirement(
                        id=f"req_{req_counter:03d}",
                        text=qual,
                        category="qualification",
                        priority="required",
                    ))

                if requirements:
                    return JobDescription(
                        job_title=extracted.job_title or job_title or "Target Role",
                        company=extracted.company or company or "Company",
                        requirements=requirements,
                        keywords=extracted.keywords or self.extract_keywords_from_text(jd_text),
                        raw_text=jd_text,
                    )
            except Exception:
                pass  # Fallback to robust heuristic parsing

        # Robust heuristic extraction (works for bulleted AND unbulleted text)
        req_counter = 0
        requirements: List[Requirement] = []
        is_preferred = False

        for line in lines:
            if line.lower().startswith("job title:") or line.lower().startswith("company:"):
                continue

            line_lower = line.lower()
            if any(k in line_lower for k in ("nice to have", "preferred", "optional", "plus")):
                is_preferred = True

            clean_line = line.lstrip("-•* ").strip()
            if len(clean_line) < 5:
                continue

            # Determine category
            if any(k in line_lower for k in ("year", "years", "experience", "background")):
                category = "experience"
            elif any(k in line_lower for k in ("degree", "education", "bachelor", "master", "phd")):
                category = "qualification"
            elif any(k in line_lower for k in ("responsible", "manage", "lead", "develop", "design", "build")):
                category = "responsibility"
            else:
                category = "skill"

            req_counter += 1
            requirements.append(Requirement(
                id=f"req_{req_counter:03d}",
                text=clean_line,
                category=category,
                priority="preferred" if is_preferred else "required",
            ))

        keywords = self.extract_keywords_from_text(jd_text)

        return JobDescription(
            job_title=job_title or "Target Role",
            company=company or "Company",
            requirements=requirements,
            keywords=keywords,
            raw_text=jd_text,
        )
