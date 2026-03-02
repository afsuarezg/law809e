"""
Batch evaluation tool for synthetic California 3-Day Notices.

Loads a batch JSON file (produced by synthetic_notices generators), runs each
notice through the extraction + validation pipeline, and reports per-defect
precision/recall/F1 plus overall exact-match accuracy.

Usage:
    python evaluate_notices.py <batch.json>
        [--mode llm|regex]                  default: llm
        [--provider anthropic|openai|ollama] default: anthropic
        [--output report.json]
        [--debug]
"""

import argparse
import json
import logging
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Ground-truth defect name → MVP-XXX mapping
# ---------------------------------------------------------------------------
DEFECT_MAPPING: Dict[str, str] = {
    "not_disjunctive":                    "MVP-001",
    "insufficient_period":                "MVP-002",
    "no_amount_stated":                   "MVP-003",
    "missing_payee_info":                 "MVP-004",
    "missing_payment_hours":              "MVP-005",
    "financial_institution_incomplete":   "MVP-006",
    "electronic_payment_not_established": "MVP-007",
    "rent_over_one_year":                 "MVP-008",
    "no_forfeiture":                      "MVP-009",
}

ALL_DEFECT_IDS = list(DEFECT_MAPPING.values())


# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------
class _Encoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# ---------------------------------------------------------------------------
# Per-defect metrics accumulator
# ---------------------------------------------------------------------------
class _DefectMetrics:
    def __init__(self) -> None:
        self.tp = 0
        self.fp = 0
        self.fn = 0

    def precision(self) -> Optional[float]:
        denom = self.tp + self.fp
        return self.tp / denom if denom else None

    def recall(self) -> Optional[float]:
        denom = self.tp + self.fn
        return self.tp / denom if denom else None

    def f1(self) -> Optional[float]:
        p = self.precision()
        r = self.recall()
        if p is None or r is None:
            return None
        denom = p + r
        return 2 * p * r / denom if denom else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision": self.precision(),
            "recall": self.recall(),
            "f1": self.f1(),
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
        }


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------
def _extract_llm(text: str, provider: str):
    """Extract fields via LLM (imports eviction_checker lazily)."""
    from eviction_checker.extractor import EntityExtractor
    extractor = EntityExtractor(provider=provider)
    return extractor.extract(text)


def _extract_regex(text: str):
    """Extract fields via regex (no API calls)."""
    from eviction_checker.regex_extractor import RegexExtractor
    extractor = RegexExtractor()
    return extractor.extract(text)


def _validate(extracted_notice):
    """Run the validator and return a set of MVP-XXX defect IDs."""
    from eviction_checker.validator import NoticeValidator
    defects = NoticeValidator().validate(extracted_notice)
    return {d.defect_id for d in defects}


def _extracted_to_dict(notice) -> Dict[str, Any]:
    """Serialise an ExtractedNotice to a plain dict for the debug output."""
    try:
        return notice.model_dump()
    except AttributeError:
        return notice.dict()


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------
def evaluate(
    batch_path: Path,
    mode: str,
    provider: str,
    debug: bool,
) -> Dict[str, Any]:
    with open(batch_path, encoding="utf-8") as fh:
        batch = json.load(fh)

    notices_raw: List[Dict[str, Any]] = batch if isinstance(batch, list) else batch["notices"]

    metrics: Dict[str, _DefectMetrics] = {mid: _DefectMetrics() for mid in ALL_DEFECT_IDS}
    exact_matches = 0
    errors = 0
    notice_results: List[Dict[str, Any]] = []

    for idx, item in enumerate(notices_raw):
        text: str = item.get("text", "")
        raw_defects: List[str] = item.get("defects", [])
        expected_ids: Set[str] = {
            DEFECT_MAPPING[d] for d in raw_defects if d in DEFECT_MAPPING
        }

        # Log unknown defect names so the caller can update the mapping
        unknown = [d for d in raw_defects if d not in DEFECT_MAPPING]
        if unknown:
            logging.warning(f"Notice #{idx + 1}: unknown defect name(s) {unknown} — skipped in mapping")

        extracted_dict: Optional[Dict[str, Any]] = None
        detected_ids: Set[str] = set()
        error_msg: Optional[str] = None

        try:
            if mode == "llm":
                extracted = _extract_llm(text, provider)
            else:
                extracted = _extract_regex(text)

            if debug:
                extracted_dict = _extracted_to_dict(extracted)

            detected_ids = _validate(extracted)

        except Exception as exc:
            error_msg = str(exc)
            errors += 1
            logging.error(f"Notice #{idx + 1} failed: {exc}")

        # Compute TP/FP/FN
        tp_ids = detected_ids & expected_ids
        fp_ids = detected_ids - expected_ids
        fn_ids = expected_ids - detected_ids

        for mid in ALL_DEFECT_IDS:
            if mid in tp_ids:
                metrics[mid].tp += 1
            elif mid in fp_ids:
                metrics[mid].fp += 1
            elif mid in fn_ids:
                metrics[mid].fn += 1

        if detected_ids == expected_ids:
            exact_matches += 1

        result: Dict[str, Any] = {
            "index": idx + 1,
            "detected": sorted(detected_ids),
            "expected": sorted(expected_ids),
            "tp": sorted(tp_ids),
            "fp": sorted(fp_ids),
            "fn": sorted(fn_ids),
            "exact_match": detected_ids == expected_ids,
        }
        if error_msg:
            result["error"] = error_msg
        if debug and extracted_dict is not None:
            result["extracted"] = extracted_dict

        notice_results.append(result)
        logging.info(
            f"Notice #{idx + 1}: expected={sorted(expected_ids)} "
            f"detected={sorted(detected_ids)} "
            f"exact={'✓' if detected_ids == expected_ids else '✗'}"
        )

    total = len(notices_raw)
    report: Dict[str, Any] = {
        "config": {
            "mode": mode,
            "provider": provider if mode == "llm" else None,
            "file": batch_path.name,
            "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "summary": {
            "total": total,
            "exact_match": exact_matches,
            "exact_match_pct": round(exact_matches / total * 100, 1) if total else 0.0,
            "errors": errors,
        },
        "per_defect": {mid: metrics[mid].to_dict() for mid in ALL_DEFECT_IDS},
        "notices": notice_results,
    }
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic eviction notice batch against ground truth."
    )
    parser.add_argument("batch", type=Path, help="Path to batch JSON file")
    parser.add_argument(
        "--mode",
        choices=["llm", "regex"],
        default="llm",
        help="Extraction mode (default: llm)",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "ollama"],
        default="anthropic",
        help="LLM provider when --mode=llm (default: anthropic)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write JSON report (default: stdout)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include extracted fields for each notice in the report",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose or args.debug else logging.WARNING,
        format="%(levelname)s  %(message)s",
    )

    if not args.batch.exists():
        print(f"Error: file not found: {args.batch}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Evaluating {args.batch.name}  mode={args.mode}"
        + (f"  provider={args.provider}" if args.mode == "llm" else ""),
        file=sys.stderr,
    )

    report = evaluate(args.batch, args.mode, args.provider, args.debug)

    output_json = json.dumps(report, indent=2, cls=_Encoder)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    # Print a compact summary to stderr regardless
    s = report["summary"]
    print(
        f"\nSummary: {s['exact_match']}/{s['total']} exact matches "
        f"({s['exact_match_pct']}%)  errors={s['errors']}",
        file=sys.stderr,
    )
    per = report["per_defect"]
    print(
        f"{'Defect':<10} {'P':>6} {'R':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4}",
        file=sys.stderr,
    )
    for mid in ALL_DEFECT_IDS:
        d = per[mid]
        fmt = lambda v: f"{v:.2f}" if v is not None else "  N/A"
        print(
            f"{mid:<10} {fmt(d['precision']):>6} {fmt(d['recall']):>6} "
            f"{fmt(d['f1']):>6} {d['tp']:>4} {d['fp']:>4} {d['fn']:>4}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
