# Build & Setup Guide — Local Resume Tailor

## Prerequisites

- macOS (M1/M2/M3 or Intel) or Linux
- Python >= 3.10 (3.13 tested)
- Ollama running locally (`ollama serve`)
- (Optional for PDF conversion) LibreOffice (`brew install --cask libreoffice`)

## Installation

1. Create a Python virtual environment inside `resume-tailor/`:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Ensure Ollama is running and download the default model:
   ```bash
   ollama pull qwen3:4b
   ```

## Optional: Using Groq Instead of a Local Model

If your local model isn't strong enough, you can route generation through
[Groq](https://console.groq.com) — a free, fast cloud inference API — instead
of Ollama. This is an opt-in trade-off: resume/JD text is sent to Groq's
servers, which departs from this project's local-first default (see
ARCHITECTURE.md).

1. Create a free API key at https://console.groq.com/keys (no card required).
2. Copy `.env.example` to `.env` if you haven't already, then set:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=your-key-here
   GROQ_MODEL=openai/gpt-oss-120b
   ```
3. Run the app as usual — `LLMClient` picks up the Groq provider automatically.
   Switch back to `LLM_PROVIDER=ollama` at any time to go fully local again.

The free tier is rate-limited per model (see Groq's docs for current limits),
which is generally fine for tailoring one resume at a time but can be hit
during heavy batch testing.

## Running Tests

```bash
pytest -q
```

## Running the Application

### CLI Mode

```bash
python -m app.cli tailor \
  --resume ./tests/fixtures/resumes/sample.docx \
  --jd ./tests/fixtures/jds/sample.txt \
  --output ./data/output/
```

### Streamlit UI Mode

```bash
streamlit run app/ui.py
```
