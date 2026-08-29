from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class DocumentLocation(BaseModel):
    section: str = "general"
    paragraph_index: Optional[int] = None
    table_index: Optional[int] = None
    row: Optional[int] = None
    column: Optional[int] = None
    run_indices: List[int] = Field(default_factory=list)
    style_name: Optional[str] = None
    original_text: str = ""

class DocumentMap(BaseModel):
    locations: Dict[str, DocumentLocation] = Field(default_factory=dict)

    def add_location(self, source_id: str, location: DocumentLocation) -> None:
        self.locations[source_id] = location

    def get_location(self, source_id: str) -> Optional[DocumentLocation]:
        return self.locations.get(source_id)
