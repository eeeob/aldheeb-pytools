from typing import (
    Callable, Any, Coroutine, Awaitable, 
    Optional, Protocol, Tuple, Type, 
    TypeAlias, TypeVar, Union,
    overload,
)

from .typings import _T, _P

_ET = TypeVar("_ET")  # middleware(): on_error's return type
_AT = TypeVar("_AT")  # middleware(): after's return type


class _PassthroughMiddlewareDecorator(Protocol):
    """middleware() factory return type, after=None and on_error=None: the
    wrapped func's own return type passes through untouched, so this needs
    no type parameters of its own -- only __call__'s per-application _P/_T.
    """

    # Awaitable-func variant listed first -- see the module-level comment
    # above the middleware() overloads for why order matters here.
    @overload
    def __call__(self, func: Callable[_P, Awaitable[_T]]) -> Callable[_P, Coroutine[Any, Any, _T]]: ...
    @overload
    def __call__(self, func: Callable[_P, _T]) -> Callable[_P, _T]: ...

class _OnErrorMiddlewareDecorator(Protocol[_ET]):
    """middleware() factory return type, on_error given but after=None: the
    result becomes Union[func's own _T, on_error's _ET] -- _ET is fixed by
    the middleware() call itself (hence Protocol[_ET]), _P/_T stay free
    until __call__ is actually applied to a func.
    """

    @overload
    def __call__(self, func: Callable[_P, Awaitable[_T]]) -> Callable[_P, Coroutine[Any, Any, Union[_T, _ET]]]: ...
    @overload
    def __call__(self, func: Callable[_P, _T]) -> Callable[_P, Union[_T, _ET]]: ...

class _AfterMiddlewareDecorator(Protocol[_AT]):
    """middleware() factory return type whenever after is given (with or
    without on_error): after's return value always replaces the result, so
    the shape only depends on _AT -- same reasoning as _OnErrorMiddlewareDecorator.
    """

    @overload
    def __call__(self, func: Callable[_P, Awaitable[_T]]) -> Callable[_P, Coroutine[Any, Any, _AT]]: ...
    @overload
    def __call__(self, func: Callable[_P, _T]) -> Callable[_P, _AT]: ...

_ExcFilter: TypeAlias = Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]]
_ExcLogger: TypeAlias = Union[bool, Callable[[BaseException], Any]]

# SystemExit/KeyboardInterrupt always propagate out of safe_call, unconditionally
# -- there is no override, so exclude_exc can never usefully name them.
_HARD_PROPAGATE = (SystemExit, KeyboardInterrupt)
