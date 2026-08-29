from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class Candidate(BaseModel):
    name: str = "Candidate"
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = Field(default_factory=list)

class ResumeBullet(BaseModel):
    id: str
    text: str
    source_location_id: Optional[str] = None

class Experience(BaseModel):
    id: str
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: List[ResumeBullet] = Field(default_factory=list)

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
    field_of_study: Optional[str] = None
    dates: Optional[str] = None

class Resume(BaseModel):
    candidate: Candidate
    summary: Optional[str] = None
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    certifications: List[Dict[str, str]] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
