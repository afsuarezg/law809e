"""
Compare manual reviewer defects against synthetic-generator ground truth.

For each notice in the eval report (produced by `evaluate_notices.py`), compare:
- A = `expected` defects (what the synthetic-notice LLM claims to have injected)
- B = `defects_observed` flagged true by a human reviewer

Reports the four-way agreement breakdown per notice and per defect, plus
overall exact-match and cell-level agreement rates. Neutral framing — neither
side is treated as ground truth.

Usage:
    python compare_manual_vs_expected.py
        [--eval evaluation/batch_30_notices_0.json]
        [--reviews benchmark/batch_30_notices__*__feedback.json]
        [--output PATH]
"""

import argparse
import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from evaluate_notices import ALL_DEFECT_IDS, _next_numeric_output_path


def _reviewer_label_from_path(path: Path, batch_stem: str) -> str:
    """Extract the reviewer slug from filenames like '<batch>__<user>__feedback.json'."""
    m = re.match(rf"^{re.escape(batch_stem)}__(.+)__feedback$", path.stem)
    return m.group(1) if m else path.stem


def _reviewer_observed_set(notice_review: Dict[str, Any]) -> Set[str]:
    """MVP IDs the reviewer marked true on a single notice."""
    obs = notice_review.get("defects_observed", {}) or {}
    return {mid for mid in ALL_DEFECT_IDS if obs.get(mid) is True}


def _compare_one_notice(expected: Set[str], observed: Set[str]) -> Dict[str, Any]:
    all_ids = set(ALL_DEFECT_IDS)
    agree_present = expected & observed
    reviewer_only = observed - expected
    generator_only = expected - observed
    agree_absent = all_ids - expected - observed
    return {
        "expected": sorted(expected),
        "observed": sorted(observed),
        "agree_present": sorted(agree_present),
        "agree_absent": sorted(agree_absent),
        "generator_only": sorted(generator_only),
        "reviewer_only": sorted(reviewer_only),
        "exact_match": expected == observed,
        "cell_agreement": len(agree_present) + len(agree_absent),  # out of len(all_ids)
    }


def _compare_reviewer(
    eval_notices: List[Dict[str, Any]],
    reviewer_file: Path,
) -> Dict[str, Any]:
    with reviewer_file.open(encoding="utf-8") as fh:
        review_data = json.load(fh)
    reviews = review_data.get("reviews", {})

    per_notice: List[Dict[str, Any]] = []
    per_defect: Dict[str, Dict[str, int]] = {
        mid: {"agree_present": 0, "agree_absent": 0, "generator_only": 0, "reviewer_only": 0}
        for mid in ALL_DEFECT_IDS
    }

    n_total = len(eval_notices)
    n_reviewed = 0
    n_exact = 0
    cell_agree = 0
    cell_total = 0

    for entry in eval_notices:
        idx = entry["index"]
        expected = set(entry.get("expected", []))
        review_entry = reviews.get(str(idx))

        if review_entry is None:
            per_notice.append({"index": idx, "skipped": True})
            continue

        observed = _reviewer_observed_set(review_entry)
        cmp = _compare_one_notice(expected, observed)
        cmp["index"] = idx
        if review_entry.get("comment"):
            cmp["comment"] = review_entry["comment"]
        per_notice.append(cmp)

        n_reviewed += 1
        if cmp["exact_match"]:
            n_exact += 1
        cell_agree += cmp["cell_agreement"]
        cell_total += len(ALL_DEFECT_IDS)

        for mid in ALL_DEFECT_IDS:
            in_a = mid in expected
            in_b = mid in observed
            if in_a and in_b:
                per_defect[mid]["agree_present"] += 1
            elif in_a and not in_b:
                per_defect[mid]["generator_only"] += 1
            elif in_b and not in_a:
                per_defect[mid]["reviewer_only"] += 1
            else:
                per_defect[mid]["agree_absent"] += 1

    summary = {
        "notices_in_eval": n_total,
        "notices_reviewed": n_reviewed,
        "exact_matches": n_exact,
        "exact_match_pct": round(n_exact / n_reviewed * 100, 1) if n_reviewed else 0.0,
        "cell_agreement_pct": round(cell_agree / cell_total * 100, 1) if cell_total else 0.0,
    }
    return {"summary": summary, "per_defect": per_defect, "per_notice": per_notice}


def _print_summary(reviewer_label: str, block: Dict[str, Any]) -> None:
    s = block["summary"]
    print(
        f"\n[{reviewer_label}]  {s['exact_matches']}/{s['notices_reviewed']} exact matches "
        f"({s['exact_match_pct']}%)  cell agreement={s['cell_agreement_pct']}%",
        file=sys.stderr,
    )
    print(
        f"{'Defect':<10} {'both':>6} {'gen-only':>9} {'rev-only':>9} {'neither':>8}",
        file=sys.stderr,
    )
    for mid in ALL_DEFECT_IDS:
        d = block["per_defect"][mid]
        print(
            f"{mid:<10} {d['agree_present']:>6} {d['generator_only']:>9} "
            f"{d['reviewer_only']:>9} {d['agree_absent']:>8}",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--eval", dest="eval_path", type=Path,
        default=Path("evaluation/batch_30_notices_0.json"),
        help="Eval report from evaluate_notices.py (default: evaluation/batch_30_notices_0.json)",
    )
    parser.add_argument(
        "--reviews", type=str, default=None,
        help="Glob for reviewer feedback JSON files. "
             "Default: benchmark/<eval_batch_stem>__*__feedback.json",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output JSON path. Default: evaluation/<eval_batch_stem>_manual_vs_expected_<N>.json",
    )
    args = parser.parse_args()

    if not args.eval_path.exists():
        print(f"Error: eval file not found: {args.eval_path}", file=sys.stderr)
        sys.exit(1)

    with args.eval_path.open(encoding="utf-8") as fh:
        eval_report = json.load(fh)
    eval_notices = eval_report.get("notices", [])
    batch_file = eval_report.get("config", {}).get("file", args.eval_path.stem)
    batch_stem = Path(batch_file).stem

    glob_pattern = args.reviews or f"benchmark/{batch_stem}__*__feedback.json"
    reviewer_files = sorted(Path(p) for p in glob.glob(glob_pattern))
    if not reviewer_files:
        print(f"Error: no reviewer files match {glob_pattern!r}", file=sys.stderr)
        sys.exit(1)

    reviewers: Dict[str, Any] = {}
    for rf in reviewer_files:
        label = _reviewer_label_from_path(rf, batch_stem)
        reviewers[label] = _compare_reviewer(eval_notices, rf)
        reviewers[label]["source_file"] = str(rf)

    report = {
        "config": {
            "eval_file": str(args.eval_path),
            "batch": batch_file,
            "reviewer_files": [str(p) for p in reviewer_files],
            "compared_at": datetime.now().isoformat(timespec="seconds"),
        },
        "reviewers": reviewers,
    }

    output_path = args.output or _next_numeric_output_path(
        Path("evaluation"), f"{batch_stem}_manual_vs_expected"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {output_path}", file=sys.stderr)

    for label, block in reviewers.items():
        _print_summary(label, block)


if __name__ == "__main__":
    main()
