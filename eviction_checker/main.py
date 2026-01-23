"""
Main entry point for eviction notice checker.

Usage:
    python -m eviction_checker.main <file_path>
    python -m eviction_checker.main notice.pdf --output report.json
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from .ocr import OCRProcessor
from .extractor import EntityExtractor
from .validator import NoticeValidator
from .models import DefectReport, Severity
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_notice(file_path: str) -> DefectReport:
    """
    Analyze an eviction notice for legal defects.

    Args:
        file_path: Path to PDF or image file

    Returns:
        DefectReport with analysis results
    """
    # Step 1: Extract text from document
    logger.info(f"Processing document: {file_path}")
    ocr = OCRProcessor()
    raw_text = ocr.process(file_path)
    logger.info(f"Extracted {len(raw_text)} characters")

    # Step 2: Extract structured entities
    logger.info("Extracting entities...")
    extractor = EntityExtractor()
    notice = extractor.extract(raw_text)

    # Step 3: Validate for defects
    logger.info("Validating notice...")
    validator = NoticeValidator()
    defects = validator.validate(notice)

    # Step 4: Generate report
    critical = [d for d in defects if d.severity == Severity.CRITICAL]
    is_valid = len(critical) == 0

    if is_valid and len(defects) == 0:
        summary = "No defects found. The notice appears legally valid."
    else:
        summary = f"Found {len(defects)} issue(s): {len(critical)} critical."
        if not is_valid:
            summary += " The notice appears INVALID."

    return DefectReport(
        notice_type=notice.notice_type,
        defects=defects,
        is_valid=is_valid,
        summary=summary,
        analysis_date=date.today()
    )


def print_report(report: DefectReport) -> None:
    """Print report to console."""
    print("\n" + "=" * 60)
    print("EVICTION NOTICE ANALYSIS REPORT")
    print("=" * 60)

    print(f"\nNotice Type: {report.notice_type.value}")
    print(f"Status: {'VALID' if report.is_valid else 'INVALID'}")
    print(f"Defects Found: {report.defect_count}")

    print(f"\nSummary: {report.summary}")

    if report.defects:
        print("\n" + "-" * 60)
        print("DEFECTS DETECTED:")
        print("-" * 60)

        for i, defect in enumerate(report.defects, 1):
            severity_label = {
                Severity.CRITICAL: "[CRITICAL]",
                Severity.MAJOR: "[MAJOR]",
                Severity.MINOR: "[MINOR]",
                Severity.WARNING: "[WARNING]"
            }.get(defect.severity, "[?]")

            print(f"\n{i}. {severity_label} {defect.title}")
            print(f"   ID: {defect.defect_id}")
            print(f"   {defect.description}")
            print(f"   Law: {defect.statute_violated}")
            if defect.evidence:
                print(f"   Evidence: {defect.evidence}")
            print(f"   Action: {defect.tenant_action}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze California eviction notices for legal defects."
    )
    parser.add_argument(
        "file",
        help="Path to PDF or image file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Save JSON report to file"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress console output"
    )

    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        report = analyze_notice(args.file)

        if not args.quiet:
            print_report(report)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report.model_dump(), f, indent=2, default=str)
            logger.info(f"Report saved to {args.output}")

        # Exit with non-zero code if notice is invalid
        sys.exit(0 if report.is_valid else 1)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
