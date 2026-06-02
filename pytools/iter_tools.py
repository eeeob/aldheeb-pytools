from typing import (
    List, Set, Union, 
    FrozenSet, Tuple, overload
)


from .typings import Container, NestedContainer, _T
from .validate_tools import is_container




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
def flat_cont(*containers: None) -> List: ...
@overload
def flat_cont(*containers: NestedContainer[_T]) -> List[_T]: ...
def flat_cont(*containers):

    def flat(item):
        r = []

        if is_container(item):
            for i in item:
                r += flat(i)
        elif item is not None:
            r.append(item)

        return r

    result = []

    for item in containers:
        result += flat(item)

    return result









__all__ = (
    "to_list", 
    "to_tuple", 
    "to_set", 
    "flat_cont", 
    "to_frozenset", 
)