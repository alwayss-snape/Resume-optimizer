import datetime
import hashlib
import json
import os
import shutil
from typing import Any, Dict

class RunManager:
    def __init__(self, base_runs_dir: str = "data/runs"):
        self.base_runs_dir = base_runs_dir

    def create_run(self, resume_path: str, jd_text: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        run_hash = hashlib.md5(f"{resume_path}_{timestamp}".encode("utf-8")).hexdigest()[:6]
        run_id = f"{timestamp}_{run_hash}"
        
        run_dir = os.path.join(self.base_runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # Copy original input resume
        if os.path.exists(resume_path):
            shutil.copy(resume_path, os.path.join(run_dir, "input_resume" + os.path.splitext(resume_path)[1]))

        # Save JD text
        with open(os.path.join(run_dir, "jd.txt"), "w", encoding="utf-8") as f:
            f.write(jd_text)

        return run_dir

    def save_json(self, run_dir: str, filename: str, data: Any) -> str:
        path = os.path.join(run_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            if hasattr(data, "model_dump_json"):
                f.write(data.model_dump_json(indent=2))
            else:
                json.dump(data, f, indent=2, default=str)
        return path
