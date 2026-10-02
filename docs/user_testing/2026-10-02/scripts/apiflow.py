"""Drive the web API end to end: parse -> proposals -> tailor (accept all) -> download.
Usage: apiflow.py <resume> <jd> <tag> [--gap]"""
import json, sys, os, time, httpx
resume, jdp, tag = sys.argv[1:4]
B = "http://127.0.0.1:8765/api"
c = httpx.Client(timeout=600)
jd = open(jdp).read()
out = f"out/api_{tag}"; os.makedirs(out, exist_ok=True)
log = open(f"{out}/flow.json", "w")

def sse(resp):
    kind = None; res = None
    for line in resp.iter_lines():
        if line.startswith("event:"): kind = line[6:].strip()
        elif line.startswith("data:"):
            data = json.loads(line[5:])
            if kind == "progress": print("  progress:", data["message"])
            else: res = (kind, data)
    return res

t = time.time()
r = c.post(f"{B}/parse", files={"file": open(resume, "rb")}, data={"jd_text": jd})
print("PARSE", r.status_code, round(time.time()-t, 1), "s")
pj = r.json(); print(json.dumps(pj, indent=1)[:2500])
t = time.time()
with c.stream("POST", f"{B}/proposals", json={"corrections": None}) as resp:
    kind, data = sse(resp)
print("PROPOSALS", kind, round(time.time()-t, 1), "s")
json.dump(data, log, indent=1)
if kind != "result":
    print(data); sys.exit()
print("llm:", data["llm"])
km = data["keyword_match"]; print("rate", km["rate"])
for row in km["rows"]:
    print(f"   {'FOUND' if row['found'] else 'miss '} {row['kind']:13s} req={int(row['required'])} {row['keyword']!r}")
for p in data["proposals"]:
    print(f"\n[{p['kind']}] {p['state']} ({(p['section'] or {}).get('label')})\n  ORIG: {p['original']}\n  NEW : {p['proposed']}\n  note: {p['note']}")
print("\nGAP QUESTIONS:")
for q in data["gap_questions"]:
    print("  ", json.dumps(q)[:300])
sel = [{"id": p["id"]} for p in data["proposals"]]
mp = c.post(f"{B}/match-preview", json={"selection": sel}).json()
print("match-preview rate", mp.get("rate"), "delta", mp.get("delta"))
body = {"selection": sel, "remember_answers": False}
if "--gap" in sys.argv and data["gap_questions"]:
    q = data["gap_questions"][0]
    body["gap_answers"] = {q["id"]: {"ticked": q["keywords"], "answer": "", "target": "auto"}}
    print("ticking ALL keywords of first gap question with no answer:", q["keywords"])
t = time.time()
with c.stream("POST", f"{B}/tailor", json=body) as resp:
    kind, res = sse(resp)
print("TAILOR", kind, round(time.time()-t, 1), "s")
print(json.dumps(res, indent=1)[:3000])
for k in ("docx", "pdf", "changes"):
    r = c.get(f"{B}/files/{k}")
    fn = r.headers.get("content-disposition", k)
    print("download", k, r.status_code, fn)
    if r.status_code == 200:
        open(f"{out}/{k}." + ("md" if k == "changes" else k), "wb").write(r.content)
