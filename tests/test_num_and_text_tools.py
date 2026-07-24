from pytools import to_int, calc, apply_discount, reverse_discount, clean_spaces, to_str, split_part


def test_to_int_basic():
    assert to_int("5") == 5
    assert to_int("5.5", as_int=False) == 5.5
    assert to_int("notanumber") == "notanumber"
    assert to_int("+123") == "+123"  # leading '+' is treated as non-numeric passthrough


def test_calc_basic_arithmetic():
    assert calc("2+2") == 4
    assert calc("10/2") == 5.0
    assert calc("2*3-1") == 5
    assert calc("-5+2") == -3
    assert calc("not math") == "not math"


def test_calc_long_compound_expressions_respect_operator_precedence():
    # calc()'s AST-based evaluator must match standard +-*/ precedence exactly,
    # the same as the eval() it replaced -- verified here against Python's own
    # operator precedence as ground truth.
    assert calc("2+3*4-5/2+10*3-7+1*2-3/3+4-5*6+7-8*9+10") == -45.5
    assert calc("1+2+3+4+5+6+7+8+9+10-1-2-3-4-5") == 40
    assert calc("2*3*4*5*6") == 720
    assert calc("-3.5+2*4-10/5+1.25*4") == 7.5
    assert calc("100-50+25-12.5+6.25-3.125") == 65.625
    assert calc("1*2*3*4*5*6*7*8*9*10") == 3628800


def test_calc_rejects_power_operator_dos_vector():
    # calc() must never evaluate "**" -- chained exponentiation like this can
    # exhaust memory/CPU. It should fail safe and return the original string.
    assert calc("9**9**9") == "9**9**9"


def test_calc_division_by_zero_falls_back_to_original_string():
    assert calc("1/0") == "1/0"


def test_calc_no_eval_side_channel():
    # Regression: calc() must never execute arbitrary code, even indirectly.
    assert calc("__import__('os')") == "__import__('os')"


def test_apply_and_reverse_discount_roundtrip():
    price = 100.0
    discounted = apply_discount(price, 20)
    assert discounted == 80.0
    original = reverse_discount(discounted, 20)
    assert round(original, 2) == 100.0


def test_clean_spaces():
    assert clean_spaces("a b\nc") == "abc"
    assert clean_spaces("a b\nc", with_lines=False) == "ab\nc"


def test_to_str():
    assert to_str(5) == "5"
    assert to_str(None) is None
    assert to_str([1, 2]) == [1, 2]


def test_split_part():
    assert split_part("a,b,c", ",", 1) == "b"
    assert split_part("a,b", ",", 5) == "a,b"  # out-of-range index falls back to original
