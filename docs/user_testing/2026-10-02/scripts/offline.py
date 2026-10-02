"""Offline (no-LLM) parse + analyze + render for persona resumes.
Usage: offline.py <resume_path> <jd_path> [--render] [--quiet]
Run with cwd = usertest/ so data/runs lands in the scratchpad."""
import json, os, sys, logging, re
logging.disable(logging.WARNING)
os.environ.setdefault("PROFILE_PATH", os.path.abspath("out/profile_facts.json"))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4]))  # repo root
from app.llm.client import LLMClient
from app.services.tailor import TailorService

def coverage(raw_doc, resume):
    blob = json.dumps(resume.model_dump(), ensure_ascii=False).lower()
    missing = []
    for b in raw_doc.blocks:
        t = b.text.strip()
        if not t: continue
        probe = re.sub(r"\s+", " ", t)[:40].lower()
        # strip bullet glyph
        probe = probe.lstrip("•-* ").strip()
        if probe and json.dumps(probe, ensure_ascii=False)[1:-1] not in blob:
            missing.append(t[:100])
    return missing

def main():
    resume_path, jd_path = sys.argv[1], sys.argv[2]
    render = "--render" in sys.argv
    quiet = "--quiet" in sys.argv
    llm = LLMClient(provider="ollama", host="http://127.0.0.1:9")
    svc = TailorService(llm_client=llm)
    jd = open(jd_path, encoding="utf-8").read()
    raw, rdoc, ev = svc.parse_resume(resume_path)
    r = rdoc.resume
    print("=== PARSE:", os.path.basename(resume_path))
    print("issues:", svc.last_parse_issues)
    c = r.candidate
    print(f"name={c.name!r} headline={c.headline!r} email={c.email!r} phone={c.phone!r} loc={c.location!r} links={c.links}")
    if not quiet:
        print("summary:", (r.summary or "")[:150])
    for e in r.experience:
        roles = [(x.title, x.start_date, x.end_date) for x in e.all_roles()]
        print(f"  EXP company={e.company!r} loc={e.location!r} roles={roles} bullets={len(e.bullets)}")
        if not quiet:
            for b in e.bullets[:6]:
                print("     -", (("["+b.group+"] ") if b.group else "") + b.text[:110])
    for p in r.projects:
        print(f"  PROJ {p.name!r} bullets={len(p.bullets)}")
    for ed in r.education:
        print(f"  EDU inst={ed.institution!r} deg={ed.degree!r} dates={ed.dates!r}")
    print("  skills:", {k: v[:8] for k, v in r.skills.items()})
    print("  certs:", [x.get('name') for x in r.certifications][:10], " achievements:", r.achievements[:5], " interests:", r.interests[:5])
    miss = coverage(raw, r)
    print(f"  NOT IN MODEL ({len(miss)} of {len(raw.blocks)} blocks):")
    for m in miss[:25]:
        print("     x", m)
    rep = svc.analyze_only(resume_path, jd)
    km = rep.keyword_match
    print(f"=== SCORE rate={km.rate}  evidence_score={rep.score_components.get('evidence_score')}")
    for row in km.rows:
        print(f"   {'FOUND' if row.found else 'miss '} {row.kind:13s} req={int(row.required)} w={row.weight} {row.keyword!r} {row.where[:2] if row.where else ''}")
    if render:
        out = os.path.abspath(f"out/{os.path.splitext(os.path.basename(resume_path))[0]}_{os.path.splitext(os.path.basename(jd_path))[0]}")
        res = svc.tailor_resume(resume_path, jd, out, preapproved_proposals=[], remember_answers=False)
        print("=== RENDER success=", res.get("success"))
        for k in ("docx", "pdf", "html", "changes_md"):
            print("  ", k, res.get(k), os.path.exists(res.get(k) or "") if res.get(k) else None)
        for k in ("warnings", "docx_warnings", "pdf_warnings"):
            print("  ", k, res.get(k))
        print("   content_lint:", json.dumps(res.get("content_lint"), default=str)[:600])

main()
