"""
json_to_pdfs.py — Convert a batch JSON notice file to one PDF per notice.

Usage:
    python utils/json_to_pdfs.py <input.json> [--output-dir DIR] [--prefix PREFIX]

The input JSON must have the shape:
    {"notices": [{"text": "...", "is_valid": true/false, "defects": [...], ...}, ...]}

Output filenames:
    <prefix>_001_valid.pdf, <prefix>_002_invalid.pdf, ...

Dependencies:
    pip install fpdf2
    (or: uv pip install --link-mode=copy fpdf2)
"""

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate one PDF per notice from a batch JSON file."
    )
    p.add_argument("input_json", help="Path to the batch JSON file")
    p.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write PDFs into (default: <input_stem>_pdfs/ next to the JSON)",
    )
    p.add_argument(
        "--prefix",
        default="notice",
        help="Filename prefix for generated PDFs (default: 'notice')",
    )
    return p


def sanitize_text(line: str) -> str:
    """Replace characters that latin-1 (fpdf2 core font encoding) cannot represent."""
    replacements = {
        "\u2013": "-",   # en dash
        "\u2014": "--",  # em dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2022": "*",   # bullet
        "\u00a0": " ",   # non-breaking space
    }
    for char, replacement in replacements.items():
        line = line.replace(char, replacement)
    # Replace any remaining non-latin-1 chars with '?'
    return line.encode("latin-1", errors="replace").decode("latin-1")


def notice_to_pdf(text: str, output_path: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    # Set margins before add_page so they take effect
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Courier", size=10)

    line_height = 5  # mm per line
    # epw = effective page width (page width minus left and right margins)
    page_width = pdf.epw

    # multi_cell handles \n splits internally; single call avoids x-position drift
    safe_text = sanitize_text(text)
    pdf.multi_cell(page_width, line_height, safe_text)

    pdf.output(str(output_path))


def main() -> None:
    args = build_parser().parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with input_path.open(encoding="utf-8") as f:
        data = json.load(f)

    notices = data.get("notices")
    if not isinstance(notices, list):
        print("Error: JSON must contain a top-level 'notices' array.", file=sys.stderr)
        sys.exit(1)

    # Resolve output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent / f"{input_path.stem}_pdfs"

    output_dir.mkdir(parents=True, exist_ok=True)

    prefix = args.prefix
    generated = 0
    errors = 0

    for i, notice in enumerate(notices, start=1):
        text = notice.get("text", "")
        is_valid = notice.get("is_valid", True)
        validity_label = "valid" if is_valid else "invalid"
        filename = f"{prefix}_{i:03d}_{validity_label}.pdf"
        output_path = output_dir / filename

        try:
            notice_to_pdf(text, output_path)
            generated += 1
        except Exception as exc:
            print(f"  [!] Notice {i}: failed to generate PDF — {exc}", file=sys.stderr)
            errors += 1

    print(
        f"Done. {generated} PDF(s) written to '{output_dir}'"
        + (f", {errors} error(s)." if errors else ".")
    )


if __name__ == "__main__":
    main()
