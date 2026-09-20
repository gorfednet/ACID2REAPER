"""
Turn ACID's raw uint16 meter pair into a REAPER time signature.

ACID stores the two halves of a time signature adjacently with nothing marking
which is which. The documented layout of the public ``acid`` RIFF chunk puts the
*denominator* first, and the project's own records use the same shape, so that
is the default. For most non-4/4 meters the question does not arise: only one
half can legally be a denominator, so the pair resolves itself.
"""

from __future__ import annotations

from typing import Optional, Tuple

# A time-signature denominator is a power of two. 5 is a numerator, never a
# denominator, which is what lets most meters disambiguate themselves.
LEGAL_DENOMINATORS = frozenset({1, 2, 4, 8, 16, 32})
MAX_NUMERATOR = 32

DEN_NUM = "den-num"
NUM_DEN = "num-den"


def resolve_meter(
    first: int,
    second: int,
    *,
    order: str = DEN_NUM,
) -> Optional[Tuple[int, int]]:
    """
    Return ``(numerator, denominator)``, or ``None`` when the pair is not a meter.

    ``order`` only decides the ambiguous case where *both* halves are legal
    denominators (4/4, 6/8, 2/4 ...). Everywhere else the legal-denominator test
    settles it regardless of ``order``: 3/4, 5/4, 7/8 and 12/8 each have exactly
    one half that could be a denominator.
    """
    if not (1 <= first <= MAX_NUMERATOR and 1 <= second <= MAX_NUMERATOR):
        return None

    first_ok = first in LEGAL_DENOMINATORS
    second_ok = second in LEGAL_DENOMINATORS
    if not first_ok and not second_ok:
        return None
    if first_ok and not second_ok:
        return (second, first)
    if second_ok and not first_ok:
        return (first, second)
    return (second, first) if order == DEN_NUM else (first, second)
