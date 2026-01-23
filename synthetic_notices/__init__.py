"""
Synthetic Eviction Notice Generator

Generates valid and invalid California 3-Day Notices for testing and training.
"""

from .models import NoticeData, GeneratedNotice, DefectType
from .generator import NoticeGenerator

__version__ = "1.0.0"
__all__ = [
    "NoticeGenerator",
    "NoticeData",
    "GeneratedNotice",
    "DefectType",
]
