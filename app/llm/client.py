import json
import re
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Any, Dict, List, Optional, Tuple, Type, TypeVar

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

# Official Anthropic SDK backs the Claude provider. Optional for the same reason.
try:
    import anthropic
except Exception:
    anthropic = None

from pydantic import BaseModel, ValidationError

from app.config.settings import settings
from app.validation.safety import SafetyGuard
from app.llm.schemas import (
    LLMConnectionError,
    LLMError,
    LLMInvalidJSONError,
    LLMResponse,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

PROVIDERS = ("anthropic", "groq", "ollama")

# Every prompt passes through this: resume / JD text is untrusted (F35).
_GUARD = SafetyGuard()

# Server-side refusal fallback for Claude: if a request is declined by a
# safety classifier, the API re-runs it on a suitable fallback model inside
# the same call. Resume text essentially never trips this, but it costs
# nothing when unused and turns a hard failure into a served response.
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
ANTHROPIC_MAX_TOKENS = 16000

GROQ_MAX_ATTEMPTS = 4          # 1 call + 3 retries on HTTP 429
GROQ_MAX_RETRY_WAIT = 30.0     # seconds; never sleep longer than this per retry
# A per-minute limit can ask for up to a minute; that's worth waiting for once
# (P9.3: a 41 s tokens-per-minute wait failed the role rewrite of the real
# resume). Only the daily limit, or a longer wait, fails fast.
GROQ_MAX_MINUTE_WAIT = 65.0


class LLMClient:
    """Unified client for text generation across three interchangeable providers:

    - "anthropic": Claude via the official SDK, with schema-guaranteed JSON
      (structured outputs). Best rewrite quality. Sends prompt content
      (resume/JD text) to Anthropic; needs a pay-as-you-go API key.
    - "groq": Groq's fast cloud inference API (OpenAI-compatible
      `chat/completions`), free tier available. Sends prompt content to Groq.
    - "ollama": a local model served by an Ollama daemon. Fully offline.

    The provider is selected via the `provider` argument, falling back to
    `settings.llm_provider` (the `LLM_PROVIDER` env var). `generate`,
    `generate_json` and `is_available` behave identically regardless of
    provider, so callers don't need to know which one is active.
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
        # is_available() result, cached per instance: one health check per
        # run instead of an HTTP round-trip before every LLM call.
        self._available: Optional[bool] = None
        self.last_error: Optional[str] = None
        # Told about each rate-limit wait, so a progress view can say why a
        # step pauses (P8.23); set by the service for the length of a run.
        self.on_wait: Optional[Callable[[str], None]] = None


        if self.provider == "anthropic":
            self.host = host or "https://api.anthropic.com"
            self.model = model or settings.anthropic_model
            # `is not None` (not `or`): an explicit "" means "no key" rather than
            # silently falling back to .env, which keeps this testable.
            self.api_key = api_key if api_key is not None else settings.anthropic_api_key
            self.client = None
            if anthropic is None:
                logger.warning("LLM_PROVIDER=anthropic but the 'anthropic' package is not installed.")
            elif not self.api_key:
                logger.warning("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set (check your .env file).")
            else:
                # The SDK retries connection errors, 408/409/429 and 5xx with backoff.
                self.client = anthropic.Anthropic(api_key=self.api_key, timeout=float(self.timeout), max_retries=3)
        elif self.provider == "groq":
            self.host = host or settings.groq_base_url
            self.model = model or settings.groq_model
            self.api_key = api_key if api_key is not None else settings.groq_api_key
            self.client = None  # Groq requests are plain HTTP calls through self._http.
            self._http = None
            if httpx is not None:
                # local_address="0.0.0.0" binds the socket to IPv4, see settings.groq_force_ipv4.
                transport = httpx.HTTPTransport(local_address="0.0.0.0") if settings.groq_force_ipv4 else None
                self._http = httpx.Client(transport=transport)
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

        # Every successful/failed LLM call on this instance gets a record
        # here — {timestamp, provider, model, success, prompt_tokens,
        # completion_tokens, duration_seconds} (or {..., success: False,
        # error} on failure). Call get_usage_summary() to aggregate it.
        # Since a single LLMClient is created once per TailorService/run
        # and reused for every pipeline call, this gives an accurate
        # per-run token count.
        self.usage_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # availability
    # ------------------------------------------------------------------

    def is_available(self, refresh: bool = False) -> bool:
        """Whether the configured provider is reachable AND the configured
        model exists there. Cached after the first check; pass refresh=True
        to re-check. On failure, `last_error` says why (shown in the UI)."""
        until = _DAILY_LIMIT_UNTIL.get(self.provider)
        if until and time.time() < until:  # shared by every client of this provider in the process
            self.last_error = daily_limit_message(until - time.time())
            return False
        if self._available is None or refresh:
            ok, reason = self._check_available()
            self._available = ok
            self.last_error = None if ok else reason
            if not ok:
                logger.warning(f"LLM unavailable ({self.provider}/{self.model}): {reason}")
        return self._available

    def _check_available(self) -> Tuple[bool, str]:
        if self.provider == "anthropic":
            return self._anthropic_check()
        if self.provider == "groq":
            return self._groq_check()
        return self._ollama_check()

    def _ollama_check(self) -> Tuple[bool, str]:
        if not self.client:
            return False, "the 'ollama' package is not installed"
        try:
            models_response = self.client.list()
            available_models = [m.get("name", m.get("model", "")) for m in models_response.get("models", [])]
        except Exception as e:
            return False, f"cannot reach Ollama at {self.host} ({e})"
        if any(self.model in m or m in self.model for m in available_models):
            return True, ""
        return False, f"model '{self.model}' is not pulled in Ollama (run: ollama pull {self.model})"

    def _groq_check(self) -> Tuple[bool, str]:
        if httpx is None:
            return False, "the 'httpx' package is not installed"
        if not self.api_key:
            return False, "GROQ_API_KEY is not set"
        try:
            resp = self._http.get(f"{self.host}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
        except Exception as e:
            return False, f"cannot reach Groq ({e})"
        if resp.status_code != 200:
            return False, f"Groq returned HTTP {resp.status_code} (check GROQ_API_KEY)"
        # A reachable API is not enough: a wrong model name (e.g. an Ollama
        # tag like "qwen3:4b") makes every call fail later, silently.
        try:
            ids = {m.get("id") for m in resp.json().get("data", [])}
        except Exception:
            ids = set()
        if ids and self.model not in ids:
            return False, f"model '{self.model}' is not available on Groq"
        return True, ""

    def _anthropic_check(self) -> Tuple[bool, str]:
        if anthropic is None:
            return False, "the 'anthropic' package is not installed (pip install anthropic)"
        if not self.client:
            return False, "ANTHROPIC_API_KEY is not set"
        try:
            self.client.models.retrieve(self.model)
            return True, ""
        except anthropic.AuthenticationError:
            return False, "ANTHROPIC_API_KEY was rejected"
        except anthropic.NotFoundError:
            return False, f"model '{self.model}' is not available to this API key"
        except anthropic.APIConnectionError as e:
            return False, f"cannot reach the Anthropic API ({e})"
        except Exception as e:
            return False, f"Anthropic availability check failed ({e})"

    # ------------------------------------------------------------------
    # generation
    # ------------------------------------------------------------------

    def _record(self, success: bool, *, model: Optional[str] = None, error: Optional[str] = None,
                response: Optional[LLMResponse] = None) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "model": model or self.model,
            "success": success,
        }
        if response is not None:
            entry.update(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                duration_seconds=response.duration_seconds,
            )
        if error is not None:
            entry["error"] = error
        self.usage_log.append(entry)

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        think: bool = False,
        response_format: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> LLMResponse:
        """Generate text from the LLM using the chat interface.

        Every call (success or failure) is recorded to `self.usage_log` —
        see `get_usage_summary()`. `effort` ("low" | "medium" | "high") tunes
        reasoning depth where the provider supports it; others ignore it.
        """
        messages = _GUARD.guard_messages(messages)
        try:
            if self.provider == "anthropic":
                response = self._generate_anthropic(messages, effort=effort)
            elif self.provider == "groq":
                response = self._generate_groq(messages, temperature=temperature,
                                               response_format=response_format, effort=effort)
            else:
                response = self._generate_ollama(messages, temperature=temperature, response_format=response_format)
        except Exception as e:
            self._record(False, error=str(e))
            raise
        self._record(True, model=response.model_name, response=response)
        return response

    def get_usage_summary(self) -> Dict[str, Any]:
        """Aggregate every LLM call made on this client instance so far
        into totals: call counts, prompt/completion/total tokens, and time
        spent in LLM calls. Saved once per run (see
        TailorService.tailor_resume -> data/runs/<run_id>/llm_usage.json)."""
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

    # --- Groq -----------------------------------------------------------

    def _groq_supports_strict_schema(self) -> bool:
        # Groq's strict json_schema mode is supported on the gpt-oss models.
        return "gpt-oss" in (self.model or "")

    def _generate_groq(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        response_format: Optional[str],
        effort: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "response",
    ) -> LLMResponse:
        if httpx is None:
            raise LLMError("The 'httpx' package is required for the Groq provider (pip install httpx).")
        if not self.api_key:
            raise LLMConnectionError("GROQ_API_KEY is not set. Add it to your .env file to use LLM_PROVIDER=groq.")

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema, "strict": True},
            }
        elif response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        if effort and self._groq_supports_strict_schema():
            payload["reasoning_effort"] = effort

        start_time = time.time()
        for attempt in range(GROQ_MAX_ATTEMPTS):
            try:
                resp = self._http.post(
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

            # Free-tier rate limits (requests/tokens per minute) are routine:
            # wait as instructed and retry instead of failing the rewrite.
            if resp.status_code == 429 and attempt < GROQ_MAX_ATTEMPTS - 1:
                if _too_long_to_wait(resp):
                    break  # e.g. the daily token limit: retrying now can't succeed
                wait = max(_retry_after_seconds(resp, attempt), min(_requested_wait(resp), GROQ_MAX_MINUTE_WAIT))
                logger.warning(f"Groq rate limited (429); retrying in {wait:.1f}s")
                if self.on_wait:
                    try:
                        self.on_wait(f"The free AI service is busy; waiting {max(1, round(wait))} s and trying again")
                    except Exception:
                        pass
                time.sleep(wait)
                continue
            break

        if resp.status_code == 429 and _too_long_to_wait(resp):
            wait_s = _requested_wait(resp)
            minutes = max(1, round(wait_s / 60))
            if "per day" in (resp.text or ""):
                _DAILY_LIMIT_UNTIL[self.provider] = time.time() + wait_s
                message = daily_limit_message(wait_s)
                self.last_error = message
                raise LLMDailyLimitError(message)
            raise LLMError(f"Groq free-tier rate limit reached; try again in about {minutes} min. ({resp.text[:200]})")
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

    # --- Anthropic ------------------------------------------------------

    @staticmethod
    def _split_system(messages: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """The Messages API takes the system prompt as a top-level field,
        not as a message with role "system"."""
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        rest = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") != "system"]
        return ("\n\n".join(system_parts) or None), rest

    def _anthropic_request(self, messages: List[Dict[str, str]], *, effort: Optional[str],
                           output_format: Optional[Type[BaseModel]] = None):
        if anthropic is None:
            raise LLMError("The 'anthropic' package is required for LLM_PROVIDER=anthropic (pip install anthropic).")
        if not self.client:
            raise LLMConnectionError("ANTHROPIC_API_KEY is not set. Add it to your .env file to use LLM_PROVIDER=anthropic.")

        system, chat = self._split_system(messages)
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "messages": chat,
            "betas": [ANTHROPIC_FALLBACK_BETA],
            "fallbacks": "default",
        }
        if system:
            kwargs["system"] = system
        if effort:
            kwargs["output_config"] = {"effort": effort}
        # No temperature: sampling parameters are rejected on current Claude models.
        try:
            if output_format is not None:
                return self.client.beta.messages.parse(output_format=output_format, **kwargs)
            return self.client.beta.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise LLMConnectionError(f"ANTHROPIC_API_KEY was rejected: {e}") from e
        except anthropic.NotFoundError as e:
            raise LLMError(f"Model '{self.model}' not found: {e}") from e
        except anthropic.RateLimitError as e:
            raise LLMError(f"Anthropic rate limit hit after retries: {e}") from e
        except anthropic.APITimeoutError as e:
            raise LLMTimeoutError(f"Anthropic request timed out after {self.timeout}s: {e}") from e
        except anthropic.APIConnectionError as e:
            raise LLMConnectionError(f"Cannot connect to the Anthropic API: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API error ({e.status_code}): {e}") from e

    def _anthropic_response(self, response, start_time: float) -> LLMResponse:
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMError(f"Claude declined the request ({getattr(details, 'category', None) or 'refusal'}).")
        if response.stop_reason == "max_tokens":
            raise LLMError("Claude's response was cut off at the max_tokens limit.")
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
        usage = response.usage
        return LLMResponse(
            raw_text=text,
            model_name=getattr(response, "model", None) or self.model,
            prompt_tokens=(usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0),
            completion_tokens=usage.output_tokens,
            duration_seconds=round(time.time() - start_time, 3),
        )

    def _generate_anthropic(self, messages: List[Dict[str, str]], *, effort: Optional[str]) -> LLMResponse:
        start_time = time.time()
        response = self._anthropic_request(messages, effort=effort)
        return self._anthropic_response(response, start_time)

    def _generate_json_anthropic(self, messages: List[Dict[str, str]], schema_model: Type[T],
                                 effort: Optional[str]) -> T:
        """Structured outputs guarantee the response matches the schema, so
        there's no prompt-embedded schema and no parse-retry loop."""
        start_time = time.time()
        try:
            response = self._anthropic_request(messages, effort=effort, output_format=schema_model)
            result = self._anthropic_response(response, start_time)
            parsed = getattr(response, "parsed_output", None)
            if parsed is None:
                raise LLMInvalidJSONError(f"Claude returned no parseable {schema_model.__name__} output.")
        except Exception as e:
            self._record(False, error=str(e))
            raise
        self._record(True, model=result.model_name, response=result)
        return parsed

    # ------------------------------------------------------------------
    # structured JSON
    # ------------------------------------------------------------------

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        schema_model: Type[T],
        *,
        temperature: float = 0.0,
        max_retries: int = 2,
        effort: Optional[str] = "medium",
    ) -> T:
        """Generate structured JSON conforming to a Pydantic model.

        Claude uses native structured outputs. Groq gpt-oss models use strict
        json_schema mode. Other models get the schema in the prompt, with
        parse-and-retry on invalid output."""
        messages = _GUARD.guard_messages(messages)
        if self.provider == "anthropic":
            return self._generate_json_anthropic(messages, schema_model, effort)

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

        strict_schema = None
        if self.provider == "groq" and self._groq_supports_strict_schema():
            strict_schema = strict_json_schema(schema_model.model_json_schema())

        last_error = None
        for attempt in range(1 + max_retries):
            if strict_schema is not None:
                try:
                    response = self._generate_groq(current_messages, temperature=temperature, response_format="json",
                                                   effort=effort, json_schema=strict_schema,
                                                   schema_name=schema_model.__name__)
                except Exception as e:
                    self._record(False, error=str(e))
                    # Groq sometimes rejects its own strict-mode output
                    # ("json_validate_failed", often with an empty generation);
                    # that's transient, so it's retried like invalid JSON.
                    if "json_validate_failed" in str(e) and attempt < max_retries:
                        logger.warning(f"Groq strict JSON validation failed on attempt {attempt + 1}; retrying")
                        last_error = e
                        # Reasoning used up the completion budget before the JSON
                        # was written (P9.3: 5 of 12 bullets lost on the real
                        # resume): think less on the next try.
                        if "max completion tokens" in str(e) and effort in ("high", "medium"):
                            effort = "medium" if effort == "high" else "low"
                        continue
                    raise
                self._record(True, model=response.model_name, response=response)
            else:
                response = self.generate(
                    messages=current_messages,
                    temperature=temperature,
                    response_format="json",
                    effort=effort,
                )
            raw_text = response.raw_text.strip()
            # Reasoning models (Qwen3) may put their thinking before the answer.
            raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

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


def _requested_wait(resp: Any) -> float:
    """How long Groq asks us to wait: the retry-after header, else the
    "Please try again in 15m43.5s" text in the body; 0 if neither."""
    try:
        header = resp.headers.get("retry-after")
        if header is not None:
            return float(header)
    except Exception:
        pass
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", getattr(resp, "text", "") or "")
    if not m or not any(m.groups()):
        return 0.0
    h, mnt, sec = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600 + mnt * 60 + sec


# provider -> time when its daily free limit resets (P8.23)
_DAILY_LIMIT_UNTIL: Dict[str, float] = {}


class LLMDailyLimitError(LLMError):
    """The provider's daily free limit is used up (P8.23)."""


def daily_limit_message(wait_seconds: float) -> str:
    hours, mins = divmod(max(1, round(wait_seconds / 60)), 60)
    when = f"about {hours} h {mins} min" if hours else f"about {mins} min"
    return (f"Today's free AI limit is used up, so drafting rewrites isn't available for {when}. You can still "
            "check your match, arrange your resume and download it; tailoring with AI works again after that.")


def _too_long_to_wait(resp: Any) -> bool:
    """A 429 not worth waiting for: the daily limit, or a wait over a minute."""
    wait = _requested_wait(resp)
    return wait > GROQ_MAX_RETRY_WAIT and ("per day" in (resp.text or "") or wait > GROQ_MAX_MINUTE_WAIT)


def _retry_after_seconds(resp: Any, attempt: int) -> float:
    """Seconds to wait before retrying a 429: the server's `retry-after`
    header when present, else exponential backoff (1, 2, 4 s)."""
    header = None
    try:
        header = resp.headers.get("retry-after")
    except Exception:
        pass
    try:
        wait = float(header) if header is not None else float(2 ** attempt)
    except (TypeError, ValueError):
        wait = float(2 ** attempt)
    return max(0.0, min(wait, GROQ_MAX_RETRY_WAIT))


def strict_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt a Pydantic JSON schema for strict structured-output modes: every
    object gets additionalProperties=false and lists all its properties as
    required, and "default" keywords are dropped. Applied recursively,
    including to $defs."""
    if isinstance(schema, list):
        return [strict_json_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: strict_json_schema(v) for k, v in schema.items() if k != "default"}
    if out.get("type") == "object" or "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}).keys())
    return out
