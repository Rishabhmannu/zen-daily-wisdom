"""Tests for the Thompson-sampling bandit (services/bandit.py)."""

from __future__ import annotations

import random

import pytest

import zen_backend.services.bandit as bandit_module
from zen_backend.services.bandit import (
    Arm,
    DEFAULT_EXPLORATION_RATE,
    enumerate_super_arms,
    make_arm_key,
    sample_arm,
    select_passage_via_bandit,
    thompson_sample,
)


# --- Arm enumeration --------------------------------------------------------


def test_enumerate_super_arms_filters_by_min_count() -> None:
    passages = [
        {"tradition": "thoreau", "tone": "warm"},
        {"tradition": "thoreau", "tone": "warm"},
        {"tradition": "thoreau", "tone": "warm"},
        {"tradition": "marcus_aurelius", "tone": "firm"},  # only 1
        {"tradition": "rumi", "tone": "warm"},
        {"tradition": "rumi", "tone": "warm"},  # only 2 — filtered at min=3
    ]
    arms = enumerate_super_arms(passages, min_count=3)
    assert [a.key for a in arms] == ["thoreau|warm"]


def test_enumerate_super_arms_handles_missing_fields() -> None:
    passages = [
        {"tradition": None, "tone": None},
        {"tradition": "", "tone": ""},
        {"tradition": "thoreau", "tone": "warm"},
        {"tradition": "thoreau", "tone": "warm"},
        {"tradition": "thoreau", "tone": "warm"},
    ]
    arms = enumerate_super_arms(passages, min_count=3)
    assert [a.key for a in arms] == ["thoreau|warm"]


def test_enumerate_super_arms_returns_deterministic_order() -> None:
    passages = [{"tradition": t, "tone": "warm"} for t in ["b", "a", "c"] for _ in range(3)]
    arms = enumerate_super_arms(passages, min_count=3)
    assert [a.key for a in arms] == ["a|warm", "b|warm", "c|warm"]


# --- Thompson sampling ------------------------------------------------------


def test_thompson_sample_picks_strong_arm_with_seeded_rng() -> None:
    arms = [
        Arm(key="strong", tradition="t", tone="warm", alpha=200.0, beta=2.0),
        Arm(key="weak", tradition="t", tone="firm", alpha=2.0, beta=200.0),
    ]
    rng = random.Random(42)
    # The strong arm has a posterior tightly clustered near 1.0; the weak arm
    # near 0.01. The argmax over a single draw is essentially deterministic.
    picks = [thompson_sample(arms, rng=rng).key for _ in range(50)]
    assert picks.count("strong") >= 49


def test_thompson_sample_raises_on_empty() -> None:
    with pytest.raises(ValueError):
        thompson_sample([])


# --- sample_arm: Thompson + epsilon-greedy ----------------------------------


def test_sample_arm_uses_thompson_when_not_exploring() -> None:
    arms = [
        Arm(key="strong", tradition="t", tone="warm", alpha=100.0, beta=1.0, pulls=20),
        Arm(key="weak", tradition="t", tone="firm", alpha=1.0, beta=100.0, pulls=20),
    ]
    rng = random.Random()
    rng.random = lambda: 0.99  # type: ignore[assignment]
    chosen, meta = sample_arm(arms, exploration_rate=0.15, rng=rng)
    assert meta["method"] == "thompson"
    assert chosen.key == "strong"
    assert meta["chosen_alpha"] == 100.0


def test_sample_arm_epsilon_greedy_picks_under_pulled() -> None:
    arms = [
        Arm(key="hot", tradition="t", tone="warm", alpha=20, beta=1, pulls=40),
        Arm(key="cold_a", tradition="t", tone="firm", alpha=1, beta=1, pulls=2),
        Arm(key="cold_b", tradition="t", tone="austere", alpha=1, beta=1, pulls=2),
    ]
    rng = random.Random(0)
    rng.random = lambda: 0.0  # always trigger exploration  # type: ignore[assignment]
    chosen, meta = sample_arm(arms, exploration_rate=0.15, rng=rng)
    assert meta["method"] == "epsilon_greedy"
    # Mean pulls = 14.67, half-mean = 7.33; "hot" is above, the two "cold"
    # arms are below — exploration must pick one of them.
    assert chosen.key in {"cold_a", "cold_b"}
    assert meta["under_pulled_count"] == 2


def test_sample_arm_epsilon_greedy_falls_back_to_full_pool_when_no_under_pulled() -> None:
    arms = [
        Arm(key="a", tradition="t1", tone="warm", pulls=10),
        Arm(key="b", tradition="t2", tone="firm", pulls=10),
    ]
    rng = random.Random(1)
    rng.random = lambda: 0.0  # type: ignore[assignment]
    chosen, meta = sample_arm(arms, exploration_rate=0.15, rng=rng)
    assert meta["method"] == "epsilon_greedy"
    assert meta["under_pulled_count"] == 0
    assert chosen.key in {"a", "b"}


# --- Convergence ------------------------------------------------------------


def test_thompson_converges_to_winning_arm_under_synthetic_reward() -> None:
    """With one arm that always succeeds (4★) and others that always fail,
    Thompson sampling should pull the winner the vast majority of the time."""
    rng = random.Random(7)
    arms = {
        "winner": Arm(key="winner", tradition="t", tone="warm"),
        "loser_1": Arm(key="loser_1", tradition="t", tone="firm"),
        "loser_2": Arm(key="loser_2", tradition="t", tone="austere"),
    }
    pulls = {"winner": 0, "loser_1": 0, "loser_2": 0}

    for _ in range(300):
        chosen, _ = sample_arm(
            list(arms.values()),
            exploration_rate=0.0,  # disable exploration to test pure convergence
            rng=rng,
        )
        pulls[chosen.key] += 1
        if chosen.key == "winner":
            chosen.alpha += 1
        else:
            chosen.beta += 1
        chosen.pulls += 1

    # Winner should dominate.
    assert pulls["winner"] > pulls["loser_1"] + pulls["loser_2"]
    assert pulls["winner"] >= 200


# --- Top-level select_passage_via_bandit ------------------------------------


class _StubClient:
    """Stand-in for the supabase client; no methods used in these tests."""


def _stub_hydrate_no_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make hydration a no-op so arms keep their Beta(1,1) priors."""
    monkeypatch.setattr(bandit_module, "hydrate_arm_states", lambda client, arms: arms)


def test_select_returns_passage_in_chosen_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_hydrate_no_state(monkeypatch)
    ranked = [
        # Top-ranked overall is Marcus, but we're going to force the bandit
        # to pick the Thoreau arm via a stubbed sample_arm.
        {"id": "m1", "tradition": "marcus_aurelius", "tone": "firm"},
        {"id": "t1", "tradition": "thoreau", "tone": "warm"},
        {"id": "m2", "tradition": "marcus_aurelius", "tone": "firm"},
        {"id": "t2", "tradition": "thoreau", "tone": "warm"},
        {"id": "m3", "tradition": "marcus_aurelius", "tone": "firm"},
        {"id": "t3", "tradition": "thoreau", "tone": "warm"},
    ]

    forced_arm = Arm(key="thoreau|warm", tradition="thoreau", tone="warm")
    forced_meta = {"method": "thompson", "candidate_count": 2}
    monkeypatch.setattr(bandit_module, "sample_arm", lambda arms, **kw: (forced_arm, forced_meta))

    passage, meta = select_passage_via_bandit(
        ranked_passages=ranked,
        fallback_candidates=[],
        client=_StubClient(),
    )
    assert passage["id"] == "t1"  # top-ranked Thoreau passage
    assert meta["arm_key"] == "thoreau|warm"
    assert meta["method"] == "thompson"


def test_select_falls_back_when_no_arms_satisfy_min_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_hydrate_no_state(monkeypatch)
    ranked = [
        {"id": 1, "tradition": "thoreau", "tone": "warm"},
        {"id": 2, "tradition": "marcus_aurelius", "tone": "firm"},
    ]
    passage, meta = select_passage_via_bandit(
        ranked_passages=ranked,
        fallback_candidates=[],
        client=_StubClient(),
    )
    assert passage["id"] == 1
    assert meta["method"] == "no_bandit"
    assert meta["reason"] == "insufficient_arms"
    assert meta["arm_key"] == "thoreau|warm"


def test_select_falls_back_when_chosen_arm_has_no_match_in_ranked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_hydrate_no_state(monkeypatch)
    ranked = [
        {"id": 1, "tradition": "thoreau", "tone": "warm"},
        {"id": 2, "tradition": "thoreau", "tone": "warm"},
        {"id": 3, "tradition": "thoreau", "tone": "warm"},
    ]
    forced_arm = Arm(key="rumi|warm", tradition="rumi", tone="warm")
    monkeypatch.setattr(
        bandit_module,
        "sample_arm",
        lambda arms, **kw: (forced_arm, {"method": "thompson"}),
    )
    passage, meta = select_passage_via_bandit(
        ranked_passages=ranked,
        fallback_candidates=[],
        client=_StubClient(),
    )
    assert passage["id"] == 1
    assert meta["method"] == "no_bandit"
    assert meta["reason"] == "no_match_for_chosen_arm"
    assert meta["intended_arm_key"] == "rumi|warm"


def test_select_raises_on_empty_pool() -> None:
    with pytest.raises(ValueError):
        select_passage_via_bandit(
            ranked_passages=[],
            fallback_candidates=[],
            client=_StubClient(),
        )


def test_default_exploration_rate_is_in_personal_yaml_range() -> None:
    """Sanity check: the documented default in personal.yaml is 0.15."""
    assert DEFAULT_EXPLORATION_RATE == 0.15
