"""Generic type aliases using PEP 695 `type X[T] = ...` syntax.

Only ever imported on Python >= 3.12 (see typings.py's version check) --
this syntax is a hard SyntaxError on older interpreters, so this module
must never be imported unconditionally.
"""

from typing import (
    Collection, Generator, Union, Reversible,
    Sequence, AbstractSet, Mapping, Any, Dict, 
    Callable, Coroutine, Awaitable,
)


type Container[I] = Union[
    Generator[I, Any, Any], Collection[I], Reversible[I],
    Sequence[I], AbstractSet[I], Mapping[I, Any],
    filter, enumerate, zip
    ]
type ContainerWithoutMapping[I] = Union[
    Generator[I, Any, Any], Collection[I], Reversible[I],
    Sequence[I], AbstractSet[I], filter, enumerate,
    ]

type MaybeContainer[I] = I | Container[I]
type NestedContainer[I] = I | Container[NestedContainer[I]]
type NestedStrKeyDict[V] = Dict[str, V | NestedStrKeyDict[V]]

type MaybeCoroutine[R] = R | Coroutine[Any, Any, R]
type MaybeCoroutineCallable[**P, R] = Callable[P, MaybeCoroutine[R]]
type MaybeAwaitableCallable[**P, R] = Callable[P, R | Awaitable[R]]
type MaybeAwaitable[**P, R] = MaybeCoroutineCallable[P, R] |  Awaitable[R]


__all__ = (
    "Container",
    "ContainerWithoutMapping",
    "MaybeContainer",
    "NestedContainer",
    "NestedStrKeyDict",
    "MaybeCoroutine",
    "MaybeCoroutineCallable",
    "MaybeAwaitableCallable",
    "MaybeAwaitable",
    
)
