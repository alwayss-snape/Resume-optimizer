import os
from typing import List
import docx

from app.analysis.rewriter import RewriteProposal
from app.rendering.document_map import DocumentMap

class DocxPatcher:
    def patch(
        self,
        source_docx_path: str,
        document_map: DocumentMap,
        approved_proposals: List[RewriteProposal],
        output_docx_path: str,
    ) -> str:
        if not os.path.exists(source_docx_path):
            raise FileNotFoundError(f"Source DOCX not found at path: {source_docx_path}")

        doc = docx.Document(source_docx_path)
        proposal_dict = {p.source_id: p for p in approved_proposals}

        for source_id, proposal in proposal_dict.items():
            location = document_map.get_location(source_id)
            if not location or location.paragraph_index is None:
                continue

            if 0 <= location.paragraph_index < len(doc.paragraphs):
                paragraph = doc.paragraphs[location.paragraph_index]
                
                # In-place text update while preserving primary run formatting
                if paragraph.runs:
                    prefix = ""
                    orig_text = paragraph.text.strip()
                    if orig_text.startswith("•") or orig_text.startswith("-"):
                        prefix = orig_text[0] + " "
                    
                    # Update first run with prefix + new text, clear subsequent runs
                    paragraph.runs[0].text = prefix + proposal.rewritten_text
                    for run in paragraph.runs[1:]:
                        run.text = ""
                else:
                    paragraph.text = proposal.rewritten_text

        os.makedirs(os.path.dirname(output_docx_path), exist_ok=True)
        doc.save(output_docx_path)
        return output_docx_path
