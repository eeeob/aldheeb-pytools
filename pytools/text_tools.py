from typing import (
    Union, Mapping, 
    Any, Literal, Optional, 
    Callable, List, overload
)

from .typings import (
    Container, ContainerWithoutMapping, 
    MaybeCoroutineCallable, 
    NestedContainer, 
    _KT, _VT, _T, _True
)

from .validate_tools import is_mapping, is_container
from .iter_tools import to_list, flat_cont
from .async_tools import gather_helper, maybe_awaitable

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
async def smart_split(
    text: "NestedContainer[str]", 
    indexing: int, 
    part_resolver: MaybeCoroutineCallable[[str], Optional[_T]], 
    *,
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]], 
) -> Optional[_T]: ...
@overload
async def smart_split(
    text: "NestedContainer[str]", 
    indexing: int, 
    part_resolver: MaybeCoroutineCallable[[str], Optional[_T]], 
    without_none: _True, 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    *, 
    separator: Union[str, MaybeCoroutineCallable[[], str]], 
) -> _T: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    indexing: int, 
    *,
    strip: bool = ...,
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> str: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    indexing: slice,
    part_resolver: MaybeCoroutineCallable[[str], Optional[_T]], 
    without_none: _True, 
    strip: bool = ...,
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    *,
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> List[_T]: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    indexing: slice,
    part_resolver: MaybeCoroutineCallable[[str], Optional[_T]], 
    *,
    strip: bool = ...,
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> List[Optional[_T]]: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    *, 
    part_resolver: MaybeCoroutineCallable[[str], Optional[_T]], 
    without_none: _True, 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> List[_T]: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    *, 
    part_resolver: MaybeCoroutineCallable[[str], Optional[_T]], 
    strip: bool = ..., 
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> List[Optional[_T]]: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    *,
    strip: bool = ...,
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> List[str]: ...
@overload
async def smart_split(
    text: "NestedContainer[str]",
    indexing: slice,
    *,
    strip: bool = ...,
    remove_spaces: bool = ..., 
    max_split: int = ..., 
    separator: Union[str, MaybeCoroutineCallable[[], str]],
) -> List[str]: ...
async def smart_split(
    text: "NestedContainer[str]", 
    indexing: Optional[Union[slice, int]] = None, 
    part_resolver: Optional[MaybeCoroutineCallable[[str], Optional[_T]]] = None, 
    without_none: bool = False, 
    strip: bool = False, 
    remove_spaces: bool = False, 
    max_split: int = -1, 
    *, 
    separator: Union[str, MaybeCoroutineCallable[[], str]], 
    ):

    if not isinstance(separator, str):
        separator = await maybe_awaitable(separator)

    texts = text.split(separator, max_split) if isinstance(text, str) else flat_cont(text)

    if indexing is not None:
        texts = to_list(texts[indexing])
    
    if strip or remove_spaces:
        texts = [
            clean_spaces(t) if remove_spaces else t.strip()
            for t in texts
            ]
    
    if part_resolver is not None:
        texts = [
            v for v in await gather_helper(maybe_awaitable(part_resolver, t) for t in texts)
            if (not without_none or v is not None)
            ]

    
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
    
)