import asyncio

from typing import Any, Awaitable, List, Optional, Union, TYPE_CHECKING, overload
from .typings import _T, _True, _False


class _GatheringFuture(asyncio.Future):
    def __init__(self, children, *, loop):
        super().__init__(loop=loop)

        self._children = children

    if not TYPE_CHECKING:
        @property
        def cancel_message(self) -> Optional[Any]:
            return getattr(self, "_cancel_message", None)
        
        @cancel_message.setter
        def cancel_message(self, value: Optional[Any]):
            setattr(self, "_cancel_message", value)


        def cancel(self, msg: Optional[Any] = None) -> bool:
            if self.done():
                return False
            
            ret = False
            
            for child in self._children:
                if child.cancel(msg=msg):
                    ret = True

            if ret:
                self.cancel_message = "" if msg is None else msg

            return ret

@overload
def _gather_cancel_on_error(*awaitables: Awaitable[_T], return_exceptions: _False = False) -> asyncio.Future[List[_T]]:...
@overload
def _gather_cancel_on_error(*awaitables: Awaitable[_T], return_exceptions: _True) -> asyncio.Future[List[Union[_T, Exception]]]:...
def _gather_cancel_on_error(*awaitables, return_exceptions = False):
    if not awaitables:
        outer = asyncio.get_event_loop().create_future()
        outer.set_result([])
        return outer
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    current_task = None if loop is None else asyncio.current_task(loop)

    def _done_callback(fut, current_task = current_task):
        nonlocal npending
        npending -= 1

        if current_task is not None:
            asyncio.future_discard_from_awaited_by(fut, current_task)

        if outer.done():
            if not fut.cancelled():
                fut.exception()  # استهلاك الاستثناء لمنع تحذير asyncio
            return

        if not return_exceptions:
            try:
                exc = fut.exception()
            except asyncio.CancelledError as e:
                exc = e

            if exc is not None:
                outer.set_exception(exc)

                for child in children:
                    if child is not fut and not child.done():
                        child.cancel()

                return

        if npending == 0:
            results = []

            for child in children:
                try:
                    result = child.exception()
                except asyncio.CancelledError as e:
                    result = e

                if result is None:
                    result = child.result()

                results.append(result)

            if (cancel_message := outer.cancel_message) is not None:
                outer.set_exception(asyncio.CancelledError(cancel_message))
            else:
                outer.set_result(results)
    
    
    
    npending = 0
    outer = None
    
    done_futs = []
    children = []

    awaitable_2_fut = {}
    

    for awaitable in awaitables:
        fut = awaitable_2_fut.get(awaitable)

        if fut is None:
            fut = asyncio.ensure_future(awaitable, loop=loop)

            if loop is None:
                loop = fut.get_loop()

            if fut is not awaitable:
                fut._log_destroy_pending = False

            npending += 1
            awaitable_2_fut[awaitable] = fut

            if fut.done():
                done_futs.append(fut)
            else:
                if current_task is not None:
                    asyncio.future_add_to_awaited_by(fut, current_task)

                fut.add_done_callback(_done_callback)

        children.append(fut)

    outer = _GatheringFuture(children, loop=loop)

    for fut in done_futs:
        _done_callback(fut)

    return outer


