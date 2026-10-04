"""P9.5: minor matching notes from the Stage K review."""
from app.analysis.jd_analyzer import JDAnalyzer
from app.analysis.keyword_match import alternatives_of, definitions


def test_connector_word_is_never_an_acronym_letter():
    assert definitions("Or Associate (OA)") == {}
    assert definitions("With Teams (WT)") == {}
    assert definitions("Must Have Or Hold A Commercial Driver License (CDL)") == {"cdl": "commercial driver license"}
    assert definitions("Knowledge Of Occupational Safety and Health Administration (OSHA)") == {
        "osha": "occupational safety and health administration"}
    # a connector that is one of the letters still counts
    assert definitions("Point Of Sale (POS)") == {"pos": "point of sale"}


def test_or_shares_a_role_word_both_ways():
    # "Java" alone counts, so "Python" alone does too
    assert ["python"] in alternatives_of("Java or Python developer")
    assert ["java"] in alternatives_of("Java or Python developer")
    assert ["lpn"] in alternatives_of("RN or LPN license")
    # a product name isn't cut down to its first word
    assert alternatives_of("NetSuite or Oracle ERP")[1][0] == "oracl" and len(alternatives_of("NetSuite or Oracle ERP")) == 2
    assert len(alternatives_of("Excel or Google Sheets")) == 2


def test_requirement_spans_point_into_the_cleaned_jd():
    html = ("<h2>Senior Accountant</h2><p>Acme &amp; Co is hiring.</p><h3>Requirements</h3><ul>"
            "<li>5+ years of accounts payable &amp; receivable experience</li>"
            "<li>Advanced Excel skills</li></ul><h3>Nice to have</h3><ul><li>Advanced Excel skills</li></ul>")
    jd = JDAnalyzer(None).analyze(html)
    assert jd.requirements
    spans = []
    for r in jd.requirements:
        s = r.source_spans[0]
        assert jd.raw_text[s["start"]:s["end"]] == r.text
        spans.append(s["start"])
    assert len(set(spans)) == len(spans)  # a repeated line maps to its own place
