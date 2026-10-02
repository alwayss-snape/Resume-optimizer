"""P8.2: content coverage of the output against the source lines."""
from types import SimpleNamespace as B

from app.validation.coverage import content_coverage, words


def block(i, text):
    return B(id=f"b{i}", text=text)


def test_words_normalise_dates_and_present():
    assert words("03/2021 - Current") == {"2021", "present"}
    assert words("Mar 2021 – Present") == {"mar", "2021", "present"}
    assert "jul" in words("July 2018 – Till Date") and "present" in words("July 2018 – Till Date")
    assert words("Enfermería en Madrid") == {"enfermería", "madrid"}


def test_lost_reworded_trimmed_and_headings():
    blocks = [block(1, "WORK HISTORY"), block(2, "Built pipeline of $3M through outbound calls"),
              block(3, "Free clinic nurse volunteer, Circle the City"), block(4, "Old bullet trimmed to fit"),
              block(5, "Original wording"), block(6, "Chess, Cycling")]
    out = "Work Experience\nBuilt pipeline of $3M through outbound calls\nNew wording"
    report = content_coverage(blocks, out, heading_texts=["WORK HISTORY"], reworded_blocks={"b5"},
                              trimmed_blocks={"b4"}, removed_text="Chess\nCycling")
    assert report.lost == ["Free clinic nurse volunteer, Circle the City"]
    assert (report.counted, report.kept, report.reworded, report.trimmed) == (5, 1, 1, 2)
    assert report.pct == 80.0


def test_reformatted_dates_and_contact_still_count_as_kept():
    blocks = [block(1, "Phoenix, AZ | (602) 555-0147 | maria@example.com"), block(2, "06/2019 - 02/2021")]
    out = "maria@example.com | (602) 555-0147 | Phoenix, AZ\nJun 2019 – Feb 2021"
    assert content_coverage(blocks, out).lost == []
