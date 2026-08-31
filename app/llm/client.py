import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar

# `ollama` is optional for tests and offline runs. Import lazily and tolerate failures.
try:
    import ollama
except Exception:
    ollama = None

# `httpx` backs the Groq provider (OpenAI-compatible HTTP API). Optional so
# the Ollama-only path keeps working even if it's missing.
try:
    import httpx
except Exception:
    httpx = None

from pydantic import BaseModel, ValidationError

from app.config.settings import settings
from app.llm.schemas import (
    LLMConnectionError,
    LLMError,
    LLMInvalidJSONError,
    LLMResponse,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class LLMClient:
    """Unified client for text generation, across two interchangeable providers:

    - "ollama" (default): a local model served by an Ollama daemon. Fully
      offline, nothing leaves the machine.
    - "groq": Groq's free, fast cloud inference API (OpenAI-compatible
      `chat/completions` endpoint). Useful when a stronger model than what
      runs locally is needed. Sends prompt content (which may include
      resume/JD text) to Groq's servers — this is an explicit opt-in.

    The provider is selected via the `provider` argument, falling back to
    `settings.llm_provider` (i.e. the `LLM_PROVIDER` env var). Every other
    method (`generate`, `generate_json`, `is_available`) behaves identically
    regardless of provider, so callers don't need to know which one is active.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = (provider or settings.llm_provider or "ollama").strip().lower()
        self.timeout = timeout or settings.llm_timeout_seconds

        if self.provider == "groq":
            self.host = host or settings.groq_base_url
            self.model = model or settings.groq_model
            # Use `is not None` (not `or`) so an explicit empty string means
            # "no key" rather than silently falling back to settings/.env — keeps
            # this testable without real credentials leaking in via .env.
            self.api_key = api_key if api_key is not None else settings.groq_api_key
            self.client = None  # Groq requests are stateless HTTP calls; no persistent client object.
            if not self.api_key:
                logger.warning("LLM_PROVIDER=groq but GROQ_API_KEY is not set (check your .env file).")
        else:
            self.provider = "ollama"
            self.host = host or settings.llm_host
            self.model = model or settings.llm_model
            self.api_key = None
            # Create Ollama client if available; otherwise keep None and operate in degraded mode.
            if ollama is not None:
                try:
                    self.client = ollama.Client(host=self.host)
                except Exception as e:
                    logger.warning(f"Could not initialize ollama client: {e}")
                    self.client = None
            else:
                self.client = None

        # Every successful/failed generate() call on this instance gets a
        # record here — {timestamp, provider, model, success, prompt_tokens,
        # completion_tokens, duration_seconds} (or {..., success: False,
        # error} on failure). Call get_usage_summary() to aggregate it.
        # Since a single LLMClient is created once per TailorService/run
        # and reused for every pipeline call, this gives an accurate
        # per-run token count instead of guessing at free-tier headroom.
        self.usage_log: List[Dict[str, Any]] = []

    def is_available(self) -> bool:
        """Check if the configured provider is reachable and the model is available."""
        if self.provider == "groq":
            return self._groq_is_available()
        try:
            models_response = self.client.list()
            available_models = [m.get("name", m.get("model", "")) for m in models_response.get("models", [])]
            # Check if self.model matches or starts with model name
            return any(self.model in m or m in self.model for m in available_models)
        except Exception as e:
            logger.warning(f"Ollama server availability check failed: {e}")
            return False

    def _groq_is_available(self) -> bool:
        if httpx is None or not self.api_key:
            return False
        try:
            resp = httpx.get(
                f"{self.host}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Groq availability check failed: {e}")
            return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        think: bool = False,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """Generate text from the LLM using the chat interface.

        Every call (success or failure) is recorded to `self.usage_log` —
        see `get_usage_summary()`.
        """
        try:
            if self.provider == "groq":
                response = self._generate_groq(messages, temperature=temperature, response_format=response_format)
            else:
                response = self._generate_ollama(messages, temperature=temperature, response_format=response_format)
        except Exception as e:
            self.usage_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": self.provider,
                "model": self.model,
                "success": False,
                "error": str(e),
            })
            raise

        self.usage_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "model": response.model_name,
            "success": True,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "duration_seconds": response.duration_seconds,
        })
        return response

    def get_usage_summary(self) -> Dict[str, Any]:
        """Aggregate every generate() call made on this client instance so
        far into totals: call counts, prompt/completion/total tokens, and
        time spent in LLM calls. Meant to be saved once per run (see
        TailorService.tailor_resume -> data/runs/<run_id>/llm_usage.json)
        so you have real numbers for whether a single free-tier Groq model
        is enough headroom, rather than estimating."""
        successes = [c for c in self.usage_log if c.get("success")]
        failures = [c for c in self.usage_log if not c.get("success")]
        total_prompt = sum(c.get("prompt_tokens") or 0 for c in successes)
        total_completion = sum(c.get("completion_tokens") or 0 for c in successes)
        return {
            "provider": self.provider,
            "model": self.model,
            "call_count": len(self.usage_log),
            "success_count": len(successes),
            "failure_count": len(failures),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_duration_seconds": round(sum(c.get("duration_seconds") or 0 for c in successes), 3),
            "calls": self.usage_log,
        }

    def _generate_ollama(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        response_format: Optional[str],
    ) -> LLMResponse:
        start_time = time.time()
        options = {
            "temperature": temperature,
        }

        if not self.client:
            raise LLMConnectionError("LLM client is not configured or Ollama client not available.")

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options=options,
                format=response_format,
            )
            duration = time.time() - start_time
            content = response.get("message", {}).get("content", "")

            prompt_tokens = response.get("prompt_eval_count")
            completion_tokens = response.get("eval_count")

            return LLMResponse(
                raw_text=content,
                model_name=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_seconds=round(duration, 3),
            )
        except Exception as e:
            # If Ollama-specific ResponseError is available, surface it as LLMError
            if ollama is not None and hasattr(ollama, "ResponseError") and isinstance(e, getattr(ollama, "ResponseError")):
                raise LLMError(f"Ollama error: {e}") from e
            if "connect" in str(e).lower() or "connection" in str(e).lower():
                raise LLMConnectionError(f"Cannot connect to Ollama host at {self.host}: {e}") from e
            raise LLMError(f"LLM generation failed: {e}") from e

    def _generate_groq(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        response_format: Optional[str],
    ) -> LLMResponse:
        if httpx is None:
            raise LLMError("The 'httpx' package is required for the Groq provider (pip install httpx).")
        if not self.api_key:
            raise LLMConnectionError("GROQ_API_KEY is not set. Add it to your .env file to use LLM_PROVIDER=groq.")

        start_time = time.time()
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = httpx.post(
                f"{self.host}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Groq request timed out after {self.timeout}s: {e}") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Cannot connect to Groq API at {self.host}: {e}") from e
        except Exception as e:
            raise LLMError(f"Groq request failed: {e}") from e

        if resp.status_code != 200:
            raise LLMError(f"Groq API error ({resp.status_code}): {resp.text}")

        duration = time.time() - start_time
        data = resp.json()
        choices = data.get("choices") or [{}]
        content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage", {}) or {}

        return LLMResponse(
            raw_text=content,
            model_name=data.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            duration_seconds=round(duration, 3),
        )

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        schema_model: Type[T],
        *,
        temperature: float = 0.0,
        max_retries: int = 2,
    ) -> T:
        """Generate structured JSON conforming to a Pydantic model with retry logic."""
        current_messages = list(messages)
        
        # Enforce system instruction for JSON output matching Pydantic schema
        schema_json = json.dumps(schema_model.model_json_schema(), indent=2)
        system_injection = (
            f"\n\nCRITICAL INSTRUCTION: Respond strictly with a valid JSON object matching this JSON Schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do NOT wrap the output in markdown backticks unless strictly JSON. Output raw JSON only."
        )
        
        if current_messages and current_messages[0]["role"] == "system":
            current_messages[0] = {
                "role": "system",
                "content": current_messages[0]["content"] + system_injection,
            }
        else:
            current_messages.insert(0, {"role": "system", "content": system_injection})

        last_error = None
        for attempt in range(1 + max_retries):
            response = self.generate(
                messages=current_messages,
                temperature=temperature,
                response_format="json",
            )
            raw_text = response.raw_text.strip()
            
            # Clean markdown JSON wrapping if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            try:
                data = json.loads(raw_text)
                parsed_object = schema_model.model_validate(data)
                return parsed_object
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"JSON validation failed on attempt {attempt + 1}: {e}")
                last_error = e
                # Retry with error feedback in message chain
                current_messages.append({"role": "assistant", "content": raw_text})
                current_messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous response failed validation with error: {e}.\n"
                        f"Please output strictly valid JSON conforming to the schema."
                    ),
                })

        raise LLMInvalidJSONError(
            f"Failed to generate valid JSON matching schema {schema_model.__name__} after {max_retries + 1} attempts. Last error: {last_error}"
        )
