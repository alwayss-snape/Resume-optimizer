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
            import fitz
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
        "proposals", "missing_suggestions", "llm_available", "pre_score",
        "resume_path", "jd_text", "model_choice", "render_mode", "strict_factual",
        "results", "output_dir", "analysis_report", "experience_options",
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

# Sidebar settings
st.sidebar.title("⚙️ Model & Configuration")
model_choice = st.sidebar.selectbox(
    "Select Model",
    options=["qwen3:4b", "qwen3:8b", "qwen3.5:4b"],
    index=0,
    help="Default qwen3:4b recommended for 8GB Mac."
)
render_mode = st.sidebar.radio(
    "Output Layout Mode",
    options=["PRESERVE", "ATS_DEFAULT"],
    index=0,
    help="PRESERVE mode patches existing DOCX in-place. ATS_DEFAULT reconstructs standard template."
)
strict_factual = st.sidebar.checkbox("Strict Factual Mode", value=True)

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
                with st.spinner("Ingesting document, analyzing the job description, and drafting proposals..."):
                    generated = service.generate_proposals(tmp_resume_path, jd_input)

                st.session_state.stage = "proposals"
                st.session_state.proposals = generated["proposals"]
                st.session_state.missing_suggestions = generated["missing_suggestions"]
                st.session_state.llm_available = generated["llm_available"]
                st.session_state.pre_score = generated["alignment_score"]
                st.session_state.experience_options = generated["experience_options"]
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


# ---------------------------------------------------------------------------
# Analysis-only results (persists across reruns)
# ---------------------------------------------------------------------------
if st.session_state.stage == "analysis" and st.session_state.get("analysis_report") is not None:
    report = st.session_state.analysis_report

    st.success("Analysis Complete!")
    st.metric("Alignment Score", f"{report.alignment_score:.1f} / 100")
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
    if not st.session_state.get("llm_available", True):
        st.warning(
            f"⚠️ The local LLM (**{st.session_state.get('model_choice', model_choice)}** at "
            f"`{settings.llm_host}`) isn't reachable right now. Until it's running, proposed "
            "rewrites below will match your original text unchanged, and no 'Suggested "
            "Additions' can be drafted. Start Ollama and make sure the model is pulled "
            f"(`ollama pull {st.session_state.get('model_choice', model_choice)}`), then click "
            "**Tailor & Generate Resume** again."
        )

    missing_suggestions = st.session_state.get("missing_suggestions", [])
    if missing_suggestions:
        with st.expander(
            f"📝 Suggested Additions — {len(missing_suggestions)} requirement(s) your résumé doesn't address yet",
            expanded=(st.session_state.stage == "proposals"),
        ):
            st.caption(
                "These are illustrative examples only, not facts about you — adapt them with your "
                "own real experience, then paste your version into the box below to have it added "
                "and phrased consistently."
            )
            for s in missing_suggestions:
                st.markdown(f"**Targets:** {s.requirement_text}")
                st.info(s.suggested_phrasing)
                if s.keywords:
                    st.caption("Keywords to work in: " + ", ".join(s.keywords))
                st.write("")

if st.session_state.stage == "proposals":
    proposals = st.session_state.get("proposals", [])

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
                st.markdown(f"**Original:** {orig}")
                edt = st.text_area(f"Proposed ({i+1})", value=prop_text, key=keybase + "_edit", height=80)
                if rationale:
                    st.caption(f"🎯 {rationale}")
            if sel:
                selected.append(p)
                edits[p.id if hasattr(p, 'id') else i] = edt

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
        if target_choice.startswith("Auto"):
            addition_target = "auto"
        elif target_choice == "Add as a new Project":
            addition_target = "new_project"
        else:
            addition_target = experience_options[target_labels.index(target_choice) - 1]["id"]

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
            base["proposed_text"] = edited_text
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
        score_suffix = f" (was {results['initial_alignment_score']} / 100 before tailoring)"

    if results.get("success"):
        st.success(f"Resume Tailoring Completed! Alignment Score: {results['alignment_score']} / 100{score_suffix}")
    else:
        st.error(f"Resume Tailoring Completed with Warnings. Alignment Score: {results['alignment_score']} / 100{score_suffix}")

    if results.get("addition_note"):
        st.caption(f"➕ Your addition was incorporated: {results['addition_note']}")

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        if results["docx"] and os.path.exists(results["docx"]):
            with open(results["docx"], "rb") as f:
                st.download_button(
                    label="📥 Download Tailored DOCX",
                    data=f.read(),
                    file_name="tailored_resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
    with res_col2:
        if results["pdf"] and os.path.exists(results["pdf"]):
            with open(results["pdf"], "rb") as f:
                st.download_button(
                    label="📥 Download Tailored PDF",
                    data=f.read(),
                    file_name="tailored_resume.pdf",
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
                    file_name="tailored_resume.pdf",
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
