import json
import logging
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
import ollama
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
    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.host = host or settings.llm_host
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout_seconds
        self.client = ollama.Client(host=self.host)

    def is_available(self) -> bool:
        """Check if Ollama server is reachable and model is available."""
        try:
            models_response = self.client.list()
            available_models = [m.get("name", m.get("model", "")) for m in models_response.get("models", [])]
            # Check if self.model matches or starts with model name
            return any(self.model in m or m in self.model for m in available_models)
        except Exception as e:
            logger.warning(f"Ollama server availability check failed: {e}")
            return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        think: bool = False,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """Generate text from LLM using chat interface."""
        start_time = time.time()
        options = {
            "temperature": temperature,
        }

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
        except ollama.ResponseError as e:
            raise LLMError(f"Ollama error: {e}") from e
        except Exception as e:
            if "connect" in str(e).lower() or "connection" in str(e).lower():
                raise LLMConnectionError(f"Cannot connect to Ollama host at {self.host}: {e}") from e
            raise LLMError(f"LLM generation failed: {e}") from e

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
