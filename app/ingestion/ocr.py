import logging
from typing import Optional

logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self):
        self._tesseract_available = False
        try:
            import pytesseract
            self._tesseract_available = True
        except ImportError:
            self._tesseract_available = False

    def is_available(self) -> bool:
        return self._tesseract_available

    def extract_text_from_image(self, image_bytes: bytes) -> Optional[str]:
        if not self._tesseract_available:
            logger.warning("pytesseract is not installed or tesseract binary unavailable.")
            return None

        try:
            import io
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None
