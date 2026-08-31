from typing import Literal, Optional
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
    # `source_id` is the canonical semantic id of the resume node when available
    # (e.g. `exp_001_b01`). `source_location_id` stores the original raw document
    # block id (e.g. `blk_0007`) used for DOCX preserve-mode patching.
    source_id: str
    source_location_id: Optional[str] = None
    text: str
