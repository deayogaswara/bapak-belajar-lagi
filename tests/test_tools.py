import pytest

from src.tools import CalculatorError, calculate


def test_basic_division():
    result = calculate("150 / 2.5")
    assert result["result"] == "60"


def test_fraction_division():
    result = calculate("(1/2) / (1/4)")
    assert result["result"] == "2"


def test_decimal_precision():
    result = calculate("0.1 + 0.2")
    assert result["result"] == "0.3"


def test_parentheses():
    result = calculate("(12 + 8) * 3")
    assert result["result"] == "60"


def test_unsafe_expression_blocked():
    with pytest.raises(CalculatorError):
        calculate("__import__('os').system('dir')")


def test_divide_by_zero_blocked():
    with pytest.raises(CalculatorError):
        calculate("10 / 0")
