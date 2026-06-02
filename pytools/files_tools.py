from typing import Union, Optional
from pathlib import Path
from pydantic import JsonValue


from .data_tools import enum_to_value



import os
import shutil
import json
import threading


_NOT_SET = object()


def remove_file(file: Union[str, Path]) -> None:
    try:
        os.remove(file)
    except FileNotFoundError:
        pass
        
def remove_folder(folder: Union[str, Path]) -> None:
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        pass
        

def load_json(
    path: Union[str, Path], 
    default: dict = _NOT_SET, 
    lock: Optional[threading.RLock] = None, 
    ):

    if lock is not None:
        lock.acquire()
    
    if isinstance(path, str):
        path = Path(path)
    
    if default is _NOT_SET:
        default = {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = default

    finally:
        if lock is not None:
            lock.release()
    
    return data

def save_json(
    path: Union[str, Path], 
    data: JsonValue, 
    lock: Optional[threading.RLock] = None, 
    ):

    if lock is not None:
        lock.acquire()

    if isinstance(path, str):
        path = Path(path)
    
    data = enum_to_value(data)

    try:
        path.write_text(json.dumps(data), encoding="utf-8")
    finally:
        if lock is not None:
            lock.release()



__all__ = (
    "remove_file", 
    "remove_folder", 
    "load_json", 
    "save_json", 
)