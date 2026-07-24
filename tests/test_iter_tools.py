from pytools import to_list, to_tuple, to_set, to_frozenset, flat_cont


def test_to_list_with_mapping_returns_keys():
    assert to_list({"a": 1, "b": 2}) == ["a", "b"]


def test_to_tuple_preserves_order():
    assert to_tuple([3, 1, 2]) == (3, 1, 2)


def test_to_set_deduplicates():
    assert to_set([1, 1, 2, 2, 3]) == {1, 2, 3}


def test_to_frozenset_is_immutable_type():
    result = to_frozenset([1, 2])
    assert isinstance(result, frozenset)


def test_flat_cont_ignores_none_entries():
    assert flat_cont([1, None, 2, None, [3, None]]) == [1, 2, 3]


def test_flat_cont_deeply_nested():
    nested = [1, [2, [3, [4, [5]]]]]
    assert flat_cont(nested) == [1, 2, 3, 4, 5]


def test_flat_cont_treats_strings_as_atomic():
    # str is explicitly excluded from Container (NotContainer), so it must
    # not be exploded into individual characters.
    assert flat_cont(["ab", ["cd"]]) == ["ab", "cd"]


def test_flat_cont_multiple_container_args():
    assert flat_cont([1, 2], [3, 4], None) == [1, 2, 3, 4]
