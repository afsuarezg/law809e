"""
Eviction Notice Checker - California 3-Day Notice Validator

A tool for detecting on-the-face defects in California eviction notices.
"""

from .models import (
    NoticeType,
    Severity,
    Charge,
    PaymentTerms,
    ExtractedNotice,
    Defect,
    DefectReport
)
from .ocr import OCRProcessor
from .extractor import EntityExtractor
from .regex_extractor import RegexExtractor
from .validator import NoticeValidator
from .main import analyze_notice

__version__ = "1.0.0"
__all__ = [
    "analyze_notice",
    "OCRProcessor",
    "EntityExtractor",
    "RegexExtractor",
    "NoticeValidator",
    "NoticeType",
    "Severity",
    "Charge",
    "PaymentTerms",
    "ExtractedNotice",
    "Defect",
    "DefectReport",
]
