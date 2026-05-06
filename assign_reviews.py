"""CLI: generate a per-reviewer assignment manifest for a batch JSON.

Examples:
    # Explicit reviewer list
    python assign_reviews.py synthetic_notices/output/LLM_generated/batch_100_notices.json \\
        --reviewers a@x.edu,b@x.edu,c@x.edu

    # Pull reviewer list from local .streamlit/secrets.toml
    python assign_reviews.py path/to/batch.json --reviewers-from-secrets

The manifest is written next to the batch as
`<batch_stem>__assignments.json`. Refuses to overwrite an existing manifest
unless --force is passed. Existing per-reviewer feedback files are never
touched by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from synthetic_notices.reviewer_assignment import (
    compute_assignment,
    manifest_path_for,
)


def _read_secrets_emails(secrets_path: Path) -> list[str]:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    with open(secrets_path, "rb") as f:
        data = tomllib.load(f)
    emails = data.get("allowed_emails", [])
    if not isinstance(emails, list):
        raise SystemExit(f"`allowed_emails` in {secrets_path} is not a list")
    return [str(e) for e in emails]


def _parse_reviewers(s: str) -> list[str]:
    return [part for part in (p.strip() for p in s.split(",")) if part]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path, help="Path to the batch JSON file.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--reviewers",
        type=_parse_reviewers,
        help="Comma-separated reviewer emails.",
    )
    src.add_argument(
        "--reviewers-from-secrets",
        action="store_true",
        help="Read reviewers from .streamlit/secrets.toml `allowed_emails`.",
    )
    parser.add_argument("--shared-ratio", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing manifest. (Per-reviewer feedback is not touched.)",
    )
    parser.add_argument(
        "--secrets-path",
        type=Path,
        default=Path(".streamlit/secrets.toml"),
        help="Path to secrets.toml when --reviewers-from-secrets is used.",
    )
    args = parser.parse_args()

    if not args.batch.exists():
        print(f"Batch file not found: {args.batch}", file=sys.stderr)
        return 2

    with open(args.batch, encoding="utf-8") as f:
        batch_data = json.load(f)
    notices = batch_data if isinstance(batch_data, list) else batch_data.get("notices", [])
    batch_size = len(notices)
    if batch_size == 0:
        print("Batch is empty.", file=sys.stderr)
        return 2

    if args.reviewers_from_secrets:
        if not args.secrets_path.exists():
            print(f"Secrets file not found: {args.secrets_path}", file=sys.stderr)
            return 2
        reviewers = _read_secrets_emails(args.secrets_path)
    else:
        reviewers = args.reviewers
    if not reviewers:
        print("No reviewers found.", file=sys.stderr)
        return 2

    manifest = compute_assignment(
        batch_size=batch_size,
        reviewers=reviewers,
        shared_ratio=args.shared_ratio,
        seed=args.seed,
    )
    manifest["batch_file"] = args.batch.name
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    out_path = manifest_path_for(args.batch)
    if out_path.exists() and not args.force:
        print(
            f"Manifest already exists at {out_path}. Pass --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    n_unique_each = [len(v) for v in manifest["per_reviewer"].values()]
    print(f"Wrote {out_path}")
    print(
        f"  batch_size={batch_size} | reviewers={len(manifest['reviewers'])} | "
        f"shared={len(manifest['shared_indices'])} | "
        f"unique_per_reviewer={min(n_unique_each)}-{max(n_unique_each)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
