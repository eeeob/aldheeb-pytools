from typing import (
    Callable, Any, Coroutine, Awaitable, Hashable,
    Optional, Tuple, Type, TypeAlias, Union, overload,
)

from .typings import NestedContainer, _T, _P, _FT, _True, _False, _ExcT
from .validate_tools import iscoroutinefunction_wrapped
from .iter_tools import iter_flat_cont, to_frozenset
from .async_tools import run_awaitable_in_coro
from ._async_tools import _get_running_loop

import asyncio
import functools
import logging


log = logging.getLogger(__name__)


_ExcFilter: TypeAlias = Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]]
_ExcLogger: TypeAlias = Union[bool, Callable[[BaseException], Any]]

# SystemExit/KeyboardInterrupt always propagate out of safe_call, unconditionally
# -- there is no override, so exclude_exc can never usefully name them.
_HARD_PROPAGATE = (SystemExit, KeyboardInterrupt)


@overload
def safe_call(
    func: Callable[_P, _T],
    *args: _P.args,
    include_exc: _ExcFilter = None,
    exclude_exc: _ExcFilter = None,
    log_exc: _ExcLogger = False,
    **kwargs: _P.kwargs,
) -> Optional[_T]: ...
@overload
def safe_call(
    func: Callable[_P, _T],
    *args: _P.args,
    return_exc: _False,
    include_exc: _ExcFilter = None,
    exclude_exc: _ExcFilter = None,
    log_exc: _ExcLogger = False,
    **kwargs: _P.kwargs,
) -> Optional[_T]: ...
@overload
def safe_call(
    func: Callable[_P, _T],
    *args: _P.args,
    return_exc: _True,
    include_exc: Type[_ExcT],
    exclude_exc: _ExcFilter = None,
    log_exc: _ExcLogger = False,
    **kwargs: _P.kwargs,
) -> Union[_T, _ExcT]: ...
@overload
def safe_call(
    func: Callable[_P, _T],
    *args: _P.args,
    return_exc: _True,
    include_exc: Tuple[Type[_ExcT], ...],
    exclude_exc: _ExcFilter = None,
    log_exc: _ExcLogger = False,
    **kwargs: _P.kwargs,
) -> Union[_T, _ExcT]: ...
@overload
def safe_call(
    func: Callable[_P, _T],
    *args: _P.args,
    return_exc: _True,
    include_exc: _ExcFilter = None,
    exclude_exc: _ExcFilter = None,
    log_exc: _ExcLogger = False,
    **kwargs: _P.kwargs,
) -> Union[_T, BaseException]: ...
def safe_call(func, *args, return_exc = False, include_exc = None, exclude_exc = None, log_exc = False, **kwargs):
    """Call `func(*args, **kwargs)`, swallowing whatever it raises.

    Returns None on failure, or the exception itself when `return_exc=True`.

    `include_exc` narrows what is swallowed to those classes; anything else
    propagates. `exclude_exc` names what must always propagate, and wins over
    `include_exc` when both match -- so `include_exc=OSError,
    exclude_exc=FileNotFoundError` swallows every OSError but that one. Each
    takes a single class or a tuple of them, exactly like `except`.

    `log_exc` fires only for an exception that ends up actually swallowed
    (after `include_exc`/`exclude_exc` have let it through) -- one that
    propagates was never "handled" here, so nothing is logged for it.
    Pass `True` to log it via this module's logger (with traceback, at
    ERROR level); pass a callable to receive the exception instead and
    decide yourself what to do with it. An exception raised by that
    callable is not caught -- it propagates out of safe_call as-is.

    SystemExit and KeyboardInterrupt always propagate, unconditionally --
    neither can be swallowed, and there is no way to opt back in via
    `include_exc`. Naming either of them (or a subclass) in `exclude_exc` is
    redundant and raises TypeError immediately, before `func` is even called.
    """

    if exclude_exc is not None:
        for exc_type in exclude_exc if isinstance(exclude_exc, tuple) else (exclude_exc,):
            if issubclass(exc_type, _HARD_PROPAGATE):
                raise TypeError(
                    f"exclude_exc: {exc_type.__name__} always propagates already -- "
                    "no need to list it"
                )

    try:
        return func(*args, **kwargs)
    except _HARD_PROPAGATE:
        raise
    except BaseException as e:
        if exclude_exc is not None and isinstance(e, exclude_exc):
            raise

        if include_exc is not None and not isinstance(e, include_exc):
            raise

        if log_exc:
            if callable(log_exc):
                try:
                    log_exc(e)
                except BaseException as le:
                    raise le from e
            else:
                log.error("error in safe_call(%r)" % (func,), exc_info=e)

        if return_exc:
            return e

def raise_if(
    exc: Union[BaseException, Callable[[], BaseException]], 
    bool_value: Optional[bool] = None, 
    values: Optional["NestedContainer[Hashable]"] = None,
    always: bool = False,
    ):

    if always and (bool_value is not None or values is not None):
        raise ValueError("raise_if: can't pass bool_value or values when always=True")

    values = to_frozenset(iter_flat_cont(values))

    @overload
    def decorator(func: Callable[_P, Awaitable[_T]]) -> Callable[_P, Coroutine[Any, Any, _T]]: ...
    @overload
    def decorator(func: Callable[_P, _T]) -> Callable[_P, _T]: ...
    def decorator(func):
        if iscoroutinefunction_wrapped(func):
            @functools.wraps(func)
            async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs):
                result = await func(*args, **kwargs)
                
                if always or result in values or (bool_value is not None and bool(result) == bool_value):
                    raise exc() if callable(exc) else exc
                
                return result
            
            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs):
            result = func(*args, **kwargs)

            if always or result in values or (bool_value is not None and bool(result) == bool_value):
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
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await await_sync(func, *args, **kwargs)

    return wrapper


def run_awaitable_sync(
    awaitable: Awaitable[_T],
    loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> _T:
    """Run an awaitable to completion from synchronous code and return its result.

    If `loop` is omitted, a fresh event loop is created, driven, and torn down
    for this call only (via asyncio.run()) -- each call gets its own loop. To
    run multiple awaitables against one persistent, reusable loop instead, use
    classes.LoopRunner.

    If `loop` is given, it must already be running in another thread (e.g. one
    started with `threading.Thread(target=loop.run_forever)`); the awaitable
    is submitted to it and this call blocks until it completes. An idle loop
    is rejected rather than driven directly, since doing so here could race
    with another thread starting that same loop concurrently. Calling this
    with `loop` set to the loop already running in the calling thread raises
    instead of deadlocking that loop.
    """

    if loop is not None:
        if loop.is_closed():
            raise RuntimeError("cannot use a closed event loop")

        if not loop.is_running():
            raise RuntimeError(
                "the given event loop is not running -- driving an idle loop "
                "directly here risks a conflict with another thread starting it "
                "at the same time; start the loop in its own thread first, or "
                "pass loop=None to let this call create and own a fresh loop"
            )

    if (running_loop := _get_running_loop()) is not None:
        if loop is None:
            raise RuntimeError(
                "an event loop is already running in the calling thread, so a "
                "new loop cannot be created and driven here -- pass an explicit "
                "`loop` that is running in another thread"
            )

        if loop is running_loop:
            raise RuntimeError(
                "cannot target the event loop already running in the calling "
                "thread -- blocking here to wait for it would deadlock that "
                "same loop"
            )

    
    coro = awaitable if asyncio.iscoroutine(awaitable) else run_awaitable_in_coro(awaitable)

    if loop is None:
        return asyncio.run(coro)

    return asyncio.run_coroutine_threadsafe(coro, loop).result()


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


@overload
def call_all(*funcs: Callable[[], _T], lazy: _False = False) -> Tuple[_T, ...]: ...
@overload
def call_all(*funcs: Callable[[], _T], lazy: _True) -> Callable[[], Tuple[_T, ...]]: ...
def call_all(*funcs: Callable[[], _T], lazy: bool = False):
    """Call every zero-argument callable in `funcs`, in order, and return
    their results as a tuple in that same order.

    Each call happens synchronously, one after another -- a callable that
    raises stops the rest from ever running, same as writing out
    `(func1(), func2(), ...)` by hand.

    `lazy=True` defers all of that -- `funcs` are only captured, not called
    yet -- and returns a zero-argument callable that runs this same call_all
    over them once it's eventually invoked.
    """

    if lazy:
        return functools.partial(call_all, *funcs)

    return tuple(func() for func in funcs)


def ignore_arguments(func: Callable[[], _T]) -> Callable[..., _T]:
    """
    Return a wrapper that ignores all positional and keyword arguments before
    calling *func*.

    Example:
        callback = ignore_arguments(cleanup)
        callback(1, 2, x=3)  # Calls cleanup()
    """

    @functools.wraps(func)
    def wrapper(*_: Any, **__: Any) -> _T:
        return func()

    return wrapper


@overload
def return_constant(
    func: Callable[_P, Any], 
    *, 
    value: _T = None, 
) -> Callable[_P, _T]: ...
@overload
def return_constant(
    func: None, 
    *, 
    value: _T = None, 
) -> Callable[[Callable[_P, Any]], Callable[_P, _T]]: ...
def return_constant(
    func: Optional[Callable[_P, Any]] = None, 
    *, 
    value: _T = None, 
):
    """
    Wrap a callable so it always returns ``value`` after execution.

    Can be used either directly::

        wrapped = return_constant(func, value=True)

    or as a decorator::

        @return_constant(value=True)
        def func():
            ...
    """

    if func is None:
        return functools.partial(return_constant, value=value)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> _T:
        func(*args, **kwargs)
        return value

    return wrapper



__all__ = (
    "safe_call", 
    "raise_if", 
    "await_sync", 
    "set_func_attrs", 
    "to_coroutine", 
    "run_awaitable_sync", 
    "ignore_arguments",
    "return_constant",
    "call_all",

)