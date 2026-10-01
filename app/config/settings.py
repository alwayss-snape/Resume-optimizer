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
    # Connect to Groq over IPv4 only. httpx has no "happy eyeballs": on a
    # network where IPv6 is advertised but black-holed, it waits out every
    # IPv6 address (~75 s each) before trying IPv4, so each call took ~150 s
    # instead of <1 s. Groq's endpoint (Cloudflare) always has IPv4.
    groq_force_ipv4: bool = True

    # Anthropic (Claude) — LLM_PROVIDER=anthropic. Best rewrite quality;
    # uses schema-guaranteed structured outputs. Pay-as-you-go API key from
    # console.anthropic.com (a Claude Pro subscription does not include API
    # access). Sends resume/JD text to Anthropic — see ARCHITECTURE.md.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"

    # LLM-as-judge for evaluation (P4.3): a different model family from the
    # generator, so it doesn't grade its own writing. Groq free tier.
    judge_provider: str = "groq"
    judge_model: str = "qwen/qwen3.8-27b"

    # Facts the user confirmed in gap questions, reused across JDs (P3.2).
    # Personal data: gitignored, never sent anywhere.
    # Absolute under the repo, so it's always the gitignored folder no matter
    # where the web API or the CLI is started from.
    profile_path: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                     "data", "profile", "facts.json")

    # Web API (P5.1): idle visitors' sessions and temp files are dropped
    # after this long; uploads above this size are refused; each visitor IP
    # may start this many LLM-costing steps (analyse, parse, draft, tailor)
    # per hour.
    api_session_ttl_minutes: int = 60
    api_max_upload_mb: int = 5
    api_rate_limit_per_hour: int = 30

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
