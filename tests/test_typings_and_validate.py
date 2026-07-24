"""Covers is_container/is_mapping and friends, including the isinstance()
vs typing.Union cross-version compatibility fix in validate_tools.py."""
from enum import Enum

from pytools import (
    is_container, is_mapping, is_sub_container, is_sub_mapping,
    is_email, is_exception, flat_cont, to_list, to_set, to_tuple,
    to_frozenset, clean_none_values, enum_to_value, value_to_enum,
)


def test_is_container_accepts_plain_collections():
    assert is_container([1, 2, 3])
    assert is_container((1, 2, 3))
    assert is_container({1, 2, 3})
    assert is_container({"a": 1})
    assert is_container(range(3))
    assert is_container(x for x in range(2))  # generator expression -> Generator ABC


def test_is_container_rejects_bare_iterator():
    # Container is defined as Generator | Collection | Reversible | Sequence |
    # AbstractSet | Mapping | filter | enumerate | zip -- a plain list_iterator
    # matches none of these, so it is intentionally NOT considered a container.
    assert not is_container(iter([1, 2]))


def test_is_container_rejects_not_container_types():
    # str/bytes/bytearray/memoryview are explicitly excluded even though
    # they are technically iterable, per typings.NotContainer.
    assert not is_container("abc")
    assert not is_container(b"abc")
    assert not is_container(bytearray(b"abc"))
    assert not is_container(1)
    assert not is_container(None)


def test_is_mapping():
    assert is_mapping({"a": 1})
    assert not is_mapping([1, 2])


def test_is_sub_container_and_is_sub_mapping():
    assert is_sub_container(list)
    assert is_sub_container(dict)
    assert not is_sub_container(str)
    assert is_sub_mapping(dict)
    assert not is_sub_mapping(list)


def test_flat_cont_flattens_nested_containers():
    # This is the exact call shape (`flat_cont(container.values())`) that runs
    # at *module import time* in tg_tools.py — a regression here breaks
    # `import pytools` entirely, which is exactly what happened pre-fix on
    # Python versions where isinstance() rejects a bare typing.Union.
    assert flat_cont([1, [2, [3, None]], (4,)]) == [1, 2, 3, 4]
    assert flat_cont(None) == []
    assert set(flat_cont({1, 2}, [3, 4])) == {1, 2, 3, 4}


def test_to_collection_helpers():
    assert to_list(None) == []
    assert to_list(5) == [5]
    assert to_list([1, 2]) == [1, 2]

    assert to_set(None) == set()
    assert to_set([1, 1, 2]) == {1, 2}

    assert to_tuple(None) == ()
    assert to_tuple(5) == (5,)

    assert to_frozenset(None) == frozenset()
    assert to_frozenset([1, 1, 2]) == frozenset({1, 2})


def test_is_email():
    assert is_email("user@example.com")
    assert not is_email("not-an-email")
    assert not is_email(123)


def test_is_exception():
    assert is_exception(ValueError("x"))
    assert not is_exception("x")


def test_clean_none_values_nested():
    assert clean_none_values({"a": 1, "b": None, "c": {"d": None, "e": 2}}) == {
        "a": 1, "c": {"e": 2}
    }


def test_enum_to_value_and_value_to_enum():
    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    assert enum_to_value(Color.RED) == "red"
    assert enum_to_value({"k": Color.RED}) == {"k": "red"}

    assert value_to_enum("red", Color) is Color.RED
    assert value_to_enum({"k": "red"}, Color) == {"k": Color.RED}
