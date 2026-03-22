from acid2reaper.rpp_format import format_rpp_float


def test_format_rpp_float_integers_without_fraction() -> None:
    assert format_rpp_float(3.0) == "3"


def test_format_rpp_float_non_integer_uses_plain_decimal() -> None:
    assert "." in format_rpp_float(1.25)
