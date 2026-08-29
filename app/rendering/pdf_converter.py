import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

class PdfConverter:
    def find_libreoffice_binary(self) -> Optional[str]:
        # Search PATH and common macOS / Linux install locations
        candidates = [
            "libreoffice",
            "soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ]
        for cmd in candidates:
            if "/" in cmd:
                if os.path.exists(cmd) and os.access(cmd, os.X_OK):
                    return cmd
            else:
                found = shutil.which(cmd)
                if found:
                    return found
        return None

    def convert_docx_to_pdf(self, docx_path: str, output_dir: str) -> Optional[str]:
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"Input DOCX file not found: {docx_path}")

        binary = self.find_libreoffice_binary()
        if not binary:
            logger.warning(
                "LibreOffice binary not found. PDF conversion requires LibreOffice.\n"
                "Install it on macOS via: brew install --cask libreoffice"
            )
            return None

        os.makedirs(output_dir, exist_ok=True)
        try:
            cmd = [
                binary,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                output_dir,
                docx_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                base_name = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
                expected_pdf = os.path.join(output_dir, base_name)
                if os.path.exists(expected_pdf):
                    return expected_pdf
            logger.error(f"LibreOffice conversion failed: {result.stderr}")
            return None
        except Exception as e:
            logger.error(f"PDF conversion exception: {e}")
            return None
