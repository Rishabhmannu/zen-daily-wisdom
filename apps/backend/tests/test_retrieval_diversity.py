"""Unit tests for the per-tradition diversity cap in retrieval.

We don't try to talk to pgvector here — the SQL path is exercised via the
production smoke run in `notebooks/rag_eval.ipynb`. These tests pin the
in-memory diversification logic so future tweaks announce themselves.
"""

from __future__ import annotations

from zen_backend.services.retrieval import _diversify_by_tradition


def _row(idx: int, tradition: str) -> dict:
    return {"id": idx, "tradition": tradition, "tone": "gentle"}


def test_diversify_caps_tradition_to_max() -> None:
    ranked = [
        _row(1, "thoreau"),
        _row(2, "thoreau"),
        _row(3, "thoreau"),
        _row(4, "marcus_aurelius"),
        _row(5, "thoreau"),
        _row(6, "rumi"),
        _row(7, "marcus_aurelius"),
        _row(8, "rumi"),
    ]
    out = _diversify_by_tradition(ranked, max_per_tradition=2, limit=5)
    traditions = [r["tradition"] for r in out]
    # thoreau allowed at most 2; marcus_aurelius at most 2; rumi at most 2.
    assert traditions.count("thoreau") <= 2
    assert traditions.count("marcus_aurelius") <= 2
    assert traditions.count("rumi") <= 2
    assert len(out) == 5
    # Order is preserved among survivors: ids should be strictly increasing.
    assert [r["id"] for r in out] == sorted(r["id"] for r in out)


def test_diversify_returns_full_limit_even_when_pool_is_homogeneous() -> None:
    """If the entire candidate pool is one tradition (so the cap would
    starve the result), the function falls back to filling from the
    leftovers in original order rather than returning a half-empty list."""
    ranked = [_row(i, "thoreau") for i in range(1, 11)]
    out = _diversify_by_tradition(ranked, max_per_tradition=2, limit=5)
    assert len(out) == 5
    assert all(r["tradition"] == "thoreau" for r in out)
    assert [r["id"] for r in out] == [1, 2, 3, 4, 5]


def test_diversify_preserves_ranking_among_survivors() -> None:
    ranked = [
        _row(1, "a"),
        _row(2, "b"),
        _row(3, "a"),
        _row(4, "b"),
        _row(5, "c"),
        _row(6, "a"),  # would exceed cap=2 for "a", dropped from primary
        _row(7, "c"),
    ]
    out = _diversify_by_tradition(ranked, max_per_tradition=2, limit=4)
    assert [r["id"] for r in out] == [1, 2, 3, 4]


def test_diversify_with_empty_input_returns_empty() -> None:
    assert _diversify_by_tradition([], max_per_tradition=2, limit=5) == []


def test_diversify_handles_missing_tradition_field() -> None:
    """Rows without a `tradition` key get bucketed under 'unknown' and are
    capped together — so a flood of malformed rows can't crowd out the
    real ones."""
    ranked = [
        {"id": 1},
        {"id": 2, "tradition": None},
        {"id": 3, "tradition": "thoreau"},
        {"id": 4},
        {"id": 5, "tradition": "thoreau"},
    ]
    out = _diversify_by_tradition(ranked, max_per_tradition=2, limit=4)
    # 'unknown' bucket contains rows 1, 2, 4 — at most 2 can pass; thoreau
    # contributes 2.
    unknown_count = sum(1 for r in out if not r.get("tradition"))
    thoreau_count = sum(1 for r in out if r.get("tradition") == "thoreau")
    assert unknown_count <= 2
    assert thoreau_count <= 2
    assert len(out) == 4
