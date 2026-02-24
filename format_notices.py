#!/usr/bin/env python3
"""
Format JSON notice files with triple-quoted strings to preserve whitespace.
"""

import json
import sys
from pathlib import Path


def format_notice_json(input_path: str, output_path: str = None):
    """
    Format a JSON notice file with triple-quoted strings for text fields.
    
    Args:
        input_path: Path to input JSON file
        output_path: Path to output file (default: input_path with '_formatted' suffix)
    """
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    if output_path is None:
        output_file = input_file.parent / f"{input_file.stem}_formatted{input_file.suffix}"
    else:
        output_file = Path(output_path)
    
    # Load JSON data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Format output
    lines = ['{']
    lines.append('  "notices": [')
    
    for i, notice in enumerate(data['notices']):
        if i > 0:
            lines.append(',')
        
        lines.append('    {')
        lines.append('      "text": """')
        
        # Split text by newlines and indent each line
        text_lines = notice['text'].split('\n')
        for line in text_lines:
            lines.append(f'        {line}')
        
        lines.append('      """,')
        lines.append(f'      "defects": {json.dumps(notice["defects"])},')
        lines.append(f'      "is_valid": {str(notice["is_valid"]).lower()},')
        lines.append(f'      "metadata": {json.dumps(notice["metadata"])}')
        lines.append('    }')
    
    lines.append('  ],')
    lines.append(f'  "count": {data["count"]},')
    lines.append(f'  "valid_count": {data["valid_count"]},')
    lines.append(f'  "invalid_count": {data["invalid_count"]}')
    lines.append('}')
    
    # Write formatted output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Formatted file saved to: {output_file}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python format_notices.py <input_json> [output_json]")
        print("Example: python format_notices.py batch_10_notices_feb7.json")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    format_notice_json(input_path, output_path)
