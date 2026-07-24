from typing import (
    Collection as  TCollection, Generator, Union, Reversible,
    Sequence, AbstractSet, Mapping, TypeAlias, List,
    Any, Dict, Annotated, TYPE_CHECKING, Callable, Coroutine,
    Awaitable, ParamSpec, TypeVar, Literal, TypedDict, Tuple
)

from enum import EnumMeta as EnumType, Enum  # EnumType is only an alias for EnumMeta added in 3.11
from concurrent.futures import Future


# Generic type-alias parameters, declared up front (instead of PEP 695's
# `type X[T] = ...` statement syntax, which is a hard SyntaxError before
# Python 3.12) so this module keeps working down to the project's 3.10 floor.
_P = ParamSpec("_P")
_T = TypeVar("_T")


JsonValue: TypeAlias = Union[
    str, bool, int, float, None,
    List['JsonValue'],
    Dict[str, 'JsonValue'],
    ]

if TYPE_CHECKING:
    Container: TypeAlias = Union[
        Generator[_T, Any, Any], TCollection[_T], Reversible[_T],
        Sequence[_T], AbstractSet[_T], Mapping[_T, Any],
        filter, enumerate, zip]

    ContainerWithoutMapping: TypeAlias = Union[
        Generator[_T, Any, Any], TCollection[_T], Reversible[_T],
        Sequence[_T], AbstractSet[_T], filter, enumerate,
        ]

else:
    Container = Union[
        Generator, TCollection, Reversible,
        Sequence, AbstractSet, Mapping,
        filter, enumerate, zip
        ]
    ContainerWithoutMapping = Union[
        Generator, TCollection, Reversible,
        Sequence, AbstractSet, filter, enumerate,
        ]


NestedContainer = Union[_T, "Container[NestedContainer]"]
NestedStrKeyDict = Dict[str, Union[_T, "NestedStrKeyDict"]]

MaybeCoroutineCallable = Callable[_P, Union[Coroutine[Any, Any, _T], _T]]
# Written out in full (not `MaybeCoroutineCallable[_P, _T]`) because
# substituting into an *already-subscripted* ParamSpec generic nested inside
# another Union is unreliable pre-3.14 -- it raises
# "Expected a list of types, an ellipsis, ParamSpec, or Concatenate".
#
# The Callable[_P, ...] member must also come FIRST in the Union: typing
# collects a Union alias's __parameters__ by scanning members left-to-right,
# so `Union[Awaitable[_T], Callable[_P, ...]]` discovers (_T, _P) -- backwards
# from the `MaybeAwaitable[_P, _T]` subscript order used at call sites, which
# raises the same TypeError (confirmed on 3.12). Callable[_P, ...] first
# discovers (_P, _T), matching the intended subscript order.
MaybeAwaitable = Union[Callable[_P, Union[Coroutine[Any, Any, _T], _T]], Awaitable[_T]]

MaybeContainer = Union[_T, "Container[_T]"]


NotContainer: TypeAlias = Union[bytearray, bytes, str, memoryview, EnumType, Awaitable]
PhoneNumber: TypeAlias = Annotated[str, "Phone number in international format, e.g. +967xxxxxxxxx"]
RegionCode: TypeAlias = Annotated[str, "يجب ان يكون lower وايضا يجب التاكد من صحته"]
Number: TypeAlias = Union[int, float]


_CT = TypeVar("_CT", bound=type)
_FT = TypeVar("_FT", bound=Callable[..., Any])
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_EnumT = TypeVar("_EnumT", bound=Enum)

_True = Literal[True]
_False = Literal[False]


class CountryInfo(TypedDict):
    cc: int
    rc: str
    flag: str
    name: str


WorkTaskInfo: TypeAlias = Tuple[
    Callable[..., Awaitable[Any]],
    Sequence[Any],
    Dict[str, Any], 
    Future
]

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
    "WorkTaskInfo", "Number", 
    "MaybeCoroutineCallable", 
    "MaybeContainer", "JsonValue", 
    "_P", "_T", "_CT", "_FT", 
    "_KT", "_VT", "_True", "_False", 
    "_EnumT", 


)



