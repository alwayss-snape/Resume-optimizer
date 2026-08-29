from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class LLMResponse(BaseModel):
    raw_text: str
    parsed_json: Optional[Dict[str, Any]] = None
    model_name: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    duration_seconds: Optional[float] = None


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMConnectionError(LLMError):
    """Raised when Ollama server is unreachable."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM call exceeds timeout."""
    pass


class LLMInvalidJSONError(LLMError):
    """Raised when structured JSON output parsing fails after retries."""
    pass
