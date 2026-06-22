from typing import (
    Union, Mapping, 
    Any, Literal, Optional, 
    Callable, List, overload
)

from .typings import (
    Container, ContainerWithoutMapping, 
    NestedContainer, 
    _KT, _VT, _T
)

from .enums import TgMessageLength

from .validate_tools import is_mapping, is_container
from .iter_tools import to_list, flat_cont

import re


def to_str(value: _T) -> Union[str, _T]:
    return (
        value 
        if value is None or isinstance(value, bool) or is_container(value) 
        else str(value)
    )

def clean_spaces(text: Any, with_lines: bool = True) -> str:
    text = to_str(text)
    return re.sub(r"\s+", "", text) if with_lines else re.sub(r"[^\S\n]+", "", text)

def split_part(
    value: str, 
    sep: str, 
    part: int = 0, 
    strip: bool = True, 
    remove_spaces: bool = False, 
    ) -> str:

    try:
        value = value.split(sep)[part]

        if strip:
            value = value.strip()
        
        if remove_spaces:
            value = clean_spaces(value)

        return value
    except IndexError:
        return value

def chunk_text(text: str, max_length: int = TgMessageLength.TEXT) -> List[str]:
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        chunk = remaining[:max_length]

        if len(remaining) <= max_length:
            remaining = ""
        elif (last_newline := chunk.rfind('\n')) > 0:
            chunk = chunk[:last_newline]
            remaining = remaining[last_newline + 1:]
        elif (last_space := chunk.rfind(" ")) > len(chunk) // 10:
            chunk = chunk[:last_space]
            remaining = remaining[last_space + 1:]
        else:
            remaining = remaining[max_length:]

        if chunk.strip():
            chunks.append(chunk.strip())

    return chunks

def format_exc_tree(exc: BaseException) -> str:
    def iter_exc():
        current = exc
        level = 0

        while current is not None:
            yield level, current

            current = current.__cause__ or current.__context__
            level += 1

    return "\n".join(
        f"{'    ' * level}└─ {type(error).__name__}: {error}"
        for level, error in iter_exc()
    )


@overload
def numbering(
    values: 'ContainerWithoutMapping[_T]', 
    start: int = 1, 
    line_parser: Optional[Callable[[_T, int], str]] = None, 
    line_sep: str = "\n", 
    ) -> str : ... 
@overload
def numbering(
    values: Mapping[_KT, _VT], 
    start: int = 1, 
    line_parser: Optional[Callable[[_KT, _VT, int], str]] = None, 
    line_sep: str = "\n", 
    ) -> str : ... 
@overload
def numbering(
    values: 'ContainerWithoutMapping[_T]',
    start: int = 1,
    line_parser: Optional[Callable[[_T, int], str]] = None,
    *, 
    line_sep: Literal[None],
) -> List[str]: ...
@overload
def numbering(
    values: Mapping[_KT, _VT],
    start: int = 1,
    line_parser: Optional[Callable[[_KT, _VT, int], str]] = None,
    *, 
    line_sep: Literal[None],
) -> List[str]: ...
def numbering(
    values: Container, 
    start: int = 1, 
    line_parser: Optional[Callable[..., str]] = None, 
    line_sep: Optional[str] = "\n", 
    ):

    is_map = is_mapping(values)

    if is_map:
        values = values.items()
    
    values = to_list(values)
    
    if line_parser is None:
        line_parser = (lambda k, v, c: f"{c}. {k} - {v}") if is_map else (lambda v, c: f"{c}. {v}")
    
    if is_map:
        values = [
            line_parser(key, value, counter)
            for counter, (key, value) in enumerate(values, start)
        ]
    else:
        values = [
            line_parser(value, counter)
            for counter, value in enumerate(values, start)
        ]
    
    if line_sep is not None:
        values = line_sep.join(values)

    return values


@overload
def smart_split(
    text: NestedContainer[str], 
    indexing: int, 
    part_resolver: Callable[[str], _T], 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    *,
    separator: Union[str, Callable[[], str]], 
) -> _T: ...
@overload
def smart_split(
    text: NestedContainer[str],
    indexing: int, 
    *,
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ...,  
    separator: Union[str, Callable[[], str]],
) -> str: ...
@overload
def smart_split(
    text: NestedContainer[str], 
    indexing: slice, 
    part_resolver: Callable[[str], _T], 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    *,
    separator: Union[str, Callable[[], str]],
) -> List[_T]: ...
@overload
def smart_split(
    text: NestedContainer[str], 
    indexing: slice, 
    *, 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, Callable[[], str]],
) -> List[str]: ...
@overload
def smart_split(
    text: NestedContainer[str], 
    *, 
    part_resolver: Callable[[str], _T], 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, Callable[[], str]],
) -> List[_T]: ...
@overload
def smart_split(
    text: NestedContainer[str], 
    *, 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, Callable[[], str]],
) -> List[str]: ...
def smart_split(
    text: NestedContainer[str], 
    indexing = None, 
    part_resolver = None, 
    strip = False, 
    remove_spaces = False, 
    max_split = -1, 
    *, 
    separator, 
    ):

    if callable(separator):
        separator = separator()

    texts = text.split(separator, max_split) if isinstance(text, str) else flat_cont(text)

    if indexing is not None:
        texts = to_list(texts[indexing])
    
    if strip or remove_spaces:
        texts = [
            clean_spaces(t) if remove_spaces else t.strip()
            for t in texts
            ]
    
    if part_resolver is not None:
        texts = [part_resolver(t) for t in texts]

    return texts[0] if isinstance(indexing, int) else texts



def y_or_n(value: Any) -> Literal["✅", "❌"]:
    return "✅" if value else "❌"

def en_or_dis(value: Any) -> Literal["مفعل ✅", "معطل ❌"]:
    return "مفعل ✅" if value else "معطل ❌"

def op_or_cl(value: Any) -> Literal["مفتوح ✅", "مغلق ❌"]:
    return "مفتوح ✅" if value else "مغلق ❌"



__all__ = (
    "clean_spaces",
    "to_str",
    "y_or_n",
    "en_or_dis",
    "op_or_cl",
    "split_part",
    "numbering",
    "format_exc_tree", 
    "smart_split", 
    "chunk_text", 
    
)