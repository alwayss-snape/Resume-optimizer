import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

class Candidate(BaseModel):
    name: str = "Candidate"
    # Short professional title under the name, e.g. "Senior Data Scientist".
    headline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = Field(default_factory=list)
    # Other header items, verbatim: an address, "Date of birth: ...",
    # "Security Clearance: Active Secret" (P8.3). Kept, never interpreted.
    details: List[str] = Field(default_factory=list)

    def display_links(self) -> List[str]:
        """Links as shown on a resume: 'linkedin.com/in/x', no scheme/www."""
        return [re.sub(r"^(?:https?://)?(?:www\.)?", "", l).rstrip("/") for l in self.links if l]

class ResumeBullet(BaseModel):
    id: str
    text: str
    source_location_id: Optional[str] = None
    # Sub-heading this bullet sits under inside a job, e.g. a project name
    # ("Fraud Detection Framework"). None = directly under the job.
    group: Optional[str] = None

class Role(BaseModel):
    """One title held at a company, e.g. 'Data Scientist II, Aug 2024 - Present'."""
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class Experience(BaseModel):
    """One company entry. `title` / `start_date` / `end_date` describe the
    most recent role. When several roles were held at the company (a
    promotion), `roles` lists all of them, most recent first; roles[0]
    matches the fields above. Empty `company` / `title` mean "not found in
    the file": renderers skip them instead of printing a placeholder."""
    id: str
    company: str
    title: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    roles: List[Role] = Field(default_factory=list)
    bullets: List[ResumeBullet] = Field(default_factory=list)
    # Source block ids of the entry's header lines (title, company, dates),
    # so a check can tell which lines of the file this job came from.
    source_blocks: List[str] = Field(default_factory=list)

    def all_roles(self) -> List[Role]:
        if self.roles:
            return list(self.roles)
        if self.title or self.start_date or self.end_date:
            return [Role(title=self.title, start_date=self.start_date, end_date=self.end_date)]
        return []

    def bullet_groups(self) -> List[Tuple[Optional[str], List[ResumeBullet]]]:
        """Consecutive bullets grouped by sub-heading, in document order."""
        groups: List[Tuple[Optional[str], List[ResumeBullet]]] = []
        for bullet in self.bullets:
            if groups and groups[-1][0] == bullet.group:
                groups[-1][1].append(bullet)
            else:
                groups.append((bullet.group, [bullet]))
        return groups

class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    bullets: List[ResumeBullet] = Field(default_factory=list)

class Education(BaseModel):
    id: str
    institution: str
    degree: str
    location: Optional[str] = None
    field_of_study: Optional[str] = None
    dates: Optional[str] = None
    # Further lines of the entry, verbatim ("Relevant Coursework: ...").
    details: List[str] = Field(default_factory=list)


class SectionLine(BaseModel):
    text: str
    bullet: bool = False
    source_location_id: Optional[str] = None


class OtherSection(BaseModel):
    """A section the resume model has no fields for (Publications, Bar
    Admissions, Languages, Volunteer, a heading in another language...),
    kept verbatim under its own heading (P8.3) so nothing is dropped."""
    id: str
    heading: str
    lines: List[SectionLine] = Field(default_factory=list)

class Resume(BaseModel):
    candidate: Candidate
    summary: Optional[str] = None
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    certifications: List[Dict[str, str]] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    other_sections: List[OtherSection] = Field(default_factory=list)
