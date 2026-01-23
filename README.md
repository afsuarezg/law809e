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

### Configure API Keys

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and add at least one LLM API key:
```
OPENAI_API_KEY=sk-your-key-here
# or
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## Usage

### Command Line

```bash
# Analyze a notice and print results
python -m eviction_checker.main notice.pdf

# Save report to JSON file
python -m eviction_checker.main notice.pdf --output report.json

# Quiet mode (no console output)
python -m eviction_checker.main notice.pdf -q -o report.json
```

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

| ID | Defect | Severity | Description |
|----|--------|----------|-------------|
| MVP-001 | Not Disjunctive | Critical | Notice must say "pay OR quit", giving tenant the choice |
| MVP-002 | Insufficient Period | Critical | Must give 3 full business days (excluding weekends/holidays) |
| MVP-003 | No Amount Stated | Critical | Must state exact dollar amount of rent owed |
| MVP-004 | Missing Payee Info | Critical | Must include name, telephone number, and address for payment |
| MVP-005 | Missing Payment Hours | Critical | If in-person payment allowed, must state usual days and hours |
| MVP-006 | Financial Institution | Critical | If bank payment allowed, must state name, street address, account number, and be within 5 miles |
| MVP-007 | Electronic Payment | Critical | If electronic funds transfer allowed, must state it was previously established |
| MVP-008 | Rent Over 1 Year | Critical | Cannot demand rent that came due more than one year ago |
| MVP-009 | No Forfeiture | Critical | Notice must declare a forfeiture of the lease/tenancy |

## Legal References

Key statutes and case law used for validation:

- **CCP § 1161(2)** - Requirements for 3-day notice

## Project Structure

```
eviction_checker/
├── __init__.py      # Package exports
├── models.py        # Pydantic data models
├── ocr.py           # PDF/image text extraction
├── llm.py           # OpenAI/Anthropic client
├── extractor.py     # LLM-based entity extraction
├── validator.py     # Rule-based defect validation
├── main.py          # CLI entry point
└── tests/
    └── test_validator.py
```

## Running Tests

```bash
pytest eviction_checker/tests/
```

## Limitations

- Currently focused on 3-Day Pay or Quit notices only
- Requires LLM API access for entity extraction
- OCR accuracy depends on document quality
- This tool provides legal information, not legal advice

## License

MIT
