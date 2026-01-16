"""
Report generator for defect analysis results.

Generates formatted reports from validation results.
"""

import logging
from datetime import date
from typing import List

from ..parser.structured_data import (
    ExtractedNotice,
    Defect,
    DefectReport,
    Severity
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates defect reports from validation results."""

    def generate_report(
        self,
        notice: ExtractedNotice,
        defects: List[Defect],
        ocr_confidence: float = None,
        ocr_warnings: List[str] = None
    ) -> DefectReport:
        """
        Generate a complete defect report.

        Args:
            notice: Extracted notice data
            defects: List of defects found
            ocr_confidence: Optional OCR confidence score
            ocr_warnings: Optional OCR quality warnings

        Returns:
            DefectReport object
        """
        logger.info(f"Generating report for {notice.notice_type}")

        # Determine if notice is valid
        critical_defects = [d for d in defects if d.severity == Severity.CRITICAL]
        is_valid = len(critical_defects) == 0

        # Generate summary
        summary = self._generate_summary(notice, defects, is_valid)

        # Create report
        report = DefectReport(
            notice_type=notice.notice_type,
            defects=defects,
            is_valid=is_valid,
            summary=summary,
            analysis_date=date.today(),
            ocr_confidence=ocr_confidence,
            ocr_warnings=ocr_warnings or []
        )

        logger.info(f"Report generated: {report.defect_count} defects found, valid={is_valid}")

        return report

    def _generate_summary(
        self,
        notice: ExtractedNotice,
        defects: List[Defect],
        is_valid: bool
    ) -> str:
        """
        Generate executive summary text.

        Args:
            notice: Extracted notice
            defects: List of defects
            is_valid: Whether notice is valid

        Returns:
            Summary text
        """
        if is_valid and len(defects) == 0:
            return (
                f"This {notice.notice_type} appears to be legally valid. "
                "No defects were found that would invalidate the notice."
            )

        # Count by severity
        critical = len([d for d in defects if d.severity == Severity.CRITICAL])
        major = len([d for d in defects if d.severity == Severity.MAJOR])
        minor = len([d for d in defects if d.severity == Severity.MINOR])
        warnings = len([d for d in defects if d.severity == Severity.WARNING])

        summary_parts = [f"This {notice.notice_type} has {len(defects)} potential issue(s):"]

        if critical > 0:
            summary_parts.append(
                f"{critical} CRITICAL defect(s) that likely invalidate the notice"
            )

        if major > 0:
            summary_parts.append(
                f"{major} MAJOR defect(s) that may invalidate the notice"
            )

        if minor > 0:
            summary_parts.append(
                f"{minor} MINOR technical issue(s)"
            )

        if warnings > 0:
            summary_parts.append(
                f"{warnings} warning(s) that require further review"
            )

        summary = ". ".join(summary_parts) + "."

        if not is_valid:
            summary += " The notice appears to be INVALID due to critical defects."

        return summary
