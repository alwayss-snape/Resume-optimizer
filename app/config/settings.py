import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    llm_provider: str = "ollama"
    llm_host: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 180
    max_context_tokens: int = 12000
    strict_factual_mode: bool = True

    # Groq (cloud, free tier) — optional alternative to local Ollama.
    # Set LLM_PROVIDER=groq to route generation through Groq instead of
    # Ollama. NOTE: this sends resume/JD text to Groq's servers, which is
    # a deliberate opt-out of this project's local-first default — see
    # ARCHITECTURE.md.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Semantic matching (local sentence-transformers embedding layer).
    # Only applied to requirements the deterministic EvidenceMatcher leaves MISSING.
    semantic_match_enabled: bool = True
    semantic_match_model: str = "all-MiniLM-L6-v2"
    semantic_match_threshold: float = 0.58

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
