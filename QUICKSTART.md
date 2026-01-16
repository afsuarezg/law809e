# Quick Start Guide

Get started with the California Eviction Notice Defect Checker in 5 minutes.

## Installation

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download spaCy model
python -m spacy download en_core_web_sm

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your API key(s)
```

## Configuration

Edit `.env` file:

```bash
# Add at least one of these:
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
```

## Basic Usage

### Analyze a Notice

```bash
# Test the CLI (currently shows placeholder output)
python cli.py analyze sample_notice.pdf
```

### In Python Code

```python
from src.ocr.processor import OCRProcessor
from src.parser.entity_extractor import EntityExtractor
from src.validators import get_validator
from src.reporter.generator import ReportGenerator

# 1. OCR the document
ocr = OCRProcessor(preprocess=True)
raw_text = ocr.process_document("notice.pdf")

# 2. Extract entities
extractor = EntityExtractor()
notice = extractor.extract(raw_text)

# 3. Validate
validator = get_validator(notice.notice_type)
if validator:
    defects = validator.validate(notice)
else:
    print(f"No validator available for {notice.notice_type}")
    defects = []

# 4. Generate report
reporter = ReportGenerator()
report = reporter.generate_report(notice, defects)

# 5. Display results
print(f"\nNotice Type: {report.notice_type}")
print(f"Valid: {report.is_valid}")
print(f"Defects Found: {report.defect_count}")

for defect in report.defects:
    print(f"\n{defect.defect_id}: {defect.title}")
    print(f"Severity: {defect.severity.value.upper()}")
    print(f"Description: {defect.description}")
```

## Testing

```bash
# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_validators.py::TestThreeDayPayValidator::test_valid_notice_no_defects -v

# Run with coverage
pytest --cov=src tests/
```

## Example: Testing Without Real Notices

If you don't have real eviction notices yet, you can test with synthetic data:

```python
from decimal import Decimal
from datetime import date
from src.parser.structured_data import (
    ExtractedNotice, NoticeType, Charge, PaymentTerms
)
from src.validators.three_day_pay import ThreeDayPayValidator

# Create a test notice with a defect (late fee included)
notice = ExtractedNotice(
    raw_text="Sample 3-day notice text...",
    notice_type=NoticeType.THREE_DAY_PAY,
    landlord_name="Test Landlord",
    tenant_names=["Test Tenant"],
    property_address="123 Test St, Los Angeles, CA 90001",
    total_amount_demanded=Decimal("1550.00"),
    charges=[
        Charge(description="Rent", amount=Decimal("1500.00"), is_rent=True),
        Charge(description="Late Fee", amount=Decimal("50.00"), is_rent=False)  # Defect!
    ],
    notice_date=date.today(),
    payment_terms=PaymentTerms(
        payee_name="Test Landlord",
        payment_address="456 Office St, Los Angeles, CA 90002",
        payment_hours="9 AM - 5 PM"
    ),
    is_signed=True
)

# Validate
validator = ThreeDayPayValidator()
defects = validator.validate(notice)

print(f"Found {len(defects)} defects:")
for defect in defects:
    print(f"- [{defect.severity.value.upper()}] {defect.title}")
```

Expected output:
```
Found 1 defects:
- [CRITICAL] Rent Only No Other Charges
```

## Project Status

Currently implemented:
- ✅ Project structure
- ✅ Legal requirements database (requirements.yaml)
- ✅ OCR pipeline (Tesseract + preprocessing)
- ✅ Data models (Pydantic)
- ✅ LLM client (OpenAI/Anthropic)
- ✅ Entity extraction
- ✅ 3-Day Pay or Quit validator (10+ rules)
- ✅ Report generation

To be implemented:
- ⏳ Additional validators (3-day cure, 30/60-day notices)
- ⏳ LLM edge case analyzer
- ⏳ Full CLI integration
- ⏳ Batch processing
- ⏳ Web interface

## Next Steps

1. **Add sample notices**: Place PDF or image files in `tests/fixtures/sample_notices/`
2. **Run validation**: Test the system on real notices
3. **Expand validators**: Implement validators for other notice types
4. **Integrate LLM analyzer**: Add edge case detection
5. **Build web interface**: Create user-friendly web app

## Troubleshooting

### Tesseract not found
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Then set path in .env
TESSERACT_PATH=/usr/local/bin/tesseract
```

### Poppler not found (for PDF processing)
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils
```

### API key not working
- Make sure `.env` file is in the project root
- Check that variable names match exactly (OPENAI_API_KEY or ANTHROPIC_API_KEY)
- Verify the key has proper permissions

## Resources

- [California CCP § 1161](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=1161)
- [California Civil Code § 1946.2 (AB 1482)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1946.2)
- [Tesseract OCR Documentation](https://github.com/tesseract-ocr/tesseract)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## Support

For issues or questions:
- Check the main README.md
- Review code comments and docstrings
- Create an issue on GitHub
