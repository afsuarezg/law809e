# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

California Eviction Notice Checker — detects "on-the-face" legal defects in California 3-Day Notices to Pay Rent or Quit (CCP § 1161(2)). Analyzes PDFs/images and reports which of 9 critical defects are present (MVP-001 through MVP-009).

## Environment Setup (Windows + OneDrive)

This repo lives in a OneDrive-synced folder on Windows, which causes hardlink errors with `uv` and occasional venv activation failures. Preferred workarounds:

```powershell
# Using uv (faster):
uv venv --link-mode=copy
uv pip install --link-mode=copy -r requirements.txt

# Or standard venv, bypassing activation entirely:
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m eviction_checker.main notice.pdf
```

If venv activation fails due to execution policy, run `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process` first, or just call `.venv\Scripts\python.exe` directly.

External system dependencies (not pip-installable): Tesseract OCR and Poppler must be installed separately.

## Commands

```bash
# Run tests
pytest eviction_checker/tests/

# Run a single test file
pytest eviction_checker/tests/test_validator.py -v

# Analyze a notice document (LLM-based extraction)
python -m eviction_checker.main notice.pdf

# Analyze using regex extraction (no API required)
python -m eviction_checker.main notice.pdf --regex

# Generate synthetic notices (LLM-based)
python -m synthetic_notices.llm_main --count 10 --valid-ratio 0.3 --provider anthropic

# Generate synthetic notices (rule-based, deterministic)
python -m synthetic_notices.rule_based_main --count 100 --output notices.json

# Batch-validate generated notices
python validate_synthetic_notices.py notices.json --llm-provider anthropic
```

LLM configuration goes in `.env` (copy from `.env.example`). Provider priority is Ollama > OpenAI > Anthropic unless overridden with `--provider` / `preferred_provider`.

## Architecture

### Analysis Pipeline

`PDF/Image → OCRProcessor → raw text → EntityExtractor (or RegexExtractor) → ExtractedNotice → NoticeValidator → DefectReport`

- **`eviction_checker/ocr.py`** — `OCRProcessor`: tries direct text extraction via `pypdf`; falls back to Tesseract OCR for scanned documents.
- **`eviction_checker/extractor.py`** — `EntityExtractor`: sends raw text to an LLM and parses a JSON response into an `ExtractedNotice`.
- **`eviction_checker/regex_extractor.py`** — regex alternative; no API calls, less flexible.
- **`eviction_checker/validator.py`** — `NoticeValidator`: pure rule-based logic that checks the `ExtractedNotice` against all 9 MVP defect rules. Implements California business-day counting with judicial holidays.
- **`eviction_checker/models.py`** — Pydantic v2 models: `ExtractedNotice`, `Defect`, `DefectReport`.
- **`eviction_checker/llm.py`** — `LLMClient`: thin wrapper supporting Ollama, OpenAI, and Anthropic. Temperature 0.0 for deterministic JSON extraction.
- **`eviction_checker/main.py`** — CLI entry point; orchestrates the pipeline and writes output to `reports/` and `extracted_texts/`.
- **`eviction_checker/__init__.py`** — exports `analyze_notice`, `OCRProcessor`, `EntityExtractor`, `NoticeValidator` for programmatic use.

### Synthetic Notice Generation (`synthetic_notices/`)

Three generators for creating test data:
- `llm_generator.py` / `llm_main.py` — uses an LLM to produce varied, realistic notices; supports injecting specific defects.
- `rule_based_generator.py` / `rule_based_main.py` — deterministic; programmatically constructs notices with or without specific defects.
- `text_notice_generator.py` / `text_notice_main.py` — human-readable text output with annotations.

`validate_synthetic_notices.py` (root level) batch-validates generated JSON notice files through the full analysis pipeline and produces `validation_report_*.json` files.

### Defect Rules

MVP-001..MVP-009 are validated automatically by `eviction_checker/validator.py`. MVP-010..MVP-012 are reviewer-only labels in `review_app.py` (no automated detection yet).

| ID | Description |
|----|-------------|
| MVP-001 | Improper phrasing — notice does not give the option to quit (must offer "pay OR quit") |
| MVP-002 | Lack of adequate time — fewer than 3 business days to comply, excluding Saturdays, Sundays, and California judicial holidays |
| MVP-003 | Does not state the amount of rent that is due |
| MVP-004 | Missing payee identity or contact info (name, phone, or address) |
| MVP-005 | In-person payment offered but business hours not stated |
| MVP-006 | Bank-deposit payment offered but financial-institution info incomplete (address, account number, or 5-mile statement) |
| MVP-007 | Electronic payment offered without prior tenant agreement ("previously established") |
| MVP-008 | Rent demanded is more than 1 year old |
| MVP-009 | No forfeiture declaration |
| MVP-010 | Missing compliance deadline / expiry date for the notice *(reviewer-only)* |
| MVP-011 | Font size below 12-point — notice is not legibly printed *(reviewer-only)* |
| MVP-012 | Payment method not clearly stated (e.g. doesn't specify check, money order, cash, etc.) *(reviewer-only)* |
