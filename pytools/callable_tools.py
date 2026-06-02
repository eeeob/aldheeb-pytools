from typing import Callable, Any, Coroutine, Awaitable, Hashable, Optional, Union, overload

from .typings import NestedContainer, _T, _P, _FT, _True
from .validate_tools import iscoroutinefunction_wrapped
from .iter_tools import flat_cont, to_frozenset

import functools


@overload
def safe_call(func: Callable[_P, _T], *args: _P.args, **kwargs: _P.kwargs) -> Optional[_T]: ...
@overload
def safe_call(func: Callable[_P, _T], *args: _P.args, return_exc: _True, **kwargs: _P.kwargs) -> Union[_T, BaseException]: ...
def safe_call(func, *args, return_exc = False, **kwargs):
    try:
        return func(*args, **kwargs)
    except BaseException as e:
        if return_exc:
            return e

def raise_if(
    exc: Union[BaseException, Callable[[], BaseException]], 
    bool_value: Optional[bool] = None, 
    values: Optional["NestedContainer[Hashable]"] = None 
    ):

    values = to_frozenset(flat_cont(values))

    @overload
    def decorator(func: Callable[_P, Awaitable[_T]]) -> Callable[_P, Coroutine[Any, Any, _T]]: ...
    @overload
    def decorator(func: Callable[_P, _T]) -> Callable[_P, _T]: ...
    def decorator(func):
        if iscoroutinefunction_wrapped(func):
            @functools.wraps(func)
            async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs):
                result = await func(*args, **kwargs)
                
                if result in values or (bool_value is not None and bool(result) == bool_value):
                    raise exc() if callable(exc) else exc
                
                return result
            
            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs):
            result = func(*args, **kwargs)

            if result in values or (bool_value is not None and bool(result) == bool_value):
                raise exc() if callable(exc) else exc
            
            return result
        
        return sync_wrapper

    return decorator

async def await_sync(
    func: Callable[_P, _T],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
    ) -> _T:
    
    return func(*args, **kwargs)


def to_coroutine(func: Callable[_P, _T]) -> Callable[_P, Coroutine[Any, Any, _T]]:
    return functools.partial(
        await_sync, func
    )


@overload
def set_func_attrs(func: _FT, **kw: Any) -> _FT: ...
@overload
def set_func_attrs(func: None = None, **kw: Any) -> Callable[[_FT], _FT]: ...
def set_func_attrs(func = None, **kw):
    def updater(f: _FT) -> _FT:
        for k, v in kw.items():
            setattr(f, k, v)

        return f

    if func is None:
        return updater

    return updater(func)




__all__ = (
    "safe_call", 
    "raise_if", 
    "await_sync", 
    "set_func_attrs", 
    "to_coroutine", 

)