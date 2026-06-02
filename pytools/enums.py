from typing import Optional
from enum import Enum, StrEnum, auto, IntEnum


class TgMessageLength(IntEnum):
    TEXT = 4096
    CAPTION = 1024

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
    "PlatformDevice", 
    "TgMessageLength", 
    "TimeUnit", 
    "IMAP_DOMAIN_TO_PROVIDER", 
)