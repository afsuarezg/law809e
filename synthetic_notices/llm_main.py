"""
CLI for generating synthetic eviction notices using LLMs.

Usage:
    python -m synthetic_notices.llm_main --count 100 --valid-ratio 0.3 --output dataset.json
    python -m synthetic_notices.llm_main --defect not_disjunctive --output single.json --provider openai
    python -m synthetic_notices.llm_main --valid --output valid_notice.txt --provider anthropic --model claude-3-opus-20240229
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from .models import DefectType, GeneratedNotice
from .llm_generator import LLMNoticeGenerator


def save_notices(notices: List[GeneratedNotice], output_path: Path, format: str = "json"):
    """Save notices to file."""
    if format == "json":
        data = {
            "count": len(notices),
            "valid_count": sum(1 for n in notices if n.is_valid),
            "invalid_count": sum(1 for n in notices if not n.is_valid),
            "notices": [n.to_dict() for n in notices]
        }
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    elif format == "txt":
        with open(output_path, "w") as f:
            for i, notice in enumerate(notices):
                if i > 0:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write(f"=== NOTICE {i + 1} ===\n")
                    f.write("=" * 80 + "\n\n")

                f.write(notice.text)
                f.write("\n\n")
                f.write(f"--- METADATA ---\n")
                f.write(f"Valid: {notice.is_valid}\n")
                if notice.defects:
                    f.write(f"Defects: {', '.join(d.value for d in notice.defects)}\n")

    elif format == "jsonl":
        with open(output_path, "w") as f:
            for notice in notices:
                f.write(json.dumps(notice.to_dict()) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic California eviction notices using LLMs."
    )

    # Generation mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--valid",
        action="store_true",
        help="Generate a single valid notice"
    )
    mode_group.add_argument(
        "--defect",
        type=str,
        choices=[d.value for d in DefectType],
        action="append",
        help="Generate notice with specific defect(s). Can be repeated."
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

    # LLM options
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "anthropic", "google"],
        default="openai",
        help="LLM provider (default: openai)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name (default: provider-specific default)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key (if not provided, reads from environment)"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output file path"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "jsonl", "txt"],
        default="json",
        help="Output format (default: json)"
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
    try:
        generator = LLMNoticeGenerator(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            seed=args.seed
        )
    except Exception as e:
        print(f"Error initializing LLM generator: {e}", file=sys.stderr)
        sys.exit(1)

    notices = []

    # Generate based on mode
    try:
        if args.valid:
            print("Generating valid notice...")
            notices = [generator.generate_valid_notice()]
            print("Generated 1 valid notice")

        elif args.defect:
            defects = [DefectType(d) for d in args.defect]
            print(f"Generating notice with defects: {', '.join(args.defect)}...")
            notices = [generator.generate_invalid_notice(defects)]
            print(f"Generated 1 notice with defects: {', '.join(args.defect)}")

        elif args.count:
            print(f"Generating {args.count} notices...")
            notices = generator.generate_batch(
                count=args.count,
                valid_ratio=args.valid_ratio,
                max_defects_per_notice=args.max_defects
            )
            valid_count = sum(1 for n in notices if n.is_valid)
            print(f"Generated {args.count} notices ({valid_count} valid, {args.count - valid_count} invalid)")

    except Exception as e:
        print(f"Error generating notices: {e}", file=sys.stderr)
        sys.exit(1)

    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_notices(notices, output_path, args.format)
    print(f"Saved to {output_path}")

    # Print summary stats for batches
    if args.count and args.count > 1:
        print("\nDefect distribution:")
        defect_counts = {}
        for notice in notices:
            for defect in notice.defects:
                defect_counts[defect.value] = defect_counts.get(defect.value, 0) + 1

        for defect, count in sorted(defect_counts.items(), key=lambda x: -x[1]):
            print(f"  {defect}: {count}")


if __name__ == "__main__":
    main()
