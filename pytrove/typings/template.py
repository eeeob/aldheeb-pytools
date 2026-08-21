"""Typing definitions shared across the models/ subpackage.

The package-wide equivalent is pytrove/typings.py -- this one holds only
what the model dataclasses themselves need, so a model module imports its
shapes from here rather than defining them inline.
"""

from __future__ import annotations

from typing import (
    Dict, Union, List, 
    Literal, TypedDict, TypeAlias,
    TYPE_CHECKING, 
)

import sys

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired


if TYPE_CHECKING:
    from pyrogram.enums import ParseMode as PyroParseMode
    from pyrogram.types import InlineKeyboardMarkup, InputRichMessage

from ..typings import MaybeList, JsonValue, StrInt


ButtonType: TypeAlias = Literal["url", "callback_data"]
ParseMode: TypeAlias = Literal["html", "markdown"]


class DefaultsDict(TypedDict):
    """Keys every renderable part accepts to carry its own fallback values."""

    default_keys: NotRequired[Dict[str, JsonValue]]
    "Fallback values for keys not passed to format()."

class ConditionalDict(DefaultsDict):
    """The opt-out/fallback keys every conditional part shares -- see
    template_models.CompiledConditional for how they are evaluated."""

    any_of: NotRequired[MaybeList[str]]
    all_of: NotRequired[MaybeList[str]]

class LineDict(ConditionalDict):
    text: str
class EachLineDict(TypedDict):
    each: str
    item: Union[str, LineDict]

class ButtonDict(ConditionalDict):
    text: str
    type: ButtonType
    value: str

    meta: NotRequired[Dict[str, StrInt]]
    """Extra InlineKeyboardButton arguments, as written in the JSON -- so raw
    values only, never enum members (`"style": "primary"`, not
    ButtonStyle.PRIMARY). CompiledButton.meta is the widened counterpart:
    compile() runs the values through from_dict(..., values_to_enums=True),
    which is what turns the ones naming a ButtonStyle into real members."""
class EachButtonDict(TypedDict):
    each: str
    item: ButtonDict
    row_width: NotRequired[int]

class RichMessageDict(DefaultsDict):
    html: NotRequired[List[Union[str, LineDict, EachLineDict]]]
    markdown: NotRequired[List[Union[str, LineDict, EachLineDict]]]
    is_rtl: NotRequired[bool]
    skip_entity_detection: NotRequired[bool]

class TemplateDict(DefaultsDict):
    message: NotRequired[List[Union[str, LineDict, EachLineDict]]]
    buttons: NotRequired[List[Union[MaybeList[ButtonDict], EachButtonDict]]]
    parse_mode: NotRequired[ParseMode]
    rich_message: NotRequired[RichMessageDict]
    key_time: NotRequired[str]

class PyroMessage(TypedDict):
    """What CompiledTemplate.format() hands back -- spread straight into
    Client.send_message()/send_rich_message(). Every key is NotRequired
    because format() drops the ones that came out empty."""

    text: NotRequired[str]
    parse_mode: NotRequired[PyroParseMode]
    rich_message: NotRequired[InputRichMessage]
    reply_markup: NotRequired[InlineKeyboardMarkup]


__all__ = (
    "ButtonType",
    "ParseMode",
    "DefaultsDict",
    "ConditionalDict",
    "LineDict",
    "EachLineDict",
    "ButtonDict",
    "EachButtonDict",
    "RichMessageDict",
    "TemplateDict",
    "PyroMessage",
)
