from typing import (
    Any, Callable, TYPE_CHECKING, 
    Coroutine, Dict, Optional, Generic, 
    overload, Type, TypeVar, 
)

from types import MethodType
from functools import partial
from datetime import datetime, timezone, timedelta
from concurrent.futures import Future, InvalidStateError

try:
    from aiologic import Condition, CountdownEvent, SimpleQueue
    HAS_AIOLOGIC = True
except ImportError:
    HAS_AIOLOGIC = False


try:
    from pymongo import IndexModel
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

from ._optional import _unavailable_class

from .typings import (
    WorkTaskInfo as WorkTaskInfoT, 
    _KT, _VT, _T, _P
)
from .async_tools import to_thread

import weakref
import logging
import threading
import asyncio


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


if HAS_AIOLOGIC:
    class AioThreadWorker:
        def __init__(
            self, 
            name: Optional[str] = None, 
            concurrency: int = 0, 
            loop_factory = None,
            exception_handler = None,
            run_now: bool = True, 
            ):

            self.concurrency = concurrency
    
            self.any_completed = Condition(None)
            self.all_completed = CountdownEvent()

            self.queue: SimpleQueue[Optional[WorkTaskInfoT]] = SimpleQueue()

            self.__thread = threading.Thread(
                target=self.__bootstrap, 
                args=(loop_factory, exception_handler), 
                name=name, 
                daemon=True
                )
            
            self.__running = threading.Event()
            self.__stopping = threading.Event()
            
            self.__loop = None
            
            if run_now:
                self.run()

        def __bootstrap(self, loop_factory=None, exception_handler=None) -> None:
            if threading.current_thread() is not self.__thread:
                raise RuntimeError("Bootstrap must be called from the worker thread")

            try:
                with asyncio.Runner(loop_factory=loop_factory) as runner:
                    runner.run(self.__worker(exception_handler))
            finally:
                self.__running.clear()
                self.__stopping.clear()
                
                self.__loop = None

        async def __worker(self, exception_handler=None) -> None:
            self.__loop = asyncio.get_running_loop()

            if exception_handler is not None:
                self.__loop.set_exception_handler(exception_handler)
            
            self.__running.set()

            def chain(t: asyncio.Task, f: Future):
                def on_task_done(task: asyncio.Task):
                    self.all_completed.down()
                    self.any_completed.notify_all()
                    
                    if task.cancelled() and not f.cancelled():
                        f.cancel()

                def on_future_done(future: Future):
                    if future.cancelled() and not t.cancelled():
                        t.get_loop().call_soon_threadsafe(t.cancel)
                
                t.add_done_callback(on_task_done)
                f.add_done_callback(on_future_done)
                

            while True:
                if self.concurrency <= 0 or self.all_completed.value < self.concurrency:
                    task_info = await self.queue.async_get()

                    if task_info is None:
                        break

                    fut = task_info[-1]

                    if fut.cancelled():
                        continue

                    self.all_completed.up()
                    chain(asyncio.create_task(self.__work(task_info)), fut)
                    
                else:
                    await self.any_completed
            
            await self.all_completed

        async def __work(self, task_info: WorkTaskInfoT) -> None:
            func, args, kwargs, future = task_info

            if future.cancelled():
                raise asyncio.CancelledError()

            try:
                result = await func(*args, **kwargs)
            except (SystemExit, KeyboardInterrupt, asyncio.CancelledError):
                raise
            except BaseException as exc:
                try:
                    future.set_exception(exc)
                except InvalidStateError:
                    pass
                raise
            else:
                try:
                    future.set_result(result)
                except InvalidStateError:
                    pass
                    
            
        def is_running(self) -> bool:
            return self.__thread.is_alive() and self.__running.is_set()
        
        def is_stopping(self):
            return self.__stopping.is_set()

        def run(self, wait: Optional[float] = None) -> None:
            if self.__thread.is_alive():
                raise RuntimeError("Already Running")
            
            self.__thread.start()

            if not self.__running.wait(wait):
                raise TimeoutError

        async def join(self) -> None:
            if not self.is_running():
                raise RuntimeError("Worker not running")
            
            if self.is_stopping():
                raise RuntimeError("Is Stopping")
            
            self.__stopping.set()
            
            self.queue.put(None)

            await self.all_completed
            await to_thread(self.__thread.join)
        
        def __await__(self):
            return self.join().__await__()

        def get_loop(self) -> asyncio.AbstractEventLoop:
            if not self.is_running():
                raise RuntimeError("Worker not running")
            
            return self.__loop
        
        def submit(
            self,
            func: Callable[_P, Coroutine[Any, Any, _T]],
            /,
            *args: _P.args,
            **kwargs: _P.kwargs,
            ) -> asyncio.Future[_T]:

            if not self.is_running():
                raise RuntimeError("worker is closed")
            
            if self.is_stopping():
                raise RuntimeError("is stopping")

            future = Future()
            self.queue.put((func, args, kwargs, future))

            return asyncio.wrap_future(future)
        
        __call__ = submit
else:
    AioThreadWorker = _unavailable_class("AioThreadWorker", ("aiologic", "aiologic"))


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


class LazyMap(Generic[_KT, _VT]):
    """A generic lazy factory map backed by weak references.

    Creates a value for each key on first access via the provided
    factory, and automatically discards it once no strong references
    remain (i.e. tied to last access lifetime).

    Args:
        factory: A zero-argument callable that produces a new value.
                 Determines both the type and behaviour of stored values.

    Examples:
        from pytools import LazyMap
        import asyncio


        locks = LazyMap(asyncio.Lock)
        async with locks("user:42"):
            ...

        caches = LazyMap(dict)
        caches["ns"]["key"] = 1
    """

    def __init__(self, factory: Callable[[], _VT]) -> None:
        self._factory = factory
        self._store: weakref.WeakValueDictionary[_KT, _VT] = weakref.WeakValueDictionary()
        

    def get(self, key: _KT) -> _VT:
        """Return the value for *key*, creating one if it does not exist."""
        try:
            return self._store[key]
        except KeyError:
            value = self._factory()
            self._store[key] = value
            return value

    __call__ = get
    __getitem__ = get

    def __contains__(self, key: _KT) -> bool:
        """Return True if *key* has a live value in the map."""
        return key in self._store

    def __len__(self) -> int:
        """Return the number of currently live entries."""
        return len(self._store)


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
    "LazyMap", 
    "classproperty", 
)