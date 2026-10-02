import sys, logging; logging.disable(logging.WARNING)
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4]))  # repo root
sys.path.insert(0, "scripts")
from make_personas import write_docx
from app.llm.client import LLMClient
from app.services.tailor import TailorService
from app.analysis.experience import years_of_experience
lines = ["Analyst, Acme Corp\tSummer 2019 – Fall 2020", "Analyst, Acme Corp\t2019–present", "Analyst, Acme Corp\t03/2019 – 06/2021",
 "Analyst, Acme Corp\t2019 - Current", "Analyst, Acme Corp\tJan 2027 – Present", "Analyst, Acme Corp\tMarch 2019 to date",
 "Analyst, Acme Corp\t2019 – Ongoing", "Analyst, Acme Corp\t2018", "Analyst, Acme Corp", "Analyst, Acme Corp\tSept. 2019 – Mar. 2020",
 "Analyst, Acme Corp\t2019-03 – 2020-06", "Analyst, Acme Corp\tJan '19 – Dec '20"]
svc = TailorService(llm_client=LLMClient(provider="ollama", host="http://127.0.0.1:9"))
for l in lines:
    spec = [("name","Test Person"),("p","t@example.com"),("h","Experience"),("bold", l),("b","Did a thing for the team")]
    write_docx("out/date.docx", spec)
    raw, rd, ev = svc.parse_resume("out/date.docx")
    e = rd.resume.experience
    print(f"{l!r:50} -> ", [(x.company, [(r.title, r.start_date, r.end_date) for r in x.all_roles()]) for x in e], "yrs=", years_of_experience(rd.resume) if e else None)
