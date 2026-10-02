"""P8.4: phone numbers in any common grouping, and links with any common
top-level domain (portfolio sites)."""
import pytest

from app.analysis.resume_normalizer import ResumeNormalizer


@pytest.mark.parametrize("line, phone", [
    ("Phoenix, AZ | (602) 555-0147 | maria@example.com", "(602) 555-0147"),
    ("Lyon, France | +33 6 12 34 56 78 | zoe@example.fr", "+33 6 12 34 56 78"),
    ("Hauptstraße 12, 10115 Berlin | +49 30 12345678 | j@example.de", "+49 30 12345678"),
    ("Bengaluru, India | +91 98765 43210 | w@example.com", "+91 98765 43210"),
    ("Madrid, España | +34 612 345 678", "+34 612 345 678"),
    ("LinkedIn | Email | +91-9000000000 | Pune, India", "+91-9000000000"),
    ("Cleveland OH   216-555-0110   d@example.com", "216-555-0110"),
    ("+44 20 7946 0000", "+44 20 7946 0000"),
    ("1234 Elm St, Arlington, VA 22201 | a@example.com | 703-555-0129", "703-555-0129"),
])
def test_phone_formats(line, phone):
    assert ResumeNormalizer.find_phone(line) == phone


@pytest.mark.parametrize("line", [
    "2013 - 2017", "2019-2023", "ORCID 0000-0002-1234-5678", "Geburtsdatum: 14.03.1990",
    "Date of birth: 02/11/1992", "Salary: $94,199 per year", "Hauptstraße 12, 10115 Berlin",
])
def test_not_phones(line):
    assert ResumeNormalizer.find_phone(line) is None


def test_links_with_any_common_domain():
    n = ResumeNormalizer()
    assert n._header_urls("portfolio: priyaraman.design") == ["priyaraman.design"]
    assert n._header_urls("Lena Park · lena@example.com · lenapark.design · Dribbble: dribbble.com/lenapark") == [
        "lenapark.design", "dribbble.com/lenapark"]
    assert n._header_urls("B.Sc in Node.js, e.g. things") == []
    assert n._header_urls("https://www.example.org/path") == ["https://www.example.org/path"]
