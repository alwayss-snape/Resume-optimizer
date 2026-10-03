"""Plain-text resumes: a .txt upload or text pasted in the app (P8.22).

Each non-empty line becomes a block: a line starting with a bullet glyph
is a bullet, a short all-caps line (or one of the known section names
alone) is a heading, anything else a paragraph. The normalizer does the
rest, exactly as for a DOCX; nothing is patched in place, so the template
is always used.
"""
import os
import re
from typing import List

from app.ingestion.docx import DocxParser, RawBlock, RawDocument
from app.ingestion.errors import NO_TEXT, UnreadableFile
from app.rendering.document_map import DocumentLocation, DocumentMap

_BULLET_RE = re.compile(r"^\s*(?:[•●◦‣▸▪·∙⁃➢➤►✓❖*–—]|-(?=\s)|\d{1,2}[.)](?=\s))\s*")
_URL_RE = re.compile(r"https?://\S+|\b[\w.-]+\.(?:com|in|io|dev|me|org|net|ai|co)/\S+", re.IGNORECASE)


def read_text_file(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            if "\x00" not in text:
                return text
        except UnicodeDecodeError:
            continue
    raise UnreadableFile(NO_TEXT)


class TextParser:
    def parse(self, file_path: str) -> RawDocument:
        text = read_text_file(file_path)
        blocks: List[RawBlock] = []
        document_map = DocumentMap()
        section = "Header"
        lines = [l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        for i, raw in enumerate(lines):
            line = DocxParser._INVISIBLE_RE.sub("", raw).strip()
            if not line:
                continue
            words = line.split()
            if _BULLET_RE.match(line) and not re.match(r"^\d{4}", line):
                kind, line = "bullet", _BULLET_RE.sub("", line, count=1).strip()
            elif (len(words) <= 5 and line.isupper() and re.search(r"[^\W\d_]", line)) or (
                    len(words) <= 4 and line.rstrip(":").lower() in {
                        "summary", "experience", "work experience", "education", "skills", "projects",
                        "certifications", "languages", "volunteer", "interests", "awards", "publications"}):
                kind, section = "heading", line
            else:
                kind = "paragraph"
            location = DocumentLocation(section=section, original_text=raw)
            block_id = f"txt_{i:04d}"
            blocks.append(RawBlock(id=block_id, block_type=kind, text=line, section=section, location=location,
                                   bold=kind == "heading"))
            document_map.add_location(block_id, location)
        if not blocks:
            raise UnreadableFile(NO_TEXT)
        return RawDocument(filename=os.path.basename(file_path), blocks=blocks, document_map=document_map,
                           raw_text="\n".join(b.text for b in blocks), links=_URL_RE.findall(text))
