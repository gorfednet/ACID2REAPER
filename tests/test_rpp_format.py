import pytest

from acid2reaper.rpp_format import format_rpp_float


def test_format_rpp_float_integers_without_fraction() -> None:
    assert format_rpp_float(3.0) == "3"


def test_format_rpp_float_non_integer_uses_plain_decimal() -> None:
    assert "." in format_rpp_float(1.25)


@pytest.mark.parametrize(
    "value, expected",
    [
        (3.1059307775e14, "310593077750000"),
        (1e-9, "0.000000001"),
        (2.5e-7, "0.00000025"),
        (1.5e20, "150000000000000000000"),
    ],
)
def test_extreme_magnitudes_never_use_scientific_notation(value: float, expected: str) -> None:
    """
    REAPER's chunk parser reads plain decimals only.

    A real project decoded a clip at 3.1e14 seconds; written as "3.1059307775e+14"
    REAPER misreads the position entirely.
    """
    text = format_rpp_float(value)
    assert "e" not in text.lower()
    assert text == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_become_zero(value: float) -> None:
    assert format_rpp_float(value) == "0"


def test_ordinary_values_keep_their_compact_form() -> None:
    """The common path must not gain spurious precision."""
    assert format_rpp_float(120.0) == "120"
    assert format_rpp_float(0.6896551724137931) == "0.689655172414"
    assert format_rpp_float(-2.5) == "-2.5"
