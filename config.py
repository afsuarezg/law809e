"""
Configuration module for eviction notice checker.
Loads settings from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
RULES_FILE = SRC_DIR / "rules" / "requirements.yaml"
STATUTE_REFERENCES = DATA_DIR / "statute_references.json"

# Create output directory if it doesn't exist
OUTPUT_DIR.mkdir(exist_ok=True)

# LLM API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")

# OCR Configuration
TESSERACT_PATH = os.getenv("TESSERACT_PATH")
if TESSERACT_PATH:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Application Settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validation
if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
    print("WARNING: No LLM API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env file")
