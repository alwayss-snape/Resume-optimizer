from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel

from app.llm.client import LLMClient
from app.llm.schemas import LLMConnectionError, LLMInvalidJSONError, LLMResponse

class SampleSchema(BaseModel):
    name: str
    age: int

def test_llm_client_initialization():
    client = LLMClient(host="http://localhost:11434", model="qwen3:4b")
    assert client.host == "http://localhost:11434"
    assert client.model == "qwen3:4b"

@patch("ollama.Client")
def test_llm_is_available_true(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.list.return_value = {"models": [{"name": "qwen3:4b"}]}
    mock_ollama.return_value = mock_inst

    client = LLMClient()
    assert client.is_available() is True

@patch("ollama.Client")
def test_llm_is_available_false(mock_ollama):
    mock_inst = MagicMock()
    mock_inst.list.side_effect = Exception("Connection refused")
    mock_ollama.return_value = mock_inst

    client = LLMClient()
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

    client = LLMClient()
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

    client = LLMClient()
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

    client = LLMClient()
    with pytest.raises(LLMInvalidJSONError):
        client.generate_json(
            messages=[{"role": "user", "content": "Test"}],
            schema_model=SampleSchema,
            max_retries=1,
        )
