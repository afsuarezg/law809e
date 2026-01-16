# California Eviction Notice Defect Checker

A tool to detect legal defects in eviction notices for California tenants. Designed for legal aid organizations to quickly identify issues that may invalidate an eviction notice.

## Features

- **OCR Processing**: Accepts PDF or image files of eviction notices
- **Hybrid Analysis**: Combines rule-based validation with LLM-powered analysis
- **Comprehensive Coverage**: Checks 3-day, 30-day, and 60-day notices
- **Detailed Reports**: Provides defect descriptions, statute citations, and tenant action recommendations
- **CLI Interface**: Easy-to-use command-line tool with rich formatting

## Installation

### Prerequisites

1. **Python 3.10+**
2. **Tesseract OCR**
   - macOS: `brew install tesseract`
   - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
   - Windows: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

3. **Poppler** (for PDF processing)
   - macOS: `brew install poppler`
   - Ubuntu/Debian: `sudo apt-get install poppler-utils`
   - Windows: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/)

### Setup

1. Clone the repository:
```bash
cd law408e
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download spaCy model:
```bash
python -m spacy download en_core_web_sm
```

5. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

Edit `.env` file with your settings:

```bash
# Required: At least one LLM API key
OPENAI_API_KEY=your_openai_key_here
# OR
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional: Custom model selection
OPENAI_MODEL=gpt-4-turbo-preview
ANTHROPIC_MODEL=claude-3-opus-20240229

# Optional: Tesseract path (if not in system PATH)
TESSERACT_PATH=/usr/local/bin/tesseract
```

## Usage

### Analyze a Notice

```bash
python cli.py analyze notice.pdf
```

### Save Report to JSON

```bash
python cli.py analyze notice.pdf --output report.json
```

### Show Verbose Output

```bash
python cli.py analyze notice.pdf --verbose
```

### Get Information About a Defect

```bash
python cli.py explain 3DP-001
```

## Project Structure

```
eviction-notice-checker/
├── cli.py                      # CLI entry point
├── config.py                   # Configuration
├── requirements.txt            # Dependencies
├── src/
│   ├── ocr/                    # OCR and document processing
│   ├── parser/                 # Entity extraction and classification
│   ├── validators/             # Rule-based defect detection
│   ├── rules/                  # Legal requirements database
│   ├── llm/                    # LLM integration
│   └── reporter/               # Report generation
├── tests/                      # Test suite
└── data/                       # Statute references
```

## Supported Notice Types

- ✅ 3-Day Notice to Pay Rent or Quit
- ✅ 3-Day Notice to Cure or Quit
- ✅ 3-Day Unconditional Notice to Quit
- ✅ 30-Day Notice to Terminate Tenancy
- ✅ 60-Day Notice to Terminate Tenancy
- ✅ 90-Day Notice (subsidized housing)

## Legal Disclaimer

This tool is designed to assist legal aid organizations in identifying potential defects in eviction notices. It is not a substitute for legal advice. Always consult with a qualified attorney for specific legal situations.

## Development Status

**Current Phase**: Phase 1 - MVP Development

- [x] Project structure setup
- [ ] Legal requirements documentation
- [ ] OCR pipeline implementation
- [ ] Data models and validators
- [ ] Testing suite
- [ ] Web interface (future)

## Contributing

This is a legal aid tool. Contributions should prioritize accuracy and cite appropriate California statutes and case law.

## License

[To be determined - likely open source for legal aid use]

## Support

For issues or questions about the tool, please open a GitHub issue.
