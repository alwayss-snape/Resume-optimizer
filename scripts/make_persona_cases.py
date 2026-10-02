"""Turn the 2026-10-02 user-testing personas into eval cases (P8.1).

Every person, employer and school is fictional. The resumes and JDs were
written for the cross-domain user test (docs/user_testing/2026-10-02/); this
script copies them into data/eval/personas/<name>/ and writes expected.json
from the ground truth below, which is what the file really says, not what the
parser happens to read today.

    python scripts/make_persona_cases.py

Expected facts are parse-level (contact, each job's title / company / dates
/ bullet count, education count) plus `must_keep`: phrases from the source
that must appear in the rendered output, so nothing is silently dropped.
`tests/integration/test_persona_cases.py` runs them offline (no LLM).
"""
import json
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "docs", "user_testing", "2026-10-02")
OUT = os.path.join(ROOT, "data", "eval", "personas")


def job(title=None, company=None, start=None, end=None, bullets=None):
    """One job as the file states it. Fields left as None aren't checked."""
    return {k: v for k, v in dict(title=title, company=company, start=start, end=end, bullets=bullets).items()
            if v is not None}


PERSONAS = {
    "nurse": {
        "resume": "nurse.docx",
        "expect": {
            "name": "Maria Gonzalez, RN, BSN", "email": "maria.gonzalez.rn@example.com", "phone": "(602) 555-0147",
            "jobs": 2,
            "job_details": [
                job("Registered Nurse - Step-Down Unit", "Banner University Medical Center", "03/2021", "Present", 4),
                job("Registered Nurse - Medical-Surgical", "St. Joseph's Hospital", "06/2019", "02/2021", 2),
            ],
            "education": 1,
            "must_keep": ["License #RN123456", "PALS", "Mayo Clinic Hospital (120 hrs)", "Phoenix Children's (90 hrs)",
                          "English (native), Spanish (fluent)", "Circle the City"],
        },
    },
    "nurse-pdf": {
        "resume": "nurse.pdf", "jd": "nurse.txt",
        "expect": {
            "email": "maria.gonzalez.rn@example.com", "phone": "(602) 555-0147", "jobs": 2,
            "job_details": [job(start="03/2021", end="Present", bullets=4), job(start="06/2019", end="02/2021", bullets=2)],
            "must_keep": ["License #RN123456", "Mayo Clinic Hospital (120 hrs)", "Circle the City"],
        },
    },
    "teacher": {
        "resume": "teacher.docx",
        "expect": {
            "name": "Priya Raman", "phone": "512-555-0199", "jobs": 2,
            "job_details": [
                job("8th Grade Science Teacher", "Round Rock ISD", "Aug 2016", "Jun 2024", 4),
                job("Curriculum Writer (contract)", "Texas Education Agency", "Summer 2021", None, 1),
            ],
            "education": 2,
            "must_keep": ["priyaraman.design", "ATD Instructional Design Certificate", "Articulate Rise 360",
                          "STAAR science pass rate"],
        },
    },
    "electrician": {
        "resume": "electrician.docx",
        "expect": {
            "name": "DEREK O'BRIEN", "phone": "216-555-0110", "jobs": 2,
            "job_details": [
                job("Journeyman Electrician", "Lakeshore Electric LLC", "2017", "Current", 3),
                job("Apprentice Electrician", "IBEW Local 38", "2013", "2017", 1),
            ],
            "must_keep": ["Ohio Journeyman Electrician License", "OSHA 30", "Valid Ohio driver's license",
                          "IBEW/NECA 5-year apprenticeship program"],
        },
    },
    "warehouse": {
        "resume": "warehouse.docx",
        "expect": {
            "name": "Tyrone Jackson", "phone": "901-555-0123", "jobs": 2,
            "job_details": [
                job("Warehouse Associate", "FedEx Ground Hub", "2019", "present", 3),
                job("Delivery Driver (part-time, concurrent)", "DoorDash", "2020", "present", 1),
            ],
            "education": 1,
            "must_keep": ["CDL Class A (2022)", "HAZMAT endorsement", "Forklift Operator Certification (OSHA)"],
        },
    },
    "retail": {
        "resume": "retail.docx",
        "expect": {
            "name": "Aaliyah Brooks", "phone": "(404) 555-0188", "jobs": 2,
            "job_details": [
                job("Shift Supervisor", "Starbucks", "2021", "Present", 3),
                job("Sales Associate", "Target", "2019", "2021", 1),
            ],
            "education": 1,
            "must_keep": ["cash reconciliation", "conflict resolution"],
        },
    },
    "sales": {
        "resume": "sales.docx",
        "expect": {
            "name": "Jordan Kim", "phone": "312-555-0166", "jobs": 3,
            "job_details": [
                job("Senior Account Executive", "CloudMetrics Inc.", "Jan 2021", "Present", 3),
                job("Account Executive", "PayStream", "Mar 2018", "Dec 2020", 2),
                job("Sales Development Representative", "PayStream", "Jun 2016", "Feb 2018", 1),
            ],
            "education": 1,
            "must_keep": ["largest deal in company history", "linkedin.com/in/jordankim"],
        },
    },
    "sales-pdf": {
        "resume": "sales.pdf", "jd": "sales.txt",
        "expect": {
            "phone": "312-555-0166", "jobs": 3,
            "job_details": [job(start="Jan 2021", end="Present", bullets=3), job(start="Mar 2018", end="Dec 2020", bullets=2),
                            job(start="Jun 2016", end="Feb 2018", bullets=1)],
            "must_keep": ["largest deal in company history"],
        },
    },
    "accountant": {
        "resume": "accountant.docx",
        "expect": {
            "name": "Rebecca Liu, CPA", "phone": "646-555-0177", "jobs": 2,
            "job_details": [
                job("Senior Accountant", "Brightline Media", "07/2022", "Present", 3),
                job("Audit Associate", "KPMG LLP", "09/2019", "06/2022", 1),
            ],
            "education": 1,
            "must_keep": ["Certified Public Accountant (CPA), New York, 2021", "BlackLine"],
        },
    },
    "lawyer": {
        "resume": "lawyer.docx",
        "expect": {
            "name": "Samuel Adeyemi, Esq.", "phone": "202-555-0135", "jobs": 2,
            "job_details": [
                job("Associate", "Hale & Morgan LLP", "Sep 2018", "Present", 3),
                job("Judicial Law Clerk", "Hon. Ellen Park", "Aug 2017", "Aug 2018", 1),
            ],
            "education": 2,
            "must_keep": ["District of Columbia Bar, 2018", "New York State Bar, 2017",
                          "Arbitration Clauses After Epic Systems", "Discovery of Ephemeral Messaging",
                          "Available upon request", "bench memoranda"],
        },
    },
    "academic": {
        "resume": "academic.docx",
        "expect": {
            "name": "Dr. Hannah Okafor", "email": "h.okafor@example.edu", "jobs": 2,
            "job_details": [
                job("Assistant Professor of Biology", "Midwestern State University", "2019", "Present", 2),
                job("Postdoctoral Research Fellow", "University of Wisconsin–Madison", "2016", "2019", 1),
            ],
            "education": 2,
            "must_keep": ["Microbial ecology, soil metagenomics", "NSF CAREER Award",
                          "Soil microbial response to warming experiment 45", "ASM Microbe 2023",
                          "Reviewer for ISME Journal", "American Society for Microbiology", "ORCID 0000-0002-1234-5678"],
        },
    },
    "designer": {
        "resume": "designer.docx",
        "expect": {
            "name": "Lena Park", "email": "lena@example.com", "jobs": 2,
            "job_details": [
                job("Product Designer", "Hopper", "2020", "Present", 2),
                job("Visual Designer", "Wieden+Kennedy", "2017", "2020", 1),
            ],
            "education": 1,
            "must_keep": ["lenapark.design", "dribbble.com/lenapark", "Design systems"],
        },
    },
    "executive": {
        "resume": "executive.docx",
        "expect": {
            "name": "Robert J. Whitfield", "phone": "214-555-0101", "jobs": 7,
            "job_details": [
                job("Chief Operating Officer", "Atlas Industrial Group", "2018", "Present", 4),
                job("SVP, Global Supply Chain", "Meridian Consumer Products", "2013", "2018", 4),
                job("VP Manufacturing", "Meridian Consumer Products", "2009", "2013", 4),
                job("Plant Director", "Kessler Foods", "2005", "2009", 4),
                job("Operations Manager", "Kessler Foods", "2001", "2005", 4),
                job("Production Supervisor", "General Mills", "1998", "2001", 4),
                job("Industrial Engineer", "General Mills", "1996", "1998", 4),
            ],
            "education": 2,
            "must_keep": ["Board Member, Dallas Regional Chamber", "Kellogg School of Management", "Purdue University"],
        },
    },
    "newgrad": {
        "resume": "newgrad.docx",
        "expect": {
            "name": "Emily Chen", "phone": "(617) 555-0142", "jobs": 0, "projects": 2, "education": 1,
            "must_keep": ["Relevant Coursework", "Treasurer, BU Statistics Club", "Teaching Assistant, MA 113",
                          "github.com/emilychen"],
        },
    },
    "gap": {
        "resume": "gap.docx",
        "expect": {
            "name": "Nicole Fischer", "phone": "303-555-0155", "jobs": 4,
            "job_details": [
                job("Freelance Content Marketer", "Self-employed", "2023", "Present", 1),
                job(start="2021", end="2023", bullets=1),
                job("Marketing Manager", "Summit Outdoor Co.", "Mar 2016", "Feb 2021", 2),
                job("Adjunct Instructor (concurrent)", "Community College of Denver", "2018", "2020", 1),
            ],
            "education": 1,
            "must_keep": ["Career Break", "Family Caregiver"],
        },
    },
    "veteran": {
        "resume": "veteran.docx",
        "expect": {
            "name": "SGT Marcus Reyes (Ret.)", "phone": "210-555-0190", "jobs": 1,
            "job_details": [job("Logistics NCOIC (92Y Unit Supply Specialist)", "U.S. Army", "2014", "2024", 3)],
            "must_keep": ["Security Clearance: Active Secret", "Army Commendation Medal (2)",
                          "Advanced Leader Course (ALC)", "B.S. Business Administration (in progress)"],
        },
    },
    "eu_cv": {
        "resume": "eu_cv.docx",
        "expect": {
            "name": "José Müller-Øberg", "email": "jose.mueller@example.de", "phone": "+49 30 12345678",
            "must_keep": ["Berufserfahrung", "Projektmanager, Siemens AG, München",
                          "Leitung von IT-Projekten mit Budgets bis 2 Mio. €", "Einführung von SAP S/4HANA in 3 Werken",
                          "Berater, Accenture GmbH, Berlin", "Technische Universität München",
                          "Deutsch (Muttersprache)", "SAP S/4HANA, Jira, Scrum, MS Project", "Geburtsdatum: 14.03.1990"],
        },
    },
    "eu_en": {
        "resume": "eu_en.docx",
        "expect": {
            "name": "Zoë Dubois", "email": "zoe.dubois@example.fr", "phone": "+33 6 12 34 56 78", "jobs": 2,
            "job_details": [
                job("Supply Chain Analyst", "Groupe SEB", "01/09/2019", "31/08/2023", 1),
                job("Logistics Intern", "Danone", "03/2018", "08/2018", 1),
            ],
            "education": 1,
            "must_keep": ["Date of birth: 02/11/1992", "Nationality: French", "French (native), English (C1), German (B1)",
                          "Trail running"],
        },
    },
    "spanish": {
        "resume": "spanish.docx",
        "expect": {
            "name": "Lucía Fernández García", "email": "lucia.fernandez@example.es", "phone": "+34 612 345 678",
            "must_keep": ["Enfermera con 5 años de experiencia", "Enfermera de Urgencias, Hospital Universitario La Paz",
                          "Atención a pacientes críticos", "Administración de medicación", "Grado en Enfermería",
                          "Español (nativo), Inglés (B2)"],
        },
    },
    "india": {
        "resume": "india.docx",
        "expect": {
            "name": "王小明 (Wang Xiaoming)", "phone": "+91 98765 43210", "jobs": 2,
            "job_details": [
                job("Senior Software Engineer", "Infosys Ltd", "July 2018", "Till Date", 1),
                job("Software Engineer", "TCS", "June 2015", "June 2018", 1),
            ],
            "education": 1,
            "must_keep": ["To obtain a challenging position", "Father's Name: Wang Wei", "I hereby declare"],
        },
    },
    "federal": {
        "resume": "federal.docx",
        "expect": {
            "name": "Angela Martin", "phone": "703-555-0129", "jobs": 1,
            "job_details": [job("Management and Program Analyst (GS-0343-12)", "U.S. Department of Agriculture",
                                "10/2019", "Present", 2)],
            "education": 1,
            "must_keep": ["40 hours per week", "Salary: $94,199 per year", "Supervisor: John Doe",
                          "Highest Grade: GS-12 Step 4", "1234 Elm St"],
        },
    },
    "textbox": {
        "resume": "textbox.docx", "jd": "retail.txt",
        "expect": {
            "name": "Sam Taylor", "phone": "555-555-0100", "jobs": 1,
            "job_details": [job("Office Manager", "Bright Dental", "2018", "Present", 1)],
            "education": 1,
            "must_keep": ["Dentrix"],
        },
    },
}


def main() -> None:
    manifest = []
    for name, spec in PERSONAS.items():
        folder = os.path.join(OUT, name)
        os.makedirs(folder, exist_ok=True)
        resume_src = os.path.join(SOURCE, "resumes", spec["resume"])
        jd_name = spec.get("jd") or f"{name}.txt"
        resume_dst = os.path.join(folder, "resume" + os.path.splitext(resume_src)[1])
        shutil.copyfile(resume_src, resume_dst)
        shutil.copyfile(os.path.join(SOURCE, "jds", jd_name), os.path.join(folder, "jd.txt"))
        with open(os.path.join(folder, "expected.json"), "w", encoding="utf-8") as f:
            json.dump(spec["expect"], f, indent=2, ensure_ascii=False)
            f.write("\n")
        rel = lambda p: os.path.relpath(p, ROOT)
        manifest.append({"name": name, "resume": rel(resume_dst), "jd": rel(os.path.join(folder, "jd.txt")),
                         "expected": rel(os.path.join(folder, "expected.json"))})
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {len(manifest)} persona cases to {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
