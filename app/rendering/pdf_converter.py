import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# LibreOffice profiles, one per conversion running at the same time: two
# conversions on one profile make the second fail, and a brand-new profile
# costs ~5 s to set up, so finished ones go back in the pool warm.
_PROFILE_ROOT = os.path.join(tempfile.gettempdir(), "tailores_lo_profiles")
_free_profiles: List[str] = []
_profiles_lock = threading.Lock()
_profile_count = [0]


def _take_profile() -> str:
    with _profiles_lock:
        if _free_profiles:
            return _free_profiles.pop()
        _profile_count[0] += 1
        path = os.path.join(_PROFILE_ROOT, f"{os.getpid()}_{_profile_count[0]}")
    os.makedirs(path, exist_ok=True)
    return path


def _give_back(path: str) -> None:
    with _profiles_lock:
        _free_profiles.append(path)

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
        # Never two conversions on one LibreOffice profile (two visitors, or a
        # page-fit loop next to another run): each takes one from the pool.
        profile = _take_profile()
        try:
            cmd = [
                binary,
                f"-env:UserInstallation={Path(profile).as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                output_dir,
                docx_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
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
        finally:
            _give_back(profile)


# The import filter per upload type. Forced, so a damaged file fails instead
# of LibreOffice falling back to reading its bytes as plain text (P9.2: a
# corrupt .doc came back as a resume full of garbage characters).
IMPORT_FILTERS = {".doc": "MS Word 97", ".odt": "writer8", ".rtf": "Rich Text Format"}
CONVERT_TIMEOUT_S = 60


def convert_to_docx(path: str, output_dir: str) -> Optional[str]:
    """A .doc / .odt / .rtf as .docx through LibreOffice (P8.22), or None."""
    binary = PdfConverter().find_libreoffice_binary()
    if not binary:
        return None
    in_filter = IMPORT_FILTERS.get(os.path.splitext(path)[1].lower())
    profile = _take_profile()
    try:
        result = subprocess.run([binary, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless",
                                 *([f"--infilter={in_filter}"] if in_filter else []),
                                 "--convert-to", "docx", "--outdir", output_dir, path],
                                capture_output=True, text=True, timeout=CONVERT_TIMEOUT_S, stdin=subprocess.DEVNULL)
        out = os.path.join(output_dir, os.path.splitext(os.path.basename(path))[0] + ".docx")
        return out if result.returncode == 0 and os.path.exists(out) else None
    except Exception as e:
        logger.error(f"DOCX conversion exception: {e}")
        return None
    finally:
        _give_back(profile)


def pdf_page_images(pdf_path: str, zoom: float = 2.0) -> list:
    """Each PDF page as PNG bytes. Shown as images, a preview works in any
    browser: Chrome blocks a PDF embedded in a page."""
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        return [page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png") for page in doc]
