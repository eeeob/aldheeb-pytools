import glob
import json

import pytest

from pytools import load_json, save_json


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    save_json(path, {"a": 1, "b": [1, 2, 3]})
    assert load_json(path) == {"a": 1, "b": [1, 2, 3]}


def test_save_json_leaves_no_temp_file_behind(tmp_path):
    path = tmp_path / "data.json"
    save_json(path, {"a": 1})
    assert glob.glob(str(path) + "*.tmp") == []


def test_load_json_missing_file_returns_default(tmp_path):
    path = tmp_path / "missing.json"
    assert load_json(path, default={"fallback": True}) == {"fallback": True}


def test_load_json_corrupted_file_raises_decode_error(tmp_path):
    # By design, only a missing file falls back to `default` -- a corrupted/
    # truncated file (e.g. from a prior interrupted write, now prevented by
    # save_json()'s atomic replace) raises loudly instead of silently
    # returning `default` and masking the corruption.
    path = tmp_path / "corrupted.json"
    path.write_text("{not valid json!!!", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_json(path, default={"fallback": True})


def test_load_json_empty_file_raises_decode_error(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_json(path, default={"fallback": True})


def test_save_json_cleans_up_temp_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "data.json"

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(json, "dumps", _boom)

    with pytest.raises(RuntimeError):
        save_json(path, {"a": 1})

    assert glob.glob(str(path) + "*.tmp") == []
    assert not path.exists()


def test_save_json_does_not_corrupt_existing_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "data.json"
    save_json(path, {"a": 1})

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(json, "dumps", _boom)
    with pytest.raises(RuntimeError):
        save_json(path, {"a": 2})

    # The atomic replace never happened, so the original content must survive.
    assert load_json(path) == {"a": 1}
