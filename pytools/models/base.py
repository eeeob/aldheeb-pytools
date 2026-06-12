from typing import (
    Dict, Self, Any, ClassVar, List, FrozenSet, 
    get_args, get_type_hints
)

from enum import EnumType
from dataclasses import dataclass, fields, asdict, is_dataclass

from ..classes import FrozenClassAttrs
from ..data_tools import clean_none_values, enum_to_value, value_to_enum
from ..iter_tools import to_frozenset, flat_cont
    

import json



@dataclass
class BaseDataClass(FrozenClassAttrs):
    __public_field_names__: ClassVar[List[str]]
    __private_field_names__: ClassVar[List[str]] 
    __raw_private_fields__: ClassVar[FrozenSet[str]]
    __enums_types__: ClassVar[FrozenSet[EnumType]]

    def __init_subclass__(cls, **_):
        if not is_dataclass(cls):
            raise TypeError(
                f"{cls.__name__} must be dataclass"
            )
        
        cls.__public_field_names__ = public = []
        cls.__private_field_names__ = private = []

        
        cls.__enums_types__ = to_frozenset(
            flat_cont(
                (get_args(t) or t) 
                for t in get_type_hints(cls).values()
                if any(isinstance(st, EnumType) for st in to_frozenset(get_args(t) or t))
                )
            )

        for f in fields(cls):
            name = f.name
            pname = name.lstrip("_")

            if name.startswith("_"):
                private.append(pname)

                if not hasattr(cls, pname):
                    prop = property(
                        fget=lambda self, _n=name: getattr(self, _n),
                        fset=lambda self, value, _n=name: setattr(self, _n, value),
                        fdel=lambda self, _n=name: delattr(self, _n),
                    )

                    setattr(cls, pname, prop)
            
            else:
                public.append(name)
        
        cls.__raw_private_fields__ = frozenset(f"_{n}" for n in private)
    
    def to_raw_dict(
        self, 
        without_none_values: bool = False, 
        enums_to_values: bool = False, 
        ) -> Dict[str, Any]:

        dct = asdict(self)

        if without_none_values:
            dct = clean_none_values(dct)
        if enums_to_values:
            dct = enum_to_value(dct)

        return dct

    def to_dict(
        self, 
        without_none_values: bool = False, 
        enums_to_values: bool = False, 
        ) -> Dict[str, Any]:

        dct = (
            {name: getattr(self, name) for name in self.__class__.__public_field_names__} | 
            {name: getattr(self, name) for name in self.__class__.__private_field_names__}
        )

        if without_none_values:
            dct = clean_none_values(dct)
        if enums_to_values:
            dct = enum_to_value(dct)

        return dct
        
    @classmethod
    def from_raw_dict(
        cls, 
        data: dict, 
        without_none_values: bool = False, 
        values_to_enums: bool = False, 
        ) -> Self:

        _private = cls.__raw_private_fields__
        _public = cls.__public_field_names__
        data = {
            k: v for k, v in data.items() 
            if k in _private or k in _public
            }

        if without_none_values:
            data = clean_none_values(data)
        
        if values_to_enums and cls.__enums_types__:
            data = value_to_enum(data, cls.__enums_types__, True)
        
        return cls(**data)
    
    @classmethod
    def from_dict(
        cls, 
        data: dict, 
        without_none_values: bool = False, 
        values_to_enums: bool = False, 
        ) -> Self:

        _private = cls.__private_field_names__
        _public = cls.__public_field_names__

        data = {
            k: v for k, v in data.items() 
            if k in _private or k in _public
            }

        for name in cls.__private_field_names__:
            if name in data:
                data[f"_{name}"] = data.pop(name)


        if without_none_values:
            data = clean_none_values(data)

        if values_to_enums and cls.__enums_types__:
            data = value_to_enum(data, cls.__enums_types__, True)

        
        return cls(**data)
    
    def copy(self) -> Self:
        return self.__class__.from_raw_dict(self.to_raw_dict())
    
    def __str__(self):
        return json.dumps(self.to_dict(True, True), indent=4, ensure_ascii=False, default=str)



__all__ = (
    "BaseDataClass", 
)