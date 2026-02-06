"""
Synthetic Eviction Notice Generator

Generates valid and invalid California 3-Day Notices for testing and training.
Supports both rule-based (conditional logic) and LLM-based generation.
"""

from .models import NoticeData, GeneratedNotice, DefectType
from .rule_based_generator import RuleBasedNoticeGenerator
from .llm_generator import LLMNoticeGenerator

# Backward compatibility: alias RuleBasedNoticeGenerator as NoticeGenerator
NoticeGenerator = RuleBasedNoticeGenerator

__version__ = "2.0.0"
__all__ = [
    "NoticeGenerator",  # Backward compatibility alias
    "RuleBasedNoticeGenerator",
    "LLMNoticeGenerator",
    "NoticeData",
    "GeneratedNotice",
    "DefectType",
]
