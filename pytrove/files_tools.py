from typing import Union, Optional, Literal, cast, overload
from pathlib import Path

from .typings import JsonValue, PathLike, LockProtocol, _T
from .validate_tools import validation
from .callable_tools import safe_call
from ._optional import _optional_import


import os
import shutil
import json
import tempfile

try:
    import jsonref
except ImportError:
    pass


_NOT_SET = object()


def resolve_path(path: PathLike, strict: bool = False) -> Path:
    if not isinstance(path, Path):
        path = Path(path)
    return path.resolve(strict=strict)

def remove_file(file: PathLike) -> None:
    safe_call(os.unlink, file, include_exc=FileNotFoundError)
        
def remove_folder(folder: PathLike) -> None:
    safe_call(
        shutil.rmtree, 
        folder, 
        include_exc=(FileNotFoundError, OSError), 
        log_exc=lambda exc: (
            None
            if isinstance(exc, FileNotFoundError)
            else
            os.unlink(folder)
            if os.path.islink(folder)
            else validation(False, exc)
        )
    )

def remove_path(path: PathLike) -> None:
    if not isinstance(path, Path):
        path = Path(path)

    if path.is_symlink():
        safe_call(path.unlink, include_exc=FileNotFoundError)
    elif path.is_dir():
        remove_folder(path)
    else:
        remove_file(path)

def write_file(
    path: PathLike, 
    content: Union[str, bytes], 
    encoding: str = "utf-8", 
    mode: Optional[int] = None, 
    lock: Optional[LockProtocol] = None
    ) -> None:

    path = resolve_path(path)
    is_binary = isinstance(content, bytes)
    directory = path.parent

    if mode is None:
        try:
            mode = path.stat().st_mode & 0o777
        except FileNotFoundError:
            mode = 0o644

    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)

    try:
        if lock is not None:
            lock.acquire()

        with os.fdopen(
            fd, 
            "wb" if is_binary else "w", 
            encoding=None if is_binary else encoding
            ) as f:

            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)

        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                safe_call(os.close, dir_fd)
        except OSError:
            pass

    finally:
        try:
            if lock is not None:
                lock.release()
        finally:
            remove_file(tmp_path)

@overload
def read_file(
    path: PathLike,
    *,
    encoding: str = "utf-8",
    lock: Optional[LockProtocol] = None, 
    **kw
) -> str: ...
@overload
def read_file(
    path: PathLike, 
    *, 
    binary: Literal[True], 
    lock: Optional[LockProtocol] = None, 
    **kw
) -> bytes: ...
@overload
def read_file(
    path: PathLike,
    *,
    binary: Literal[False] = False,
    encoding: str = "utf-8",
    lock: Optional[LockProtocol] = None, 
    **kw
) -> str: ...
def read_file(
    path: PathLike,
    *, 
    binary: bool = False, 
    encoding: str = "utf-8", 
    lock: Optional[LockProtocol] = None, 
    **kw
):
    path = resolve_path(path)

    try:
        if lock is not None:
            lock.acquire()

        return path.read_bytes(**kw) if binary else path.read_text(encoding=encoding, **kw)
    finally:
        if lock is not None:
            lock.release()


def read_json(
    path: PathLike, 
    default: _T = cast(dict, _NOT_SET), 
    lock: Optional[LockProtocol] = None, 
    **kw, 
    ) -> Union[JsonValue, _T]:

    try:
        content = read_file(path, encoding="utf-8", lock=lock)
        data = json.loads(content, **kw)
        del content
    except FileNotFoundError:
        data = {} if default is _NOT_SET else default

    return data

def write_json(
    path: PathLike, 
    data: JsonValue, 
    lock: Optional[LockProtocol] = None, 
    **kw, 
    ) -> None:

    kw.setdefault("ensure_ascii", False)
    kw.setdefault("indent", 4)

    content = json.dumps(data, **kw)
    del data
    write_file(path, content, encoding="utf-8", lock=lock)
    

load_json = read_json
save_json = write_json

@_optional_import(("jsonref", "jsonref"))
def load_ref_json(path: PathLike, lock: Optional[LockProtocol] = None, **kw) -> JsonValue:
    """Load the JSON file at `path` and resolve every `$ref` inside it.

    `base_uri` defaults to the file's own location (as a `file://` URI) so
    relative `$ref` targets (e.g. "./schemas/address.json") resolve against
    the file's directory -- without it, jsonref has no directory to resolve
    a relative ref against and raises `JsonRefError` on the first one.
    """

    path = resolve_path(path)

    kw.setdefault("proxies", False)
    kw.setdefault("lazy_load", False)
    kw.setdefault("base_uri", path.as_uri())

    return jsonref.loads(
        read_file(path, encoding="utf-8", lock=lock),
        **kw
    )
    


__all__ = (
    "resolve_path", 
    "remove_file",
    "remove_folder",
    "remove_path", 
    "load_json",
    "save_json",
    "read_json",
    "write_json",
    "load_ref_json",
    "write_file", 
    "read_file", 
)