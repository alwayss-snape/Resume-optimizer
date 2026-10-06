import os
import re
from typing import Any, Dict, List, Optional, Tuple
import docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field

from app.rendering.document_map import DocumentLocation, DocumentMap

class RawBlock(BaseModel):
    id: str
    block_type: str  # 'heading', 'paragraph', 'bullet', 'table_cell'
    text: str
    section: str = "general"
    location: DocumentLocation
    # Layout hints (set when the parser knows them): the whole line is bold,
    # and its font size in points. The normalizer uses them to tell a
    # project sub-heading from a bullet or a company line.
    bold: bool = False
    font_size: Optional[float] = None
    # Structural role set by the LLM structure extractor (P1.13): "name",
    # "company", "job_title", "subheading", "bullet" or "section:<Name>".
    # Overrides the normalizer's own layout guesses; the text is untouched.
    # A known layout (the LinkedIn export, P10.1) also sets "headline",
    # "location" and "text" (a plain line that is never a heading).
    hint: Optional[str] = None

class RawDocument(BaseModel):
    filename: str
    blocks: List[RawBlock] = Field(default_factory=list)
    document_map: DocumentMap = Field(default_factory=DocumentMap)
    raw_text: str = ""
    # Hyperlink targets found in the file (LinkedIn, GitHub, portfolio...).
    links: List[str] = Field(default_factory=list)
    # Set when the file was read by a layout-specific reader whose blocks
    # already carry structure hints, e.g. "linkedin_export" (P10.1).
    layout: Optional[str] = None

class DocxParser:
    # "●" (U+25CF) and friends are common Word bullet glyphs that are NOT the
    # same character as "•" (U+2022) — missing them here left the raw glyph
    # baked into bullet text (double-bulleted output: "• ● Built...").
    BULLET_PREFIXES = ("•", "●", "◦", "‣", "▸", "▪", "·", "∙", "⁃", "➢", "➤", "►", "✓", "❖",
                       "-", "*", "–", "—", "o ")

    _LABEL_RE = re.compile(r"^[^:\t]{1,40}:\s+\S")

    # Invisible characters some exporters leave in text (see ingestion/pdf.py).
    _INVISIBLE_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")

    def _classify(self, paragraph, text: str) -> Tuple[str, str, bool]:
        """-> (block_type, text without a bullet glyph, whole line bold)."""
        style_name = paragraph.style.name if paragraph.style else ""
        runs_with_text = [r for r in paragraph.runs if r.text.strip()]
        all_bold = bool(runs_with_text) and all(r.bold for r in runs_with_text)
        is_bullet = (
            style_name.lower().startswith("list bullet")
            or text.startswith(self.BULLET_PREFIXES)
        )
        # "Tools: Docker, Git" with only the label bold is a content line.
        bold_label_only = bool(self._LABEL_RE.match(text)) and not all_bold
        is_heading = (
            style_name.lower().startswith("heading")
            or (len(text) < 60 and paragraph.runs and any(r.bold for r in paragraph.runs)
                and not is_bullet and not bold_label_only)
        )
        if is_heading:
            return "heading", text, all_bold
        if is_bullet:
            # Strip leading bullet symbol if present
            for prefix in self.BULLET_PREFIXES:
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    break
            return "bullet", text, all_bold
        return "paragraph", text, all_bold

    _SKILLS_SECTION_RE = re.compile(r"skill|technolog|competenc|expertise|tools", re.IGNORECASE)
    _SKILL_CATEGORIES = {
        "languages", "programming languages", "frameworks", "libraries", "tools", "platforms", "cloud",
        "databases", "data", "ml", "machine learning", "devops", "testing", "technologies", "technical skills",
        "soft skills", "skills", "software", "web", "frontend", "backend", "mobile", "other", "certifications",
    }

    def _skills_label_row(self, row, current_section: str) -> Optional[str]:
        """'Label: values' for a two-cell row of a skills table, else None."""
        if not self._SKILLS_SECTION_RE.search(current_section or ""):
            return None
        cells, seen = [], set()
        for cell in row.cells:
            if id(cell._tc) not in seen:
                seen.add(id(cell._tc))
                text = self._INVISIBLE_RE.sub("", cell.text).strip()
                if text:
                    runs = [r for p in cell.paragraphs for r in p.runs if r.text.strip()]
                    cells.append((text, bool(runs) and all(r.bold for r in runs)))
        if len(cells) != 2:
            return None
        (label, label_bold), (values, values_bold) = cells
        if values_bold or values.lower().rstrip(":") in self._SKILL_CATEGORIES:
            return None  # a header row ("Languages | Tools"), not label + values
        # A label cell (bold, "Label:", or a known category) next to a list;
        # two skills side by side ("Python | SQL, Excel") stay separate.
        is_label = label_bold or label.endswith(":") or label.lower().rstrip(":") in self._SKILL_CATEGORIES
        if not is_label or len(label.split()) > 4 or "," in label or "\n" in label:
            return None
        return f"{label.rstrip(':')}: {values}"

    _MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"

    @classmethod
    def _text_box_paragraphs(cls, paragraph) -> List[Paragraph]:
        """Paragraphs inside text boxes anchored in this paragraph (P8.7:
        Canva and many Word templates put whole sections in text boxes,
        which python-docx doesn't walk). Word stores each box twice, the
        second copy as a legacy fallback; that copy is skipped."""
        out: List[Paragraph] = []
        for box in paragraph._p.iter(qn("w:txbxContent")):
            node, fallback = box.getparent(), False
            while node is not None:
                if node.tag == cls._MC_FALLBACK:
                    fallback = True
                    break
                node = node.getparent()
            if not fallback:
                out.extend(Paragraph(p, paragraph._parent) for p in box.iter(qn("w:p")))
        return out

    @staticmethod
    def _hyperlinks(doc) -> List[str]:
        """Targets of every external hyperlink in the body, in rId order
        (Word assigns rIds roughly in document order)."""
        rels = [r for r in doc.part.rels.values() if r.reltype == RT.HYPERLINK and r.is_external]
        rels.sort(key=lambda r: int(re.sub(r"\D", "", r.rId) or 0))
        links: List[str] = []
        for rel in rels:
            if rel.target_ref and rel.target_ref not in links:
                links.append(rel.target_ref)
        return links

    def parse(self, file_path: str) -> RawDocument:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"DOCX file not found at path: {file_path}")

        doc = docx.Document(file_path)
        blocks: List[RawBlock] = []
        document_map = DocumentMap()
        full_text_lines: List[str] = []

        current_section = "Header"
        block_counter = 0

        def add_block(block_id: str, block_type: str, text: str, bold: bool, location: DocumentLocation) -> None:
            blocks.append(RawBlock(
                id=block_id, block_type=block_type, text=text, section=current_section,
                location=location, bold=bold,
            ))
            document_map.add_location(block_id, location)
            full_text_lines.append(text)

        # Contact details sometimes live in the Word page header. They're
        # read first, but never patched (no paragraph_index), and only when
        # the body doesn't already open with the same text.
        header_paragraphs = []
        if doc.sections:
            header_paragraphs = [p for p in doc.sections[0].header.paragraphs if p.text.strip()]
        body_text = "\n".join(p.text for p in doc.paragraphs[:5])
        for h_idx, paragraph in enumerate(header_paragraphs):
            text = self._INVISIBLE_RE.sub("", paragraph.text).strip()
            if text in body_text:
                continue
            location = DocumentLocation(section="Header", original_text=paragraph.text)
            add_block(f"hdr_{h_idx:02d}", "paragraph", text, False, location)

        # Paragraphs and tables are walked in document order: processing
        # every table after all paragraphs put table content (a two-column
        # job header, a skills grid) under whichever section came last.
        p_idx = -1
        t_idx = -1
        box_counter = 0
        for item in doc.iter_inner_content():
            if isinstance(item, Paragraph):
                p_idx += 1
                p = item
                text = self._INVISIBLE_RE.sub("", p.text).strip()
                if text:
                    block_type, text, bold = self._classify(p, text)
                    if block_type == "heading":
                        current_section = text

                    block_id = f"blk_{block_counter:04d}"
                    block_counter += 1
                    location = DocumentLocation(
                        section=current_section,
                        paragraph_index=p_idx,
                        run_indices=list(range(len(p.runs))),
                        style_name=p.style.name if p.style else "",
                        original_text=p.text,
                    )
                    add_block(block_id, block_type, text, bold, location)
                # Text boxes anchored here, in reading order. Never patched
                # in place (no paragraph index): the template rebuilds them.
                for box_p in self._text_box_paragraphs(p):
                    box_text = self._INVISIBLE_RE.sub("", box_p.text).strip()
                    if not box_text:
                        continue
                    block_type, box_text, bold = self._classify(box_p, box_text)
                    if block_type == "heading":
                        current_section = box_text
                    location = DocumentLocation(section=current_section, original_text=box_p.text,
                                                style_name=box_p.style.name if box_p.style else "")
                    add_block(f"txb_{box_counter:04d}", block_type, box_text, bold, location)
                    box_counter += 1
                continue

            # Process every table paragraph individually. A cell may contain multiple
            # bullets; recording it as one block makes a safe in-place patch impossible.
            t_idx += 1
            table = item
            for r_idx, row in enumerate(table.rows):
                label_row = self._skills_label_row(row, current_section)
                if label_row:
                    # "Languages | Python, SQL" in a skills grid reads as one
                    # "Languages: Python, SQL" line, like the plain-text form.
                    block_id = f"tbl_{t_idx}_r{r_idx}_c0_p0"
                    location = DocumentLocation(section=current_section, table_index=t_idx, row=r_idx, column=0,
                                                cell_paragraph_index=0, original_text=label_row)
                    add_block(block_id, "paragraph", label_row, False, location)
                    continue
                seen_cells = set()
                for c_idx, cell in enumerate(row.cells):
                    # A merged cell is returned once per grid column it spans.
                    if id(cell._tc) in seen_cells:
                        continue
                    seen_cells.add(id(cell._tc))
                    for cp_idx, paragraph in enumerate(cell.paragraphs):
                        cell_text = self._INVISIBLE_RE.sub("", paragraph.text).strip()
                        if not cell_text:
                            continue
                        block_type, cell_text, bold = self._classify(paragraph, cell_text)
                        if block_type == "heading":
                            current_section = cell_text
                        block_id = f"tbl_{t_idx}_r{r_idx}_c{c_idx}_p{cp_idx}"
                        location = DocumentLocation(
                            section=current_section,
                            table_index=t_idx,
                            row=r_idx,
                            column=c_idx,
                            cell_paragraph_index=cp_idx,
                            run_indices=list(range(len(paragraph.runs))),
                            style_name=paragraph.style.name if paragraph.style else "",
                            original_text=paragraph.text,
                        )
                        add_block(block_id, block_type, cell_text, bold, location)

        return RawDocument(
            filename=os.path.basename(file_path),
            blocks=blocks,
            document_map=document_map,
            raw_text="\n".join(full_text_lines),
            links=self._hyperlinks(doc),
        )
