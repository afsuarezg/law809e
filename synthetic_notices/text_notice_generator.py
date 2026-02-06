"""
Text notice generator for creating raw text notices with defect annotations.

Generates text notices that can be later processed by LLMs. Notices are saved
as .txt files with defects listed at the end.
"""

import random
from datetime import date, timedelta
from typing import List, Optional
from pathlib import Path
from copy import deepcopy

from .models import NoticeData, DefectType
from .rule_based_generator import RuleBasedNoticeGenerator


class TextNoticeGenerator:
    """Generates text notices with defect annotations for LLM processing."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize generator with optional random seed."""
        self.rule_generator = RuleBasedNoticeGenerator(seed=seed)
        if seed is not None:
            random.seed(seed)

    def generate_notice(
        self,
        defects: Optional[List[DefectType]] = None,
        data: Optional[NoticeData] = None
    ) -> str:
        """
        Generate a text notice with defect annotations.
        
        Args:
            defects: List of defects to include (None or empty for valid notice)
            data: Optional NoticeData (generates random if not provided)
            
        Returns:
            Formatted text notice with defects listed at the end
        """
        if defects is None:
            defects = []
        
        # Generate notice using rule-based generator
        if defects:
            notice = self.rule_generator.generate_invalid_notice(defects, data)
        else:
            notice = self.rule_generator.generate_valid_notice(data)
        
        # Format with defect annotations
        return self._format_notice_with_defects(notice.text, defects, notice.is_valid)

    def generate_batch(
        self,
        count: int,
        valid_ratio: float = 0.3,
        max_defects_per_notice: int = 3
    ) -> List[tuple[str, List[DefectType]]]:
        """
        Generate a batch of text notices.
        
        Args:
            count: Total number of notices
            valid_ratio: Ratio of valid notices (0.0 to 1.0)
            max_defects_per_notice: Maximum defects per invalid notice
            
        Returns:
            List of tuples: (notice_text, defects_list)
        """
        notices = []
        num_valid = int(count * valid_ratio)
        num_invalid = count - num_valid
        
        all_defects = list(DefectType)
        
        # Generate valid notices
        for _ in range(num_valid):
            text = self.generate_notice(defects=[])
            notices.append((text, []))
        
        # Generate invalid notices
        for _ in range(num_invalid):
            num_defects = random.randint(1, max_defects_per_notice)
            selected_defects = random.sample(all_defects, min(num_defects, len(all_defects)))
            text = self.generate_notice(defects=selected_defects)
            notices.append((text, selected_defects))
        
        random.shuffle(notices)
        return notices

    def _format_notice_with_defects(
        self,
        notice_text: str,
        defects: List[DefectType],
        is_valid: bool
    ) -> str:
        """
        Format notice text with defect annotations at the end.
        
        Args:
            notice_text: The notice text
            defects: List of defects
            is_valid: Whether notice is valid
            
        Returns:
            Formatted text with notice and defect list
        """
        lines = []
        lines.append(notice_text)
        lines.append("")
        lines.append("=" * 80)
        lines.append("DEFECT ANNOTATIONS")
        lines.append("=" * 80)
        lines.append("")
        
        if is_valid and not defects:
            lines.append("VALID NOTICE - No defects found.")
        else:
            lines.append(f"DEFECTIVE NOTICE - {len(defects)} defect(s) found:")
            lines.append("")
            
            defect_descriptions = {
                DefectType.NOT_DISJUNCTIVE: "Notice uses 'pay AND quit' instead of 'pay OR quit'",
                DefectType.INSUFFICIENT_PERIOD: "Less than 3 business days given",
                DefectType.NO_AMOUNT_STATED: "No specific dollar amount of rent owed stated",
                DefectType.MISSING_PAYEE_INFO: "Missing landlord name, address, or phone number",
                DefectType.MISSING_PAYMENT_HOURS: "In-person payment allowed but no business hours specified",
                DefectType.FINANCIAL_INSTITUTION_INCOMPLETE: "Bank payment option missing address, account number, or 5-mile statement",
                DefectType.ELECTRONIC_PAYMENT_NOT_ESTABLISHED: "Electronic payment offered without 'previously established' language",
                DefectType.RENT_OVER_ONE_YEAR: "Demands rent from more than 12 months ago",
                DefectType.NO_FORFEITURE: "Missing forfeiture declaration"
            }
            
            for i, defect in enumerate(defects, 1):
                desc = defect_descriptions.get(defect, defect.value)
                lines.append(f"{i}. [{defect.value}] {desc}")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)

    def save_notice(
        self,
        notice_text: str,
        output_path: Path,
        notice_number: Optional[int] = None
    ):
        """
        Save a single notice to a text file.
        
        Args:
            notice_text: The formatted notice text
            output_path: Path to save the file
            notice_number: Optional notice number for filename
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(notice_text)

    def save_batch(
        self,
        notices: List[tuple[str, List[DefectType]]],
        output_dir: Path,
        base_filename: str = "notice"
    ):
        """
        Save a batch of notices to individual text files.
        
        Args:
            notices: List of (notice_text, defects) tuples
            output_dir: Directory to save notices
            base_filename: Base filename (will be appended with number)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, (notice_text, defects) in enumerate(notices, 1):
            filename = f"{base_filename}_{i:04d}.txt"
            file_path = output_dir / filename
            self.save_notice(notice_text, file_path, i)
