# Synthetic Eviction Notice Generator

Generates synthetic California 3-Day Pay or Quit notices for testing and training purposes. Notices can be valid or contain specific legal defects.

## Installation

No additional dependencies required beyond Python 3.9+.

## Usage

### Command Line

```bash
# Generate a single valid notice
python -m synthetic_notices.main --valid -o output/valid.txt -f txt

# Generate a notice with a specific defect
python -m synthetic_notices.main --defect not_disjunctive -o output/defective.json

# Generate a notice with multiple defects
python -m synthetic_notices.main --defect not_disjunctive --defect no_forfeiture -o output/multi.json

# Generate a batch of 100 notices (30% valid, 70% invalid)
python -m synthetic_notices.main --count 100 --valid-ratio 0.3 -o output/dataset.json

# Generate with reproducible random seed
python -m synthetic_notices.main --count 50 --seed 42 -o output/reproducible.json

# List all available defect types
python -m synthetic_notices.main --list-defects
```

### Python API

```python
from synthetic_notices import NoticeGenerator, DefectType

generator = NoticeGenerator(seed=42)

# Generate a valid notice
valid = generator.generate_valid_notice()
print(valid.text)
print(f"Valid: {valid.is_valid}")

# Generate a notice with specific defects
invalid = generator.generate_invalid_notice([
    DefectType.NOT_DISJUNCTIVE,
    DefectType.NO_FORFEITURE
])
print(invalid.text)
print(f"Defects: {invalid.defects}")

# Generate a random invalid notice
random_invalid = generator.generate_random_invalid_notice(num_defects=2)

# Generate a batch
batch = generator.generate_batch(
    count=100,
    valid_ratio=0.3,
    max_defects_per_notice=3
)
```

## Defect Types

| Defect | Description |
|--------|-------------|
| `not_disjunctive` | Notice says "pay AND quit" instead of "pay OR quit" |
| `insufficient_period` | Less than 3 business days given |
| `no_amount_stated` | No specific dollar amount of rent owed |
| `missing_payee_info` | Missing name, phone, or address of payee |
| `missing_payment_hours` | In-person payment allowed but no hours stated |
| `financial_institution_incomplete` | Bank payment missing address, account, or 5-mile statement |
| `electronic_payment_not_established` | Electronic payment offered without "previously established" |
| `rent_over_one_year` | Demands rent from more than 12 months ago |
| `no_forfeiture` | No forfeiture declaration |

## Output Formats

### JSON (default)
```json
{
  "count": 100,
  "valid_count": 30,
  "invalid_count": 70,
  "notices": [
    {
      "text": "THREE-DAY NOTICE...",
      "defects": ["not_disjunctive"],
      "is_valid": false,
      "metadata": {
        "landlord": "ABC Property Management",
        "tenant": ["John Doe"],
        "amount": 1500.0,
        ...
      }
    }
  ]
}
```

### JSONL (one JSON object per line)
```jsonl
{"text": "...", "defects": [], "is_valid": true, "metadata": {...}}
{"text": "...", "defects": ["not_disjunctive"], "is_valid": false, "metadata": {...}}
```

### TXT (human-readable)
```
======================================================================
THREE-DAY NOTICE TO PAY RENT OR QUIT
======================================================================

TO: John Doe
...

--- METADATA ---
Valid: False
Defects: not_disjunctive, no_forfeiture
```

## Project Structure

```
synthetic_notices/
├── __init__.py
├── main.py           # CLI entry point
├── models.py         # Data models
├── generator.py      # Notice generator
├── templates/
│   └── base.py       # Notice templates
└── output/           # Default output directory
```

## Integration with Eviction Checker

Use generated notices to test the eviction checker:

```bash
# Generate test dataset
python -m synthetic_notices.main --count 50 --seed 42 -o test_notices.json

# Test each notice with the checker
python -c "
import json
from eviction_checker import analyze_notice

with open('test_notices.json') as f:
    data = json.load(f)

for notice in data['notices']:
    # Write notice to temp file and analyze
    # Compare detected defects vs expected defects
    pass
"
```
