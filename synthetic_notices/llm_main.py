"""
CLI for generating synthetic eviction notices using LLMs.

Usage:
    # Generate batch (saves to output/LLM_generated/batch_100_notices.json by default)
    python -m synthetic_notices.llm_main --count 100 --valid-ratio 0.3
    
    # Generate with specific defects (saves to output/LLM_generated/defective_not_disjunctive.json by default)
    python -m synthetic_notices.llm_main --defect not_disjunctive --provider openai
    
    # Generate valid notice (saves to output/LLM_generated/valid_notice.txt by default)
    python -m synthetic_notices.llm_main --valid --format txt --provider anthropic
    
    # Specify custom output path
    python -m synthetic_notices.llm_main --count 50 -o custom/path/notices.json
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


class IncrementalSaver:
    """Saves notices incrementally as they're generated."""
    
    def __init__(self, output_path: Path, format: str = "json"):
        self.output_path = output_path
        self.format = format
        self.count = 0
        self.valid_count = 0
        self.invalid_count = 0
        self.defect_counts = {}  # Track defect distribution
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize file based on format
        if format == "jsonl":
            # JSONL: append mode, one notice per line
            self.file = open(output_path, "w", encoding="utf-8")
        elif format == "txt":
            # TXT: append mode
            self.file = open(output_path, "w", encoding="utf-8")
        elif format == "json":
            # JSON: write incrementally using a list structure
            self.file = open(output_path, "w", encoding="utf-8")
            self.file.write('{\n  "notices": [\n')
            self.first_notice = True
    
    def save_notice(self, notice: GeneratedNotice):
        """Save a single notice incrementally."""
        self.count += 1
        if notice.is_valid:
            self.valid_count += 1
        else:
            self.invalid_count += 1
        
        # Track defect distribution
        for defect in notice.defects:
            self.defect_counts[defect.value] = self.defect_counts.get(defect.value, 0) + 1
        
        if self.format == "jsonl":
            self.file.write(json.dumps(notice.to_dict()) + "\n")
            self.file.flush()  # Ensure it's written to disk
        
        elif self.format == "txt":
            if self.count > 1:
                self.file.write("\n" + "=" * 80 + "\n")
                self.file.write(f"=== NOTICE {self.count} ===\n")
                self.file.write("=" * 80 + "\n\n")
            
            self.file.write(notice.text)
            self.file.write("\n\n")
            self.file.write(f"--- METADATA ---\n")
            self.file.write(f"Valid: {notice.is_valid}\n")
            if notice.defects:
                self.file.write(f"Defects: {', '.join(d.value for d in notice.defects)}\n")
            self.file.flush()
        
        elif self.format == "json":
            if not self.first_notice:
                self.file.write(",\n")
            self.file.write("    " + json.dumps(notice.to_dict(), indent=2).replace("\n", "\n    "))
            self.first_notice = False
            self.file.flush()
    
    def finalize(self):
        """Close the file and finalize the format."""
        if self.format == "json":
            # Close the JSON structure
            self.file.write('\n  ],\n')
            self.file.write(f'  "count": {self.count},\n')
            self.file.write(f'  "valid_count": {self.valid_count},\n')
            self.file.write(f'  "invalid_count": {self.invalid_count}\n')
            self.file.write('}\n')
        
        self.file.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finalize()


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
        default=None,
        help="Output file path (default: output/LLM_generated/<auto-generated-name>.<format>)"
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
            # Determine output path first (needed for incremental saving)
            if args.output:
                output_path = Path(args.output)
            else:
                # Generate default path in output/LLM_generated/
                base_dir = Path(__file__).parent / "output" / "LLM_generated"
                base_dir.mkdir(parents=True, exist_ok=True)
                filename = f"batch_{args.count}_notices.{args.format}"
                output_path = base_dir / filename
            
            # Use incremental saving for batch generation
            print(f"Generating {args.count} notices (saving incrementally to {output_path})...")
            
            with IncrementalSaver(output_path, args.format) as saver:
                def progress_callback(notice, current, total):
                    saver.save_notice(notice)
                    # Print progress every 10 notices or at milestones
                    if current % 10 == 0 or current == total or current <= 5:
                        print(f"  Progress: {current}/{total} notices generated and saved...", end='\r')
                
                notices = generator.generate_batch(
                    count=args.count,
                    valid_ratio=args.valid_ratio,
                    max_defects_per_notice=args.max_defects,
                    progress_callback=progress_callback
                )
            
            print(f"\nGenerated {args.count} notices ({saver.valid_count} valid, {saver.invalid_count} invalid)")
            print(f"Saved to {output_path}")
            
            # Print defect distribution
            if saver.defect_counts:
                print("\nDefect distribution:")
                for defect, count in sorted(saver.defect_counts.items(), key=lambda x: -x[1]):
                    print(f"  {defect}: {count}")

    except Exception as e:
        print(f"\nError generating notices: {e}", file=sys.stderr)
        if 'output_path' in locals():
            print(f"Note: Partial results may have been saved to {output_path}")
        sys.exit(1)

    # For single notice generation, save normally
    if args.valid or args.defect:
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Generate default path in output/LLM_generated/
            base_dir = Path(__file__).parent / "output" / "LLM_generated"
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename based on mode
            if args.valid:
                filename = f"valid_notice.{args.format}"
            elif args.defect:
                defect_str = "_".join(args.defect)
                filename = f"defective_{defect_str}.{args.format}"
            else:
                filename = f"notices.{args.format}"
            
            output_path = base_dir / filename

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        save_notices(notices, output_path, args.format)
        print(f"Saved to {output_path}")



if __name__ == "__main__":
    main()
