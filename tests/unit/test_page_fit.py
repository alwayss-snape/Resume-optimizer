"""P2.4: the page-fit loop trims in a fixed order, keeps minimums, reports
every removal and stops after MAX_RENDERS renders. Rendering and page
counting are faked, so no LibreOffice is needed."""
from app.domain.resume import Candidate, Experience, Project, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.rendering.page_fit import MAX_RENDERS, PAGE_BODY_PT, PageFitter, bullet_height


def _doc():
    current = Experience(id="e1", company="Acme", title="Engineer", bullets=[
        ResumeBullet(id=f"c{i}", text=f"Current role bullet {i}.") for i in range(5)])
    older = Experience(id="e2", company="Initech", title="Analyst", bullets=[
        ResumeBullet(id=f"o{i}", text=f"Older role bullet {i}.") for i in range(4)])
    project = Project(id="p1", name="Side Project", bullets=[ResumeBullet(id="p0", text="Built a thing.")])
    return ResumeDocument(resume=Resume(candidate=Candidate(name="A"), experience=[current, older],
                                        projects=[project], interests=["Chess"]))


class FakeLayout:
    """Pages follow the content: a fixed height per bullet / section."""

    def __init__(self, base_pt):
        self.base_pt = base_pt
        self.renders = 0

    def height(self, doc):
        r = doc.resume
        h = self.base_pt + sum(bullet_height(b.text) for s in [*r.experience, *r.projects] for b in s.bullets)
        h += 40 if r.interests else 0
        return h * (0.9 if doc.presentation.compact else 1.0)

    def render(self, doc, docx_path, out_dir):
        self.renders += 1
        self.last_height = self.height(doc)
        return "fake.pdf"

    def measure(self, _pdf):
        pages = int(self.last_height // PAGE_BODY_PT) + 1
        return pages, self.last_height - (pages - 1) * PAGE_BODY_PT


RELEVANCE = {"c0": 0.9, "c1": 0.8, "c2": 0.7, "c3": 0.2, "c4": 0.1,
             "o0": 0.6, "o1": 0.5, "o2": 0.3, "o3": 0.05, "p0": 0.4}


def test_fits_without_trimming():
    doc, layout = _doc(), FakeLayout(100)
    result = PageFitter(layout.render, layout.measure).fit(doc, "x.docx", "out", 1, RELEVANCE)
    assert result.fits and result.renders == 1 and not result.notes
    assert doc.resume.interests == ["Chess"]


def test_interests_go_first():
    doc = _doc()
    layout = FakeLayout(PAGE_BODY_PT - FakeLayout(0).height(doc) + 20)  # 20pt over, interests are 40
    result = PageFitter(layout.render, layout.measure).fit(doc, "x.docx", "out", 1, RELEVANCE)
    assert result.fits and result.renders == 2
    assert doc.resume.interests == []
    assert len(doc.resume.experience[0].bullets) == 5  # no bullet touched
    assert result.notes == ["Removed the Interests section to fit the page target."]


def test_least_relevant_bullets_older_roles_first_within_minimums():
    doc = _doc()
    layout = FakeLayout(PAGE_BODY_PT - FakeLayout(0).height(doc) + 40 + 3 * bullet_height("x"))
    result = PageFitter(layout.render, layout.measure).fit(doc, "x.docx", "out", 1, RELEVANCE,
                                                           trim_candidates={"c4"})
    assert result.fits
    current, older = doc.resume.experience
    assert "c4" not in [b.id for b in current.bullets]  # planner's trim candidate goes first
    assert [b.id for b in older.bullets][:2] == ["o0", "o1"]  # the most relevant stay
    assert len(current.bullets) >= 3 and len(older.bullets) >= 2
    assert any("less relevant bullet" in n for n in result.notes)


def test_minimums_hold_and_render_cap_is_respected():
    doc = _doc()
    layout = FakeLayout(5 * PAGE_BODY_PT)  # can never fit on 1 page
    result = PageFitter(layout.render, layout.measure).fit(doc, "x.docx", "out", 1, RELEVANCE)
    assert not result.fits and result.renders <= MAX_RENDERS
    current, older = doc.resume.experience
    assert len(current.bullets) >= 3 and len(older.bullets) >= 2
    assert doc.presentation.compact
    assert not doc.resume.projects and any('"Side Project" project' in n for n in result.notes)
    assert "Still" in result.notes[-1]


def test_lone_irrelevant_bullet_goes_with_its_sub_heading():
    doc = _doc()
    doc.resume.experience[0].bullets = [
        ResumeBullet(id="g1", text="Relevant work.", group="Platform"),
        ResumeBullet(id="g2", text="More relevant work.", group="Platform"),
        ResumeBullet(id="g3", text="Still relevant.", group="Platform"),
        ResumeBullet(id="g4", text="Unrelated side task.", group="Misc"),
    ]
    relevance = {"g1": 0.9, "g2": 0.8, "g3": 0.7, "g4": 0.01, **RELEVANCE}
    doc.resume.experience[1].bullets = doc.resume.experience[1].bullets[:2]  # at its minimum
    doc.resume.projects = []
    layout = FakeLayout(PAGE_BODY_PT - FakeLayout(0).height(doc) + 40 + 10)
    result = PageFitter(layout.render, layout.measure).fit(doc, "x.docx", "out", 1, relevance)
    assert result.fits
    assert [b.id for b in doc.resume.experience[0].bullets] == ["g1", "g2", "g3"]  # g3 (0.7) kept


def test_whole_sub_section_removed_when_bullets_are_at_minimum():
    doc = _doc()
    doc.resume.experience[0].bullets = [
        ResumeBullet(id="g1", text="Relevant work.", group="Platform"),
        ResumeBullet(id="g2", text="More relevant work.", group="Platform"),
        ResumeBullet(id="g3", text="Still relevant.", group="Platform"),
        ResumeBullet(id="m1", text="Side task one.", group="Misc"),
        ResumeBullet(id="m2", text="Side task two.", group="Misc"),
    ]
    relevance = {"g1": 0.9, "g2": 0.8, "g3": 0.7, "m1": 0.02, "m2": 0.01, **RELEVANCE}
    doc.resume.experience[1].bullets = doc.resume.experience[1].bullets[:2]
    doc.resume.projects = []
    doc.resume.interests = []
    # Over by more than two bullets: both Misc bullets go (bullet step), and
    # the fit is reached without touching the current role's minimum.
    layout = FakeLayout(PAGE_BODY_PT - FakeLayout(0).height(doc) + 2 * bullet_height("x") + 5)
    result = PageFitter(layout.render, layout.measure).fit(doc, "x.docx", "out", 1, relevance)
    assert result.fits
    assert [b.id for b in doc.resume.experience[0].bullets] == ["g1", "g2", "g3"]
    assert len(doc.resume.experience[1].bullets) == 2


def test_no_pdf_converter_renders_once():
    doc = _doc()
    result = PageFitter(lambda *a: None, lambda p: (1, 0.0)).fit(doc, "x.docx", "out", 1, RELEVANCE)
    assert result.renders == 1 and result.pages is None
    assert "not checked" in result.notes[0]
