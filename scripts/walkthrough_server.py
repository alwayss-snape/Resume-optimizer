"""The real web app with the offline eval LLM, for browser walkthroughs that
shouldn't spend the Groq quota (P9.4):

    PYTHONPATH=. .venv_py311/bin/python -m uvicorn scripts.walkthrough_server:app --port 8010

WALKTHROUGH_WAIT=6 makes drafting pause once as if the free AI service had
asked us to wait 6 s, to see the countdown (P9.7).
"""
import os
import time

from app.api.main import create_app
from app.eval.harness import OfflineLLM
from app.llm.client import WaitNotice
from app.services.tailor import TailorService

WAIT_S = int(os.environ.get("WALKTHROUGH_WAIT", "0"))


class WalkthroughService(TailorService):
    def generate_proposals(self, *args, progress=None, **kwargs):
        if WAIT_S and progress is not None:
            inner = progress
            state = {"waited": False}

            def progress(message):  # noqa: F811 - the first step pauses once
                inner(message)
                if not state["waited"]:
                    state["waited"] = True
                    inner(WaitNotice(f"The free AI service asked us to wait; trying again in {WAIT_S} s", WAIT_S))
                    time.sleep(WAIT_S)
        return super().generate_proposals(*args, progress=progress, **kwargs)


app = create_app(make_service=lambda model=None: WalkthroughService(llm_client=OfflineLLM(), keep_run=False),
                 rate_limit=1000)
