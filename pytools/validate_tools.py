
from typing import (
    Any, Union, 
    TypeIs, Optional, 
    Mapping, Type, Required, 
    NotRequired, Dict, Never, 
    overload, get_args, 
    get_origin, get_type_hints, 
    is_typeddict, TYPE_CHECKING, 
)

from types import UnionType
from enum import EnumType

try:
    from aioimaplib import aioimaplib
except ImportError:
    if not TYPE_CHECKING:
        aioimaplib = None

from pyrogram import Client
from pyrogram.utils import get_peer_type
from pyrogram.types import Message



from .typings import (
    Container, NotContainer, 
    NestedContainer, _T, _KT, _VT, _True, _False
)
from .errors import ValidationError



import phonenumbers
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

def is_tg_channel_id(value: Any) -> TypeIs[int]:
    try:
        return isinstance(value, int) and get_peer_type(value) == "channel"
    except ValueError:
        return False

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
        and parts[1].isalnum()
    )

def is_tg_bot_command(message: Union[Message, str]) -> TypeIs[str]:
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

def is_phone_number(
    phone_number: Union[str, int], 
    remove_spaces: bool = True, 
    resolve: bool = True
    ) -> TypeIs[Union[int, str]]:
    
    if not isinstance(phone_number, (int, str)):
        return False
    
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
        return phonenumbers.is_possible_number(parsed_number) and phonenumbers.is_valid_number(parsed_number)
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
    return inspect.iscoroutinefunction(inspect.unwrap(f))

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

async def is_accessible_received_email(email: str, password: str):
    from .email_tools import detect_email_provider

    provider = detect_email_provider(email)

    if provider is None:
        return False
    
    if aioimaplib is None:
        raise ImportError("is_accessible_received_email aioimaplib required")

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

def validate_type(value: Any, annotation: Any) -> None:
    if isinstance(annotation, EnumType):
        try:
            annotation(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"expected {annotation.__name__}, got {value!r}") from exc

        return

    if is_typeddict(annotation):
        return validate_typed_dict(value, annotation)
        
    origin = get_origin(annotation)

    if origin is not None:
        args = get_args(annotation)

        if origin in (Required, NotRequired):
            return validate_type(value, args[0])
            
        if origin in (Union, UnionType):
            union_errors = []

            for arg in args:
                try:
                    return validate_type(value, arg)
                except ValidationError as exc:
                    union_errors.append(str(exc))

            raise ValidationError(
                f"value {value!r} does not match any union type:\n" 
                + "\n".join(f"- {err}" for err in union_errors)
            )

        elif (
            origin is tuple
            and len(args) > 1
            and args[1] is not Ellipsis
        ):
    
            validation(isinstance(value, tuple), f"expected tuple, got {type(value).__name__}")
            validation(len(value) == len(args), f"expected tuple length {len(args)}, got {len(value)}")
            
            for index, (item, ann) in enumerate(zip(value, args)):
                try:
                    validate_type(item, ann)
                except ValidationError as exc:
                    raise ValidationError(f"tuple index {index}: {exc}") from exc


        elif is_sub_mapping(origin) and args:
            validation(isinstance(value, origin), f"expected {origin.__name__}, got {type(value).__name__}")

            for k, v in value.items():
                try:
                    validate_type(k, args[0])
                except ValidationError as exc:
                    raise ValidationError(f"invalid mapping key {k!r}: {exc}") from exc

                try:
                    validate_type(v, args[1])
                except ValidationError as exc:
                    raise ValidationError(f"invalid value for key {k!r}: {exc}") from exc

        elif is_sub_container(origin) and args:
            validation(isinstance(value, origin), f"expected {origin.__name__}, got {type(value).__name__}")

            for index, item in enumerate(value):
                try:
                    validate_type(item, args[0])
                except ValidationError as exc:
                    raise ValidationError(f"container index {index}: {exc}") from exc

        else:
            annotation = args[0]
            origin = None
        
        if origin is not None:
            return

    if annotation is Any:
        return
    
    if annotation is None:
        return validation(value is None, "expected None")
    
    if isinstance(annotation, type):
        return validation(isinstance(value, annotation), f"expected {annotation.__name__}, got {type(value).__name__}")
    
    raise TypeError(f"unsupported annotation: {annotation!r}")

def validate_typed_dict(data: Dict, scheme: Type) -> None:
    validation(
        is_mapping(data),
        f"expected mapping, got {type(data).__name__}"
    )

    validation(
        is_typeddict(scheme),
        f"{scheme!r} is not a TypedDict"
    )

    hints = get_type_hints(scheme, include_extras=True)

    name = scheme.__name__
    is_total = scheme.__total__

    errors = []

    for key, annotation in hints.items():
        if key not in data:
            origin = get_origin(annotation)

            is_required = (
                (is_total and origin is not NotRequired)
                or
                (not is_total and origin is Required)
            )

            if is_required:
                errors.append(
                    f"{name}.{key}: missing required key"
                )

            continue

        try:
            validate_type(data[key], annotation)
        except ValidationError as exc:
            errors.append(
                f"{name}.{key}: {exc}"
            )

    if errors:
        raise ValidationError(
            "typed dict validation failed:\n"
            + "\n".join(
                f"  • {error}"
                for error in errors
            )
        )
    

    

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
    "validate_typed_dict", 
    "iscoroutinefunction_wrapped", 
    
)