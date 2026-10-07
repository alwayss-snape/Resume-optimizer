"""Region of the job (P10.3): which paper and date style the resume uses.

Deterministic: read from the JD's own words (a USAJOBS posting, a "City, ST"
location, a country, a city, a currency), with the words that decided it
kept as evidence so the user can see why. The user confirms or changes it;
nothing here calls the LLM.

US: Letter and "01/2022 – Present". UK / Europe, India and anything else:
A4 and "Jan 2022 – Present" (the template's default).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from app.domain.resume import Resume
from app.domain.resume_document import ResumePresentation

REGIONS = {
    "us": "US (Letter)",
    "uk_eu": "UK / Europe (A4)",
    "india": "India (A4)",
    "other": "Other (A4)",
}
DEFAULT_REGION = "other"

_US_STATES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK "
    "OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC"
).split()
_US_STATE_NAMES = (
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|"
    "Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|"
    "Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
    "North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|"
    "Utah|Vermont|Virginia|Washington,? D\\.?C\\.?|West Virginia|Wisconsin|Wyoming"
)
_UK_EU = (
    "United Kingdom|England|Scotland|Wales|Northern Ireland|Ireland|Germany|France|Spain|Portugal|Italy|"
    "Netherlands|Belgium|Luxembourg|Austria|Switzerland|Denmark|Sweden|Norway|Finland|Iceland|Poland|Czechia|"
    "Czech Republic|Slovakia|Hungary|Romania|Bulgaria|Greece|Croatia|Slovenia|Estonia|Latvia|Lithuania|"
    "Deutschland|London|Manchester|Birmingham|Edinburgh|Glasgow|Leeds|Bristol|Cambridge, UK|Oxford, UK|Dublin|"
    "Berlin|Munich|München|Hamburg|Frankfurt|Paris|Lyon|Madrid|Barcelona|Lisbon|Milan|Rome|Amsterdam|"
    "Rotterdam|Brussels|Vienna|Zurich|Zürich|Geneva|Copenhagen|Stockholm|Oslo|Helsinki|Warsaw|Krakow|Prague|"
    "Budapest|Bucharest|Athens"
)
_INDIA = (
    "India|Bengaluru|Bangalore|Mumbai|New Delhi|Delhi NCR|Delhi|Gurugram|Gurgaon|Noida|Hyderabad|Chennai|Pune|"
    "Kolkata|Ahmedabad|Jaipur|Kochi|Thiruvananthapuram|Coimbatore|Indore|Chandigarh|Lucknow|Nagpur|"
    "Bhubaneswar|Visakhapatnam|Mysuru|Mysore"
)

# Checked in this order; the first hit decides. A posting on USAJOBS is US
# whatever else it says; an Indian city before "City, ST" (so "Pune, IN" is
# India), and a place always beats a currency sign.
_RULES = [
    ("us", re.compile(r"\bUSAJOBS\b|\busajobs\.gov\b|\bGS-\d{1,2}\b|\b(?:GS|GG)-\d{4}-\d{1,2}\b", re.IGNORECASE)),
    ("india", re.compile(r"\b(?:" + _INDIA.replace("India|", "") + r")\b")),
    ("us", re.compile(r"\b[A-Z][a-z]+(?:[ .'-]+[A-Z][a-z]+)*,\s*(?:" + "|".join(_US_STATES) + r")\b(?:\s+\d{5})?(?![A-Za-z])")),
    ("us", re.compile(r"\b(?:United States(?: of America)?|U\.S\.A?\.|USA)\b|\bRemote[,\s(-]+US\b")),
    ("us", re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)?,\s*(?:" + _US_STATE_NAMES + r")\b")),
    ("india", re.compile(r"\b(?:" + _INDIA + r")\b")),
    ("uk_eu", re.compile(r"\b(?:" + _UK_EU + r")\b|\bUK\b|\bEU\b")),
    ("india", re.compile(r"₹|\bINR\b|\bLPA\b|\blakhs?\b|\bCTC\b", re.IGNORECASE)),
    ("uk_eu", re.compile(r"£|€|\bGBP\b|\bEUR\b")),
    ("us", re.compile(r"\bUSD\b|\$\s?\d{2,3}(?:,\d{3}|[kK])")),
]


@dataclass
class RegionGuess:
    region: str
    evidence: Optional[str]  # the JD's words that decided it; None for the default

    @property
    def label(self) -> str:
        return REGIONS[self.region]

    def model_dump(self) -> dict:
        return {"region": self.region, "label": self.label, "evidence": self.evidence}


def suggest_region(jd_text: str) -> RegionGuess:
    """The region the JD points to, with its evidence; "other" (A4, the
    default) when nothing in it says."""
    text = jd_text or ""
    for region, pattern in _RULES:
        match = pattern.search(text)
        if match:
            return RegionGuess(region, match.group(0).strip())
    return RegionGuess(DEFAULT_REGION, None)


def apply_region(presentation: ResumePresentation, region: Optional[str]) -> ResumePresentation:
    """Set the paper and date style for `region`; None or unknown keeps the
    default (A4, "Jan 2022")."""
    region = region if region in REGIONS else DEFAULT_REGION
    presentation.region = region
    presentation.page_size = "Letter" if region == "us" else "A4"
    presentation.date_style = "numeric" if region == "us" else "month"
    return presentation


# Personal details US / UK / EU employers don't expect (P10.3). Advice only:
# they are never removed for the user.
_PERSONAL = [
    ("date of birth", re.compile(r"\b(?:date of birth|d\.?o\.?b\.?|born on)\b", re.IGNORECASE)),
    ("father's or spouse's name", re.compile(r"\b(?:father'?s|mother'?s|husband'?s|spouse'?s) name\b", re.IGNORECASE)),
    ("marital status", re.compile(r"\bmarital status\b", re.IGNORECASE)),
    ("religion", re.compile(r"\breligion\b", re.IGNORECASE)),
    ("gender", re.compile(r"\b(?:gender|sex)\s*:", re.IGNORECASE)),
    ("a declaration", re.compile(r"\bdeclaration\b|\bhereby declare\b", re.IGNORECASE)),
    ("a photo", re.compile(r"\bphoto(?:graph)?\b", re.IGNORECASE)),
]


def personal_details_found(resume: Resume) -> List[str]:
    """Which of the personal details above the resume includes, by name."""
    texts = list(resume.candidate.details)
    for sec in resume.other_sections:
        texts.append(sec.heading or "")
        texts.extend(line.text for line in sec.lines)
    joined = "\n".join(t for t in texts if t)
    return [name for name, pattern in _PERSONAL if pattern.search(joined)]


def personal_details_advice(resume: Resume, region: Optional[str]) -> Optional[str]:
    """A note for US / UK / Europe jobs when the resume lists personal details
    employers there don't expect (and may not be allowed to consider). None
    for India and other regions, where they are common."""
    if region not in ("us", "uk_eu"):
        return None
    found = personal_details_found(resume)
    if not found:
        return None
    where = "US" if region == "us" else "UK and European"
    items = ", ".join(found[:-1]) + (" and " if len(found) > 1 else "") + found[-1]
    return (f"Your resume includes {items}. {where} employers don't expect these and often prefer not to see "
            "them; you may want to remove them in Arrange. We left them as they are.")
