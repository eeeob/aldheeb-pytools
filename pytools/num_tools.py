
from typing import Union, overload, Optional

from .typings import _True, _False, _T, Number
from .validate_tools import validation

import logging
import random


log = logging.getLogger(__name__)
CALC_ALLOWED_CHARS = frozenset("0123456789*/-+.")



@overload
def to_int(value: str, as_int: _True = ...) -> Union[str, int]: ...
@overload
def to_int(value: str, as_int: _False) -> Union[str, int, float]: ...
@overload
def to_int(value: _T, as_int: bool = ...) -> _T: ...
def to_int(value: Union[str, _T], as_int: bool = True):
    if not isinstance(value, str) or value.startswith("+"):
        return value
    
    try:
        return int(value) if (as_int or "." not in value) else float(value)
    except (ValueError, TypeError):
        return value


@overload
def calc(value: str, as_int: _False = ...) -> Union[str, int, float]: ...
@overload
def calc(value: str, as_int: _True) -> Union[str, int]: ...
@overload
def calc(value: _T, as_int: bool = ...) -> _T: ...
def calc(value: Union[str, _T], as_int: bool = False):
    if not isinstance(value, str):
        return value
    
    value = to_int(value, False)

    if isinstance(value, str):
        from .text_tools import clean_spaces
        c_value = clean_spaces(value)

        if all(i in CALC_ALLOWED_CHARS for i in c_value):
            try:
                c_value = eval(c_value, {"__builtins__": None}, {})
            except Exception as e:
                log.exception(e)

        if isinstance(c_value, (int, float)):
            value = c_value
    
    if as_int and isinstance(value, float):
        value = int(value)

    return value


def apply_discount(price: Number, discount_percent: Number, ndigits: Optional[int] = 4) -> float:
    validation(discount_percent <= 100, "discount_percent must be <= 100")
    return round(price * (1 - discount_percent / 100), ndigits)

def reverse_discount(
    discounted_price: Number,
    discount_percent: Number,
    ndigits: Optional[int] = 4
) -> float:

    validation(
        0 <= discount_percent < 100,
        "discount_percent must be between 0 and < 100"
    )

    return round(discounted_price / (1 - discount_percent / 100), ndigits)

def jitter(
    base: Number,
    minus: Number = 2,
    plus: Number = 2
    ) -> float:
    
    low = max(0, base - minus)
    high = max(low, base + plus)

    return random.uniform(low, high)

__all__ = (
    "to_int", 
    "calc", "reverse_discount", 
    "apply_discount", "jitter", 

)