"""
Lightweight local stub for the `ollama` package used in tests.

This file intentionally provides a minimal, import-safe `Client` class so
that tests can patch `ollama.Client` without importing the real `ollama`
package (which may attempt network or proxy initialization on import).
"""
from typing import Any, Dict, List, Optional

class ResponseError(Exception):
    pass

class Client:
    def __init__(self, host: Optional[str] = None):
        self.host = host

    def list(self) -> Dict[str, Any]:
        return {"models": []}

    def chat(self, model: str, messages: List[Dict[str, str]], options: Dict[str, Any] = None, format: Optional[str] = None) -> Dict[str, Any]:
        # Return a default structure compatible with expected usage in tests
        return {"message": {"content": ""}, "prompt_eval_count": 0, "eval_count": 0}
