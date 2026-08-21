from typing import Optional

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum
    
    class StrEnum(str, Enum):
        def _generate_next_value_(name, *args):
            return name.lower()
        def __str__(self):
            return str(self.value)
        
from enum import Enum, IntEnum, auto


class TriggerOn(StrEnum):
    SUCCESS = auto()
    ERROR = auto()
    ALWAYS = auto()

class TgMessageLength(IntEnum):
    TEXT = 4096
    CAPTION = 1024

class PickleSafety(IntEnum):
    """How much files_tools.read_pickle is willing to reconstruct.

    Ordered by how much it refuses, so a higher member is always at least
    as strict as a lower one -- `>=` comparisons between them are
    meaningful, and STRICT (the highest) is read_pickle's default.
    """

    NONE = 0
    """No restriction at all -- plain pickle.loads, so the file decides what
    runs. Only for a file nothing else on the machine can write."""

    BLOCKLIST = 1
    """Everything except the known code-execution vectors (os/subprocess/
    ctypes/..., builtins.eval/exec/__import__/...). Best-effort by nature:
    a blocklist can only refuse what it has been told about, so treat this
    as a guard against accidents, not against an attacker."""

    MODULES = 2
    """The safe types, plus anything defined in a module named in
    `allow_modules` -- for loading your own app's classes in bulk without
    listing each one."""

    STRICT = 3
    """Only the inert builtin/stdlib types, plus whatever `allow_classes`
    names explicitly. Anything else raises UnpicklingError."""

class ImapEmailProvider(Enum):
    GMAIL = ("imap.gmail.com", 993)
    OUTLOOK = ("outlook.office365.com", 993)
    YAHOO = ("imap.mail.yahoo.com", 993)
    ZOHO = ("imap.zoho.com", 993)

    @property
    def host(self) -> str:
        return self.value[0]

    @property
    def port(self) -> int:
        return self.value[1]
    
    @classmethod
    def from_domain(cls, domain: str) -> Optional["ImapEmailProvider"]:
        return IMAP_DOMAIN_TO_PROVIDER.get(domain.lower())
    
class PlatformDevice(StrEnum):
    ANDROID = auto()
    IOS = auto()
    DESKTOP = auto()

class TimeUnit(IntEnum):
    MINUTE = 60
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    WEEK = DAY * 7
    MONTH = DAY * 30
    YEAR = MONTH * 12


IMAP_DOMAIN_TO_PROVIDER = {
    "gmail.com": ImapEmailProvider.GMAIL,
    "outlook.com": ImapEmailProvider.OUTLOOK,
    "hotmail.com": ImapEmailProvider.OUTLOOK,
    "live.com": ImapEmailProvider.OUTLOOK,
    "yahoo.com": ImapEmailProvider.YAHOO,
    "zoho.com": ImapEmailProvider.ZOHO,
}



__all__ = (
    "ImapEmailProvider",
    "PickleSafety",
    "PlatformDevice",
    "TgMessageLength",
    "TimeUnit", "TriggerOn", 
    "IMAP_DOMAIN_TO_PROVIDER", 

)