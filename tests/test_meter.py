"""Time-signature pair resolution."""

from __future__ import annotations

import pytest

from acid2reaper.binary.meter import DEN_NUM, NUM_DEN, resolve_meter


@pytest.mark.parametrize(
    "pair, expected",
    [
        # Only one half can legally be a denominator, so the order in the file
        # does not matter: these resolve identically either way round.
        ((4, 3), (3, 4)),
        ((3, 4), (3, 4)),
        ((4, 5), (5, 4)),
        ((5, 4), (5, 4)),
        ((8, 7), (7, 8)),
        ((7, 8), (7, 8)),
        ((8, 12), (12, 8)),
        ((12, 8), (12, 8)),
        ((8, 6), (6, 8)),
        ((6, 8), (6, 8)),
        ((4, 9), (9, 4)),
        ((16, 15), (15, 16)),
    ],
)
def test_pairs_that_resolve_themselves(pair, expected) -> None:
    assert resolve_meter(*pair, order=DEN_NUM) == expected
    assert resolve_meter(*pair, order=NUM_DEN) == expected


@pytest.mark.parametrize("pair", [(4, 4), (2, 4), (4, 2), (8, 8), (4, 8), (8, 4)])
def test_ambiguous_pairs_follow_the_declared_order(pair) -> None:
    """Both halves are powers of two, so only `order` can decide."""
    first, second = pair
    assert resolve_meter(first, second, order=DEN_NUM) == (second, first)
    assert resolve_meter(first, second, order=NUM_DEN) == (first, second)


@pytest.mark.parametrize("pair", [(0, 4), (4, 0), (5, 5), (33, 4), (4, 33), (7, 3), (-1, 4)])
def test_pairs_that_are_not_a_meter(pair) -> None:
    assert resolve_meter(*pair) is None
