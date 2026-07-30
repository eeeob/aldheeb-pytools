from typing import (
    Any, Awaitable, Callable, TYPE_CHECKING,
    Coroutine, Dict, Optional, Generic, Set,
    overload, Type, TypeVar,
)

from types import MethodType
from functools import partial
from datetime import datetime, timezone, timedelta
from concurrent.futures import Future, InvalidStateError

try:
    from pymongo import IndexModel
except ImportError:
    HAS_PYMONGO = False
else:
    HAS_PYMONGO = True

from ._optional import _unavailable_class

from .typings import _KT, _VT, _T, _P
from .async_tools import to_thread
from .callable_tools import run_awaitable_sync

import weakref
import logging
import threading
import asyncio
import sys
import time
import warnings

_C = TypeVar("_C")

class classproperty(Generic[_C, _T]):
    @overload
    def __new__(
        cls,
        fget: Callable[[Type[_C]], _T],
        *,
        doc: Optional[str] = None,
        cached: bool = False
    ) -> "classproperty[_C, _T]": ...
    @overload
    def __new__(
        cls,
        fget: None = None,
        *,
        doc: Optional[str] = None, 
        cached: bool = False 
    ) -> Callable[
        [Callable[[Type[_C]], _T]], "classproperty[_C, _T]"
        ]: ...
    def __new__(cls, fget = None, *, doc = None, cached = False): 
        if fget is None:
            return partial(cls, doc=doc, cached=cached)

        return super().__new__(cls)

    def __init__(
        self, 
        fget: Callable[[Type[_C]], _T], 
        *, 
        doc: Optional[str] = None, 
        cached: bool = False 
    ) -> None:
        
        self.fget = fget
        self.cached = cached
        self._cache: Dict[Type[_C], _T] = {}

        if doc is None:
            doc = fget.__doc__

        self.__doc__ = doc

    @overload
    def __get__(self, _: Any, owner: None) -> "classproperty[_C, _T]": ...
    @overload
    def __get__(self, _: Any, owner: Type[_C]) -> _T: ...
    def __get__(self, _, owner):
        if owner is None:
            return self

        if not self.cached:
            return self.fget(owner)

        try:
            return self._cache[owner]
        except KeyError:
            value = self.fget(owner)
            self._cache[owner] = value
            return value



if TYPE_CHECKING:
    hybridmethod = classmethod
else:
    class hybridmethod(classmethod):
        def __get__(self, instance, owner = None, /):
            if instance is not None:
                owner = instance

            return MethodType(self.__func__, owner)

class FrozenClassAttrs:
    def __setattr__(self, name, value):
        if hasattr(self.__class__, name):
            raise AttributeError(
                f"Cannot override class attribute '{name}' from instance"
            )
        super().__setattr__(name, value) 
 
class KeyDefaultDict(Dict[_KT, _VT]):
    def __init__(self, default_factory: Callable[[_KT], _VT]) -> None:
        super().__init__()
        self.default_factory = default_factory

    def __missing__(self, key: _KT) -> _VT:
        value = self.default_factory(key)
        self[key] = value
        return value
    
    def __call__(self, key: _KT) -> _VT:
        return self[key]


class AioThreadWorker:
    """Runs coroutine functions on a private event loop in its own thread.

    Every submission goes straight onto that loop via
    asyncio.run_coroutine_threadsafe(), so submit() is safe to call from any
    thread -- including threads with no event loop of their own -- and returns
    an awaitable handle (see _WorkFuture) that can be awaited from whichever
    loop is running when it is awaited, or read synchronously via .result().

    A worker owns exactly one thread for its whole lifetime: once that thread
    ends the worker is finished for good and a new instance is needed.

    `concurrency` caps how many submissions execute at once (0 or less means
    unlimited). Note that submissions above the cap are already live tasks
    parked on a semaphore inside the loop, not entries in an external queue.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        concurrency: int = 0,
        loop_factory = None,
        exception_handler = None,
        run_now: bool = True,
        ):

        if not isinstance(concurrency, int):
            raise TypeError(
                f"concurrency must be an int, got {type(concurrency).__name__!r}"
            )

        if loop_factory is not None and not callable(loop_factory):
            raise TypeError(
                f"loop_factory must be callable, got {type(loop_factory).__name__!r}"
            )

        if exception_handler is not None and not callable(exception_handler):
            raise TypeError(
                f"exception_handler must be callable, "
                f"got {type(exception_handler).__name__!r}"
            )

        # asyncio.run() only gained loop_factory in 3.12, not 3.11.
        if sys.version_info < (3, 12) and loop_factory is not None:
            warnings.warn(
                "loop_factory is ignored on Python < 3.12 "
                "(asyncio.run() has no loop_factory parameter there); "
                "falling back to a plain asyncio.run()",
                stacklevel=2,
            )

        self.__name = name
        self.__concurrency = concurrency
        self.__loop_factory = loop_factory
        self.__exception_handler = exception_handler

        # The thread is created in run(), not here, so nothing is spawned until
        # the worker is actually started.
        self.__thread: Optional[threading.Thread] = None

        self.__loop: Optional[asyncio.AbstractEventLoop] = None
        # Reentrant: __forget_pending() takes this lock from a future callback
        # that may fire on whichever thread completes the future.
        self.__lock = threading.RLock()

        self.__running = threading.Event()
        self.__stopping = threading.Event()

        # Submitted-but-unfinished handles, guarded by __lock. Only used to fail
        # them loudly if the loop dies with work still outstanding.
        self.__pending: Set["Future[Any]"] = set()

        # All three live on the worker's loop and are only touched from it.
        self.__tasks: Optional[Set["asyncio.Task[Any]"]] = None
        self.__slots: Optional[asyncio.Semaphore] = None
        self.__drain: Optional[asyncio.Event] = None
        

        if run_now:
            self.run()

    def __bootstrap(self) -> None:
        if threading.current_thread() is not self.__thread:
            raise RuntimeError("Bootstrap must be called from the worker thread")

        try:
            if sys.version_info < (3, 12):
                asyncio.run(self.__worker())
            else:
                loop_factory = self.__loop_factory
                del self.__loop_factory
                asyncio.run(self.__worker(), loop_factory=loop_factory)
        finally:
            self.__running.clear()

            self.__tasks = None
            self.__slots = None
            self.__drain = None

            with self.__lock:
                pending = tuple(self.__pending)
                self.__pending.clear()
    
            for handle in pending:
                try:
                    handle.set_exception(
                        RuntimeError(
                            "AioThreadWorker stopped before this task completed"
                        )
                    )
                except InvalidStateError:
                    pass

    async def __worker(self) -> None:
        loop = asyncio.get_running_loop()

        exception_handler = self.__exception_handler
        
        if exception_handler is not None:
            loop.set_exception_handler(exception_handler)

        del self.__exception_handler, exception_handler

        # asyncio primitives bind to the loop that first uses them, so they
        # are built here, on the worker's own loop.
        self.__tasks = set()
        self.__drain = asyncio.Event()
        self.__slots = (
            asyncio.Semaphore(self.__concurrency)
            if self.__concurrency > 0
            else None
        )

        del self.__concurrency

        # published last: a non-None __loop is what marks setup complete
        self.__loop = loop
        self.__running.set()

        if not self.is_stopping():
            await self.__drain.wait()

        # Everything submitted is tracked in __tasks -- including tasks still
        # parked on the semaphore -- so gathering until the set is empty drains
        # all of it. Re-checked in a loop because draining work may itself
        # schedule more work on this loop.
        while self.__tasks:
            await asyncio.gather(*self.__tasks, return_exceptions=True)

    async def __run_task(
        self,
        coro: "Coroutine[Any, Any, _T]",
        holder: "list[Future[_T]]",
        ) -> _T:

        task = asyncio.current_task()

        # Captured once: __bootstrap nulls these during teardown, and a task
        # scheduled just before that must still untrack itself from the very
        # set it registered in.
        tasks = self.__tasks
        slots = self.__slots

        if tasks is not None:
            tasks.add(task)

        # Reporting has to happen from a done callback rather than from an
        # `except` inside this coroutine: call_exception_handler() re-enters the
        # failing task's own contextvars.Context to invoke a custom handler
        # (3.12+), which raises "cannot enter context: ... is already entered"
        # while that context is still the one executing. A done callback runs
        # after the task's step has left it.
        task.add_done_callback(partial(self.__report_undelivered, holder))

        try:
            if slots is None:
                return await coro

            # Semaphore rather than a condition/counter pair: release() is
            # synchronous, so the slot is given back even while the task is
            # being cancelled -- an awaited release could be interrupted and
            # leak the slot forever.
            try:
                await slots.acquire()
            except:
                coro.close()
                raise

            try:
                return await coro
            finally:
                slots.release()
        finally:
            if tasks is not None:
                tasks.discard(task)

    @staticmethod
    def __report_undelivered(
        holder: "list[Future[Any]]",
        task: "asyncio.Task[Any]",
        ) -> None:

        if task.cancelled():
            return

        # Retrieving the exception is also what clears the flag behind asyncio's
        # contextless "Task exception was never retrieved" report.
        exc = task.exception()

        if exc is None:
            return

        handle = holder[0] if holder else None

        # Delivered to the caller as usual -- nothing to add. `holder` being
        # empty can only mean submit() had not stored the handle yet, which
        # implies it was still pending, so delivery worked.
        if handle is None or not handle.cancelled():
            return

        # A cancelled handle means the caller already received CancelledError,
        # so this failure -- raised while the work unwound, typically by cleanup
        # in a finally -- can never reach them. Cancellation stays the outcome
        # they see; the error is surfaced here instead of vanishing.
        task.get_loop().call_exception_handler({
            "message": (
                "AioThreadWorker: submitted work raised while being cancelled, "
                "so its caller received CancelledError and never saw this "
                "exception"
            ),
            "exception": exc,
            "task": task,
        })

    # ---------------- state ----------------

    def is_started(self) -> bool:
        return self.__thread is not None
    
    def is_running(self) -> bool:
        thread = self.__thread

        return (
            thread is not None
            and thread.is_alive()
            and self.__running.is_set()
        )

    def is_stopping(self) -> bool:
        return self.__stopping.is_set()

    def is_finished(self) -> bool:
        """Whether the worker's single thread has run and ended for good."""
        thread = self.__thread

        return thread is not None and not thread.is_alive()

    def get_loop(self) -> asyncio.AbstractEventLoop:
        loop = self.__loop

        if loop is None or not self.is_running():
            raise RuntimeError("Worker not running")

        return loop

    # ---------------- lifecycle ----------------

    def run(self, wait: Optional[float] = None) -> None:
        with self.__lock:
            # checked before is_stopping(): a worker that ran and was joined has
            # both flags set, and "finished" is the more informative message.
            if self.is_started():
                raise RuntimeError(
                    "Already Running"
                    if self.__thread.is_alive()
                    else
                    "worker is finished -- a worker owns a single thread for "
                    "its whole lifetime and cannot be restarted; create a new "
                    "AioThreadWorker instead"
                )

            if self.is_stopping():
                raise RuntimeError(
                    "worker has already been asked to stop and cannot be "
                    "started; create a new AioThreadWorker instead"
                )

            thread = threading.Thread(
                target=self.__bootstrap,
                name=self.__name,
                daemon=True,
            )

            del self.__name

            self.__thread = thread
            thread.start()

        deadline = None if wait is None else time.monotonic() + wait

        # Polled rather than one blocking wait so a thread dying during startup
        # is reported instead of hanging the caller forever.
        while not self.__running.wait(0.005):
            if not thread.is_alive():
                raise RuntimeError(
                    "worker thread died during startup -- see the traceback "
                    "reported by threading.excepthook for the cause"
                )

            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"worker did not start within {wait!r} seconds"
                )

    async def join(self, timeout: Optional[float] = None) -> None:
        if asyncio.get_running_loop() is self.__loop:
            raise RuntimeError(
                "cannot join from inside the worker's own event loop -- the "
                "calling task is itself in-flight work, so waiting for the "
                "worker to drain here would deadlock"
            )

        was_stopping = False
        
        with self.__lock:
            if self.is_stopping():
                was_stopping = True

            if not was_stopping:
                self.__stopping.set()
            
            if not self.is_started():
                return

            if not was_stopping and self.__drain is not None and not self.__loop.is_closed():
                self.__loop.call_soon_threadsafe(self.__drain.set)

            thread = self.__thread

        if not thread.is_alive():
            return

        # The worker drains its own tasks before returning, so waiting for the
        # thread covers both the drain and the loop teardown.
        if timeout is None:
            await to_thread(thread.join)
            return

        await to_thread(thread.join, timeout)

        if thread.is_alive():
            raise TimeoutError(
                f"worker did not stop within {timeout!r} seconds"
            )

    def __await__(self):
        return self.join().__await__()

    # ---------------- submission ----------------

    async def submit(
        self,
        func: Callable[_P, Coroutine[Any, Any, _T]],
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
        ) -> _T:
        """Schedule `func(*args, **kwargs)` on the worker's loop.

        `func` must be a coroutine function; calling it here only builds a
        coroutine object, which touches no event loop and is therefore safe
        from any thread. Returns an awaitable handle.
        """

        coro = func(*args, **kwargs)

        if not asyncio.iscoroutine(coro):
            raise TypeError(
                f"func must be a coroutine function; calling it returned "
                f"{type(coro).__name__!r}"
            )

        with self.__lock:
            try:
                if not self.is_running():
                    raise RuntimeError("worker is closed")

                if self.is_stopping():
                    raise RuntimeError("worker is stopping")
            except RuntimeError:
                coro.close()
                raise

            

            # Lets __report_undelivered see whether the outcome reached the
            # caller; filled right after, since the handle only exists once
            # run_coroutine_threadsafe returns.
            holder: "list[Future[_T]]" = []

            handle = asyncio.run_coroutine_threadsafe(
                self.__run_task(coro, holder), self.__loop
            )

            holder.append(handle)

            self.__pending.add(handle)

        try:
            return await asyncio.wrap_future(handle)
        finally:
            with self.__lock:
                self.__pending.discard(handle)

    __call__ = submit


if HAS_PYMONGO:
    class MongoIndex(IndexModel):
        @classmethod
        def from_dict(cls, dct: Dict[str, Any]):
            dct.pop("v", None)
            dct.pop("name", None)

            return cls(dct.pop("key"), **dct)
        
        @property
        def name(self):
            return self.document["name"]
        
        @property
        def key(self):
            return "_".join(self.document["key"].keys())

        def __hash__(self):
            return hash(repr(self))
        
        def __eq__(self, other):
            if not isinstance(other, MongoIndex):
                raise NotImplementedError
            return repr(self) == repr(other)
else:
    MongoIndex = _unavailable_class("MongoIndex", ("pymongo", "mongo"))


class KeyDefaultWeakValueDict(weakref.WeakValueDictionary[_KT, _VT]):
    def __init__(self, default_factory: Callable[[_KT], _VT]) -> None:
        if not callable(default_factory):
            raise TypeError("default_factory must be callable")
        
        super().__init__()

        self.default_factory = default_factory

    def __getitem__(self, key: _KT) -> _VT:
        try:
            return super().__getitem__(key)
        except KeyError:
            value = self.default_factory(key)
            self[key] = value
            return value
    
    __call__ = __getitem__


class DefaultWeakValueDict(KeyDefaultWeakValueDict[_KT, _VT]):
    def __init__(self, default_factory: Callable[[], _VT]) -> None:
        if not callable(default_factory):
            raise TypeError("default_factory must be callable")

        def wrapper(_: _KT) -> _VT:
            return default_factory()

        super().__init__(wrapper)




class SyncAwaitableRunner:
    """Owns a background thread running a persistent asyncio event loop, and
    lets synchronous code submit awaitables to run on it via run_awaitable_sync().

    Unlike calling run_awaitable_sync() with no `loop` (which creates and tears
    down a fresh loop per call via asyncio.run()), a SyncAwaitableRunner keeps a
    single loop alive across every .run() call, so state bound to that loop
    (tasks, connections, etc.) persists between calls.

    >>> with SyncAwaitableRunner() as runner:
    ...     runner.run(coro_one())
    ...     runner.run(coro_two())

    Pass `lazy=True` to defer creating the loop and its thread until the first
    .run() call, instead of at construction time.
    """


    def __init__(self, name: Optional[str] = None, lazy: bool = False) -> None:
        self.__name = name
        self.__loop: Optional[asyncio.AbstractEventLoop] = None
        self.__thread: Optional[threading.Thread] = None
        self.__closed = False
        self.__start_lock = threading.Lock()

        if not lazy:
            self.__ensure_started()

    def __ensure_started(self) -> None:
        if self.__closed:
            raise RuntimeError(f"{self.__class__.__name__} is closed")

        if self.__thread is not None:
            return

        with self.__start_lock:
            if self.__closed:
                raise RuntimeError(f"{self.__class__.__name__} is closed")

            if self.__thread is not None:
                return

            loop = asyncio.new_event_loop()
            started_event = threading.Event()

            thread = threading.Thread(
                target=self.__worker_loop,
                args=(loop, started_event),
                name=self.__name,
                daemon=True,
            )
            thread.start()
            started_event.wait()

            self.__loop = loop
            self.__thread = thread

    @staticmethod
    def __worker_loop(loop: asyncio.AbstractEventLoop, started_event: threading.Event) -> None:
        loop.call_soon(started_event.set)
        loop.run_forever()

        # loop.stop() was called and run_forever() returned -- clean up
        # entirely on this same thread, which owns the loop and is
        # guaranteed to have no other loop running on it.
        try:
            to_cancel = asyncio.all_tasks(loop)

            for task in to_cancel:
                task.cancel()

            if to_cancel:
                loop.run_until_complete(
                    asyncio.gather(*to_cancel, return_exceptions=True)
                )

                for task in to_cancel:
                    if not task.cancelled() and task.exception() is not None:
                        loop.call_exception_handler({
                            "message": "unhandled exception during SyncAwaitableRunner shutdown",
                            "exception": task.exception(),
                            "task": task,
                        })

            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            loop.close()


    @property
    def started(self) -> bool:
        """Whether the background loop/thread has been created at least once."""
        return self.__thread is not None

    @property
    def running(self) -> bool:
        """Whether the background thread is actually alive right now."""
        return self.__thread is not None and self.__thread.is_alive()

    @property
    def closed(self) -> bool:
        return self.__closed

    def run(self, awaitable: Awaitable[_T]) -> _T:
        self.__ensure_started()

        return run_awaitable_sync(awaitable, self.__loop)

    __call__ = run

    def close(self) -> None:
        with self.__start_lock:
            if self.__closed:
                return

            self.__closed = True

            if self.__thread is None:
                # never started (lazy=True and .run()/.loop were never used) --
                # nothing to clean up
                return

            self.__loop.call_soon_threadsafe(self.__loop.stop)
            self.__thread.join()

    def __enter__(self) -> "SyncAwaitableRunner":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()


UTC3LogFormatter = type(
    "UTC3LogFormatter", 
    (logging.Formatter, ), 
    {"converter": lambda _, stamp: datetime.fromtimestamp(stamp, tz=timezone(timedelta(hours=3))).timetuple()}
    )


__all__ = (
    "FrozenClassAttrs",
    "KeyDefaultDict",
    "AioThreadWorker",
    "MongoIndex",
    "UTC3LogFormatter",
    "hybridmethod",
    "KeyDefaultWeakValueDict",
    "DefaultWeakValueDict",
    "classproperty",
    "SyncAwaitableRunner",
)