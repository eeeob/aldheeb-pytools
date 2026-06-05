from typing import (
    Collection as  TCollection, Generator, Union, Reversible, 
    Sequence, AbstractSet, Mapping, TypeAlias, 
    Any, Dict, Annotated, TYPE_CHECKING, Callable, Coroutine, 
    Awaitable, ParamSpec, TypeVar, Literal, TypedDict, Tuple
)

from enum import EnumType, Enum
from concurrent.futures import Future

if TYPE_CHECKING:
    type Container[I] = Union[
        Generator[I, Any, Any], TCollection[I], Reversible[I], 
        Sequence[I], AbstractSet[I], Mapping[I, Any], 
        filter, enumerate, zip]
    
    type ContainerWithoutMapping[I] = Union[
        Generator[I, Any, Any], TCollection[I], Reversible[I], 
        Sequence[I], AbstractSet[I], filter, enumerate, 
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
    

type NestedContainer[I] = I | "Container[NestedContainer[I]]"

type NestedStrKeyDict[V] = Dict[str, V | NestedStrKeyDict[V]]

type MaybeCoroutineCallable[**P, R] = Callable[P, Coroutine[Any, Any, R] | R]
type MaybeAwaitable[**P, R] = Awaitable[R] | MaybeCoroutineCallable[P, R]

type MaybeContainer[I] = I | "Container[I]"


NotContainer: TypeAlias = Union[bytearray, bytes, str, memoryview, EnumType]
PhoneNumber: TypeAlias = Annotated[str, "Phone number in international format, e.g. +967xxxxxxxxx"]
RegionCode: TypeAlias = Annotated[str, "يجب ان يكون lower وايضا يجب التاكد من صحته"]
Number: TypeAlias = Union[int, float]


_P = ParamSpec("_P")
_T = TypeVar("_T")
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
    "MaybeContainer", 
    "_P", "_T", "_CT", "_FT", 
    "_KT", "_VT", "_True", "_False", 
    "_EnumT", 


)



