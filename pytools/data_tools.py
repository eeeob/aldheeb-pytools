from typing import Union, Dict, Any, Mapping, Literal, Tuple, Type, overload
from enum import Enum

from .typings import _T, _KT, _VT, _EnumT, Container, NestedContainer, NestedStrKeyDict
from .errors import ValidationError
from .validate_tools import is_container, is_mapping
from .iter_tools import flat_cont, to_frozenset




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

    map_resolve_type = map_resolve_type.lower()

    if map_resolve_type not in ("v", "k"):
        raise ValidationError(f"map_resolve_type must be k or v not {map_resolve_type}")

    enum_map = {}

    for enum_cls in to_frozenset(flat_cont(enum_classes)):
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