"""Thompson-sampling bandit over `(tradition, tone)` super-arms.

Replaces the previous hardcoded `bootstrap|calm|medium|gold` arm. Each
daily generation samples one super-arm, then picks the highest-ranked
passage in that arm from the embedding-ranked candidate list.

State (alpha, beta, pulls per arm) lives in the `bandit_state` table
and is updated on each feedback insert by the existing trigger
(`infra/supabase/migrations/003_bandit_trigger.sql`):
  - rating >= 4 and tone_tag != 'irrelevant' → alpha += 1
  - otherwise → beta += 1

The `Arm` here is intentionally just `(tradition, tone)` — the planned
fully-decomposed arm space (`tradition × tone × length × tier`) is too
sparse for the first ~100 days of feedback. We can graduate to the full
space once `bandit_state` has ≥ 300 rows and the per-arm posteriors are
no longer flat.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Iterable

from supabase import Client

from zen_backend.db.queries import get_bandit_state_for_arm_keys

logger = logging.getLogger(__name__)

DEFAULT_EXPLORATION_RATE = 0.15
MIN_PASSAGES_PER_ARM = 3


@dataclass
class Arm:
    key: str
    tradition: str
    tone: str
    alpha: float = 1.0
    beta: float = 1.0
    pulls: int = 0

    @property
    def expected_value(self) -> float:
        denom = self.alpha + self.beta
        return self.alpha / denom if denom else 0.0


def make_arm_key(tradition: str, tone: str) -> str:
    return f"{tradition}|{tone}"


# --- Arm enumeration --------------------------------------------------------


def enumerate_super_arms(
    passages: Iterable[dict[str, Any]],
    *,
    min_count: int = MIN_PASSAGES_PER_ARM,
) -> list[Arm]:
    """Return one Arm per `(tradition, tone)` pair represented by at least
    `min_count` passages in `passages`. Order is deterministic (sorted by key)
    so the same input always produces the same arm list."""
    counts: dict[tuple[str, str], int] = {}
    for p in passages:
        tradition = str(p.get("tradition") or "unknown").strip() or "unknown"
        tone = str(p.get("tone") or "gentle").strip() or "gentle"
        counts[(tradition, tone)] = counts.get((tradition, tone), 0) + 1

    arms = [
        Arm(key=make_arm_key(t, n), tradition=t, tone=n)
        for (t, n), c in counts.items()
        if c >= min_count
    ]
    arms.sort(key=lambda a: a.key)
    return arms


def hydrate_arm_states(client: Client, arms: list[Arm]) -> list[Arm]:
    """Bulk-load `(alpha, beta, pulls)` for each arm from `bandit_state`.
    Arms with no row keep the Beta(1, 1) defaults."""
    if not arms:
        return arms
    keys = [a.key for a in arms]
    state_by_key = get_bandit_state_for_arm_keys(client, keys)
    for arm in arms:
        row = state_by_key.get(arm.key)
        if row:
            try:
                arm.alpha = float(row.get("alpha", 1.0))
                arm.beta = float(row.get("beta", 1.0))
                arm.pulls = int(row.get("pulls", 0))
            except (TypeError, ValueError):
                # Bad row — keep the priors and move on.
                pass
    return arms


# --- Sampling ---------------------------------------------------------------


def thompson_sample(arms: list[Arm], rng: random.Random | None = None) -> Arm:
    """Draw one sample from each arm's Beta posterior; return the argmax arm.
    Pure function — no DB access, no side effects."""
    if not arms:
        raise ValueError("Cannot sample from empty arm list.")
    rnd = rng or random
    return max(arms, key=lambda a: rnd.betavariate(a.alpha, a.beta))


def _under_pulled(arms: list[Arm]) -> list[Arm]:
    """Arms with fewer pulls than half the mean. Used as the exploration
    pool for the epsilon-greedy fallback."""
    if not arms:
        return []
    mean_pulls = sum(a.pulls for a in arms) / len(arms)
    threshold = mean_pulls / 2 if mean_pulls > 0 else 1
    return [a for a in arms if a.pulls < threshold]


def sample_arm(
    arms: list[Arm],
    *,
    exploration_rate: float = DEFAULT_EXPLORATION_RATE,
    rng: random.Random | None = None,
) -> tuple[Arm, dict[str, Any]]:
    """Pick an arm via Thompson sampling, with an epsilon-greedy detour
    that picks uniformly from under-pulled arms `exploration_rate` of the
    time. Returns the chosen arm and a small meta dict describing how it
    was picked (suitable for stashing in `retrieval_trace.bandit_sample`).
    """
    if not arms:
        raise ValueError("Cannot sample from empty arm list.")
    rnd = rng or random.Random()

    if rnd.random() < exploration_rate:
        under_pulled_arms = _under_pulled(arms)
        pool = under_pulled_arms if under_pulled_arms else arms
        chosen = rnd.choice(pool)
        return chosen, {
            "method": "epsilon_greedy",
            "exploration_rate": exploration_rate,
            "candidate_count": len(arms),
            "under_pulled_count": len(under_pulled_arms),
        }

    chosen = thompson_sample(arms, rng=rnd)
    return chosen, {
        "method": "thompson",
        "exploration_rate": exploration_rate,
        "candidate_count": len(arms),
        "chosen_alpha": chosen.alpha,
        "chosen_beta": chosen.beta,
        "chosen_pulls": chosen.pulls,
    }


# --- Top-level entry --------------------------------------------------------


def select_passage_via_bandit(
    *,
    ranked_passages: list[dict[str, Any]],
    fallback_candidates: list[dict[str, Any]],
    client: Client,
    exploration_rate: float = DEFAULT_EXPLORATION_RATE,
    rng: random.Random | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Top-level entry used by the daily generator.

    Strategy:
      1. Treat `ranked_passages` (or `fallback_candidates` if empty) as the
         universe of viable passages for today.
      2. Enumerate `(tradition, tone)` super-arms with at least
         `MIN_PASSAGES_PER_ARM` passages in that universe.
      3. Hydrate per-arm `(alpha, beta, pulls)` from `bandit_state`.
      4. Sample an arm with Thompson + epsilon-greedy.
      5. Return the highest-ranked passage *in that arm*. If the chosen arm
         has no representative in the ranked list (e.g. retrieval narrowed
         the field), fall back to the top-ranked passage overall.
      6. If anything in this pipeline raises, return the top-ranked passage
         and tag the meta dict with the failure reason.

    Returns `(passage, meta)`. `meta["arm_key"]` is always present and is
    what should be written to `sent_history.arm_key`.
    """
    pool = ranked_passages or fallback_candidates
    if not pool:
        raise ValueError("No passages available for bandit selection.")

    def _top_with_arm(reason: str, extra: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        top = pool[0]
        tradition = str(top.get("tradition") or "unknown")
        tone = str(top.get("tone") or "gentle")
        meta: dict[str, Any] = {
            "method": "no_bandit",
            "reason": reason,
            "candidate_count": len(pool),
            "arm_key": make_arm_key(tradition, tone),
        }
        if extra:
            meta.update(extra)
        return top, meta

    arms = enumerate_super_arms(pool, min_count=MIN_PASSAGES_PER_ARM)
    if not arms:
        return _top_with_arm("insufficient_arms")

    try:
        arms = hydrate_arm_states(client, arms)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to hydrate bandit state, sampling from priors: %s", exc)

    try:
        chosen_arm, meta = sample_arm(arms, exploration_rate=exploration_rate, rng=rng)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Bandit sampling failed: %s", exc)
        return _top_with_arm("sampling_error")

    matching = [
        p for p in pool
        if str(p.get("tradition") or "unknown") == chosen_arm.tradition
        and str(p.get("tone") or "gentle") == chosen_arm.tone
    ]
    if not matching:
        return _top_with_arm("no_match_for_chosen_arm", {"intended_arm_key": chosen_arm.key})

    meta["arm_key"] = chosen_arm.key
    return matching[0], meta
