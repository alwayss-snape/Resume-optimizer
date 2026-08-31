import os
import logging
from typing import List, Optional

try:
    import fitz  # PyMuPDF
    _FITZ_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - runtime dependency may be missing in some environments
    fitz = None
    _FITZ_IMPORT_ERROR = e

from app.ingestion.docx import RawBlock, RawDocument
from app.ingestion.ocr import OCREngine
from app.rendering.document_map import DocumentLocation, DocumentMap

logger = logging.getLogger(__name__)

class PdfParser:
    BULLET_PREFIXES = ("•", "-", "*", "▪", "–", "—", "o ")

    def __init__(self):
        self.ocr_engine = OCREngine()

    def _ensure_fitz(self) -> None:
        if fitz is None:
            raise RuntimeError(
                "PyMuPDF is required to parse PDFs but it's not installed. "
                "Install it with `pip install PyMuPDF` (or add `PyMuPDF` to your project dependencies). "
                f"Underlying import error: {_FITZ_IMPORT_ERROR!r}"
            )

    def parse(self, file_path: str) -> RawDocument:
        self._ensure_fitz()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at path: {file_path}")

        doc = fitz.open(file_path)
        blocks: List[RawBlock] = []
        document_map = DocumentMap()
        full_text_lines: List[str] = []

        current_section = "Header"
        block_counter = 0

        total_text_length = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            text_page = page.get_text("blocks")
            for b in text_page:
                if len(b) >= 5 and b[4]:
                    raw_text = b[4].strip()
                    total_text_length += len(raw_text)
                    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                    for line_idx, line in enumerate(lines):
                        is_bullet = line.startswith(self.BULLET_PREFIXES)
                        COMMON_SECTIONS = {"summary", "professional summary", "experience", "work experience", "skills", "technical skills", "education", "projects", "certifications", "achievements", "profile"}
                        is_common_section = line.lower() in COMMON_SECTIONS
                        is_heading = is_common_section or (
                            len(line) < 40
                            and not line.endswith(".")
                            and not is_bullet
                            and line.isupper()
                            and (page_num > 0 or line_idx > 0)
                        )

                        if is_heading:
                            current_section = line
                            block_type = "heading"
                        elif is_bullet:
                            block_type = "bullet"
                            for prefix in self.BULLET_PREFIXES:
                                if line.startswith(prefix):
                                    line = line[len(prefix):].strip()
                                    break
                        else:
                            block_type = "paragraph"

                        block_id = f"pdf_p{page_num+1}_b{block_counter:04d}"
                        location = DocumentLocation(
                            section=current_section,
                            paragraph_index=block_counter,
                            original_text=line,
                        )
                        block_counter += 1

                        raw_block = RawBlock(
                            id=block_id,
                            block_type=block_type,
                            text=line,
                            section=current_section,
                            location=location,
                        )
                        blocks.append(raw_block)
                        document_map.add_location(block_id, location)
                        full_text_lines.append(line)

        # Fallback to OCR if total text extracted is minimal (scanned PDF)
        if total_text_length < 50 and len(doc) > 0:
            logger.info("PDF has minimal text layer; attempting OCR fallback...")
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                ocr_text = self.ocr_engine.extract_text_from_image(img_bytes)
                if ocr_text:
                    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
                    for line in lines:
                        block_id = f"ocr_p{page_num+1}_b{block_counter:04d}"
                        block_counter += 1
                        location = DocumentLocation(
                            section=current_section,
                            paragraph_index=block_counter,
                            original_text=line,
                        )
                        raw_block = RawBlock(
                            id=block_id,
                            block_type="paragraph",
                            text=line,
                            section=current_section,
                            location=location,
                        )
                        blocks.append(raw_block)
                        document_map.add_location(block_id, location)
                        full_text_lines.append(line)

        doc.close()

        return RawDocument(
            filename=os.path.basename(file_path),
            blocks=blocks,
            document_map=document_map,
            raw_text="\n".join(full_text_lines),
        )
