"""Generate linkedin_export.pdf: an anonymized profile laid out like
LinkedIn's "More → Save to PDF" export (P10.1).

All names, companies, numbers and text are invented. What's copied is the
*layout* of the export:
- a grey left sidebar (under ~35% of the width) with Contact, Top Skills,
  Languages, Certifications and Honors-Awards, set at 13 pt over 10.5 pt items;
- a main column with the name (26 pt), the headline (12 pt), the location in
  grey, and section headings at 15.75 pt;
- Experience as company (12 pt) → an optional total duration line (several
  roles) → title (11.5 pt bold) → "Month YYYY - Present (2 years 6 months)"
  and the location in grey → the description;
- descriptions wrap back to the column's left edge (no hanging indent), and
  the bullets are typed characters ("•", "-") or plain paragraphs;
- a description that wraps across a page break, a role with no description;
- a long profile URL that wraps inside the sidebar, a certification that wraps;
- Education as school (12 pt) → "Degree, Field · (2013 - 2017)";
- "Page N of M" footers, and link annotations for the profile and website.

Run from the repo root (macOS, needs the system Arial fonts):
    .venv_py311/bin/python tests/fixtures/resumes/make_linkedin_export_pdf.py
"""
import os

import pymupdf as fitz  # PyMuPDF

FONT_DIR = "/System/Library/Fonts/Supplemental"
OUT = os.path.join(os.path.dirname(__file__), "linkedin_export.pdf")

REG = fitz.Font(fontfile=f"{FONT_DIR}/Arial.ttf")
BOLD = fitz.Font(fontfile=f"{FONT_DIR}/Arial Bold.ttf")

W, H = 612, 792
SIDEBAR_W = 190           # grey panel width (31% of the page)
SIDE_X, SIDE_R = 28, 172  # sidebar text column
MAIN_X, MAIN_R = 220, 578  # main text column
TOP, BOTTOM = 48, 735

BLACK = (0, 0, 0)
GREY = (0.45, 0.45, 0.45)
PANEL = (0.95, 0.95, 0.95)

LINKEDIN_URL = "https://www.linkedin.com/in/morgan-ellis-4b7a21c9"
SITE_URL = "https://morganellis.dev"


def wrap(text, font, size, width):
    """Greedy word wrap, the way the export breaks a description."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and font.text_length(trial, fontsize=size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class Writer:
    """Writes lines down a column, starting a new page (with its footer)
    when the column is full. One TextWriter per page and colour."""

    def __init__(self, doc):
        self.doc = doc
        self.pages = 0
        self.writers = {}
        self.links = []
        self.new_page()

    def new_page(self):
        page = self.doc.new_page(width=W, height=H)
        if not self.pages:
            page.draw_rect(fitz.Rect(0, 0, SIDEBAR_W, H), color=None, fill=PANEL)
        self.pages += 1
        self.y = TOP

    def tw(self, color, page_no=None):
        page_no = self.pages - 1 if page_no is None else page_no
        key = (page_no, color)
        if key not in self.writers:
            self.writers[key] = fitz.TextWriter(fitz.Rect(0, 0, W, H), color=color)
        return self.writers[key]

    def text(self, x, y, text, font, size, color=BLACK, page_no=None):
        self.tw(color, page_no).append(fitz.Point(x, y), text, font=font, fontsize=size)

    def main(self, text, font=REG, size=10.5, color=BLACK, gap=0.0, wrap_width=None):
        """One main-column paragraph, wrapped; page breaks fall between lines."""
        self.y += gap
        step = size * 1.3
        for piece in wrap(text, font, size, wrap_width or (MAIN_R - MAIN_X)):
            if self.y + step > BOTTOM:
                self.new_page()
            self.y += step
            self.text(MAIN_X, self.y, piece, font, size, color)

    def finish(self):
        total = self.pages
        for i in range(total):
            footer = f"Page {i + 1} of {total}"
            x = (W - REG.text_length(footer, fontsize=9)) / 2
            self.text(x, H - 22, footer, REG, 9, GREY, page_no=i)
        for (page_no, _), tw in self.writers.items():
            tw.write_text(self.doc[page_no])
        for uri, rect in self.links:
            self.doc[0].insert_link({"kind": fitz.LINK_URI, "uri": uri, "from": rect})


def sidebar(w):
    y = TOP

    def head(text):
        nonlocal y
        y += 26
        w.text(SIDE_X, y, text, BOLD, 13, page_no=0)
        y += 4

    def item(text, color=BLACK):
        nonlocal y
        for piece in wrap(text, REG, 10.5, SIDE_R - SIDE_X):
            y += 14
            w.text(SIDE_X, y, piece, REG, 10.5, color, page_no=0)
        return y

    head("Contact")
    item("morgan.ellis@example.com")
    item("+91 98765 43210 (Mobile)")
    # The export breaks a long profile URL to fit the column.
    y += 14
    w.text(SIDE_X, y, "www.linkedin.com/in/morgan-", REG, 10.5, page_no=0)
    link_top = y - 10
    y += 14
    w.text(SIDE_X, y, "ellis-4b7a21c9 (LinkedIn)", REG, 10.5, page_no=0)
    w.links.append((LINKEDIN_URL, fitz.Rect(SIDE_X, link_top, SIDE_R, y + 3)))
    item("morganellis.dev (Personal)")
    w.links.append((SITE_URL, fitz.Rect(SIDE_X, y - 10, SIDE_R, y + 3)))

    head("Top Skills")
    for skill in ("Distributed Systems", "Go (Programming Language)", "PostgreSQL"):
        item(skill)

    head("Languages")
    item("English (Full Professional)")
    item("Hindi (Native or Bilingual)")

    head("Certifications")
    item("AWS Certified Solutions Architect – Associate")
    item("Certified Kubernetes Application Developer (CKAD)")

    head("Honors-Awards")
    item("Engineering Excellence Award 2022")


def main_column(w):
    w.y = TOP + 4
    w.main("Morgan Ellis", REG, 26)
    w.main("Senior Backend Engineer | Payments and Distributed Systems", REG, 12, gap=4)
    w.main("Bengaluru, Karnataka, India", REG, 10.5, GREY, gap=2)

    def heading(text):
        w.main(text, REG, 15.75, gap=16)
        w.y += 2

    def company(name, duration=None):
        w.main(name, REG, 12, gap=10)
        if duration:
            w.main(duration, REG, 10.5, GREY)

    def role(title, dates, location=None):
        w.main(title, BOLD, 11.5, gap=4)
        w.main(dates, REG, 10.5, GREY)
        if location:
            w.main(location, REG, 10.5, GREY)
        w.y += 4

    heading("Summary")
    w.main("Backend engineer with 7 years of experience building payment and ledger services in Go and Java. "
           "I care about reliable systems, clear on-call runbooks and mentoring the engineers around me.")

    heading("Experience")
    company("Lumen Pay", "4 years 10 months")
    role("Senior Backend Engineer", "April 2022 - Present (2 years 7 months)", "Bengaluru, Karnataka, India")
    w.main("• Led the move of card settlement from a nightly batch to an event-driven service in Go and "
           "Kafka, cutting settlement time from 9 hours to 40 minutes")
    w.main("• Designed an idempotent ledger API on PostgreSQL that handles 3,000 requests per second at peak")
    w.main("• Mentor four engineers and run the payments on-call rotation")
    role("Backend Engineer", "January 2020 - March 2022 (2 years 3 months)", "Mumbai, Maharashtra, India")
    w.main("Built the merchant onboarding service in Java and Spring Boot and reduced manual KYC reviews by "
           "35% within two quarters.")
    w.main("Added contract tests between the onboarding and risk services, catching breaking API changes "
           "before release.", gap=6)

    company("Brightline Logistics")
    role("Software Engineer", "July 2017 - December 2019 (2 years 6 months)", "Pune, Maharashtra, India")
    w.main("- Wrote route-assignment jobs in Python that matched 20,000 daily parcels to delivery vans "
           "across 14 city depots")
    w.main("- Moved the parcel-tracking database from MySQL to PostgreSQL with zero downtime, using "
           "dual writes and a staged read cutover")
    w.main("- Built Grafana dashboards for depot managers to follow late deliveries by route")
    # Leave just enough room on page 1 for this bullet's first line, so it
    # wraps across the page break.
    w.y = BOTTOM - 14
    w.main("- Cut the nightly reconciliation job from 3 hours to 25 minutes by replacing row-by-row "
           "updates with batched upserts")

    company("Northstar Labs")
    role("Software Engineering Intern", "January 2017 - June 2017 (6 months)")

    heading("Education")
    w.main("Westbrook Institute of Technology", REG, 12, gap=6)
    w.main("Bachelor of Engineering - BE, Computer Science · (2013 - 2017)", REG, 10.5)
    w.main("Lakeside College", REG, 12, gap=8)
    w.main("Higher Secondary Certificate, Science · (2011 - 2013)", REG, 10.5)


def build():
    doc = fitz.open()
    w = Writer(doc)
    main_column(w)
    sidebar(w)
    w.finish()
    doc.subset_fonts()
    doc.save(OUT, garbage=4, deflate=True)
    print("wrote", OUT, "pages =", w.pages)


if __name__ == "__main__":
    build()
