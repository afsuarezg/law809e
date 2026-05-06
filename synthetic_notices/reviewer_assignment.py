"""Deterministic per-reviewer assignment of notice indices within a batch.

Used by both `assign_reviews.py` (CLI) and `review_app.py` (UI) so they
cannot diverge on the partition logic.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterable


MANIFEST_SUFFIX = "__assignments.json"


def compute_assignment(
    batch_size: int,
    reviewers: Iterable[str],
    shared_ratio: float = 0.25,
    seed: int = 42,
) -> dict:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if not 0.0 <= shared_ratio <= 1.0:
        raise ValueError("shared_ratio must be in [0, 1]")

    normalized = sorted({e.strip().lower() for e in reviewers if e and e.strip()})
    if not normalized:
        raise ValueError("at least one reviewer is required")

    rng = random.Random(seed)
    indices = list(range(batch_size))
    rng.shuffle(indices)

    n_shared = round(batch_size * shared_ratio)
    n_shared = max(0, min(n_shared, batch_size))
    shared = sorted(indices[:n_shared])
    remaining = indices[n_shared:]

    per_reviewer: dict[str, list[int]] = {e: [] for e in normalized}
    for i, idx in enumerate(remaining):
        per_reviewer[normalized[i % len(normalized)]].append(idx)
    for e in per_reviewer:
        per_reviewer[e].sort()

    return {
        "batch_size": batch_size,
        "shared_ratio": shared_ratio,
        "seed": seed,
        "reviewers": normalized,
        "shared_indices": shared,
        "per_reviewer": per_reviewer,
    }


def manifest_path_for(batch_path: Path) -> Path:
    return batch_path.with_name(batch_path.stem + MANIFEST_SUFFIX)


def load_manifest(batch_path: Path) -> dict | None:
    path = manifest_path_for(batch_path)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def assigned_indices_for(manifest: dict, reviewer_email: str) -> list[int]:
    """Original-batch indices (0-indexed) the reviewer should see, sorted."""
    email = (reviewer_email or "").strip().lower()
    shared = list(manifest.get("shared_indices", []))
    unique = list(manifest.get("per_reviewer", {}).get(email, []))
    return sorted(set(shared + unique))


def is_shared(manifest: dict, batch_index: int) -> bool:
    return batch_index in set(manifest.get("shared_indices", []))
