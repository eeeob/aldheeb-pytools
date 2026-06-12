from typing import Callable
from dataclasses import dataclass

from ..enums import TimeUnit
from .base import BaseDataClass


@dataclass(slots=True)
class UnitForms(BaseDataClass):
    one: str
    two: str
    many: str


@dataclass(slots=True)
class DurationFormatter(BaseDataClass):
    time_resolver: Callable[[int, str, str, str], str]
    and_word: str
    year: UnitForms
    month: UnitForms
    day: UnitForms
    hour: UnitForms
    minute: UnitForms
    second: UnitForms
    
    
    def format_date(self, seconds: int) -> str:
        seconds = int(seconds)

        years, seconds = divmod(seconds, TimeUnit.YEAR)
        months, seconds = divmod(seconds, TimeUnit.MONTH)
        days, seconds = divmod(seconds, TimeUnit.DAY)
        hours, seconds = divmod(seconds, TimeUnit.HOUR)
        minutes, seconds = divmod(seconds, TimeUnit.MINUTE)

        time_parts = [years, months, days, hours, minutes, seconds]
        options_parts = [self.year, self.month, self.day, self.hour, self.minute, self.second]
        
        parts = [
            self.time_resolver(t, options.one, options.two, options.many)
            for t, options in zip(time_parts, options_parts)
            if t
        ]
        
        
        return f" {self.and_word} ".join(parts) if parts else f"0 {self.second.many}"
    




__all__ = (
    "UnitForms", 
    "DurationFormatter", 

)