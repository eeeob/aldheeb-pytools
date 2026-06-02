from typing import Optional, Any, Callable
from .typings import _CT



import inspect
import secrets
import string
import functools


def unwrap_cls(cls):
    count = 0

    for name in dir(cls):
        method = getattr(cls, name)
        
        if hasattr(method, "__wrapped__"):
            setattr(cls, name, inspect.unwrap(method))
            count += 1
    
    return count


def generate_secret(
    length: int,
    use_upper: bool = True,
    use_lower: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    ) -> str:

    if length <= 0:
        raise ValueError("Password length must be greater than 0")

    pools = []
    guaranteed = []

    if use_lower:
        pools.append(string.ascii_lowercase)
        guaranteed.append(secrets.choice(string.ascii_lowercase))

    if use_upper:
        pools.append(string.ascii_uppercase)
        guaranteed.append(secrets.choice(string.ascii_uppercase))

    if use_digits:
        pools.append(string.digits)
        guaranteed.append(secrets.choice(string.digits))

    if use_symbols:
        pools.append("!@#$%^&*()-_=+[]{};:,.<>?/")
        guaranteed.append(secrets.choice("!@#$%^&*()-_=+[]{};:,.<>?/"))

    if not pools:
        raise ValueError("At least one character set must be enabled")

    all_chars = "".join(pools)

    if length < len(guaranteed):
        raise ValueError("Length too small for selected options")

    password = guaranteed + [
        secrets.choice(all_chars)
        for _ in range(length - len(guaranteed))
    ]

    secrets.SystemRandom().shuffle(password)

    return "".join(password)


def unwrap(obj: Any, with_prop: bool = True) -> Any:
    if with_prop and isinstance(obj, property):
        obj = obj.fget
    
    return functools._unwrap_partialmethod(inspect.unwrap(obj))
        
    
def patch_into(
    target: type, 
    *, 
    patch_key: str = "should_patch", 
    preserve_old: bool = True, 
    transform: Optional[Callable[[type, Any], Any]] = None,
    ) -> Callable[[_CT], _CT]:
    
    def apply(current_class: _CT) -> _CT:
        patched_members = {
            name: member
            for name, member in current_class.__dict__.items()
            if getattr(unwrap(member), patch_key, False)
        }

        for name, member in patched_members.items():
            if preserve_old:
                if old_member := getattr(target, name, None):
                    setattr(target, f"old_{name}", old_member)

            if transform is not None:
                member = transform(current_class, member)

            setattr(target, name, member)

        return current_class

    return apply   


__all__ = (
    "unwrap_cls", 
    "generate_secret", 
    "unwrap", 
    "patch_into", 
)