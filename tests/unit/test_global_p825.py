"""P8.25: other scripts render, file names keep their letters, no "_Company",
and a non-English resume or JD is named as such."""
from app.analysis.language import other_language
from app.services.tailor import TailorService
from app.domain.resume import Candidate, Resume
from app.rendering.layout import fallback_font, needs_fallback_font, output_basename


def test_file_names_keep_letters_and_drop_the_placeholder_company():
    r = Resume(candidate=Candidate(name="Lucía Fernández García"))
    assert output_basename(r, "Company") == "Lucía_Fernández_García_Resume"
    assert output_basename(Resume(candidate=Candidate(name="王小明 (Wang Xiaoming)")), "Infosys Ltd") == \
        "王小明_Wang_Xiaoming_Resume_Infosys_Ltd"


def test_fallback_font_and_detection():
    assert fallback_font()  # a family name, whatever is installed
    assert needs_fallback_font("王小明") and needs_fallback_font("Иван") and not needs_fallback_font("José Müller")


def test_language_detection():
    assert other_language(open("data/eval/personas/eu_cv/jd.txt", encoding="utf-8").read()) == "German"
    assert other_language(open("data/eval/personas/spanish/jd.txt", encoding="utf-8").read()) == "Spanish"
    assert other_language(open("data/eval/personas/nurse/jd.txt", encoding="utf-8").read()) is None
    assert other_language("Python SQL") is None  # too little to tell


def test_english_resume_with_spanish_names_is_english():
    """P9.1 (review F2): "Banco de España", "María de la Cruz" made a short
    English resume read as Spanish."""
    text = ("María de la Cruz\nData Analyst, Barcelona\nSkills: SQL, Python, Tableau, Excel, Power BI\n"
            "Banco de España, Data Analyst, 2021 - Present\nTelefónica de España y Portugal, Analyst, 2019 - 2021\n"
            "Universidad de Barcelona, BSc Estadística\nFundación de la Mujer, Volunteer\n"
            "Instituto de la Juventud, Intern\nHospital del Mar, Data Assistant\nLanguages: Spanish, English, Catalan")
    assert other_language(text) is None
    for persona, language in (("spanish", "Spanish"), ("eu_cv", "German")):
        raw, _doc, _ = TailorService(llm_client=None).parse_resume(f"docs/user_testing/2026-10-02/resumes/{persona}.docx")
        assert other_language(raw.raw_text) == language, persona


def test_file_name_stays_short():
    """P9.1 (review F3): a 300-character company gave a file name the OS refuses."""
    name = output_basename(Resume(candidate=Candidate(name="Lucía Fernández")), "A" * 300)
    assert name.startswith("Lucía_Fernández_Resume_A") and len(name.encode("utf-8")) <= 150
    assert len(output_basename(Resume(candidate=Candidate(name="李" * 100)), None).encode("utf-8")) <= 150
