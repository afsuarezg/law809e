# California Eviction Notice Checker

A tool for detecting on-the-face legal defects in California 3-Day Notices to Pay Rent or Quit.

## Overview

This tool analyzes eviction notice documents (PDF or images) and identifies common legal defects that may invalidate the notice. It focuses on "on-the-face" defects—issues that can be detected directly from the document without requiring tenant interviews or additional context.

## Installation

### Prerequisites

- Python 3.9+
- Tesseract OCR
- Poppler (for PDF processing)

**macOS:**
```bash
brew install tesseract poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr poppler-utils
```

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Configure LLM

Choose one of the following options:

#### Option 1: Local LLM with Ollama (Recommended for Privacy)

Your data stays on your machine—no third-party API calls.

```bash
# Install Ollama
brew install ollama

# Pull a model (qwen2.5:7b recommended for JSON extraction)
ollama pull qwen2.5:7b

# Start the server (runs on port 11434)
ollama serve
```

Create `.env` file:
```bash
echo "OLLAMA_MODEL=qwen2.5:7b" > .env
```

**Recommended models for Apple Silicon:**

| Model | Size | RAM | Notes |
|-------|------|-----|-------|
| `qwen2.5:7b` | 4.7GB | 8GB | Best for JSON extraction |
| `mistral:7b` | 4.1GB | 8GB | Good general purpose |
| `llama3.1:8b` | 4.7GB | 8GB | Good balance |
| `qwen2.5:14b` | 9GB | 16GB | Best quality |

#### Option 2: Cloud APIs

If you prefer cloud APIs (note: data is sent to third parties):

```bash
cat > .env <<'EOF'
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Or Anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here
EOF
```

## Usage

### Command Line

```bash
# Analyze a notice and print results
python -m eviction_checker.main notice.pdf

# Use regex extraction instead of LLM (faster, no API needed)
python -m eviction_checker.main notice.pdf --regex

# Reports and extracted text are saved automatically using the input filename:
# - reports/<input_name>.json
# - extracted_texts/<input_name>.txt

# Override where the report is saved
python -m eviction_checker.main notice.pdf --output report.json

# Override output directories
python -m eviction_checker.main notice.pdf --report-dir out/reports --text-dir out/text

# Quiet mode (no console output)
python -m eviction_checker.main notice.pdf -q -o report.json
```

### Extraction Methods

| Method | Flag | Pros | Cons |
|--------|------|------|------|
| **LLM** | (default) | Handles varied formats, understands context | Requires Ollama or API, slower |
| **Regex** | `--regex` | Instant, free, no dependencies | Less flexible with unusual formats |

Use `--regex` for well-formatted notices or when LLM is unavailable.

### Python API

```python
from eviction_checker import analyze_notice

# Analyze a document
report = analyze_notice("notice.pdf")

# Check results
print(f"Valid: {report.is_valid}")
print(f"Defects found: {report.defect_count}")

for defect in report.defects:
    print(f"[{defect.severity.value}] {defect.title}")
    print(f"  {defect.description}")
    print(f"  Law: {defect.statute_violated}")
```

### Using Individual Components

```python
from eviction_checker import OCRProcessor, EntityExtractor, NoticeValidator

# Step 1: Extract text from document
ocr = OCRProcessor()
text = ocr.process("notice.pdf")

# Step 2: Parse structured data using LLM
extractor = EntityExtractor()
notice = extractor.extract(text)

# Step 3: Validate for defects
validator = NoticeValidator()
defects = validator.validate(notice)
```

## Pipeline

```
┌─────────────────┐
│  PDF / Image    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OCR Processor  │  Extract text (direct extraction or Tesseract OCR)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Raw Text     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Entity Extractor│  LLM parses: parties, amounts, dates, payment terms
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ExtractedNotice │  Structured data model
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Validator    │  Rule-based defect checking
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DefectReport   │  List of defects with severity, citations, actions
└─────────────────┘
```

## Defects Detected

MVP-010..MVP-012 are reviewer-only labels exposed in the Streamlit annotation tool (`review_app.py`) with no automated detection yet; all other IDs (MVP-001..MVP-009 and MVP-013) are validated automatically.

| ID | Defect | Severity | Description |
|----|--------|----------|-------------|
| MVP-001 | Improper Phrasing | Critical | Notice does not give the option to quit — must offer "pay OR quit", giving the tenant the choice |
| MVP-002 | Lack of Adequate Time | Critical | Fewer than 3 business days to comply, excluding Saturdays, Sundays, and California judicial holidays |
| MVP-003 | Amount Not Stated | Critical | Does not state the amount of rent that is due |
| MVP-004 | Missing Payee Info | Critical | Missing payee identity or contact info (name, telephone number, or address) |
| MVP-005 | Missing Payment Hours | Critical | In-person payment offered but business hours not stated |
| MVP-006 | Financial Institution | Critical | Bank-deposit payment offered but financial-institution info incomplete (address, account number, or 5-mile statement) |
| MVP-007 | Electronic Payment | Critical | Electronic payment offered without prior tenant agreement ("previously established") |
| MVP-008 | Rent Over 1 Year | Critical | Rent demanded is more than 1 year old |
| MVP-009 | No Forfeiture | Critical | Notice does not declare a forfeiture of the lease/tenancy |
| MVP-010 | Missing Expiry Date | Critical | Missing compliance deadline / expiry date for the notice *(reviewer-only)* |
| MVP-011 | Font Too Small | Critical | Font size below 12-point — notice is not legibly printed *(reviewer-only)* |
| MVP-012 | Vague Payment Method | Critical | Payment method not clearly stated (e.g. doesn't specify check, money order, cash, etc.) *(reviewer-only)* |
| MVP-013 | Missing Service Date | Critical | Notice does not state the date it was served on the tenant — the 3-day compliance clock cannot be computed |

## Legal References

Key statutes and case law used for validation:

- **CCP § 1161(2)** - Requirements for 3-day notice

## Project Structure

```
eviction_checker/
├── __init__.py        # Package exports
├── models.py          # Pydantic data models
├── ocr.py             # PDF/image text extraction
├── llm.py             # LLM client (Ollama/OpenAI/Anthropic)
├── extractor.py       # LLM-based entity extraction
├── regex_extractor.py # Regex-based entity extraction (no LLM needed)
├── validator.py       # Rule-based defect validation
├── main.py            # CLI entry point
└── tests/
    └── test_validator.py
```

## Running Tests

```bash
pytest eviction_checker/tests/
```

## Limitations

- Currently focused on "on-the-face" defects on 3-Day Pay or Quit notices only
- Requires LLM for entity extraction (local Ollama or cloud API)
- OCR accuracy depends on document quality
- This tool provides legal information, not legal advice

## License

MIT
