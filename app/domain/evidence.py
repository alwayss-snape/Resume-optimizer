from typing import Literal
from pydantic import BaseModel

class Evidence(BaseModel):
    id: str
    source_type: Literal[
        "experience",
        "project",
        "skill",
        "education",
        "certification",
        "achievement",
        "summary",
        "general"
    ]
    source_id: str
    text: str
