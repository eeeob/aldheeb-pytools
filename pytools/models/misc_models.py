from typing import Generic, Tuple, Mapping, Optional, Any, Union, Dict

try:
    from typing import Self
except ImportError:  # Python < 3.11
    from typing_extensions import Self

from dataclasses import field, dataclass
from pathlib import Path
from threading import RLock
from concurrent.futures import ThreadPoolExecutor

from ..typings import (
    MaybeAwaitable, Number, 
    MaybeCoroutineCallable, 
    _T, _KT, _VT
)
from ..enums import TriggerOn


from ..validate_tools import is_exception
from ..async_tools import maybe_awaitable, to_thread, safe_wait_task
from ..files_tools import load_json, save_json

from .base import BaseDataClass


import asyncio


@dataclass(slots=True)
class DeferredCall(Generic[_T]):
    func: MaybeAwaitable[..., _T]
    args: Optional[Tuple] = None
    kw: Optional[Mapping] = None

    when: TriggerOn = TriggerOn.SUCCESS
    

    def should_run(self, r: Any) -> bool:
        when = self.when

        return (
            when == TriggerOn.ALWAYS or
            (is_exception(r) and when == TriggerOn.ERROR) or
            (not is_exception(r) and when == TriggerOn.SUCCESS)
            
        )

    async def run(self, executor: Optional[ThreadPoolExecutor] = None) -> _T:
        if self.args is not None:
            args = self.args
        else:
            args = ()
        
        if self.kw is not None:
            kw = self.kw
        else:
            kw = {}

        return await maybe_awaitable(
            self.func, 
            *args, **kw, 
            executor=executor
        )

@dataclass(slots=True)
class JsonContainer(Generic[_KT, _VT], BaseDataClass):
    path: Union[str, Path]
    lock: Optional[RLock] = None

    data: Dict[_KT, _VT] = field(default=None, init=False)
    

    def load(self) -> None:
        if self.data is None:
            self.data = load_json(self.path, lock=self.lock)

    def save(self) -> None:
        save_json(
            self.path, 
            self.data, 
            self.lock
        )
    
    def get(self, key: _KT, default: Optional[_T] = None) -> Optional[Union[_VT, _T]]:
        if self.data is None:
            self.load()
        return self.data.get(key, default)
    
    def set(self, key: _KT, value: _VT, save_now: bool = False) -> None:
        if self.data is None:
            self.load()

        self.data[key] = value

        if save_now:
            self.save()

    def delete(self, key: _KT, save_now: bool = False) -> None:
        if self.data is None:
            self.load()

        if self.data.pop(key, None) is not None:
            if save_now:
                self.save()
    
    def update(self, update: Dict[_KT, _VT], save_now: bool = False) -> None:
        if self.data is None:
            self.load()

        self.data.update(update)

        if save_now:
            self.save()

    async def async_load(self) -> None:
        await to_thread(self.load)
    
    async def async_save(self) -> None:
        await to_thread(self.save)
    
    async def async_get(self, key: _KT, default: Optional[_T] = None) -> Optional[Union[_VT, _T]]:
        if self.data is None:
            await self.async_load()
        return self.data.get(key, default)

    async def async_set(self, key: _KT, value: _VT, save_now: bool = False) -> None:
        if self.data is None:
            await self.async_load()

        self.data[key] = value

        if save_now:
            await self.async_save()

    async def async_delete(self, key: _KT, save_now: bool = False) -> None:
        if self.data is None:
            await self.async_load()

        if self.data.pop(key, None) is not None:

            if save_now:
                await self.async_save()

    async def async_update(self, update: Dict[_KT, _VT], save_now: bool = False) -> None:
        if self.data is None:
            await self.async_load()

        self.data.update(update)
        
        if save_now:
            await self.async_save()


@dataclass(slots=True)
class DelayedCallback(Generic[_T]):
    delay: Number
    callback: MaybeAwaitable[..., _T]

    args: Optional[Tuple[Any, ...]] = None
    kw: Optional[Mapping[str, Any]] = None

    on_finished: Optional[MaybeCoroutineCallable[[Self], Any]] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    callback_started: bool = field(default=False, init=False)
    _task: Optional[asyncio.Task[Optional[_T]]] = field(
        default=None, 
        init=False, 
        repr=False, 
    )

    
    async def wait(self) -> Optional[_T]:
        try:
            await asyncio.wait_for(self.cancel_event.wait(), timeout=self.delay)
        except asyncio.TimeoutError:
            self.callback_started = True

            return await maybe_awaitable(
                self.callback, 
                *(self.args or ()), 
                **(self.kw or {}) 
            )

        finally:
            if self.on_finished is not None:
                await maybe_awaitable(self.on_finished, self)

    def start(self) -> asyncio.Task[Optional[_T]]:
        if self._task is None:
            self._task = asyncio.create_task(self.wait())

        return self._task

    async def cancel(self, force: bool = False) -> None:
        task = self._task

        if task is None:
            return

        self.cancel_event.set()

        if not task.done():
            if force or not self.callback_started:
                task.cancel()

            await safe_wait_task(task)

        self._task = None

    @property
    def task(self) -> Optional[asyncio.Task[Optional[_T]]]:
        return self._task

    @property
    def started(self) -> bool:
        return self._task is not None

    @property
    def done(self) -> bool:
        return self._task is not None and self._task.done()

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()


__all__ = (
    "DeferredCall", 
    "JsonContainer", 
    "DelayedCallback", 

)