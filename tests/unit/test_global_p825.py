"""P8.25: other scripts render, file names keep their letters, no "_Company",
and a non-English resume or JD is named as such."""
from app.analysis.language import other_language
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
