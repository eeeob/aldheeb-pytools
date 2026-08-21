"""The package-wide type aliases, TypeVars and protocols.

Everything here is general to pytrove as a whole -- anything scoped to one
feature lives in its own sibling module (see template.py) and is named for
that scope, since the whole package is re-exported flat from
pytrove.typings.
"""

from __future__ import annotations

from typing import (
    Collection, Union, Reversible, Iterator, 
    Sequence, AbstractSet, Mapping, TypeAlias, 
    Any, Dict, Annotated, Callable, Coroutine, 
    Awaitable, ParamSpec, TypeVar, Literal, 
    TypedDict, Hashable, Protocol, List, 
    
)

from enum import EnumMeta as EnumType, Enum  # EnumType is only an alias for EnumMeta added in 3.11

import sys
import os


class LockProtocol(Protocol):
    def acquire(self) -> bool: ...
    def release(self) -> Any: ...


_P = ParamSpec("_P")
_T = TypeVar("_T")


# PEP 695's `type X[T] = ...` statement is a hard SyntaxError before Python
# 3.12 -- an `if sys.version_info >= (3, 12):` guard around it in THIS file
# would not help, since the whole file is parsed before any branch ever
# executes. A conditional IMPORT is the only way to gate syntax itself: only
# _core_py312.py (which uses that syntax) is ever parsed, and only when the
# running interpreter is 3.12+.
if sys.version_info >= (3, 12):
    from ._core_py312 import *
else:
    Container: TypeAlias = Union[
        Iterator[_T], Collection[_T], Reversible[_T], 
        Sequence[_T], AbstractSet[_T], Mapping[_T, Any], 
    ]

    ContainerWithoutMapping: TypeAlias = Union[
        Iterator[_T], Collection[_T], Reversible[_T], 
        Sequence[_T], AbstractSet[_T], 
    ]

    
    MaybeList: TypeAlias = Union[_T, List[_T]]
    MaybeContainer: TypeAlias = Union[_T, Container[_T]]
    NestedContainer: TypeAlias = Union[_T, Container["NestedContainer[_T]"]]
    NestedStrKeyDict: TypeAlias = Dict[str, Union[_T, "NestedStrKeyDict[_T]"]]

    MaybeCoroutine: TypeAlias = Union[_T, Coroutine[Any, Any, _T]]
    MaybeCoroutineCallable: TypeAlias = Callable[_P, MaybeCoroutine[_T]]
    MaybeAwaitableCallable: TypeAlias = Callable[_P, Union[_T, Awaitable[_T]]]
    # Written out in full (not `MaybeCoroutineCallable[_P, _T]`) because
    # substituting into an *already-subscripted* ParamSpec generic nested
    # inside another Union is unreliable pre-3.14 -- it raises "Expected a
    # list of types, an ellipsis, ParamSpec, or Concatenate".
    #
    # The Callable[_P, ...] member must also come FIRST in the Union: typing
    # collects a Union alias's __parameters__ by scanning members
    # left-to-right, so `Union[Awaitable[_T], Callable[_P, ...]]` discovers
    # (_T, _P) -- backwards from the `MaybeAwaitable[_P, _T]` subscript order
    # used at call sites, which raises the same TypeError (confirmed on
    # 3.12). Callable[_P, ...] first discovers (_P, _T), matching the
    # intended subscript order.
    MaybeAwaitable: TypeAlias = Union[MaybeCoroutineCallable[_P, _T], Awaitable[_T]]
    


JsonValue: TypeAlias = Union[
    str, bool, int, float, None,
    List['JsonValue'],
    Dict[str, 'JsonValue'],
    ]

NotContainer: TypeAlias = Union[bytearray, bytes, str, memoryview, EnumType, Awaitable]
PhoneNumber: TypeAlias = Annotated[str, "Phone number in international format, e.g. +967xxxxxxxxx"]
RegionCode: TypeAlias = Annotated[str, "ISO region code, verify that it is valid"]
Number: TypeAlias = Union[int, float]
StrInt: TypeAlias = Union[int, str]
PathLike: TypeAlias = Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]


_CT = TypeVar("_CT", bound=type)
_FT = TypeVar("_FT", bound=Callable[..., Any])
_KT = TypeVar("_KT", bound=Hashable)
_VT = TypeVar("_VT")
_ExcT = TypeVar("_ExcT", bound=BaseException)
_EnumT = TypeVar("_EnumT", bound=Enum)

_True = Literal[True]
_False = Literal[False]


class CountryInfo(TypedDict):
    cc: int
    rc: str
    flag: str
    name: str



__all__ = (
    "Container",
    "NestedContainer",
    "NotContainer",
    "ContainerWithoutMapping",
    "PhoneNumber",
    "NestedStrKeyDict",
    "RegionCode",
    "MaybeAwaitable",
    "CountryInfo",
    "Number",
    "StrInt", 
    "MaybeCoroutineCallable",
    "MaybeContainer", 
    "JsonValue", 
    "PathLike", 
    "LockProtocol", 
    "MaybeAwaitableCallable", 
    "MaybeCoroutine", 
    "MaybeList", 
    "_P", "_T", "_CT", "_FT",
    "_KT", "_VT", "_True", "_False",
    "_EnumT", "_ExcT", 


)
