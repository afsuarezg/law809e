"""
Script to validate synthetic eviction notices using the eviction checker.

This script:
1. Loads synthetic notices from JSON
2. Validates each notice using the eviction checker
3. Compares detected defects with expected defects
4. Generates a validation report

Usage:
    # Use LLM extraction (default) and print results
    python validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json
    
    # Use regex extraction (faster, no API needed)
    python validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json --regex
    
    # Print only, don't save report
    python validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json --print-only
    
    # Save detailed report
    python validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json --output validation_report.json
    
    # Using uv
    uv run python validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json --regex --print-only
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

# Import directly to avoid importing OCRProcessor (which requires pytesseract)
# Note: This still imports __init__.py, but we handle the error gracefully
try:
    from eviction_checker.extractor import EntityExtractor
    from eviction_checker.regex_extractor import RegexExtractor
    from eviction_checker.validator import NoticeValidator
    from eviction_checker.models import DefectReport, Severity
except ModuleNotFoundError as e:
    if 'pytesseract' in str(e) or 'ocr' in str(e).lower():
        print("Error: Missing dependencies. Please ensure you're using the virtual environment.", file=sys.stderr)
        print("\nTo fix:", file=sys.stderr)
        print("  1. Activate venv: .\\.venv\\Scripts\\Activate.ps1", file=sys.stderr)
        print("  2. Or use uv: uv run python validate_synthetic_notices.py ...", file=sys.stderr)
        print("  3. Or use venv Python: .\\.venv\\Scripts\\python.exe validate_synthetic_notices.py ...", file=sys.stderr)
        sys.exit(1)
    raise

from synthetic_notices.models import DefectType


# Map synthetic notice defect types to eviction checker defect IDs
DEFECT_MAPPING = {
    "not_disjunctive": "MVP-001",
    "insufficient_period": "MVP-002",
    "no_amount_stated": "MVP-003",
    "missing_payee_info": "MVP-004",
    "missing_payment_hours": "MVP-005",
    "financial_institution_incomplete": "MVP-006",
    "electronic_payment_not_established": "MVP-007",
    "rent_over_one_year": "MVP-008",
    "no_forfeiture": "MVP-009",
}


def validate_synthetic_notice(
    notice_text: str,
    expected_defects: List[str],
    use_regex: bool = False
) -> Dict[str, Any]:
    """
    Validate a single synthetic notice.
    
    Args:
        notice_text: The text of the eviction notice
        expected_defects: List of expected defect type strings
        use_regex: If True, use regex extraction instead of LLM
        
    Returns:
        Dictionary with validation results
    """
    try:
        # Extract entities from text (bypassing OCR since we have text)
        if use_regex:
            extractor = RegexExtractor()
        else:
            extractor = EntityExtractor()
        
        extracted_notice = extractor.extract(notice_text)
        
        # Validate for defects
        validator = NoticeValidator()
        detected_defects = validator.validate(extracted_notice)
        
        # Map detected defects to defect IDs
        detected_defect_ids = {d.defect_id for d in detected_defects}
        
        # Map expected defects to defect IDs
        expected_defect_ids = {
            DEFECT_MAPPING.get(d, d) for d in expected_defects
        }
        
        # Calculate metrics
        critical_defects = [d for d in detected_defects if d.severity == Severity.CRITICAL]
        is_valid = len(critical_defects) == 0
        
        # Compare expected vs detected
        true_positives = detected_defect_ids & expected_defect_ids
        false_positives = detected_defect_ids - expected_defect_ids
        false_negatives = expected_defect_ids - detected_defect_ids
        
        return {
            "notice_text": notice_text[:200] + "..." if len(notice_text) > 200 else notice_text,
            "expected_defects": expected_defects,
            "expected_defect_ids": list(expected_defect_ids),
            "detected_defects": [
                {
                    "defect_id": d.defect_id,
                    "title": d.title,
                    "severity": d.severity.value
                }
                for d in detected_defects
            ],
            "detected_defect_ids": list(detected_defect_ids),
            "true_positives": list(true_positives),
            "false_positives": list(false_positives),
            "false_negatives": list(false_negatives),
            "is_valid": is_valid,
            "expected_valid": len(expected_defects) == 0,
            "validation_correct": (is_valid == (len(expected_defects) == 0)) and 
                                 (len(false_positives) == 0) and 
                                 (len(false_negatives) == 0),
            "precision": len(true_positives) / len(detected_defect_ids) if detected_defect_ids else 1.0,
            "recall": len(true_positives) / len(expected_defect_ids) if expected_defect_ids else 1.0,
        }
    except Exception as e:
        return {
            "error": str(e),
            "notice_text": notice_text[:200] + "..." if len(notice_text) > 200 else notice_text,
            "expected_defects": expected_defects,
        }


def validate_batch(
    json_file_path: str,
    use_regex: bool = False,
    output_path: str = None
) -> Dict[str, Any]:
    """
    Validate a batch of synthetic notices.
    
    Args:
        json_file_path: Path to JSON file with synthetic notices
        use_regex: If True, use regex extraction instead of LLM
        output_path: Optional path to save validation report (None = print only)
        
    Returns:
        Dictionary with validation results for all notices
    """
    # Load synthetic notices
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    notices = data.get('notices', [])
    if not notices:
        raise ValueError("No notices found in JSON file")
    
    print(f"Validating {len(notices)} notices...")
    print(f"Using {'regex' if use_regex else 'LLM'} extraction")
    if not use_regex:
        print("Note: LLM extraction requires API access (OpenAI, Anthropic, or Ollama)\n")
    else:
        print()
    
    results = []
    for i, notice in enumerate(notices, 1):
        print(f"Processing notice {i}/{len(notices)}...", end='\r')
        
        notice_text = notice.get('text', '')
        expected_defects = notice.get('defects', [])
        
        result = validate_synthetic_notice(
            notice_text,
            expected_defects,
            use_regex=use_regex
        )
        result['notice_index'] = i
        results.append(result)
    
    print(f"\nCompleted validation of {len(notices)} notices\n")
    
    # Calculate aggregate statistics
    total = len(results)
    correct_validations = sum(1 for r in results if r.get('validation_correct', False))
    errors = sum(1 for r in results if 'error' in r)
    
    # Precision and recall metrics
    precisions = [r.get('precision', 0) for r in results if 'precision' in r]
    recalls = [r.get('recall', 0) for r in results if 'recall' in r]
    
    avg_precision = sum(precisions) / len(precisions) if precisions else 0
    avg_recall = sum(recalls) / len(recalls) if recalls else 0
    
    # Defect-level statistics
    defect_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0})
    
    for result in results:
        if 'error' in result:
            continue
            
        for defect_id in result.get('true_positives', []):
            defect_stats[defect_id]['tp'] += 1
        for defect_id in result.get('false_positives', []):
            defect_stats[defect_id]['fp'] += 1
        for defect_id in result.get('false_negatives', []):
            defect_stats[defect_id]['fn'] += 1
    
    report = {
        "summary": {
            "total_notices": total,
            "correct_validations": correct_validations,
            "incorrect_validations": total - correct_validations - errors,
            "errors": errors,
            "accuracy": correct_validations / total if total > 0 else 0,
            "average_precision": avg_precision,
            "average_recall": avg_recall,
            "f1_score": 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall) 
                       if (avg_precision + avg_recall) > 0 else 0,
        },
        "defect_statistics": {
            defect_id: {
                "true_positives": stats['tp'],
                "false_positives": stats['fp'],
                "false_negatives": stats['fn'],
                "precision": stats['tp'] / (stats['tp'] + stats['fp']) 
                            if (stats['tp'] + stats['fp']) > 0 else 0,
                "recall": stats['tp'] / (stats['tp'] + stats['fn']) 
                         if (stats['tp'] + stats['fn']) > 0 else 0,
            }
            for defect_id, stats in defect_stats.items()
        },
        "notices": results
    }
    
    # Save report if output path specified
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Validation report saved to {output_path}\n")
    
    return report


def print_summary(report: Dict[str, Any]):
    """Print a summary of validation results."""
    summary = report['summary']
    
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Notices: {summary['total_notices']}")
    print(f"Correct Validations: {summary['correct_validations']}")
    print(f"Incorrect Validations: {summary['incorrect_validations']}")
    print(f"Errors: {summary['errors']}")
    print(f"\nAccuracy: {summary['accuracy']:.2%}")
    print(f"Average Precision: {summary['average_precision']:.2%}")
    print(f"Average Recall: {summary['average_recall']:.2%}")
    print(f"F1 Score: {summary['f1_score']:.2%}")
    
    if report.get('defect_statistics'):
        print("\n" + "-" * 70)
        print("DEFECT-LEVEL STATISTICS")
        print("-" * 70)
        for defect_id, stats in sorted(report['defect_statistics'].items()):
            print(f"\n{defect_id}:")
            print(f"  True Positives: {stats['true_positives']}")
            print(f"  False Positives: {stats['false_positives']}")
            print(f"  False Negatives: {stats['false_negatives']}")
            print(f"  Precision: {stats['precision']:.2%}")
            print(f"  Recall: {stats['recall']:.2%}")
    
    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Validate synthetic eviction notices using the eviction checker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use LLM extraction (default) and print results
  python validate_synthetic_notices.py batch_10_notices.json
  
  # Use regex extraction (faster, no API)
  python validate_synthetic_notices.py batch_10_notices.json --regex
  
  # Print only, don't save report
  python validate_synthetic_notices.py batch_10_notices.json --print-only
  
  # Save report to file
  python validate_synthetic_notices.py batch_10_notices.json --output report.json
  
  # Using uv
  uv run python validate_synthetic_notices.py batch_10_notices.json --regex --print-only
        """
    )
    parser.add_argument(
        "json_file",
        help="Path to JSON file with synthetic notices"
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to save validation report JSON (optional, use --print-only to skip saving)"
    )
    parser.add_argument(
        "--regex",
        action="store_true",
        help="Use regex extraction instead of LLM (faster, no API needed). Default: uses LLM"
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print results only, don't save report to file"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress detailed output (only show errors)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.json_file).exists():
        print(f"Error: File not found: {args.json_file}", file=sys.stderr)
        sys.exit(1)
    
    # Determine output path
    if args.print_only:
        output_path = None  # Don't save
    else:
        output_path = args.output or "validation_report.json"
    
    try:
        report = validate_batch(
            args.json_file,
            use_regex=args.regex,
            output_path=output_path
        )
        
        if not args.quiet:
            print_summary(report)
            
            # Show some examples of incorrect validations
            incorrect = [
                r for r in report['notices'] 
                if not r.get('validation_correct', True) and 'error' not in r
            ]
            
            if incorrect:
                print("\n" + "-" * 70)
                print("SAMPLE INCORRECT VALIDATIONS")
                print("-" * 70)
                for result in incorrect[:5]:  # Show first 5
                    print(f"\nNotice {result['notice_index']}:")
                    print(f"  Expected defects: {result.get('expected_defects', [])}")
                    print(f"  Detected defects: {[d['defect_id'] for d in result.get('detected_defects', [])]}")
                    print(f"  False positives: {result.get('false_positives', [])}")
                    print(f"  False negatives: {result.get('false_negatives', [])}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
