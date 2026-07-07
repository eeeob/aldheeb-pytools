
from typing import (
    Any, Union, Optional, 
    Mapping, Type, Never, 
    overload, Tuple, 
)

import sys

if sys.version_info >= (3, 13):
    from typing import TypeIs
else:
    from typing import TypeGuard as TypeIs

from typeguard import (
    check_type, check_type_internal, 
    checker_lookup_functions, 
    TypeCheckMemo, TypeCheckError, 
    CollectionCheckStrategy, 
)
from enum import EnumType, Enum

try:
    from aioimaplib import aioimaplib
except ImportError:
    pass

try:
    from pyrogram import Client
    from pyrogram.utils import get_peer_type
    from pyrogram.types import Message
except ImportError:
    pass



from .typings import (
    Container, NotContainer, 
    NestedContainer, _T, _KT, _VT, _True, _False
)
from .errors import ValidationError

from ._optional import _optional_import

try:
    import phonenumbers
except ImportError:
    pass

import re
import inspect


TG_BOT_COMMAND_PATTERN = re.compile(r"^/[A-Za-z][\w\d]*$")
TG_CHANNEL_MSG_LINK_PATTERN = re.compile(r"^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:org|me|dog)/(?:c/)?)([\w]+)(?:/\d+)*/(\d+)/?$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")



def is_exception(obj: Any) -> TypeIs[BaseException]:
    return isinstance(obj, BaseException)

def is_container(obj: Union['Container[_T]', Any]) -> TypeIs['Container[_T]']:
    return isinstance(obj, Container) and not isinstance(obj, NotContainer)

def is_mapping(obj: Union[Mapping[_KT, _VT], Any]) -> TypeIs[Mapping[_KT, _VT]]:
    return isinstance(obj, Mapping)

def is_sub_mapping(obj: Any) -> TypeIs[Type[Mapping]]:
    return isinstance(obj, type) and issubclass(obj, Mapping)

def is_sub_container(obj: Any) -> TypeIs[Type[Container]]:
    return isinstance(obj, type) and issubclass(obj, Container) and not issubclass(obj, NotContainer)

@_optional_import(("kurigram", "tg"))
def is_tg_channel_id(value: Any) -> TypeIs[int]:
    try:
        return isinstance(value, int) and get_peer_type(value) == "channel"
    except ValueError:
        return False
    
@_optional_import(("kurigram", "tg"))
def is_tg_user_id(value: Any) -> TypeIs[int]:
    try:
        return isinstance(value, int) and get_peer_type(value) == "user"
    except ValueError:
        return False

def is_tg_bot_token(bot_token: Any) -> TypeIs[str]:
    if not isinstance(bot_token, str) or ":" not in bot_token:
        return False

    parts = bot_token.split(":")

    return (
        len(parts) == 2
        and parts[0].isdecimal()
    )

@_optional_import(("kurigram", "tg"))
def is_tg_bot_command(message: Union["Message", str]) -> TypeIs[str]:
    if isinstance(message, Message):
        message = message.text or ""

    return (
        isinstance(message, str)
        and bool(message)
        and bool(TG_BOT_COMMAND_PATTERN.match(message))
    )

def is_tg_channel_message_link(message_link: Any) -> TypeIs[str]:
    return (
        isinstance(message_link, str)
        and bool(TG_CHANNEL_MSG_LINK_PATTERN.match(message_link.lower()))
    )

@overload
def is_tg_otp_code(code: Any, with_str: _True = True, remove_spaces: bool = False) -> TypeIs[Union[int, str]]: ...
@overload
def is_tg_otp_code(code: Any, with_str: _False) -> TypeIs[int]: ...
def is_tg_otp_code(code, with_str = True, remove_spaces = False):
    if isinstance(code, int):
        return len(str(code)) == 5
    elif isinstance(code, str):
        if with_str:
            if remove_spaces:
                from .text_tools import clean_spaces
                code = clean_spaces(code)
            from .num_tools import to_int
            return len(code) == 5 and isinstance(to_int(code, False), int)
    
    return False

@_optional_import(("phonenumbers", "phone"))
def is_phone_number(
    phone_number: Union[str, int, "phonenumbers.PhoneNumber"], 
    remove_spaces: bool = True, 
    resolve: bool = True
    ) -> TypeIs[Union[int, str]]:

    if isinstance(phone_number, phonenumbers.PhoneNumber):
        parsed_number = phone_number

    elif isinstance(phone_number, (int, str)):
        phone_number = str(phone_number)
        
        if remove_spaces:
            from .text_tools import clean_spaces
            phone_number = clean_spaces(phone_number)
        
        if resolve:
            if phone_number.startswith("00"):
                phone_number = phone_number[2:]

            if not phone_number.startswith("+"):
                phone_number = "+" + phone_number
        
        try:
            parsed_number = phonenumbers.parse(phone_number)
        except Exception:
            return False
    else:
        return False
    
    try:
        return (
            phonenumbers.is_possible_number(parsed_number) 
            and phonenumbers.is_valid_number(parsed_number)
        )
    except Exception:
        return False

def is_rc(rc: Any) -> TypeIs[str]:
    return isinstance(rc, str) \
    and rc.isalpha() and len(rc) == 2 \
    and rc.lower() != "zz" \
    and phonenumbers.country_code_for_region(rc.upper()) != 0
    
def is_email(email: Any) -> TypeIs[str]:
    return isinstance(email, str) \
    and bool(EMAIL_PATTERN.fullmatch(email))

def iscoroutinefunction_wrapped(f):
    is_coro = False

    def _stop(func):
        nonlocal is_coro

        if inspect.iscoroutinefunction(func):
            is_coro = True
            return True
        
        return False

    unwrapped = inspect.unwrap(f, stop=_stop)
    return is_coro or inspect.iscoroutinefunction(unwrapped)

@_optional_import(("kurigram", "tg"))
async def is_valid_tg_app(api_id, api_hash) -> bool:
    c = Client(f"check_session_{api_id}", api_id=api_id, api_hash=api_hash, in_memory=True, no_updates=True)

    try:
        await c.connect()
    except Exception:
        return False
    else:
        return True
    finally:
        from .async_tools import safe_await
        await safe_await(c.disconnect())

@_optional_import(("aioimaplib", "imap"))
async def is_accessible_received_email(email: str, password: str):
    from .email_tools import detect_email_provider

    provider = detect_email_provider(email)

    if provider is None:
        return False

    client = aioimaplib.IMAP4_SSL(host=provider.host, port=provider.port)

    try:
        await client.wait_hello_from_server()
        await client.login(email, password)
    except Exception:
        return False
    else:
        return True
    finally:
        from .async_tools import safe_await
        await safe_await(client.logout())
    
@overload
def validation(cond: _True, custom_exc: Optional[Union[BaseException, str]] = None) -> None: ...
@overload
def validation(cond: _False, custom_exc: Optional[Union[BaseException, str]] = None) -> Never: ...
def validation(cond: bool, custom_exc = None):
    if not cond:
        if is_exception(custom_exc):
            raise custom_exc
        elif isinstance(custom_exc, str):
            raise ValidationError(custom_exc)
        raise ValidationError

def all_of(*values: Any) -> bool:
    return all(values)
def any_of(*values: Any) -> bool:
    return any(values)

def all_deep(*values: NestedContainer[Any]) -> bool:
    from .iter_tools import flat_cont
    return all(flat_cont(values))
def any_deep(*values: NestedContainer[Any]) -> bool:
    from .iter_tools import flat_cont
    return any(flat_cont(values))


def checker_lookup(origin_type: Any, *_):
    def validate_enum(value, origin_type: Type[Enum], *_):
        try:
            origin_type(value)
        except (ValueError, TypeError) as exc:
            raise TypeCheckError(str(exc)) from exc

    def validate_container(value, origin_type, args: Tuple[Any], memo: TypeCheckMemo, *_):
        if not is_container(value):
            raise TypeCheckError("is not container")
        
        if not args or args == (Any,):
            return

        samples = memo.config.collection_check_strategy.iterate_samples(value)

        for i, v in enumerate(samples):
            try:
                check_type_internal(v, args[0], memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"item {i}")
                raise
    
    if isinstance(origin_type, EnumType):
        return validate_enum
    
    if is_sub_container(origin_type):
        return validate_container
    
checker_lookup_functions.append(checker_lookup)

def validate_type(value: Any, annotation: Any) -> None:
    try:
        return check_type(
            value, annotation, 
            typecheck_fail_callback=None, 
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS
            )
    except TypeCheckError as exc:
        raise ValidationError(str(exc)) from exc







    

__all__ = (
    "is_exception",
    "is_container",
    "is_tg_channel_id",
    "is_tg_user_id",
    "is_tg_bot_token",
    "is_tg_bot_command",
    "is_tg_channel_message_link",
    "is_mapping", 
    "is_tg_otp_code", 
    "is_phone_number", 
    "is_rc", 
    "is_email", 
    "validation", 
    "all_of",
    "any_of",
    "all_deep",
    "any_deep", 
    "is_valid_tg_app", 
    "is_accessible_received_email", 
    "is_sub_mapping", 
    "is_sub_container", 
    "validate_type", 
    "iscoroutinefunction_wrapped", 
    
)