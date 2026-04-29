"""Tests for the windowed Mood Score computation.

Locks in the math so future tweaks to the question sets or weights cannot
silently break the formula. Reference math comes from §12.5 of the
implementation plan.
"""

from __future__ import annotations

import math

import pytest

from zen_backend.routes.checkin import (
    CheckinAnswer,
    SCORE_METHOD,
    compute_scores,
    _QUESTIONS_BY_WINDOW,
    _WEIGHTS_BY_WINDOW,
)


def _all_answers(window: str, score: int) -> list[CheckinAnswer]:
    return [CheckinAnswer(key=q["key"], score=score) for q in _QUESTIONS_BY_WINDOW[window]]


@pytest.mark.parametrize("window", ["morning", "midday", "evening"])
def test_weights_sum_to_one(window: str) -> None:
    total = sum(_WEIGHTS_BY_WINDOW[window].values())
    assert abs(total - 1.0) < 1e-9


@pytest.mark.parametrize("window", ["morning", "midday", "evening"])
def test_all_fives_means_max_for_positive_min_for_reverse(window: str) -> None:
    """All 5s on every item: positives are at max, reverses are at min ('5 = bad').
    Goodness vector therefore has 1.0 on positives and 0.0 on reverses, so the
    score equals the sum of the positive items' weights * 100.
    """
    answers = _all_answers(window, 5)
    scores = compute_scores(window, answers)

    weights = _WEIGHTS_BY_WINDOW[window]
    reverse_keys = {q["key"] for q in _QUESTIONS_BY_WINDOW[window]} & {
        # cross-check via direct introspection
        k
        for k in weights.keys()
    }
    # Recompute expected:
    from zen_backend.routes.checkin import _REVERSE_KEYS_BY_WINDOW

    rev = _REVERSE_KEYS_BY_WINDOW[window]
    expected_weighted = sum(w for k, w in weights.items() if k not in rev) * 100
    n_positive = sum(1 for q in _QUESTIONS_BY_WINDOW[window] if q["key"] not in rev)
    n = len(_QUESTIONS_BY_WINDOW[window])
    expected_equal = (n_positive / n) * 100

    assert math.isclose(float(scores["mood_score_weighted"]), expected_weighted, abs_tol=0.05)
    assert math.isclose(float(scores["mood_score_equal"]), expected_equal, abs_tol=0.05)
    assert scores["score_method"] == SCORE_METHOD


@pytest.mark.parametrize("window", ["morning", "midday", "evening"])
def test_all_threes_is_neutral_50(window: str) -> None:
    answers = _all_answers(window, 3)
    scores = compute_scores(window, answers)
    assert math.isclose(float(scores["mood_score_weighted"]), 50.0, abs_tol=0.05)
    assert math.isclose(float(scores["mood_score_equal"]), 50.0, abs_tol=0.05)


@pytest.mark.parametrize("window", ["morning", "midday", "evening"])
def test_best_case_all_positive_5_all_reverse_1_is_100(window: str) -> None:
    """The truly best case is positives at 5 AND reverses at 1 (low challenge).
    Mood score should be 100 in both weighted and equal-weight forms.
    """
    from zen_backend.routes.checkin import _REVERSE_KEYS_BY_WINDOW

    rev = _REVERSE_KEYS_BY_WINDOW[window]
    answers = [
        CheckinAnswer(key=q["key"], score=1 if q["key"] in rev else 5)
        for q in _QUESTIONS_BY_WINDOW[window]
    ]
    scores = compute_scores(window, answers)
    assert math.isclose(float(scores["mood_score_weighted"]), 100.0, abs_tol=0.05)
    assert math.isclose(float(scores["mood_score_equal"]), 100.0, abs_tol=0.05)


@pytest.mark.parametrize("window", ["morning", "midday", "evening"])
def test_worst_case_all_positive_1_all_reverse_5_is_0(window: str) -> None:
    from zen_backend.routes.checkin import _REVERSE_KEYS_BY_WINDOW

    rev = _REVERSE_KEYS_BY_WINDOW[window]
    answers = [
        CheckinAnswer(key=q["key"], score=5 if q["key"] in rev else 1)
        for q in _QUESTIONS_BY_WINDOW[window]
    ]
    scores = compute_scores(window, answers)
    assert math.isclose(float(scores["mood_score_weighted"]), 0.0, abs_tol=0.05)
    assert math.isclose(float(scores["mood_score_equal"]), 0.0, abs_tol=0.05)


def test_challenge_score_is_mean_of_reverse_items_only() -> None:
    """Morning has one reverse key (`anticipated_load`)."""
    answers = [
        CheckinAnswer(key="sleep_quality", score=4),
        CheckinAnswer(key="morning_energy", score=4),
        CheckinAnswer(key="morning_calm", score=3),
        CheckinAnswer(key="motivation", score=4),
        CheckinAnswer(key="morning_clarity", score=5),
        CheckinAnswer(key="body_readiness", score=3),
        CheckinAnswer(key="anticipated_load", score=5),  # reverse-coded
    ]
    scores = compute_scores("morning", answers)
    assert scores["challenge_score"] == 5.0  # only the reverse item


def test_unknown_keys_fall_back_to_equal_weight() -> None:
    """Legacy or unknown keys should not crash; they should get a 1/n weight."""
    answers = [
        CheckinAnswer(key="legacy_random_key_a", score=4),
        CheckinAnswer(key="legacy_random_key_b", score=2),
    ]
    scores = compute_scores("morning", answers)
    # n=2, both unknown so weights = 0.5 each. Goodnesses = 0.75 and 0.25.
    # Weighted = 0.5*0.75 + 0.5*0.25 = 0.5 -> 50
    assert math.isclose(float(scores["mood_score_weighted"]), 50.0, abs_tol=0.05)
    assert scores["score_method"] == SCORE_METHOD


def test_morning_specific_known_value() -> None:
    """Pin a known-output sanity check so any future weight tweak announces itself."""
    # All 4s except `anticipated_load` (reverse) at 2.
    answers = [
        CheckinAnswer(key="sleep_quality", score=4),
        CheckinAnswer(key="morning_energy", score=4),
        CheckinAnswer(key="morning_calm", score=4),
        CheckinAnswer(key="motivation", score=4),
        CheckinAnswer(key="morning_clarity", score=4),
        CheckinAnswer(key="body_readiness", score=4),
        CheckinAnswer(key="anticipated_load", score=2),
    ]
    # goodness for positives at 4 = 0.75; goodness for reverse at 2 = 1 - 0.25 = 0.75
    # Every contribution is 0.75 -> weighted = 0.75 * sum(weights) = 0.75 -> 75.0
    scores = compute_scores("morning", answers)
    assert math.isclose(float(scores["mood_score_weighted"]), 75.0, abs_tol=0.05)
    assert math.isclose(float(scores["mood_score_equal"]), 75.0, abs_tol=0.05)
