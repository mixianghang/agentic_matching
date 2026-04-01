"""Negotiation-privacy helpers.

Implements range-based offers, offer randomisation, and strategy obfuscation
as described in design/privacy_preserving_agentic_matching_v1.0.md §6.
"""
from __future__ import annotations

import random
from typing import Optional


def make_offer(
    floor: float,
    ceiling: float,
    round_number: int,
    total_rounds: int,
    *,
    rng: Optional[random.Random] = None,
) -> float:
    """Generate a privacy-preserving negotiation offer (§6.2).

    The offer converges from floor + 25 % of range (round 1) toward
    floor + 100 % of range (final round) over successive rounds.  A small
    random noise term and rounding to the nearest $10 prevent the peer agent
    from inferring the user's reservation value.

    Args:
        floor: The user's minimum acceptable value (never disclosed directly).
        ceiling: The user's maximum acceptable value (never disclosed directly).
        round_number: Current negotiation round (1-indexed).
        total_rounds: Total expected rounds in the session.
        rng: Optional :class:`random.Random` instance (for reproducible tests).

    Returns:
        A positive offer value rounded to the nearest 10.
    """
    if floor > ceiling:
        raise ValueError(f"floor ({floor}) must not exceed ceiling ({ceiling})")
    if round_number < 1 or total_rounds < 1:
        raise ValueError("round_number and total_rounds must be >= 1")

    _rng = rng or random

    midpoint = floor + (ceiling - floor) * (round_number / total_rounds)
    noise = _rng.uniform(-0.05, 0.05) * (ceiling - floor)
    raw = midpoint + noise
    # Round to nearest 10; keep at least 10 to avoid zeroing small values
    return max(round(raw / 10) * 10, 10)


def opening_offer(
    floor: float,
    ceiling: float,
    *,
    rng: Optional[random.Random] = None,
) -> float:
    """Generate the first offer using a random offset from the floor (§6.1).

    The offset is in [0, 30 %] of the floor→ceiling range so the opening bid
    does not reveal the reservation value.

    Args:
        floor: The user's minimum acceptable value.
        ceiling: The user's maximum acceptable value.
        rng: Optional :class:`random.Random` instance (for reproducible tests).

    Returns:
        An opening offer value (positive, rounded to nearest 10).
    """
    if floor > ceiling:
        raise ValueError(f"floor ({floor}) must not exceed ceiling ({ceiling})")

    _rng = rng or random
    offset = _rng.uniform(0, 0.3) * (ceiling - floor)
    raw = floor + offset
    return max(round(raw / 10) * 10, 10)


def should_pause_before_accept(
    *,
    rng: Optional[random.Random] = None,
    pause_probability: float = 0.25,
) -> bool:
    """Return True if the agent should add a strategic pause (§6.3).

    The agent occasionally delays acceptance even when the counter-offer is
    within range, mimicking realistic human negotiation behaviour.

    Args:
        rng: Optional :class:`random.Random` instance.
        pause_probability: Probability of a strategic pause (default 25 %).

    Returns:
        True if the agent should pause this round.
    """
    _rng = rng or random
    return _rng.random() < pause_probability


def should_reject_within_range(
    *,
    rng: Optional[random.Random] = None,
    reject_probability: float = 0.10,
) -> bool:
    """Return True if the agent should reject an in-range offer (§6.3).

    A small probability of rejecting technically-acceptable offers prevents
    the peer agent from inferring the user's exact acceptable range.

    Args:
        rng: Optional :class:`random.Random` instance.
        reject_probability: Probability of a strategic rejection (default 10 %).

    Returns:
        True if the agent should reject even though the offer is within range.
    """
    _rng = rng or random
    return _rng.random() < reject_probability
