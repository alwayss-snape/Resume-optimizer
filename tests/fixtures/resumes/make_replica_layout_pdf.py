"""Generate replica_layout.pdf: an anonymized resume with the same PDF layout
traits as a real user resume that the old parser misread (P1.11 / P1.12).

All names, companies, numbers and bullets are invented. What's copied is the
*layout*: a large bold name, "●" + zero-width-space bullets with continuation
lines indented to the bullet text, a bold continuation line, project
sub-headings inside a job, two roles at one company, a location pushed right
with spaces, right-aligned columns printed as separate text runs on the same
row, a two-category skills line, and labelled certification / interest lines.

Run from the repo root (macOS, needs the system Arial fonts):
    .venv_py311/bin/python tests/fixtures/resumes/make_replica_layout_pdf.py
"""
import os

import fitz  # PyMuPDF

FONT_DIR = "/System/Library/Fonts/Supplemental"
OUT = os.path.join(os.path.dirname(__file__), "replica_layout.pdf")

REG = fitz.Font(fontfile=f"{FONT_DIR}/Arial.ttf")
BOLD = fitz.Font(fontfile=f"{FONT_DIR}/Arial Bold.ttf")
ITAL = fitz.Font(fontfile=f"{FONT_DIR}/Arial Italic.ttf")

ZWSP = "​"
LEFT, INDENT = 9, 27


def line(tw, x, y, parts, size=11.5):
    """parts: list of (text, font). One text line made of several spans."""
    pos = fitz.Point(x, y)
    for text, font in parts:
        _, pos = tw.append(pos, text, font=font, fontsize=size)


def bullet(tw, y, first, rest=(), size=11.5, step=14.2):
    """A '●' bullet; `first` / each item of `rest` is a list of (text, font)."""
    line(tw, LEFT, y, [("●", REG), (ZWSP + " ", REG)] + first, size)
    for cont in rest:
        y += step
        line(tw, INDENT, y, cont, size)
    return y + 12.4


def right(tw, y, text, font, size=11.5, right_edge=560):
    """A separate text run right-aligned on the same row as a left one."""
    width = font.text_length(text, fontsize=size)
    line(tw, right_edge - width, y + 1.3, [(text, font)], size)


def build():
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    tw = fitz.TextWriter(page.rect)

    line(tw, LEFT, 70, [("Jordan Avery ", BOLD)], 23)
    line(tw, LEFT, 90, [("jordan.avery@example.com | +91-9000000000 | Pune, India ", REG)], 12)

    line(tw, LEFT, 116, [("PROFESSIONAL ", BOLD), ("SUMMARY ", BOLD)], 12)
    line(tw, 0, 131, [("   ", REG), ("Data Scientist", BOLD),
                      (" with 4 years of experience building forecasting and ranking systems for ", REG)], 12)
    line(tw, LEFT, 145, [("retail and logistics clients. Uses ", REG), ("Python, SQL, Spark", BOLD),
                         (" and cloud MLOps to turn data into ", REG)], 12)
    line(tw, LEFT, 159, [("measurable business outcomes. ", REG)], 12)

    line(tw, LEFT, 174, [(" ", REG), ("WORK EXPERIENCE  ", BOLD)], 12)
    line(tw, LEFT, 193, [("Northwind Analytics - A Contoso Group Company" + " " * 70 + "Pune, India ", BOLD)], 11)
    line(tw, LEFT, 205, [("Senior Data Scientist, March 2024 - Present   ", BOLD)], 11)
    line(tw, LEFT, 217, [("Data Scientist, July 2021 - March 2024 ", REG)], 11)

    y = 232
    line(tw, LEFT, y, [("Demand Forecasting Platform ", BOLD)])
    y = bullet(tw, y + 12.5, [("Built", REG), (" a demand forecasting service on Google Cloud using ", REG),
                              ("Prophet", BOLD), (" and gradient boosted trees, ", REG)],
               [[("covering 1,200 stores and replacing a spreadsheet process. ", REG)]])
    y = bullet(tw, y, [("Automated", REG), (" weekly retraining and backtesting with Airflow, keeping forecast ", REG)],
               [[("error under 8% across seasonal peaks ", REG)]])

    line(tw, LEFT, y + 2, [(" ", REG), ("Route Optimization Analytics ", BOLD)])
    y = bullet(tw, y + 16, [("Designed", REG), (" a routing analysis in Python that combined GPS pings, delivery ", REG)],
               [[("windows and depot capacity ", REG)]])
    y = bullet(tw, y, [("Reported", REG), (" late-delivery hotspots to regional managers across three ", REG)],
               [[("distribution networks ", BOLD)]])

    line(tw, LEFT, y + 2, [(" ", REG), ("Customer Churn Model ", BOLD)])
    y = bullet(tw, y + 16, [("Trained", REG), (" an XGBoost churn model with engineered tenure and usage features, ", REG)],
               [[("lifting retention campaign response by 15% ", BOLD)]])
    y = bullet(tw, y, [("Deployed", REG), (" the model behind a FastAPI service with drift monitoring ", REG)])

    line(tw, LEFT, y + 4, [("Blue Harbor Bank" + " " * 118 + "Mumbai, India ", BOLD)], 11)
    line(tw, LEFT, y + 16, [("Analytics Intern, January 2021 - June 2021 ", BOLD)], 11)
    y = bullet(tw, y + 30, [("Cleaned", REG), (" loan application data in SQL and built Tableau reports for the credit ", REG)],
               [[("risk team ", REG)]])

    line(tw, LEFT, y + 6, [("SKILLS ", BOLD)], 12)
    line(tw, LEFT, y + 20, [("Languages: ", BOLD), ("Python, Scala, SQL, R     ", REG),
                            ("Frameworks: ", BOLD), ("Pandas, NumPy, PyTorch, and XGBoost ", REG)])
    line(tw, LEFT, y + 35, [("Tools: ", BOLD), ("PostgreSQL, Tableau, Airflow, GCP, Excel ", REG)])

    y += 50
    line(tw, LEFT, y, [("EDUCATION ", BOLD)], 12)
    line(tw, LEFT, y + 14, [("Riverside Institute of Technology", BOLD), (ZWSP, REG)])
    right(tw, y + 14, "Chennai, India ", REG)
    line(tw, LEFT, y + 27, [("B.Tech in Electronics Engineering(CGPA : 8.5/10)" + ZWSP, ITAL)])
    right(tw, y + 27, "2016-2020 ", BOLD, size=11)

    y += 42
    line(tw, LEFT, y, [("CERTIFICATIONS &  INTERESTS ", BOLD)], 11)
    line(tw, LEFT, y + 14, [("Certifications: ", BOLD),
                            ("Google Cloud Professional Data Engineer | Statistics for Data Science ", REG)])
    line(tw, LEFT, y + 27, [("Interests: ", BOLD), ("Chess • Cycling • Photography ", REG)])

    tw.write_text(page)
    doc.subset_fonts()
    doc.save(OUT, garbage=4, deflate=True)
    print("wrote", OUT, "last y =", y + 27)


if __name__ == "__main__":
    build()
