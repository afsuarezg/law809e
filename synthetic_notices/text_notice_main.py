"""
CLI for generating text notices with defect annotations.

Generates raw text notices (.txt format) with defects listed, ready for LLM processing.

Usage:
    # Generate a single valid notice
    python -m synthetic_notices.text_notice_main --valid
    
    # Generate a notice with specific defects
    python -m synthetic_notices.text_notice_main --defect not_disjunctive --defect no_forfeiture
    
    # Generate a batch of notices
    python -m synthetic_notices.text_notice_main --count 100 --valid-ratio 0.3
"""

import argparse
import sys
from pathlib import Path
from typing import List

from .models import DefectType
from .text_notice_generator import TextNoticeGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate text notices with defect annotations for LLM processing."
    )

    # Generation mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--valid",
        action="store_true",
        help="Generate a single valid notice (no defects)"
    )
    mode_group.add_argument(
        "--defect",
        type=str,
        choices=[d.value for d in DefectType],
        action="append",
        help="Generate notice with specific defect(s). Can be repeated for multiple defects."
    )
    mode_group.add_argument(
        "--count",
        type=int,
        help="Generate a batch of notices"
    )

    # Batch options
    parser.add_argument(
        "--valid-ratio",
        type=float,
        default=0.3,
        help="Ratio of valid notices in batch (default: 0.3)"
    )
    parser.add_argument(
        "--max-defects",
        type=int,
        default=3,
        help="Max defects per invalid notice (default: 3)"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file or directory path (default: output/text_notices/notice.txt or notice_XXXX.txt)"
    )
    parser.add_argument(
        "--base-filename",
        type=str,
        default="notice",
        help="Base filename for batch generation (default: notice)"
    )

    # Other options
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--list-defects",
        action="store_true",
        help="List all available defect types"
    )

    args = parser.parse_args()

    # List defects and exit
    if args.list_defects:
        print("Available defect types:")
        print("-" * 50)
        for defect in DefectType:
            print(f"  {defect.value}")
        print("\nUse with: --defect <defect_type>")
        return

    # Initialize generator
    generator = TextNoticeGenerator(seed=args.seed)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Default: output/text_notices/
        base_dir = Path(__file__).parent / "output" / "text_notices"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        if args.valid:
            output_path = base_dir / "valid_notice.txt"
        elif args.defect:
            defect_str = "_".join(args.defect)
            output_path = base_dir / f"defective_{defect_str}.txt"
        elif args.count:
            output_path = base_dir  # Directory for batch
        else:
            output_path = base_dir / "notice.txt"

    try:
        if args.valid:
            print("Generating valid notice...")
            notice_text = generator.generate_notice(defects=[])
            generator.save_notice(notice_text, output_path)
            print(f"Saved valid notice to {output_path}")

        elif args.defect:
            defects = [DefectType(d) for d in args.defect]
            print(f"Generating notice with defects: {', '.join(args.defect)}...")
            notice_text = generator.generate_notice(defects=defects)
            generator.save_notice(notice_text, output_path)
            print(f"Saved defective notice to {output_path}")
            print(f"Defects included: {', '.join(args.defect)}")

        elif args.count:
            print(f"Generating {args.count} text notices...")
            notices = generator.generate_batch(
                count=args.count,
                valid_ratio=args.valid_ratio,
                max_defects_per_notice=args.max_defects
            )
            
            # Save batch
            generator.save_batch(notices, output_path, args.base_filename)
            
            valid_count = sum(1 for _, defects in notices if not defects)
            invalid_count = args.count - valid_count
            
            print(f"\nGenerated {args.count} notices:")
            print(f"  Valid: {valid_count}")
            print(f"  Invalid: {invalid_count}")
            print(f"Saved to {output_path}/")
            print(f"Files: {args.base_filename}_0001.txt through {args.base_filename}_{args.count:04d}.txt")
            
            # Print defect distribution
            defect_counts = {}
            for _, defects in notices:
                for defect in defects:
                    defect_counts[defect.value] = defect_counts.get(defect.value, 0) + 1
            
            if defect_counts:
                print("\nDefect distribution:")
                for defect, count in sorted(defect_counts.items(), key=lambda x: -x[1]):
                    print(f"  {defect}: {count}")

    except Exception as e:
        print(f"Error generating notices: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
