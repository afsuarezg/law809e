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
def _extract_llm(text: str, provider: str, model: Optional[str] = None):
    """Extract fields via LLM (imports eviction_checker lazily)."""
    import os
    from eviction_checker.extractor import EntityExtractor
    env_key = {
        "anthropic": "ANTHROPIC_MODEL",
        "openai": "OPENAI_MODEL",
        "ollama": "OLLAMA_MODEL",
        "google": "GOOGLE_MODEL",
    }.get(provider)
    original = None
    if model and env_key:
        original = os.environ.get(env_key)
        os.environ[env_key] = model
    try:
        extractor = EntityExtractor(provider=provider)
        return extractor.extract(text)
    finally:
        if model and env_key:
            if original is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original


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
# Multi-model comparison builder
# ---------------------------------------------------------------------------
def _build_comparison(runs: List[Dict[str, Any]], batch_path: Path) -> Dict[str, Any]:
    """Combine multiple single-model runs into one comparison report."""
    labels = [
        r["config"].get("model") or r["config"].get("provider") or f"run_{i + 1}"
        for i, r in enumerate(runs)
    ]

    comparison: Dict[str, Any] = {
        "exact_match_pct": {label: runs[i]["summary"]["exact_match_pct"] for i, label in enumerate(labels)},
        "per_defect": {
            mid: {
                metric: {label: runs[i]["per_defect"][mid][metric] for i, label in enumerate(labels)}
                for metric in ("precision", "recall", "f1", "tp", "fp", "fn")
            }
            for mid in ALL_DEFECT_IDS
        },
    }

    return {
        "file": batch_path.name,
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "models": labels,
        "runs": runs,
        "comparison": comparison,
    }


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------
def evaluate(
    batch_path: Path,
    mode: str,
    provider: str,
    debug: bool,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    import os
    # Resolve the model name that will actually be used
    if mode == "llm":
        env_key = {
            "anthropic": "ANTHROPIC_MODEL",
            "openai": "OPENAI_MODEL",
            "ollama": "OLLAMA_MODEL",
            "google": "GOOGLE_MODEL",
        }.get(provider)
        resolved_model = model or (os.environ.get(env_key) if env_key else None)
        if resolved_model is None:
            defaults = {
                "anthropic": "claude-sonnet-4-6",
                "openai": "gpt-4-turbo-preview",
                "google": "gemini-2.5-flash",
            }
            resolved_model = defaults.get(provider)
    else:
        resolved_model = None

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
                extracted = _extract_llm(text, provider, model)
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
            "model": resolved_model,
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
        choices=["anthropic", "openai", "ollama", "google"],
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
        "--model",
        type=str,
        action="append",
        default=None,
        dest="models",
        metavar="MODEL",
        help="LLM model name, optionally prefixed with provider: "
             "'provider/model-name' (e.g. anthropic/claude-sonnet-4-6, openai/gpt-4o, google/gemini-2.5-flash). "
             "Repeatable for multi-model/multi-provider comparison. "
             "Without prefix, uses --provider. Defaults to provider built-in default.",
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

    # Parse model specs: "provider/model-name" or plain "model-name" or None (default)
    raw_models = args.models or [None]
    VALID_PROVIDERS = {"anthropic", "openai", "ollama", "google"}
    run_specs: List[tuple] = []  # (provider, model_or_None)
    for m in raw_models:
        if m and "/" in m:
            prov, mod = m.split("/", 1)
            if prov not in VALID_PROVIDERS:
                print(f"Error: unknown provider '{prov}' in --model {m!r}", file=sys.stderr)
                sys.exit(1)
            run_specs.append((prov, mod))
        else:
            run_specs.append((args.provider, m))

    runs: List[Dict[str, Any]] = []
    for provider, model in run_specs:
        label = f"{provider}/{model}" if model else provider
        print(
            f"Evaluating {args.batch.name}  mode={args.mode}"
            + (f"  provider={provider}  model={model or 'default'}" if args.mode == "llm" else ""),
            file=sys.stderr,
        )
        run = evaluate(args.batch, args.mode, provider, args.debug, model)
        runs.append(run)

    # Single model → existing flat format; multiple → comparison format
    if len(runs) == 1:
        report = runs[0]
    else:
        report = _build_comparison(runs, args.batch)

    output_json = json.dumps(report, indent=2, cls=_Encoder)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    # Print a compact per-model summary table to stderr
    fmt = lambda v: f"{v:.2f}" if v is not None else "  N/A"
    for run in runs:
        model_label = run["config"].get("model") or "default"
        s = run["summary"]
        print(
            f"\n[{model_label}]  {s['exact_match']}/{s['total']} exact matches "
            f"({s['exact_match_pct']}%)  errors={s['errors']}",
            file=sys.stderr,
        )
        per = run["per_defect"]
        print(
            f"{'Defect':<10} {'P':>6} {'R':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4}",
            file=sys.stderr,
        )
        for mid in ALL_DEFECT_IDS:
            d = per[mid]
            print(
                f"{mid:<10} {fmt(d['precision']):>6} {fmt(d['recall']):>6} "
                f"{fmt(d['f1']):>6} {d['tp']:>4} {d['fp']:>4} {d['fn']:>4}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
