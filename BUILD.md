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
