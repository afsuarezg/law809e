import json

import pytest

from synthetic_notices.reviewer_assignment import (
    assigned_indices_for,
    compute_assignment,
    is_shared,
    load_manifest,
    manifest_path_for,
)


def _flatten(manifest):
    out = list(manifest["shared_indices"])
    for v in manifest["per_reviewer"].values():
        out.extend(v)
    return out


def test_partition_is_exact_no_duplicates():
    m = compute_assignment(100, ["a@x.edu", "b@x.edu", "c@x.edu"], 0.25, seed=42)
    flat = _flatten(m)
    assert sorted(flat) == list(range(100)), "indices must cover 0..99 exactly"
    assert len(flat) == len(set(flat)), "no index may appear twice"


def test_shared_count_matches_ratio():
    m = compute_assignment(100, ["a@x.edu", "b@x.edu", "c@x.edu", "d@x.edu", "e@x.edu"], 0.25)
    assert len(m["shared_indices"]) == 25


def test_unique_chunks_balanced_within_one():
    m = compute_assignment(100, ["a@x.edu", "b@x.edu", "c@x.edu", "d@x.edu", "e@x.edu"], 0.25)
    sizes = [len(v) for v in m["per_reviewer"].values()]
    assert max(sizes) - min(sizes) <= 1
    assert sum(sizes) == 75


def test_deterministic_with_same_seed():
    a = compute_assignment(50, ["x@a.com", "y@a.com"], 0.3, seed=7)
    b = compute_assignment(50, ["x@a.com", "y@a.com"], 0.3, seed=7)
    assert a == b


def test_different_seeds_produce_different_partitions():
    a = compute_assignment(50, ["x@a.com", "y@a.com"], 0.3, seed=1)
    b = compute_assignment(50, ["x@a.com", "y@a.com"], 0.3, seed=2)
    assert a != b


def test_reviewer_emails_are_normalized():
    m = compute_assignment(20, ["  Alice@X.EDU  ", "alice@x.edu", "bob@x.edu"], 0.2)
    assert m["reviewers"] == ["alice@x.edu", "bob@x.edu"]


def test_assigned_indices_for_returns_shared_plus_unique():
    m = compute_assignment(40, ["a@x.edu", "b@x.edu"], 0.25, seed=42)
    a_idx = assigned_indices_for(m, "a@x.edu")
    expected = sorted(set(m["shared_indices"]) | set(m["per_reviewer"]["a@x.edu"]))
    assert a_idx == expected


def test_assigned_indices_for_unknown_reviewer_returns_only_shared():
    m = compute_assignment(40, ["a@x.edu"], 0.25)
    other = assigned_indices_for(m, "stranger@x.edu")
    assert other == sorted(m["shared_indices"])


def test_is_shared():
    m = compute_assignment(20, ["a@x.edu", "b@x.edu"], 0.25, seed=42)
    for i in m["shared_indices"]:
        assert is_shared(m, i)
    for unique_idx in m["per_reviewer"]["a@x.edu"]:
        assert not is_shared(m, unique_idx)


def test_load_manifest_returns_none_when_missing(tmp_path):
    batch = tmp_path / "fake_batch.json"
    batch.write_text("[]", encoding="utf-8")
    assert load_manifest(batch) is None


def test_load_manifest_reads_written_file(tmp_path):
    batch = tmp_path / "fake_batch.json"
    batch.write_text("[]", encoding="utf-8")
    m = compute_assignment(10, ["a@x.edu"], 0.2)
    manifest_path_for(batch).write_text(json.dumps(m), encoding="utf-8")
    loaded = load_manifest(batch)
    assert loaded["batch_size"] == 10
    assert loaded["reviewers"] == ["a@x.edu"]


def test_invalid_inputs():
    with pytest.raises(ValueError):
        compute_assignment(0, ["a@x.edu"])
    with pytest.raises(ValueError):
        compute_assignment(10, ["a@x.edu"], shared_ratio=1.5)
    with pytest.raises(ValueError):
        compute_assignment(10, [])
    with pytest.raises(ValueError):
        compute_assignment(10, ["", "  "])


def test_full_shared_ratio_means_everyone_shares_everything():
    m = compute_assignment(10, ["a@x.edu", "b@x.edu"], 1.0)
    assert len(m["shared_indices"]) == 10
    assert all(v == [] for v in m["per_reviewer"].values())


def test_zero_shared_ratio_partitions_completely():
    m = compute_assignment(10, ["a@x.edu", "b@x.edu"], 0.0)
    assert m["shared_indices"] == []
    sizes = [len(v) for v in m["per_reviewer"].values()]
    assert sum(sizes) == 10
