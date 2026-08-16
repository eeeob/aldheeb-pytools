from typing import (
    List, Set, Union,
    FrozenSet, Tuple,
    Generator, Any, overload, TypeVar
)


from .typings import Container, NestedContainer, _T
from .validate_tools import is_container

_D = TypeVar("_D")




@overload
def to_list(value: None) -> List: ...
@overload
def to_list(value: Union[_T, 'Container[_T]']) -> List[_T]: ...
def to_list(value: Union[None, _T, 'Container[_T]']):
    if is_container(value):
        return list(value)
    return [value] if value is not None else []

@overload
def to_tuple(value: None) -> Tuple: ...
@overload
def to_tuple(value: Union[_T, 'Container[_T]']) -> Tuple[_T, ...]: ...
def to_tuple(value: Union[None, _T, 'Container[_T]']):
    if is_container(value):
        return tuple(value)
    return (value, ) if value is not None else tuple()

@overload
def to_set(value: None) -> Set: ...
@overload
def to_set(value: Union[_T, 'Container[_T]']) -> Set[_T]: ...
def to_set(value: Union[None, _T, 'Container[_T]']):
    if is_container(value):
        return set(value)
    return {value} if value is not None else set()

@overload
def to_frozenset(value: None) -> FrozenSet: ...
@overload
def to_frozenset(value: Union[_T, 'Container[_T]']) -> FrozenSet[_T]: ...
def to_frozenset(value: Union[None, _T, 'Container[_T]']):
    if is_container(value):
        return frozenset(value)
    return frozenset({value}) if value is not None else frozenset()


@overload
def iter_flat_cont(*containers: None) -> Generator[Any, None, None]: ...
@overload
def iter_flat_cont(*containers: NestedContainer[None]) -> Generator[Any, None, None]: ...
@overload
def iter_flat_cont(*containers: NestedContainer[_T]) -> Generator[_T, None, None]: ...
def iter_flat_cont(*containers):
    for item in containers:
        if is_container(item):
            yield from iter_flat_cont(*item)
        elif item is not None:
            yield item

@overload
def flat_cont(*containers: None) -> List: ...
@overload
def flat_cont(*containers: NestedContainer[None]) -> List: ...
@overload
def flat_cont(*containers: NestedContainer[_T]) -> List[_T]: ...
def flat_cont(*containers):
    return list(iter_flat_cont(*containers))


def pad_list(values: List[_T], length: int, exact: bool = False, default: _D = None) -> List[Union[_T, _D]]:
    """Pad `values` in place to `length`, filling missing positions with
    `default` -- mutates the list itself rather than building a new one, and
    returns it back for convenience.

    `values` shorter than `length` is always padded on the right with
    `default`. Longer is left alone unless `exact=True`, which truncates it
    down to `length` too -- so `length` becomes a hard cap instead of just a
    floor.
    """

    if len(values) < length:
        values.extend([default] * (length - len(values)))
    elif exact and len(values) > length:
        del values[length:]

    return values


__all__ = (
    "to_list",
    "to_tuple",
    "to_set",
    "to_frozenset",
    "iter_flat_cont",
    "flat_cont",
    "pad_list",

)