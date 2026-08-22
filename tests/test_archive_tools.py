"""Covers backup_folder/extract_archive: the filtering rules, the
self-exclusion that keeps an archive out of itself, and the traversal guard
extraction needs because tarfile had none before 3.12."""
import io
import os
import subprocess
import sys
import tarfile
import zipfile

import pytest

from pytrove import backup_folder, extract_archive
from pytrove.enums import ArchiveFormat
from pytrove._archive_tools import HAS_ZSTD, _safe_target


# tar.zst needs the `zstd` extra; the other two are stdlib-only.
FORMATS = [ArchiveFormat.ZIP, ArchiveFormat.TAR_GZ] + (
    [ArchiveFormat.TAR_ZST] if HAS_ZSTD else []
)


@pytest.fixture
def tree(tmp_path):
    """A source folder with hidden files, empty dirs and nested content."""

    src = tmp_path / "src"
    (src / "sub" / "deep").mkdir(parents=True)
    (src / "empty").mkdir()
    (src / ".hidden").mkdir()

    (src / "a.py").write_text("a")
    (src / "b.txt").write_text("b")
    (src / "sub" / "c.py").write_text("c")
    (src / "sub" / "deep" / "d.txt").write_text("d")
    (src / ".env").write_text("secret")
    (src / ".hidden" / "x.txt").write_text("x")

    return src


def _names(archive):
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            return {n for n in zf.namelist() if not n.endswith("/")}

    with tarfile.open(archive) as tf:
        return {m.name for m in tf.getmembers() if m.isfile()}


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("fsync", [False, True])
def test_round_trip_every_format_and_fsync(tree, tmp_path, fmt, fsync):
    # fsync=True is the default and must be exercised: zstandard's
    # stream_writer closes the file it is handed unless told not to, which
    # made only this combination fail with "flush of closed file".
    archive = backup_folder(tree, tmp_path / "out", format=fmt, fsync=fsync)
    assert archive.exists()

    dest = tmp_path / f"x_{fmt.name}_{fsync}"
    extract_archive(archive, dest)

    got = {
        str(p.relative_to(dest)).replace(os.sep, "/"): p.read_bytes()
        for p in dest.rglob("*") if p.is_file()
    }
    assert got == {
        "a.py": b"a", "b.txt": b"b",
        "sub/c.py": b"c", "sub/deep/d.txt": b"d",
    }


def test_hidden_excluded_by_default(tree, tmp_path):
    assert _names(backup_folder(tree, tmp_path / "h.zip", fsync=False)) == {
        "a.py", "b.txt", "sub/c.py", "sub/deep/d.txt",
    }


def test_hidden_included_when_asked(tree, tmp_path):
    names = _names(backup_folder(tree, tmp_path / "h2.zip", hidden=True, fsync=False))
    assert ".env" in names and ".hidden/x.txt" in names


def test_empty_directories_are_not_recorded(tree, tmp_path):
    archive = backup_folder(tree, tmp_path / "e.zip", fsync=False)

    with zipfile.ZipFile(archive) as zf:
        dirs = {n for n in zf.namelist() if n.endswith("/")}

    assert "empty/" not in dirs
    # ...but a directory holding a kept file is still recorded, so an
    # extractor makes the parent before the child.
    assert "sub/" in dirs


def test_include_narrows_to_a_subtree(tree, tmp_path):
    assert _names(backup_folder(tree, tmp_path / "i.zip", include="sub/*", fsync=False)) == {
        "sub/c.py", "sub/deep/d.txt",
    }


def test_exclude_beats_include(tree, tmp_path):
    names = _names(backup_folder(
        tree, tmp_path / "x.zip", include="*", exclude="*.txt", fsync=False,
    ))
    assert names == {"a.py", "sub/c.py"}


@pytest.mark.parametrize("fmt", FORMATS)
def test_archive_does_not_swallow_itself(tree, tmp_path, fmt):
    # Written into the folder being archived, and to the same name twice:
    # without skipping the destination (and the temp file it is written
    # through) the second run would contain the first.
    sizes = [
        backup_folder(
            tree, tree / f"self.{fmt.value}", format=fmt, hidden=True, fsync=False,
        ).stat().st_size
        for _ in range(3)
    ]
    assert len(set(sizes)) == 1


def test_dest_directory_names_archive_after_source(tree, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert backup_folder(tree, out, fsync=False).name == "src.zip"


def test_rejects_a_file_as_source(tree, tmp_path):
    from pytrove.errors import ValidationError

    with pytest.raises(ValidationError):
        backup_folder(tree / "a.py", tmp_path / "no.zip")


@pytest.mark.parametrize("name", [
    "../escape.txt",
    "../../escape.txt",
    "a/../../escape.txt",
    "..\\escape.txt",
    "",
])
def test_safe_target_refuses_traversal(tmp_path, name):
    dest = tmp_path / "dest"
    dest.mkdir()
    assert _safe_target(dest, name) is None


def test_safe_target_contains_absolute_names(tmp_path):
    # tar strips a leading "/" rather than dropping the member; the point
    # is only that it cannot land outside dest.
    dest = tmp_path / "dest"
    dest.mkdir()
    target = _safe_target(dest, "/etc/passwd")

    assert target is not None and dest in target.parents


def test_extract_refuses_to_escape_the_destination(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    victim = tmp_path / "VICTIM.txt"
    victim.write_text("ORIGINAL")

    evil = tmp_path / "evil.zip"

    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../VICTIM.txt", "PWNED")
        zf.writestr("ok.txt", "fine")

    extract_archive(evil, dest)

    assert victim.read_text() == "ORIGINAL"
    assert (dest / "ok.txt").read_text() == "fine"


def test_extract_skips_symlink_members(tmp_path):
    # A symlink member can point anywhere; a later member written "through"
    # it would land outside despite its own name looking harmless.
    dest = tmp_path / "dest"
    dest.mkdir()
    evil = tmp_path / "evil.tar.gz"

    with tarfile.open(evil, "w:gz") as tf:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = str(tmp_path)
        tf.addfile(link)

        data = b"fine"
        info = tarfile.TarInfo("ok.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    extract_archive(evil, dest)

    assert not (dest / "link").is_symlink()
    assert (dest / "ok.txt").read_bytes() == b"fine"


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_detected_from_content_not_extension(tree, tmp_path, fmt):
    archive = backup_folder(tree, tmp_path / "out", format=fmt, fsync=False)
    renamed = archive.with_name("mystery.bin")
    archive.rename(renamed)

    dest = tmp_path / f"d_{fmt.name}"
    extract_archive(renamed, dest)

    assert (dest / "a.py").read_bytes() == b"a"


@pytest.mark.skipif(sys.platform != "win32", reason="hidden attribute is Windows-only")
def test_windows_hidden_attribute_is_honoured(tmp_path):
    src = tmp_path / "s"
    src.mkdir()
    (src / "plain.txt").write_text("p")
    marked = src / "marked.txt"
    marked.write_text("m")
    subprocess.run(["attrib", "+H", str(marked)], capture_output=True, check=False)

    assert _names(backup_folder(src, tmp_path / "w.zip", fsync=False)) == {"plain.txt"}
