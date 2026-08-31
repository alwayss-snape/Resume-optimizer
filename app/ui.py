import os
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
                
                st.success("Analysis Complete!")
                st.metric("Alignment Score", f"{report.alignment_score:.1f} / 100")
                
                tab1, tab2, tab3 = st.tabs(["Required Matches", "Preferred Matches", "Missing Requirements"])
                with tab1:
                    for m in report.required_matches:
                        st.write(f"- **[{m.status}]** {m.requirement_text}")
                with tab2:
                    for m in report.preferred_matches:
                        st.write(f"- **[{m.status}]** {m.requirement_text}")
                with tab3:
                    for m in report.missing_requirements:
                        st.write(f"- ❌ {m.requirement_text}")

            elif btn_tailor:
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text("Ingesting document and extracting evidence ledger...")
                progress_bar.progress(25)

                status_text.text("Analyzing job description and generating tailoring plan...")
                progress_bar.progress(50)

                status_text.text("Executing controlled LLM rewriting and factual validation (generating proposals)...")
                progress_bar.progress(75)

                # Generate proposals for UI review before applying
                proposals = service.generate_proposals(tmp_resume_path, jd_input)

                st.markdown("### Review Proposed Rewrites")
                st.markdown("Edit proposed text or uncheck to reject. Then click **Apply & Generate**.")

                with st.form("proposal_review_form"):
                    selected = []
                    edits = {}
                    for i, p in enumerate(proposals):
                        keybase = f"p_{i}"
                        orig = getattr(p, "original_text", "")
                        prop_text = getattr(p, "proposed_text", None) or getattr(p, "rewritten_text", None) or ""
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            sel = st.checkbox("Apply", value=True, key=keybase+"_apply")
                        with col2:
                            st.markdown(f"**Original:** {orig}")
                            edt = st.text_area(f"Proposed ({i+1})", value=prop_text, key=keybase+"_edit", height=80)
                        if sel:
                            selected.append(p)
                            edits[p.id if hasattr(p, 'id') else i] = edt
                    apply_btn = st.form_submit_button("Apply & Generate")

                if not apply_btn:
                    st.info("Review the proposals and press 'Apply & Generate' when ready.")
                else:
                    # Build preapproved proposals list from selected edits
                    preapproved = []
                    for p in selected:
                        edited_text = edits.get(p.id if hasattr(p, 'id') else None) or (getattr(p, "proposed_text", None) or getattr(p, "rewritten_text", None) or "")
                        # Coerce to dict for transport into tailor_resume
                        if hasattr(p, 'model_dump'):
                            base = p.model_dump()
                        elif hasattr(p, 'dict'):
                            base = p.dict()
                        else:
                            base = {}
                        base["proposed_text"] = edited_text
                        preapproved.append(base)

                    output_dir = tempfile.mkdtemp()
                    results = service.tailor_resume(tmp_resume_path, jd_input, output_dir, mode=render_mode, strict_factual=strict_factual, preapproved_proposals=preapproved)
                    progress_bar.progress(100)
                    status_text.text("Done!")

                    if results.get("success"):
                        st.success(f"Resume Tailoring Completed! Alignment Score: {results['alignment_score']} / 100")
                    else:
                        st.error(f"Resume Tailoring Completed with Warnings. Alignment Score: {results['alignment_score']} / 100")

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

                        # Surface per-artifact warnings prominently
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

        except Exception as e:
            st.error(f"Execution Error: {e}")
        finally:
            if os.path.exists(tmp_resume_path):
                os.remove(tmp_resume_path)
