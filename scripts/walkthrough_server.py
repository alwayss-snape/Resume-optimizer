"""The real web app with the offline eval LLM, for browser walkthroughs that
shouldn't spend the Groq quota (P9.4):

    PYTHONPATH=. .venv_py311/bin/python -m uvicorn scripts.walkthrough_server:app --port 8010
"""
from app.api.main import create_app
from app.eval.harness import OfflineLLM
from app.services.tailor import TailorService

app = create_app(make_service=lambda model=None: TailorService(llm_client=OfflineLLM(), keep_run=False), rate_limit=1000)
