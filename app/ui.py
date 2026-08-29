import base64
import os
import sys
import tempfile

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

                status_text.text("Executing controlled LLM rewriting and factual validation...")
                progress_bar.progress(75)

                output_dir = tempfile.mkdtemp()
                results = service.tailor_resume(tmp_resume_path, jd_input, output_dir, mode=render_mode)
                progress_bar.progress(100)
                status_text.text("Done!")

                st.success(f"Resume Tailoring Completed! Alignment Score: {results['alignment_score']} / 100")

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
                        # Preview the generated document itself, not a flattened
                        # Markdown reconstruction of its contents.
                        with open(results["pdf"], "rb") as f:
                            pdf_b64 = base64.b64encode(f.read()).decode("ascii")
                        st.components.v1.html(
                            f'<iframe src="data:application/pdf;base64,{pdf_b64}" '
                            f'width="100%" height="900" style="border: 1px solid #374151;"></iframe>',
                            height=920,
                        )
                    else:
                        st.info("The generated DOCX is available for download. A visual preview requires PDF conversion.")

                with changes_tab:
                    st.markdown("### Change Log & Audit Report")
                    if os.path.exists(results["changes_md"]):
                        with open(results["changes_md"], "r", encoding="utf-8") as f:
                            st.markdown(f.read())

        except Exception as e:
            st.error(f"Execution Error: {e}")
        finally:
            if os.path.exists(tmp_resume_path):
                os.remove(tmp_resume_path)
