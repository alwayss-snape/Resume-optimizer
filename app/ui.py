import os
import shutil
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Ensure project root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from app.config.settings import settings
from app.llm.client import LLMClient
from app.services.tailor import TailorService

st.set_page_config(
    page_title="Local Resume Tailor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

def get_local_pdf_preview_url(pdf_path: str):
    """Serve a PDF from a temporary HTTP endpoint so Chrome can render it in an iframe."""
    pdf_dir = os.path.dirname(os.path.abspath(pdf_path))
    pdf_name = os.path.basename(pdf_path)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return

    handler = partial(QuietHandler, directory=pdf_dir)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    return httpd, f"http://127.0.0.1:{port}/{pdf_name}"


def display_pdf_with_fallback(pdf_path: str, height: int = 900):
    """Try to use Streamlit's native PDF display if available, otherwise fall back
    to the local HTTP server preview. If PyMuPDF is installed, also offer a PNG
    raster fallback for environments where embedding is restricted.
    """
    # Prefer native `st.pdf` if available
    try:
        st_pdf = getattr(st, "pdf", None)
        if callable(st_pdf):
            with open(pdf_path, "rb") as f:
                st_pdf(f.read())
            return None
    except Exception:
        pass

    # Fallback: serve via local HTTP endpoint
    try:
        httpd, url = get_local_pdf_preview_url(pdf_path)
        st.caption("Preview is served from a local HTTP endpoint so Chrome can render the PDF normally.")
        st.components.v1.iframe(url, height=height, scrolling=True)
        return httpd
    except Exception:
        # Try PNG raster via PyMuPDF if available
        try:
            import pymupdf as fitz
            doc = fitz.open(pdf_path)
            pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
            from io import BytesIO
            buf = BytesIO()
            pix.save(buf, output="png")
            st.image(buf.getvalue(), use_column_width=True)
            return None
        except Exception:
            st.info("Could not render PDF preview in this environment.")
            return None


def _cleanup_session_state():
    """Remove temp files from a previous run and reset to a clean 'idle' state."""
    for key in ("resume_path", "output_dir"):
        path = st.session_state.get(key)
        if path and os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except Exception:
                pass

    for key in (
        "proposals", "gap_questions", "llm_available", "pre_score", "keyword_match", "job_description",
        "resume_path", "jd_text", "model_choice", "render_mode", "strict_factual",
        "results", "output_dir", "analysis_report", "experience_options",
        "llm_status", "proposal_usage", "parsed", "parse_issues", "parse_corrected",
    ):
        st.session_state.pop(key, None)

    st.session_state.stage = "idle"


if "stage" not in st.session_state:
    st.session_state.stage = "idle"


# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #6B7280;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1E1B4B;
        border: 1px solid #4338CA;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">Local Resume Tailor</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Privacy-first, evidence-based local AI resume optimization</div>', unsafe_allow_html=True)

def model_options(provider: str) -> list:
    """Models offered in the sidebar for the configured provider. The
    configured default always comes first; a model name from one provider
    must never be sent to another (an Ollama tag sent to Groq made every
    rewrite fail silently)."""
    if provider == "anthropic":
        options = [settings.anthropic_model, "claude-opus-5-5", "claude-sonnet-5-5"]
    elif provider == "groq":
        options = [settings.groq_model, "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    else:
        options = [settings.llm_model, "qwen3:4b", "qwen3:8b", "qwen3.5:4b"]
    return list(dict.fromkeys(o for o in options if o))


PROVIDER_LABELS = {"anthropic": "Claude (Anthropic API)", "groq": "Groq (cloud)", "ollama": "Ollama (local)"}
PROVIDER_FIX_HINTS = {
    "anthropic": "Check ANTHROPIC_API_KEY in your .env (a pay-as-you-go key from console.anthropic.com).",
    "groq": "Check GROQ_API_KEY and GROQ_MODEL in your .env.",
    "ollama": "Start Ollama (`ollama serve`) and pull the model (`ollama pull <model>`).",
}

# Sidebar settings
st.sidebar.title("⚙️ Model & Configuration")
llm_provider = (settings.llm_provider or "ollama").strip().lower()
st.sidebar.caption(f"Provider: **{PROVIDER_LABELS.get(llm_provider, llm_provider)}** (set `LLM_PROVIDER` in `.env`)")
model_choice = st.sidebar.selectbox(
    "Select Model",
    options=model_options(llm_provider),
    index=0,
)
render_mode = st.sidebar.radio(
    "Output Layout Mode",
    options=["PRESERVE", "ATS_DEFAULT"],
    index=0,
    help="PRESERVE mode patches existing DOCX in-place. ATS_DEFAULT reconstructs standard template."
)
strict_factual = st.sidebar.checkbox(
    "Strict Factual Mode",
    value=False,
    help="All-or-nothing: if any rewrite fails fact validation, withhold every rewrite. "
    "With this off, each failing rewrite is still dropped individually.",
)

if st.session_state.stage != "idle":
    if st.sidebar.button("🔄 Start Over", use_container_width=True):
        _cleanup_session_state()
        st.rerun()

# Main layout split
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Upload Resume")
    uploaded_file = st.file_uploader(
        "Choose a DOCX or PDF resume",
        type=["docx", "pdf"],
        help="DOCX output preserves the uploaded layout. PDF layout reproduction is best-effort."
    )

with col2:
    st.subheader("2. Job Description")
    jd_input = st.text_area(
        "Paste Job Description text",
        height=220,
        placeholder="Paste the target job description requirements, responsibilities, and qualifications here..."
    )

# Execution actions
st.write("---")
action_col1, action_col2 = st.columns([1, 1])

with action_col1:
    btn_analyze = st.button("📊 Analyze Match Alignment", use_container_width=True)
with action_col2:
    btn_tailor = st.button("✨ Tailor & Generate Resume", type="primary", use_container_width=True)

if btn_analyze or btn_tailor:
    if not uploaded_file:
        st.error("Please upload a resume file before proceeding.")
    elif not jd_input.strip():
        st.error("Please paste the job description text before proceeding.")
    else:
        # Starting a fresh run — clear out anything left over from a previous
        # analysis/tailoring pass (including its temp files) first.
        _cleanup_session_state()

        # Save upload to temporary file
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_resume_path = tmp.name

        try:
            llm_client = LLMClient(model=model_choice)
            service = TailorService(llm_client=llm_client)

            if btn_analyze:
                with st.spinner("Analyzing resume against job description requirements..."):
                    report = service.analyze_only(tmp_resume_path, jd_input)
                st.session_state.stage = "analysis"
                st.session_state.analysis_report = report
                os.remove(tmp_resume_path)

            elif btn_tailor:
                # Step 1 of tailoring: read the resume and let the user check
                # what was parsed before any rewriting (P3.5).
                with st.spinner("Reading your resume..."):
                    st.session_state.parsed = service.parse_resume(tmp_resume_path)
                st.session_state.parse_issues = list(service.last_parse_issues)
                st.session_state.stage = "check_parse"
                # Keep the temp resume file alive — it's needed again when
                # "Apply & Generate" runs, on a LATER script rerun.
                st.session_state.resume_path = tmp_resume_path
                st.session_state.jd_text = jd_input
                st.session_state.model_choice = model_choice
                st.session_state.render_mode = render_mode
                st.session_state.strict_factual = strict_factual
                st.rerun()

        except Exception as e:
            st.error(f"Execution Error: {e}")
            if os.path.exists(tmp_resume_path):
                os.remove(tmp_resume_path)


def _show_keyword_match(keyword_report, heading: str = "Keyword match") -> None:
    """Match rate against the target band, then the matched / missing table
    that explains it (P1.2)."""
    if keyword_report is None:
        return
    low, high = keyword_report.target_band
    rate = keyword_report.rate
    if rate < low:
        verdict = f"below the {low:.0f}-{high:.0f}% target"
    elif rate > high:
        verdict = f"above {high:.0f}%: check the resume doesn't read as keyword-stuffed"
    else:
        verdict = "in the target band"
    st.metric(heading, f"{rate:.1f}%", help="Weighted share of the job description's keywords found in your "
              "resume: hard skills count most, then the job title, education/certifications, soft skills; "
              "required keywords count 1.5x.")
    st.caption(f"{len(keyword_report.matched)} of {len(keyword_report.rows)} keywords found, {verdict}.")
    rows = sorted(keyword_report.rows, key=lambda r: (r.found, -r.weight))
    st.dataframe(
        [{"Keyword": r.keyword, "Found": "✅" if r.found else "❌", "Kind": r.kind,
          "Required": "yes" if r.required else "no", "Where": ", ".join(r.where)} for r in rows],
        use_container_width=True, hide_index=True,
    )


# ---------------------------------------------------------------------------
# Check parsed resume (P3.5): confirm or fix what was read from the file
# before any rewriting. Bullet text is reviewed later, with the proposals.
# ---------------------------------------------------------------------------
def _draft_proposals(parsed, parse_corrected: bool) -> None:
    llm_client = LLMClient(model=st.session_state.model_choice)
    service = TailorService(llm_client=llm_client)
    with st.spinner("Analyzing the job description and drafting proposals..."):
        generated = service.generate_proposals(
            st.session_state.resume_path, st.session_state.jd_text, parsed=parsed,
        )
    st.session_state.parsed = parsed
    st.session_state.parse_corrected = parse_corrected
    st.session_state.stage = "proposals"
    st.session_state.proposals = generated["proposals"]
    st.session_state.gap_questions = generated.get("gap_questions") or []
    st.session_state.llm_available = generated["llm_available"]
    st.session_state.llm_status = generated.get("llm_status") or {}
    st.session_state.proposal_usage = generated.get("llm_usage")
    st.session_state.pre_score = generated["alignment_score"]
    st.session_state.keyword_match = generated.get("keyword_match")
    st.session_state.job_description = generated.get("job_description")
    st.session_state.experience_options = generated["experience_options"]


if st.session_state.stage == "check_parse" and st.session_state.get("parsed") is not None:
    parsed_resume = st.session_state.parsed[1].resume
    cand = parsed_resume.candidate

    st.markdown("### Check your parsed resume")
    st.caption("This is what was read from your file. Fix anything that's wrong, then continue. "
               "Bullets are reviewed in the next step.")
    for issue in st.session_state.get("parse_issues") or []:
        st.warning(f"Possible parsing problem: {issue}")

    with st.form("check_parse_form"):
        c1, c2 = st.columns(2)
        with c1:
            f_name = st.text_input("Name", value=cand.name if cand.name != "Candidate" else "")
            f_headline = st.text_input("Headline (optional)", value=cand.headline or "",
                                       placeholder="e.g. Senior Data Scientist")
            f_location = st.text_input("Location", value=cand.location or "")
        with c2:
            f_email = st.text_input("Email", value=cand.email or "")
            f_phone = st.text_input("Phone", value=cand.phone or "")
            f_links = st.text_area("Links (one per line)", value="\n".join(cand.links), height=80,
                                   placeholder="linkedin.com/in/you\ngithub.com/you")

        exp_fixes = []
        for i, exp in enumerate(parsed_resume.experience):
            st.markdown(f"**Job {i + 1}** · {len(exp.bullets)} bullet(s)"
                        + (f" in {len({b.group for b in exp.bullets if b.group})} sub-section(s)"
                           if any(b.group for b in exp.bullets) else ""))
            e1, e2 = st.columns(2)
            with e1:
                f_company = st.text_input("Company", value=exp.company, key=f"pc_company_{i}")
            with e2:
                f_exp_loc = st.text_input("Location", value=exp.location or "", key=f"pc_loc_{i}")
            roles = exp.all_roles() or [None]
            role_fixes = []
            for j, role in enumerate(roles):
                r1, r2, r3 = st.columns([2, 1, 1])
                with r1:
                    t = st.text_input("Title" if j == 0 else "Earlier title", value=role.title if role else "",
                                      key=f"pc_title_{i}_{j}")
                with r2:
                    sd = st.text_input("Start", value=(role.start_date or "") if role else "",
                                       key=f"pc_start_{i}_{j}")
                with r3:
                    ed = st.text_input("End", value=(role.end_date or "") if role else "", key=f"pc_end_{i}_{j}")
                role_fixes.append({"title": t, "start_date": sd, "end_date": ed})
            exp_fixes.append({"id": exp.id, "company": f_company, "location": f_exp_loc, "roles": role_fixes})

        confirm_btn = st.form_submit_button("✅ Looks right — draft rewrites", type="primary")

    if confirm_btn:
        corrections = {
            "candidate": {
                "name": f_name, "headline": f_headline, "email": f_email, "phone": f_phone,
                "location": f_location, "links": f_links.splitlines(),
            },
            "experience": exp_fixes,
        }
        try:
            service = TailorService(llm_client=LLMClient(model=st.session_state.model_choice))
            corrected, changed = service.apply_parse_corrections(st.session_state.parsed, corrections)
            _draft_proposals(corrected, changed)
            st.rerun()
        except Exception as e:
            st.error(f"Execution Error: {e}")


# ---------------------------------------------------------------------------
# Analysis-only results (persists across reruns)
# ---------------------------------------------------------------------------
if st.session_state.stage == "analysis" and st.session_state.get("analysis_report") is not None:
    report = st.session_state.analysis_report

    st.success("Analysis Complete!")
    _show_keyword_match(report.keyword_match)
    if report.score_components and "evidence_score" in report.score_components:
        st.caption(f"Evidence score (requirement level): {report.score_components['evidence_score']:.1f} / 100")
    if report.score_components and report.score_components.get("semantic_coverage", 0) > 0:
        st.caption(
            f"🔎 Semantic coverage: {report.score_components['semantic_coverage']:.1f}% "
            "of requirement weight is matched only via inferred (paraphrase) similarity, "
            "not counted in the score above — see the 🔎 items below."
        )

    tab1, tab2, tab3 = st.tabs(["Required Matches", "Preferred Matches", "Missing Requirements"])

    status_badges = {
        "EXPLICIT": "✅",
        "SUPPORTED": "✅",
        "PARTIAL": "⚠️",
        "SEMANTIC_PARTIAL": "🔎",
        "UNCERTAIN": "❓",
        "MISSING": "❌",
    }

    def _render_match(m):
        badge = status_badges.get(m.status, "•")
        st.write(f"- {badge} **[{m.status}]** {m.requirement_text}")
        if m.status == "SEMANTIC_PARTIAL":
            st.caption(f"　　{m.explanation}")

    with tab1:
        for m in report.required_matches:
            _render_match(m)
    with tab2:
        for m in report.preferred_matches:
            _render_match(m)
    with tab3:
        for m in report.missing_requirements:
            st.write(f"- ❌ {m.requirement_text}")


# ---------------------------------------------------------------------------
# Review Proposed Rewrites + Suggested Additions + free-text addition
# (persists across reruns — this is what "Apply & Generate" was silently
# losing before, since it used to be gated on a one-shot button click.)
# ---------------------------------------------------------------------------
if st.session_state.stage in ("proposals", "results"):
    llm_status = st.session_state.get("llm_status") or {}
    status_provider = llm_status.get("provider") or llm_provider
    status_model = llm_status.get("model") or st.session_state.get("model_choice", model_choice)
    if not st.session_state.get("llm_available", True):
        st.error(
            f"⚠️ The AI model isn't usable: **{PROVIDER_LABELS.get(status_provider, status_provider)}**, "
            f"model `{status_model}`: {llm_status.get('reason') or 'unavailable'}. "
            "No rewrites or suggestions could be generated, so the proposals below are your original text. "
            f"{PROVIDER_FIX_HINTS.get(status_provider, '')} Then click **Tailor & Generate Resume** again."
        )
    elif llm_status.get("failed"):
        errors = llm_status.get("errors") or []
        st.warning(
            f"⚠️ {llm_status['failed']} of {llm_status.get('attempted', '?')} rewrites failed and show your "
            "original text. " + (f"Reason: {errors[0]}" if errors else "")
        )


if st.session_state.stage == "proposals":
    proposals = st.session_state.get("proposals", [])

    with st.expander(f"🔑 Keyword match before tailoring: {st.session_state.get('pre_score', 0):.1f}%"):
        _show_keyword_match(st.session_state.get("keyword_match"))

    st.markdown("### Review Proposed Rewrites")
    if proposals:
        st.markdown("Edit proposed text or uncheck to reject. Then add anything else below and click **Apply & Generate**.")
    else:
        st.info("No existing bullets needed rewriting for this job description.")

    experience_options = st.session_state.get("experience_options", [])
    target_labels = ["Auto — add to my most recent role"] + [
        f"Add to: {opt['label']}" for opt in experience_options
    ] + ["Add as a new Project"]

    with st.form("proposal_review_form"):
        selected = []
        edits = {}
        for i, p in enumerate(proposals):
            keybase = f"p_{i}"
            orig = getattr(p, "original_text", "")
            prop_text = getattr(p, "proposed_text", None) or getattr(p, "rewritten_text", None) or ""
            rationale = getattr(p, "rationale", None)
            col1, col2 = st.columns([1, 3])
            with col1:
                sel = st.checkbox("Apply", value=True, key=keybase + "_apply")
            with col2:
                if getattr(p, "kind", "bullet") == "summary":
                    st.markdown("**Professional summary**")
                elif getattr(p, "kind", "bullet") == "skills":
                    st.markdown("**Skills** (one \"Category: a, b, c\" line each; reordering only, nothing is added)")
                st.markdown(f"**Original:** {orig or '(no summary)'}")
                edt = st.text_area(f"Proposed ({i+1})", value=prop_text, key=keybase + "_edit", height=80)
                if rationale:
                    st.caption(f"🎯 {rationale}")
                verdict = getattr(p, "validation", None)
                note = getattr(p, "validation_note", None)
                if verdict == "REJECT":
                    st.caption(f"⛔ Will be dropped unless you edit it: {note}")
                elif verdict == "NEEDS_CONFIRM":
                    st.caption(f"⚠️ {note}")
                p_status = getattr(p, "status", None)
                if p_status in ("llm_unavailable", "llm_error"):
                    st.caption(f"❌ Not rewritten: {getattr(p, 'error', None) or 'the AI call failed'}")
                elif p_status == "unchanged":
                    st.caption("➖ The AI kept your original wording for this bullet.")
            if sel:
                selected.append(p)
                edits[p.id if hasattr(p, 'id') else i] = edt

        # Suggest-and-confirm (P3.1): only what you confirm is used.
        gap_questions = st.session_state.get("gap_questions") or []
        gap_inputs = []
        if gap_questions:
            st.markdown("---")
            st.markdown(f"**❓ {len(gap_questions)} question(s) about what the job asks for**")
            st.caption("Your resume doesn't show these yet. Tick only what you have really used; nothing is "
                       "added unless you tick it or describe it.")
            for q in gap_questions:
                st.markdown(f"*{q.requirement}*" + (" (nice to have)" if q.priority == "preferred" else ""))
                ticked = [k for k in q.keywords if st.checkbox(f"I have used {k}", key=f"{q.id}_{k}")]
                answer = st.text_area("Where and how? (optional, your own words; becomes a bullet)",
                                      key=f"{q.id}_answer", height=68)
                where = st.selectbox("Add the bullet to", options=target_labels, key=f"{q.id}_target")
                gap_inputs.append((q, ticked, answer, where))

        st.markdown("---")
        st.markdown("**Add anything else** — a project, achievement, or skill you'd like included.")
        addition_text = st.text_area(
            "Describe it in your own words",
            key="addition_text_input",
            height=100,
            placeholder="e.g. Led a cross-functional migration to Kubernetes, cutting deploy time by 40%.",
            label_visibility="collapsed",
        )
        target_choice = st.selectbox("Where should this go?", options=target_labels, key="addition_target_choice")

        apply_btn = st.form_submit_button("Apply & Generate")

    if not apply_btn:
        st.info("Review the proposals and press 'Apply & Generate' when ready.")
    else:
        def _target_id(choice):
            if choice.startswith("Auto"):
                return "auto"
            if choice == "Add as a new Project":
                return "new_project"
            return experience_options[target_labels.index(choice) - 1]["id"]

        addition_target = _target_id(target_choice)
        gap_answers = [
            {"question_id": q.id, "confirmed_keywords": ticked, "answer": answer or "", "target": _target_id(where)}
            for q, ticked, answer, where in gap_inputs if ticked or (answer or "").strip()
        ]

        preapproved = []
        for p in selected:
            edited_text = edits.get(p.id if hasattr(p, 'id') else None) or (
                getattr(p, "proposed_text", None) or getattr(p, "rewritten_text", None) or ""
            )
            if hasattr(p, 'model_dump'):
                base = p.model_dump()
            elif hasattr(p, 'dict'):
                base = p.dict()
            else:
                base = {}
            original_proposed = getattr(p, "proposed_text", None) or getattr(p, "rewritten_text", None) or ""
            base["user_edited"] = edited_text.strip() != original_proposed.strip()
            base["proposed_text"] = edited_text
            base.pop("rewritten_text", None)  # model_dump mirrors it; the edit must win
            preapproved.append(base)

        output_dir = tempfile.mkdtemp()
        try:
            with st.spinner("Applying changes, regenerating your résumé, and rescoring..."):
                llm_client = LLMClient(model=st.session_state.model_choice)
                service = TailorService(llm_client=llm_client)
                results = service.tailor_resume(
                    st.session_state.resume_path,
                    st.session_state.jd_text,
                    output_dir,
                    mode=st.session_state.render_mode,
                    strict_factual=st.session_state.strict_factual,
                    preapproved_proposals=preapproved,
                    addition_text=addition_text,
                    addition_target=addition_target,
                    proposal_usage=st.session_state.get("proposal_usage"),
                    parsed=st.session_state.get("parsed"),
                    parse_corrected=bool(st.session_state.get("parse_corrected")),
                    job_desc=st.session_state.get("job_description"),
                    gap_answers=gap_answers,
                )
            st.session_state.results = results
            st.session_state.output_dir = output_dir
            st.session_state.stage = "results"
            st.rerun()
        except Exception as e:
            shutil.rmtree(output_dir, ignore_errors=True)
            st.error(f"Execution Error: {e}")


# ---------------------------------------------------------------------------
# Final results: score, downloads, live preview, change log
# (persists across reruns triggered by download-button clicks, tab
# switches, etc. — previously this whole section only ever rendered on the
# exact script run 'Apply & Generate' was clicked, and vanished immediately.)
# ---------------------------------------------------------------------------
if st.session_state.stage == "results" and st.session_state.get("results") is not None:
    results = st.session_state.results

    pre_score = st.session_state.get("pre_score")
    score_suffix = ""
    if results.get("initial_alignment_score") is not None:
        score_suffix = f" (was {results['initial_alignment_score']}% before tailoring)"

    if results.get("success"):
        st.success(f"Resume Tailoring Completed! Keyword match: {results['alignment_score']}%{score_suffix}")
    else:
        st.error(f"Resume Tailoring Completed with Warnings. Keyword match: {results['alignment_score']}%{score_suffix}")
    with st.expander("Keyword match details"):
        _show_keyword_match(results.get("keyword_match"), heading="Keyword match after tailoring")

    if results.get("addition_note"):
        st.caption(f"➕ Your addition was incorporated: {results['addition_note']}")

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        if results["docx"] and os.path.exists(results["docx"]):
            with open(results["docx"], "rb") as f:
                st.download_button(
                    label="📥 Download Tailored DOCX",
                    data=f.read(),
                    file_name=os.path.basename(results["docx"]),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
    with res_col2:
        if results["pdf"] and os.path.exists(results["pdf"]):
            with open(results["pdf"], "rb") as f:
                st.download_button(
                    label="📥 Download Tailored PDF",
                    data=f.read(),
                    file_name=os.path.basename(results["pdf"]),
                    mime="application/pdf",
                    use_container_width=True,
                )

    st.write("---")
    preview_tab, changes_tab = st.tabs(["👁️ Live Preview of Tailored Resume", "📋 Change Log & Audit Report"])

    with preview_tab:
        st.markdown("### Tailored Resume Document Preview")
        if results.get("pdf") and os.path.exists(results["pdf"]):
            preview_server = display_pdf_with_fallback(results["pdf"], height=900)
            with open(results["pdf"], "rb") as f:
                st.download_button(
                    label="📥 Open / Download Tailored PDF",
                    data=f.read(),
                    file_name=os.path.basename(results["pdf"]),
                    mime="application/pdf",
                    use_container_width=True,
                    key="preview_download_pdf",
                )
            if preview_server:
                st.session_state["preview_server"] = preview_server
        elif results.get("html") and os.path.exists(results["html"]):
            with open(results["html"], "r", encoding="utf-8") as f:
                st.components.v1.html(f.read(), height=900, scrolling=True)
        else:
            st.info("The generated DOCX is available for download. A visual preview could not be generated.")

    with changes_tab:
        st.markdown("### Change Log & Audit Report")
        if os.path.exists(results["changes_md"]):
            with open(results["changes_md"], "r", encoding="utf-8") as f:
                st.markdown(f.read())

        st.markdown("#### Artifact Warnings")
        docx_warns = results.get("docx_warnings", []) or []
        pdf_warns = results.get("pdf_warnings", []) or []
        if docx_warns:
            st.markdown("**DOCX Warnings:**")
            for w in docx_warns:
                st.warning(w)
        else:
            st.success("DOCX: No warnings")

        if results.get("pdf"):
            if pdf_warns:
                st.markdown("**PDF Warnings:**")
                for w in pdf_warns:
                    st.warning(w)
            else:
                st.success("PDF: No warnings")

    if st.button("🔄 Start Over", key="start_over_bottom"):
        _cleanup_session_state()
        st.rerun()
