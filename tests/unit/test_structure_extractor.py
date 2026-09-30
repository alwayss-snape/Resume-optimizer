"""LLM-assisted structure extraction with a verbatim guard (P1.13)."""
from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.structure_extractor import LineLabel, ResumeLineLabels, StructureExtractor
from app.ingestion.docx import RawBlock, RawDocument
from app.ingestion.pdf import PdfParser
from app.rendering.document_map import DocumentLocation


class FakeLLM:
    def __init__(self, labels, available=True):
        self.labels = labels
        self.available = available
        self.calls = 0

    def is_available(self):
        return self.available

    def generate_json(self, messages, schema_model, **kwargs):
        self.calls += 1
        assert schema_model is ResumeLineLabels
        return ResumeLineLabels(lines=[LineLabel(index=i, label=l) for i, l in self.labels])


def _raw(lines):
    blocks = []
    for i, (block_type, text) in enumerate(lines):
        loc = DocumentLocation(section="x", paragraph_index=i, original_text=text)
        blocks.append(RawBlock(id=f"b{i}", block_type=block_type, text=text, location=loc))
    return RawDocument(filename="t.docx", blocks=blocks, raw_text="\n".join(t for _, t in lines))


# An unusual layout: section headings the normalizer doesn't know, and a
# plain (not bold) company line with no separator.
ODD = [
    ("paragraph", "Riley Chen"),
    ("paragraph", "riley@example.com"),
    ("paragraph", "WHERE I'VE BEEN"),
    ("paragraph", "Initech"),
    ("paragraph", "Platform Engineer 2019 to 2023"),
    ("bullet", "Moved 40 services to Kubernetes."),
    ("bullet", "Cut deploy time from hours to minutes."),
]
ODD_LABELS = [(0, "name"), (1, "contact"), (2, "section_experience"), (3, "company"),
              (4, "job_title"), (5, "bullet"), (6, "bullet")]


def _parse(lines):
    raw = _raw(lines)
    doc, evidence = ResumeNormalizer().normalize(raw)
    return raw, doc, evidence


def test_good_parse_never_calls_the_llm():
    raw = PdfParser().parse("tests/fixtures/resumes/replica_layout.pdf")
    doc, evidence = ResumeNormalizer().normalize(raw)
    llm = FakeLLM([])
    out_doc, _, issues = StructureExtractor(llm).improve(raw, doc, evidence)
    assert issues == [] and llm.calls == 0 and out_doc is doc


def test_bad_parse_is_relabelled_and_text_stays_verbatim():
    raw, doc, evidence = _parse(ODD)
    extractor = StructureExtractor(FakeLLM(ODD_LABELS))
    assert extractor.problems(doc.resume, evidence, raw)  # the deterministic parse misread it

    new_doc, new_evidence, issues = extractor.improve(raw, doc, evidence)
    resume = new_doc.resume
    assert issues == []
    assert resume.candidate.name == "Riley Chen"
    [exp] = resume.experience
    assert exp.company == "Initech"
    assert (exp.title, exp.start_date, exp.end_date) == ("Platform Engineer", "2019", "2023")
    assert [b.text for b in exp.bullets] == ["Moved 40 services to Kubernetes.", "Cut deploy time from hours to minutes."]
    # Verbatim guard: every value is a substring of the original file text.
    for value in (resume.candidate.name, exp.company, exp.title, *[b.text for b in exp.bullets]):
        assert value in raw.raw_text
    # The raw document itself is not modified.
    assert all(b.hint is None for b in raw.blocks)


def test_hallucinated_indices_are_dropped():
    raw, doc, evidence = _parse(ODD)
    labels = ODD_LABELS + [(99, "company"), (3, "bullet")]  # unknown index, duplicate index
    parsed = StructureExtractor(FakeLLM(labels)).label_lines(raw)
    assert (99, "company") not in parsed and parsed.count((3, "company")) == 1 and (3, "bullet") not in parsed


def test_llm_unavailable_keeps_deterministic_parse():
    raw, doc, evidence = _parse(ODD)
    llm = FakeLLM(ODD_LABELS, available=False)
    out_doc, _, issues = StructureExtractor(llm).improve(raw, doc, evidence)
    assert out_doc is doc and issues and llm.calls == 0


def test_worse_llm_parse_is_rejected():
    raw, doc, evidence = _parse(ODD)
    # Everything labelled as plain text: the re-parse is no better.
    labels = [(i, "text") for i in range(len(ODD))]
    out_doc, _, _ = StructureExtractor(FakeLLM(labels)).improve(raw, doc, evidence)
    assert out_doc is doc
