from typing import Union, Dict, Any, Mapping, Literal, Tuple, Type, overload
from enum import Enum

from .typings import _T, _KT, _VT, _EnumT, Container, NestedContainer, NestedStrKeyDict
from .errors import ValidationError
from .validate_tools import is_container, is_mapping
from .iter_tools import iter_flat_cont, to_frozenset




def enum_to_value(data: _T) -> _T:
    if isinstance(data, Enum):
        return data.value
    
    elif is_mapping(data):
        return type(data)(enum_to_value(i) for i in data.items())
    
    elif is_container(data):
        return type(data)(enum_to_value(i) for i in data)
    
    else:
        return data


@overload
def value_to_enum(
    values: Mapping[_KT, _VT], 
    enum_classes: NestedContainer[Type[_EnumT]], 
    map_resolve_type: Literal["k", "K"], 
    ) -> Mapping[Union[_KT, _EnumT], _VT]: ...
@overload
def value_to_enum(
    values: Mapping[_KT, _VT], 
    enum_classes: NestedContainer[Type[_EnumT]], 
    map_resolve_type: Literal["v", "V"] = "v", 
    ) -> Mapping[_KT, Union[_EnumT, _VT]]: ...
@overload
def value_to_enum(
    values: 'Container[ _T]', 
    enum_classes: NestedContainer[Type[_EnumT]], 
    ) -> 'Container[Union[_EnumT, _T]]': ...
@overload
def value_to_enum(
    values: _T, 
    enum_classes: NestedContainer[Type[_EnumT]], 
    ) -> Union[_EnumT, _T]: ...
def value_to_enum(
    values: Any,
    enum_classes: NestedContainer[Type[_EnumT]],
    map_resolve_type = "v"
    ):
    """Recursively replace raw values with their matching enum member,
    wherever one of `enum_classes` has a member with that value.

    `enum_map` is built once from every class's `_value2member_map_` (the
    private dict Enum itself maintains for `SomeEnum(value)` lookups), so
    later classes in `enum_classes` silently win over earlier ones on a
    value collision. Values with no matching member pass through unchanged
    -- this is a best-effort convert, not a validating one.

    For a mapping, `map_resolve_type` picks which side gets converted:
    `"k"` converts keys and leaves values alone, `"v"` (default) converts
    values and leaves keys alone. Containers/mappings are rebuilt with
    `type(v)(...)` so the original container type is preserved.
    """

    map_resolve_type = map_resolve_type.lower()

    if map_resolve_type not in ("v", "k"):
        raise ValidationError(f"map_resolve_type must be k or v not {map_resolve_type}")

    enum_map = {}

    for enum_cls in to_frozenset(iter_flat_cont(enum_classes)):
        enum_map.update(enum_cls._value2member_map_)

    def convert(v):

        if is_mapping(v):
            

            return (
                type(v)((convert(k), i) for k, i in v.items()) 
                if map_resolve_type == "k" 
                else type(v)((k, convert(i)) for k, i in v.items())
            )

        elif is_container(v):
            return type(v)(convert(i) for i in v)

        return enum_map.get(v, v)

    return convert(values)

def clean_none_values(data: _T) -> _T:
    if is_mapping(data):
        return type(data)(
            (k, clean_none_values(v)) 
            for k, v in data.items() 
            if v is not None
            )
    
    elif is_container(data):
        return type(data)(clean_none_values(i) for i in data)
    
    return data

def clean_none_kw(**kwargs) -> Dict[str, Any]:
    return clean_none_values(kwargs)


def get_nested_dict_value(dct: NestedStrKeyDict[_T], path: str, sep: str = ".") -> _T:
    for key in path.split(sep):
        dct = dct[key]
    return dct

def get_nested_dict_key(path_dct: NestedStrKeyDict[Literal[True, 1]], sep: str = ".") -> str:
    """Inverse of get_nested_dict_value(): given a single-branch nested dict
    that marks one path with a leaf of `True`/`1` (e.g. `{"a": {"b": True}}`),
    return that path joined by `sep` (`"a.b"`).

    NOTE: the leaf-value check below (`value != 1: value = value.numerator`)
    only rejects non-numeric leaves -- `.numerator` raises AttributeError for
    those, but for any *other* number (e.g. a leaf of `2`) `.numerator`
    succeeds and its result is discarded, so an invalid leaf like `2` is
    silently accepted instead of rejected. This looks like leftover/incomplete
    validation rather than intended behavior; flagging here rather than
    silently treating it as correct.
    """

    def flatten(current_dict: NestedStrKeyDict[Literal[True, 1]], current_path: str = "") -> Tuple[str, Literal[1]]:
        key, value = next(iter(current_dict.items()))

        new_path = f"{current_path}{sep}{key}" if current_path else key

        if isinstance(value, dict):
            return flatten(value, new_path)

        if value != 1:
            value = value.numerator
        
        return new_path
    
    if len(path_dct) != 1:
        raise TypeError(f"len nested dict must be 1 not {len(path_dct)}")
    
    return flatten(path_dct)


    
__all__ = (
    "enum_to_value", 
    "clean_none_values", 
    "value_to_enum", 
    "clean_none_kw", 
    "get_nested_dict_value", 
    "get_nested_dict_key", 

)