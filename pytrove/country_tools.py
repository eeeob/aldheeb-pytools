from typing import Dict, Union, Optional

from .typings import CountryInfo
from .phone_tools import cc_from_rc, is_rc

try:
    from pycountry import countries
except ImportError:
    pass

from ._optional import _optional_import

_COUNTRIES: Optional[Dict[str, CountryInfo]] = None
_COUNTRIES_BY_CC: Optional[Dict[int, CountryInfo]] = None

@_optional_import((("pycountry", "phonenumbers"), "country"))
def _build_countries():
    global _COUNTRIES, _COUNTRIES_BY_CC

    if _COUNTRIES is not None:
        return

    _COUNTRIES = {
        c._fields["alpha_2"].lower(): dict(
            cc=cc_from_rc(c._fields["alpha_2"].lower()),
            rc=c._fields["alpha_2"].lower(),
            flag=c._fields["flag"],
            name=c._fields["name"]
        )
        for c in list(countries)
        if is_rc(c._fields["alpha_2"])
    }

    _COUNTRIES_BY_CC = {
        ci["cc"]: ci
        for ci in _COUNTRIES.values()
    }


@_optional_import((("pycountry", "phonenumbers"), "country"))
def get_cinfo(rc_or_cc: Union[str, int]) -> CountryInfo:
    _build_countries()
    if isinstance(rc_or_cc, str):
        return _COUNTRIES[rc_or_cc.lower()]
    return _COUNTRIES_BY_CC[rc_or_cc]


@_optional_import((("pycountry", "phonenumbers"), "country"))
def get_cfullname(rc_or_cc: Union[str, int]) -> str:
    info = get_cinfo(rc_or_cc)
    return f"{info['name']} {info['flag']}"


@_optional_import((("pycountry", "phonenumbers"), "country"))
def get_countries() -> Dict[str, CountryInfo]:
    _build_countries()
    return _COUNTRIES

@_optional_import((("pycountry", "phonenumbers"), "country"))
def get_countries_by_cc() -> Dict[int, CountryInfo]:
    _build_countries()
    return _COUNTRIES_BY_CC


__all__ = (
    "get_cinfo",
    "get_cfullname",
    "get_countries",
    "get_countries_by_cc",
)