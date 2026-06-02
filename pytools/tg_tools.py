from typing import Union, Tuple, Optional, List, Dict, Final, overload
from pathlib import Path

from pyrogram.types.user_and_chats.user import Link

from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery as Query, Message, User, Chat
from pyrogram.utils import get_channel_id
from pyrogram import Client

from .typings import _T, _True, _False
from .errors import ValidationError
from .enums import TgMessageLength, PlatformDevice
from ._devices import (
    AndroidDevice, 
    iOSDeivce, 
    WindowsDevice, 
    LinuxDevice, 
    macOSDevice, 
    DeviceInfo
)
from .validate_tools import is_tg_user_id
from .num_tools import to_int
from .text_tools import to_str
from .date_tools import date_to_stamp, time_utc
from .files_tools import load_json
from .iter_tools import flat_cont
from .email_tools import fetch_emails_from, detect_email_provider

import random
import re

_POINTS: Final[Tuple[Tuple[int, float]]] = tuple(
    (uid, date_to_stamp(date, format="%Y-%m-%d")) 
    for uid, date in load_json(Path(__file__).parent / "data" / "tg_points.json")
)


_DEVICES: Final[Dict[PlatformDevice, Union[AndroidDevice, Tuple[AndroidDevice, ...]]]] = {
    PlatformDevice.ANDROID: AndroidDevice, 
    PlatformDevice.IOS: iOSDeivce, 
    PlatformDevice.DESKTOP: (WindowsDevice, LinuxDevice, macOSDevice)
}
_FLATTED_DEVICES = flat_cont(_DEVICES.values())


def make_pyro_update_key(update: Union[Message, Query]) -> Tuple[int, int]:
    if isinstance(update, Query):
        update = update.message
    
    return (update.chat.id, update.id)

def extract_pyro_update_text(update: Union[Message, Query]) -> str:
    if isinstance(update, Message):
        txt = update.text or update.caption or ""
    elif isinstance(update, Query):
        txt = update.data or ""
    else:
        raise ValidationError(f"extract_pyro_update_text doesn't work with {type(update)}")
    
    return txt


@overload
def format_tg_username(
    target: Union[str, Chat, User], 
    with_invite_link: bool = False, 
    with_at: bool = True, 
    ) -> Optional[str]: ...
@overload
def format_tg_username(
    target: Union[str, Chat, User], 
    with_invite_link: bool = False, 
    with_at: bool = True, 
    default: _T = ...
    ) -> Union[str, _T]: ...
def format_tg_username(
    target: Union[str, Chat, User], 
    with_invite_link: bool = False, 
    with_at: bool = True, 
    default = None
    ):


    if isinstance(target, (User, Chat)):
        target = target.username
    
    if not target:
        return default
    
    if bool(Client.INVITE_LINK_RE.match(target.lower())):
        return target if with_invite_link else default
    
    
    match = Client.CHANNEL_MESSAGE_LINK_RE.match(target.lower())
    target = (match.group(1) if match else target.replace("@", "")).strip()

    if with_at:
        target = "@" + target
    
    return target
    
@overload
def format_tg_link(
    target: Union[str, int, Message, Chat, User], 
    ) -> Optional[str]: ...
@overload
def format_tg_link(
    target: Union[str, int, Message, Chat, User], 
    default: _T
    ) -> Union[str, _T]: ...
def format_tg_link(
    target: Union[str, int, Message, Chat, User], 
    default = None
    ):

    if isinstance(target, Message):
        return target.link
    
    if isinstance(target, (User, Chat)):
        target = target.username or getattr(target, "invite_link", None) or target.id
    
    if not target:
        return default
    
    target = to_str(target)

    if Client.INVITE_LINK_RE.match(target):
        return target
    
    match = Client.CHANNEL_MESSAGE_LINK_RE.match(target.lower())
    target = to_int((match.group(1) if match else target.replace("@", "")).strip())
    
    if isinstance(target, int):
        target = (
            f"tg://openmessage?user_id={target}" 
            if is_tg_user_id(target) else 
            f"tg://openmessage?chat_id={get_channel_id(target)}" 
        )
    else:
        target = f"https://t.me/{target}"
    
    return target

def format_hidden_tg_link(
    url: str, 
    text: str, 
    parse_mode: ParseMode = ParseMode.HTML
    ) -> str:

    return Link(
        url, text, parse_mode
    )()

def mention_tg_user(
    user_id: int, 
    user_full_name: Optional[str] = None, 
    parse_mode: ParseMode = ParseMode.HTML
    ) -> str:

    if user_full_name is None:
        user_full_name = "Deleted Account"

    return format_hidden_tg_link(
        f"tg://user?id={user_id}", 
        user_full_name, 
        parse_mode
    )

def split_tg_message(
    text: str, 
    length: int = TgMessageLength.TEXT, 
    reverse: bool = False, 
    ) -> List[str]:

    text = text.strip()

    if len(text) <= length:
        return [text]
    
    lines = text.splitlines(True)

    if reverse:
        lines = reversed(lines)

    messages: List[str] = []
    current = ""

    for line in lines:
        if len(current) + len(line) <= length:
            current = (line + current) if reverse else (current + line)
        else:
            if current:
                messages.append(current)
            
            current = line

            while len(current) > length:
                if reverse:
                    messages.append(current[-length:])
                    current = current[:-length]
                else:
                    messages.append(current[:length])
                    current = current[length:]

    if current:
        messages.append(current)
    
    return [m.strip() for m in messages if m.strip()]


@overload
def rand_tg_device(platform_device: Optional[PlatformDevice] = ..., to_tuple: _False = False) -> DeviceInfo: ...
@overload
def rand_tg_device(platform_device: Optional[PlatformDevice] = ..., *, to_tuple: _True) -> Tuple[str, str]: ...
def rand_tg_device(platform_device: Optional[PlatformDevice] = None, to_tuple: bool = False):
    device = (
        _DEVICES[platform_device] 
        if platform_device is not None 
        else random.choice(_FLATTED_DEVICES)
        ).RandomDevice()

    if to_tuple:
        device = device.model, device.version
    
    return device
    

def _interpolate_time(
    uid: int, 
    id1: int, t1: float, 
    id2: int, t2: float
    ):

    if id1 == id2:
        return t1

    ratio = (uid - id1) / (id2 - id1)
    ts = t1 + (t2 - t1) * ratio

    return min(ts, time_utc())

def tg_account_created_at(user_id: int):
    points = _POINTS
    
    if user_id <= points[0][0]:
        return points[0][1]

    for i in range(len(points)-1):
        id1, t1 = points[i]
        id2, t2 = points[i+1]

        if id1 <= user_id <= id2:
            return _interpolate_time(user_id, id1, t1, id2, t2)

    return _interpolate_time(user_id, *points[-2], *points[-1])


async def fetch_tg_email_code(
    email: str, 
    password: str, 
    full_name: str, 
    code_length: int
    ):

    code_pattern = re.compile(fr"\b\d{code_length}\b")

    async for message in fetch_emails_from(email, password, detect_email_provider(email)):
        match = code_pattern.search(message)

        if match and full_name in message:
            return match.group()




__all__ = (
    "extract_pyro_update_text", 
    "make_pyro_update_key", 
    "format_tg_username", 
    "format_tg_link", 
    "format_hidden_tg_link", 
    "mention_tg_user", 
    "split_tg_message", 
    "rand_tg_device", 
    "tg_account_created_at", 
    "fetch_tg_email_code", 


)
