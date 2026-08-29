import os
from typing import List, Optional
import docx
import fitz  # PyMuPDF

class OutputQAValidator:
    def validate_docx(self, docx_path: str, expected_candidate_name: Optional[str] = None) -> List[str]:
        warnings: List[str] = []
        if not os.path.exists(docx_path):
            warnings.append(f"DOCX output file does not exist: {docx_path}")
            return warnings

        if os.path.getsize(docx_path) == 0:
            warnings.append("DOCX output file is 0 bytes.")
            return warnings

        try:
            doc = docx.Document(docx_path)
            full_text = "\n".join([p.text for p in doc.paragraphs]).strip()
            if not full_text:
                warnings.append("DOCX document contains no text.")
            elif expected_candidate_name and expected_candidate_name.lower() not in full_text.lower():
                warnings.append(f"Expected candidate name '{expected_candidate_name}' not found in DOCX.")
        except Exception as e:
            warnings.append(f"Failed to parse rendered DOCX: {e}")

        return warnings

    def validate_pdf(self, pdf_path: str, expected_candidate_name: Optional[str] = None) -> List[str]:
        warnings: List[str] = []
        if not os.path.exists(pdf_path):
            warnings.append(f"PDF output file does not exist: {pdf_path}")
            return warnings

        if os.path.getsize(pdf_path) == 0:
            warnings.append("PDF output file is 0 bytes.")
            return warnings

        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                warnings.append("PDF output file contains 0 pages.")

            extracted_text = ""
            for page in doc:
                extracted_text += page.get_text()

            if not extracted_text.strip():
                warnings.append("PDF contains no readable text.")
            elif expected_candidate_name and expected_candidate_name.lower() not in extracted_text.lower():
                warnings.append(f"Expected candidate name '{expected_candidate_name}' not found in PDF.")
            doc.close()
        except Exception as e:
            warnings.append(f"Failed to parse rendered PDF: {e}")

        return warnings
