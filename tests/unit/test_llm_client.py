from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.llm.client import LLMClient
from app.llm.schemas import LLMConnectionError, LLMError, LLMInvalidJSONError, LLMResponse

class SampleSchema(BaseModel):
    name: str
    age: int

# --- Ollama provider (existing behavior; provider pinned explicitly so
# these stay correct regardless of LLM_PROVIDER in .env) ---

def test_llm_client_initialization():
    client = LLMClient(host="http://localhost:11434", model="qwen3:4b", provider="ollama")
    assert client.host == "http://localhost:11434"
    assert client.model == "qwen3:4b"
    assert client.provider == "ollama"

@patch("ollama.Client")
def test_llm_is_available_true(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.list.return_value = {"models": [{"name": "qwen3:4b"}]}
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    assert client.is_available() is True

@patch("ollama.Client")
def test_llm_is_available_false(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.list.side_effect = Exception("Connection refused")
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    assert client.is_available() is False

@patch("ollama.Client")
def test_generate_text_success(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.chat.return_value = {
        "message": {"content": "Hello World"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    resp = client.generate([{"role": "user", "content": "Hi"}])
    assert isinstance(resp, LLMResponse)
    assert resp.raw_text == "Hello World"
    assert resp.prompt_tokens == 10

@patch("ollama.Client")
def test_generate_json_success(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.chat.return_value = {
        "message": {"content": '{"name": "Alice", "age": 30}'},
        "prompt_eval_count": 15,
        "eval_count": 10,
    }
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    obj = client.generate_json(
        messages=[{"role": "user", "content": "Parse Alice 30"}],
        schema_model=SampleSchema,
    )
    assert isinstance(obj, SampleSchema)
    assert obj.name == "Alice"
    assert obj.age == 30

@patch("ollama.Client")
def test_generate_json_retry_failure(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.chat.return_value = {
        "message": {"content": "invalid json output"},
    }
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    with pytest.raises(LLMInvalidJSONError):
        client.generate_json(
            messages=[{"role": "user", "content": "Test"}],
            schema_model=SampleSchema,
            max_retries=1,
        )


# --- Groq provider ---

def test_groq_client_initialization():
    client = LLMClient(provider="groq", model="openai/gpt-oss-120b", api_key="test-key")
    assert client.provider == "groq"
    assert client.model == "openai/gpt-oss-120b"
    assert client.api_key == "test-key"
    assert client.host == "https://api.groq.com/openai/v1"

def test_groq_missing_api_key_raises_connection_error():
    client = LLMClient(provider="groq", api_key="")
    with pytest.raises(LLMConnectionError):
        client.generate([{"role": "user", "content": "Hi"}])

@patch("httpx.post")
def test_groq_generate_text_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "openai/gpt-oss-120b",
        "choices": [{"message": {"content": "Hello from Groq"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }
    mock_post.return_value = mock_response

    client = LLMClient(provider="groq", api_key="test-key")
    resp = client.generate([{"role": "user", "content": "Hi"}])

    assert isinstance(resp, LLMResponse)
    assert resp.raw_text == "Hello from Groq"
    assert resp.prompt_tokens == 12
    assert resp.completion_tokens == 4
    mock_post.assert_called_once()
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.groq.com/openai/v1/chat/completions"

@patch("httpx.post")
def test_groq_generate_api_error_raises_llm_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid API key"
    mock_post.return_value = mock_response

    client = LLMClient(provider="groq", api_key="bad-key")
    with pytest.raises(LLMError):
        client.generate([{"role": "user", "content": "Hi"}])

@patch("httpx.get")
def test_groq_is_available_true(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    client = LLMClient(provider="groq", api_key="test-key")
    assert client.is_available() is True

def test_groq_is_available_false_without_key():
    client = LLMClient(provider="groq", api_key="")
    assert client.is_available() is False


# --- Usage tracking (get_usage_summary) ---

@patch("ollama.Client")
def test_usage_log_records_successful_call(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.chat.return_value = {
        "message": {"content": "Hello"},
        "prompt_eval_count": 20,
        "eval_count": 8,
    }
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    client.generate([{"role": "user", "content": "Hi"}])
    client.generate([{"role": "user", "content": "Hi again"}])

    summary = client.get_usage_summary()
    assert summary["call_count"] == 2
    assert summary["success_count"] == 2
    assert summary["failure_count"] == 0
    assert summary["total_prompt_tokens"] == 40
    assert summary["total_completion_tokens"] == 16
    assert summary["total_tokens"] == 56
    assert len(summary["calls"]) == 2

@patch("ollama.Client")
def test_usage_log_records_failed_call(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.chat.side_effect = Exception("boom")
    mock_ollama.return_value = mock_inst

    client = LLMClient(provider="ollama")
    with pytest.raises(LLMError):
        client.generate([{"role": "user", "content": "Hi"}])

    summary = client.get_usage_summary()
    assert summary["call_count"] == 1
    assert summary["success_count"] == 0
    assert summary["failure_count"] == 1
    assert summary["total_tokens"] == 0
    assert summary["calls"][0]["success"] is False
