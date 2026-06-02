from typing import Dict, Union
from pycountry import countries

from .typings import CountryInfo
from .phone_tools import cc_from_rc, is_rc




COUNTRIES: Dict[str, CountryInfo] = {
    c._fields["alpha_2"].lower(): dict(
        cc = cc_from_rc(c._fields["alpha_2"].lower()), 
        rc = c._fields["alpha_2"].lower(), 
        flag = c._fields["flag"], 
        name = c._fields["name"]
    )
    for c in list(countries)
    if is_rc(c._fields["alpha_2"])
}

COUNTRIES_BY_CC: Dict[int, CountryInfo] = {
    ci["cc"]: ci
    for ci in COUNTRIES.values()
} 

def get_cinfo(rc_or_cc: Union[str, int]) -> CountryInfo:
    if isinstance(rc_or_cc, str):
        info = COUNTRIES[rc_or_cc.lower()]
    else:
        info = COUNTRIES_BY_CC[rc_or_cc]
    return info

def get_cfullname(rc_or_cc: Union[str, int]) -> str:
    info = get_cinfo(rc_or_cc)
    
    return f"{info['name']} {info['flag']}"



__all__ = (
    "get_cinfo", 
    "get_cfullname", 
    "COUNTRIES", 
    "COUNTRIES_BY_CC", 
    
)
