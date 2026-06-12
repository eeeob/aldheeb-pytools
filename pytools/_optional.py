from typing import Tuple, Union
from importlib.metadata import distribution, PackageNotFoundError

import importlib.util
import functools


def _build_error_msg(packages, missing):
    all_extras = ", ".join(extra for _, extra in packages)
    all_names = ", ".join(
        f"'{pkg}'" for pkgs, _ in packages
        for pkg in ((pkgs,) if isinstance(pkgs, str) else pkgs)
    )
    missing_names = ", ".join(f"'{pkg}'" for pkgs, _ in missing for pkg in pkgs)

    return (
        f"To use this feature, all required packages must be installed.\n"
        f"Run: pip install 'aldheeb-pytools[{all_extras}]'\n"
        f"\n"
        f"Required : {all_names}\n"
        f"Missing  : {missing_names}"
    )

def _is_installed(package: str):
    try:
        distribution(package)
    except PackageNotFoundError:
        return importlib.util.find_spec(package) is not None
    else:
        return True


def _get_missing(packages):
    missing = []

    for pkgs, extra in packages:
        if isinstance(pkgs, str):
            pkgs = (pkgs,)

        missing_in_group = tuple(pkg for pkg in pkgs if not _is_installed(pkg))

        if missing_in_group:
            missing.append((missing_in_group, extra))

    return missing


def _optional_import(*packages: Tuple[Union[str, Tuple[str, ...]], str]):
    missing = _get_missing(packages)
    error_msg = _build_error_msg(packages, missing) if missing else None

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if error_msg is not None:
                raise ImportError(error_msg)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def _unavailable_class(name: str, *packages: Tuple[Union[str, Tuple[str, ...]], str]):
    missing = _get_missing(packages)

    if not missing:
        raise RuntimeError("No missing packages for unavailable class")

    msg = _build_error_msg(packages, missing)

    class _Unavailable:
        def __new__(cls, *args, **kwargs):
            raise ImportError(msg)

        def __getattr__(self, name):
            raise ImportError(msg)

        def __class_getitem__(cls, item):
            raise ImportError(msg)

        @classmethod
        def __init_subclass__(cls, **kwargs):
            raise ImportError(msg)

    class _UnavailableMeta(type):
        def __getattr__(cls, name):
            raise ImportError(msg)

        def __instancecheck__(cls, instance):
            raise ImportError(msg)

        def __subclasscheck__(cls, subclass):
            raise ImportError(msg)

    return _UnavailableMeta(name, (), dict(_Unavailable.__dict__))