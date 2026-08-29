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
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def analyze(self, jd_text: str) -> JobDescription:
        # Heuristic baseline extraction
        lines = [line.strip() for line in jd_text.split("\n") if line.strip()]
        job_title = None
        company = None

        for line in lines[:5]:
            if line.lower().startswith("job title:") or line.lower().startswith("role:"):
                job_title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("company:"):
                company = line.split(":", 1)[1].strip()

        # If LLM client provided and available, perform LLM extraction
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

                return JobDescription(
                    job_title=extracted.job_title or job_title,
                    company=extracted.company or company,
                    requirements=requirements,
                    keywords=extracted.keywords,
                    raw_text=jd_text,
                )
            except Exception as e:
                pass  # Fallback to heuristic parsing if LLM call fails

        # Pure heuristic parsing fallback
        req_counter = 0
        requirements: List[Requirement] = []
        keywords: List[str] = []
        is_preferred = False

        for line in lines:
            if "nice to have" in line.lower() or "preferred" in line.lower():
                is_preferred = True
            if line.startswith("-") or line.startswith("•") or line.startswith("*"):
                req_text = line.lstrip("-•* ").strip()
                req_counter += 1
                requirements.append(Requirement(
                    id=f"req_{req_counter:03d}",
                    text=req_text,
                    category="skill",
                    priority="preferred" if is_preferred else "required",
                ))

        return JobDescription(
            job_title=job_title or "Position",
            company=company or "Company",
            requirements=requirements,
            keywords=keywords,
            raw_text=jd_text,
        )
