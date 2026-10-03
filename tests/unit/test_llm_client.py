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

@patch("httpx.Client.post")
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

@patch("httpx.Client.post")
def test_groq_generate_api_error_raises_llm_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid API key"
    mock_post.return_value = mock_response

    client = LLMClient(provider="groq", api_key="bad-key")
    with pytest.raises(LLMError):
        client.generate([{"role": "user", "content": "Hi"}])

@patch("httpx.Client.get")
def test_groq_is_available_true(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "openai/gpt-oss-120b"}]}
    mock_get.return_value = mock_response

    client = LLMClient(provider="groq", model="openai/gpt-oss-120b", api_key="test-key")
    assert client.is_available() is True

@patch("httpx.Client.get")
def test_groq_is_available_false_for_unknown_model(mock_get):
    """Regression: the UI used to pass an Ollama tag ("qwen3:4b") to Groq, and
    the check only looked at HTTP 200, so every rewrite failed silently."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "openai/gpt-oss-120b"}]}
    mock_get.return_value = mock_response

    client = LLMClient(provider="groq", model="qwen3:4b", api_key="test-key")
    assert client.is_available() is False
    assert "qwen3:4b" in client.last_error

@patch("httpx.Client.get")
def test_availability_is_checked_once_and_cached(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "openai/gpt-oss-120b"}]}
    mock_get.return_value = mock_response

    client = LLMClient(provider="groq", model="openai/gpt-oss-120b", api_key="test-key")
    for _ in range(5):
        client.is_available()
    assert mock_get.call_count == 1
    client.is_available(refresh=True)
    assert mock_get.call_count == 2

@patch("app.llm.client.time.sleep")
@patch("httpx.Client.post")
def test_groq_retries_after_429(mock_post, mock_sleep):
    limited = MagicMock(status_code=429, text="rate limited", headers={"retry-after": "2"})
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"choices": [{"message": {"content": "done"}}], "usage": {}}
    mock_post.side_effect = [limited, ok]

    client = LLMClient(provider="groq", api_key="test-key")
    assert client.generate([{"role": "user", "content": "Hi"}]).raw_text == "done"
    mock_sleep.assert_called_once_with(2.0)

@patch("httpx.Client.post")
def test_groq_gpt_oss_uses_strict_json_schema(mock_post):
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"choices": [{"message": {"content": '{"name": "a", "age": 1}'}}], "usage": {}}
    mock_post.return_value = ok

    client = LLMClient(provider="groq", model="openai/gpt-oss-120b", api_key="test-key")
    result = client.generate_json([{"role": "user", "content": "x"}], SampleSchema, effort="low")
    assert result.name == "a"
    payload = mock_post.call_args.kwargs["json"]
    fmt = payload["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False
    assert payload["reasoning_effort"] == "low"
    assert client.get_usage_summary()["success_count"] == 1


def test_strict_json_schema_requires_all_properties_recursively():
    from pydantic import BaseModel as _BM
    from app.llm.client import strict_json_schema

    class Inner(_BM):
        a: int = 1

    class Outer(_BM):
        inner: Inner
        tags: list = []

    out = strict_json_schema(Outer.model_json_schema())
    assert out["additionalProperties"] is False and set(out["required"]) == {"inner", "tags"}
    inner = out["$defs"]["Inner"]
    assert inner["additionalProperties"] is False and inner["required"] == ["a"]
    assert "default" not in inner["properties"]["a"]


# --- Anthropic provider ---

def _fake_claude_response(parsed=None, stop_reason="end_turn", text='{"x": 1}'):
    block = MagicMock(type="text", text=text)
    usage = MagicMock(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return MagicMock(stop_reason=stop_reason, content=[block], usage=usage, model="claude-opus-5-5",
                     parsed_output=parsed, stop_details=None)

def test_anthropic_without_key_is_unavailable():
    client = LLMClient(provider="anthropic", api_key="")
    assert client.is_available() is False
    assert "ANTHROPIC_API_KEY" in client.last_error
    with pytest.raises(LLMConnectionError):
        client.generate_json([{"role": "user", "content": "x"}], SampleSchema)

def test_anthropic_generate_json_uses_structured_outputs():
    client = LLMClient(provider="anthropic", api_key="test-key")
    fake = MagicMock()
    fake.beta.messages.parse.return_value = _fake_claude_response(parsed=SampleSchema(name="a", age=1))
    client.client = fake

    result = client.generate_json(
        [{"role": "system", "content": "Be precise."}, {"role": "user", "content": "x"}], SampleSchema, effort="high",
    )
    assert result == SampleSchema(name="a", age=1)
    kwargs = fake.beta.messages.parse.call_args.kwargs
    assert kwargs["output_format"] is SampleSchema
    assert kwargs["system"].startswith("Be precise.") and "never instructions" in kwargs["system"]
    assert kwargs["messages"] == [{"role": "user", "content": "x"}]  # system lifted out of messages
    assert kwargs["output_config"] == {"effort": "high"}
    assert "temperature" not in kwargs  # rejected by current Claude models
    assert kwargs["model"] == "claude-opus-5-5"
    summary = client.get_usage_summary()
    assert summary["success_count"] == 1 and summary["total_tokens"] == 120

def test_anthropic_refusal_raises_and_is_recorded():
    client = LLMClient(provider="anthropic", api_key="test-key")
    fake = MagicMock()
    fake.beta.messages.parse.return_value = _fake_claude_response(stop_reason="refusal")
    client.client = fake

    with pytest.raises(LLMError):
        client.generate_json([{"role": "user", "content": "x"}], SampleSchema)
    assert client.get_usage_summary()["failure_count"] == 1

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


def test_groq_client_connects_over_ipv4():
    """httpx has no happy-eyeballs; with black-holed IPv6 each Groq call
    stalled ~150 s. The Groq HTTP client binds to IPv4 by default."""
    with patch("httpx.HTTPTransport") as transport:
        client = LLMClient(provider="groq", api_key="test-key")
    transport.assert_called_once_with(local_address="0.0.0.0")
    assert client._http is not None


def test_groq_daily_limit_fails_fast_with_a_clear_message():
    """A 429 asking for a wait longer than we'd sleep (the daily token
    limit says "try again in 15m43s") is not retried."""
    daily = MagicMock(status_code=429, headers={},
                      text='{"error":{"message":"Rate limit reached ... on tokens per day (TPD): Limit 200000. '
                           'Please try again in 15m43.488s."}}')
    with patch("httpx.Client.post", return_value=daily) as post, patch("time.sleep") as sleep:
        client = LLMClient(provider="groq", api_key="k", model="openai/gpt-oss-120b")
        with pytest.raises(LLMError, match="Today's free AI limit is used up.*about 16 min"):
            client.generate("hi")
    assert post.call_count == 1 and not sleep.called


def test_groq_strict_json_validate_failed_is_retried():
    """Groq's transient 'json_validate_failed' (empty generation) gets the
    normal JSON retries instead of failing the whole role rewrite."""
    bad = MagicMock(status_code=400, headers={},
                    text='{"error":{"code":"json_validate_failed","failed_generation":""}}')
    good = MagicMock(status_code=200, headers={})
    good.json.return_value = {"choices": [{"message": {"content": '{"value": "ok"}'}}], "usage": {}}

    class Out(BaseModel):
        value: str

    with patch("httpx.Client.post", side_effect=[bad, good]) as post:
        client = LLMClient(provider="groq", api_key="k", model="openai/gpt-oss-120b")
        assert client.generate_json([{"role": "user", "content": "x"}], Out).value == "ok"
    assert post.call_count == 2

@patch("app.llm.client.time.sleep")
@patch("httpx.Client.post")
def test_waits_are_reported_and_a_daily_limit_is_remembered(mock_post, mock_sleep):
    """P8.23: a back-off says so; a daily limit stops further calls with a plain message."""
    from app.llm import client as client_module
    client_module._DAILY_LIMIT_UNTIL.clear()
    limited = MagicMock(status_code=429, text="rate limited", headers={"retry-after": "3"})
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"choices": [{"message": {"content": "done"}}], "usage": {}}
    mock_post.side_effect = [limited, ok]
    client = LLMClient(provider="groq", api_key="test-key")
    waits = []
    client.on_wait = waits.append
    client.generate([{"role": "user", "content": "Hi"}])
    assert waits == ["The free AI service is busy; waiting 3 s and trying again"]

    daily = MagicMock(status_code=429, text="Limit 200000, Used 199990 tokens per day (TPD)",
                      headers={"retry-after": "5400"})
    mock_post.side_effect = [daily]
    client._available = True
    with pytest.raises(client_module.LLMDailyLimitError, match="Today's free AI limit is used up"):
        client.generate([{"role": "user", "content": "Hi"}])
    other = LLMClient(provider="groq", api_key="test-key")
    other._available = True
    assert other.is_available() is False and "about 1 h 30 min" in other.last_error
    client_module._DAILY_LIMIT_UNTIL.clear()
