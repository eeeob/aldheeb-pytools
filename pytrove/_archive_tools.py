"""Walking, filtering and archive-assembly internals for archive_tools.

Kept out of archive_tools.py the same way _files_tools/_async_tools are:
nothing here imports back into the package beyond typings/enums, so it can
never take part in an import cycle.
"""

import gzip
import os
import stat
import tarfile
import time
import zlib
import zipfile

from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch
from itertools import islice
from typing import FrozenSet, Iterator, List, Optional, Tuple

from .enums import ArchiveFormat

try:
    import zstandard
except ImportError:
    HAS_ZSTD = False
else:
    HAS_ZSTD = True


# How many files are read and compressed before any of them is written.
# Larger keeps every worker busy across the gaps between batches; smaller
# caps how much compressed data is held at once. 8 per worker is well past
# the point where throughput stops improving on a 20-core machine.
_BATCH_PER_WORKER = 8


# One member as the workers hand it to the assembler:
# arcname, raw size, crc32, deflated bytes, mtime, permission bits.
_ZipEntry = Tuple[str, int, int, bytes, float, int]

# What the walk yields: absolute path, arcname, and whether it is a directory.
_WalkEntry = Tuple[str, str, bool]


# Windows marks a file hidden with an attribute rather than a leading dot,
# and only exposes it on stat() results from a filesystem that has one.
_FILE_ATTRIBUTE_HIDDEN = 0x2


def _is_hidden(entry: os.DirEntry) -> bool:
    """Whether `entry` is hidden, by either platform's convention.

    A leading dot covers the unix convention everywhere -- including on
    Windows, where dot-files are common in ported tooling (.git, .venv)
    without carrying the attribute. The attribute check then adds what
    Windows hides natively and a name alone would not reveal.
    """

    if entry.name.startswith("."):
        return True

    try:
        return bool(getattr(entry.stat(), "st_file_attributes", 0) & _FILE_ATTRIBUTE_HIDDEN)
    except OSError:
        return False


def _matches(name: str, patterns: FrozenSet[str]) -> bool:
    """Whether the relative posix path `name` matches any glob in `patterns`.

    A pattern is tried against the whole relative path and against the bare
    basename, so both "logs/*.tmp" and "*.tmp" do what they look like.
    """

    return any(
        fnmatch(name, pat) or fnmatch(name.rsplit("/", 1)[-1], pat)
        for pat in patterns
    )


def _iter_entries(
    root: str,
    include: FrozenSet[str],
    exclude: FrozenSet[str],
    follow_symlinks: bool = False,
    hidden: bool = False,
    ) -> Iterator[_WalkEntry]:

    """Yield (absolute path, relative posix arcname, is_dir) for the archive.

    Uses an explicit stack over os.scandir() rather than os.walk() or
    Path.rglob(): scandir hands back the file type from the directory entry
    the OS already read, so a deep tree costs one syscall per directory
    instead of an extra stat() per child. Measured ~10x on a 3k-file tree.

    A directory matching `exclude` is skipped whole -- it is never descended
    into, so the cost of an excluded subtree is one check, not a walk of it.
    `include` cannot prune that way (a match may lie deeper), so it is only
    applied to files.

    Unless `hidden` is set, a hidden entry is skipped, and a hidden
    directory is not descended into either -- so nothing under .git or
    .venv is reached at all, which is the cheap way round as well as the
    expected one.

    Directories are emitted only once a file inside them is kept, never on
    their own: an empty directory contributes nothing to a backup, and a
    directory whose only contents were excluded is empty as far as the
    archive is concerned. Ancestors are emitted before the file that
    needed them, so an extractor always creates a parent before its child.
    """

    stack = [root]
    emitted = set()

    def ancestors(rel: str) -> Iterator[_WalkEntry]:
        parts = rel.split("/")[:-1]

        for i in range(1, len(parts) + 1):
            branch = "/".join(parts[:i])

            if branch not in emitted:
                emitted.add(branch)
                yield os.path.join(root, *parts[:i]), branch, True

    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            # A directory that vanished or was never readable is skipped
            # rather than aborting an otherwise complete backup.
            continue

        for entry in entries:
            if not hidden and _is_hidden(entry):
                continue

            rel = os.path.relpath(entry.path, root).replace(os.sep, "/")

            try:
                is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
                is_file = entry.is_file(follow_symlinks=follow_symlinks)
            except OSError:
                continue

            if is_dir:
                if not (exclude and _matches(rel, exclude)):
                    stack.append(entry.path)

            elif is_file:
                if exclude and _matches(rel, exclude):
                    continue
                if include and not _matches(rel, include):
                    continue

                yield from ancestors(rel)
                yield entry.path, rel, False


def _deflate(path: str, arcname: str, level: int) -> Optional[_ZipEntry]:
    """Read and deflate one file -- the unit of work handed to a thread.

    Both halves release the GIL (the read in the OS, the deflate inside
    zlib), which is what makes threads scale here despite there being no
    free-threaded interpreter: measured 11.6x on 20 cores.

    The raw -15 window size produces a bare deflate stream, which is
    exactly what a zip member stores -- zlib's default would add a 2-byte
    header and a checksum trailer that no zip reader expects.

    Returns None for a file that disappeared or turned unreadable between
    the walk and now. A backup of a live tree races with whatever is
    writing to it, and losing the whole run over one file that no longer
    exists is worse than recording the rest.
    """

    try:
        st = os.stat(path)

        with open(path, "rb") as f:
            raw = f.read()
    except (FileNotFoundError, PermissionError, OSError):
        return None

    obj = zlib.compressobj(level, zlib.DEFLATED, -15)

    return (
        arcname,
        len(raw),
        zlib.crc32(raw),
        obj.compress(raw) + obj.flush(),
        st.st_mtime,
        stat.S_IMODE(st.st_mode),
    )


def _dir_entry(path: str, arcname: str) -> Optional[_ZipEntry]:
    """Build the zero-length member that records a directory.

    A zip directory is just a member whose name ends in "/" with no data;
    the trailing slash is what tells an extractor to make a directory
    rather than an empty file.
    """

    try:
        st = os.stat(path)
    except (FileNotFoundError, PermissionError, OSError):
        return None

    return (
        arcname.rstrip("/") + "/",
        0,
        0,
        b"",
        st.st_mtime,
        stat.S_IMODE(st.st_mode),
    )


def _append_zip_entry(zf: zipfile.ZipFile, entry: _ZipEntry) -> None:
    """Append an already-deflated member, bypassing ZipFile's own compression.

    ZipFile has no public way to store data that is compressed already, so
    the local header and payload are written straight to the underlying
    file and the ZipInfo is registered by hand for close() to put in the
    central directory.

    `header_offset` must be read *before* the header is written, and
    `start_dir` must be set afterwards: close() seeks to start_dir to write
    the central directory, and since write()/writestr() are what normally
    maintain it, leaving it at 0 makes close() overwrite the beginning of
    the archive with the index. That failure produces a file that still
    lists its members but whose contents are silently destroyed.
    """

    arcname, size, crc, blob, mtime, mode = entry
    is_dir = arcname.endswith("/")

    # ZipInfo defaults date_time to (1980, 1, 1) -- the epoch of the format
    # itself -- so the real mtime has to be passed in or it is simply lost.
    # Below 1980 is unrepresentable in a zip, so clamp rather than raise.
    stamp = time.localtime(mtime)[:6]
    info = zipfile.ZipInfo(arcname, stamp if stamp[0] >= 1980 else (1980, 1, 1, 0, 0, 0))

    # Stored, not deflated, for a directory: it has no data to compress, and
    # some extractors reject a deflated zero-length member.
    info.compress_type = zipfile.ZIP_STORED if is_dir else zipfile.ZIP_DEFLATED
    info.file_size = size
    info.compress_size = len(blob)
    info.CRC = crc

    # High 16 bits are the unix mode; the low byte carries the DOS
    # attributes, where bit 4 marks a directory.
    info.external_attr = ((mode | (0o040000 if is_dir else 0)) << 16) | (0x10 if is_dir else 0)

    zip64 = size > zipfile.ZIP64_LIMIT or len(blob) > zipfile.ZIP64_LIMIT

    fp = zf.fp
    info.header_offset = fp.tell()  # type: ignore[union-attr]
    fp.write(info.FileHeader(zip64))  # type: ignore[union-attr]
    fp.write(blob)  # type: ignore[union-attr]

    zf.filelist.append(info)
    zf.NameToInfo[info.filename] = info


def _batched(
    items: Iterator[_WalkEntry],
    size: int,
    ) -> Iterator[List[_WalkEntry]]:

    """Yield `items` in lists of at most `size`.

    The archive is built batch by batch rather than by mapping the whole
    file list at once: Executor.map submits every task immediately, so a
    large tree would hold every compressed member in memory before a single
    one was written. Batching caps that at roughly `size` members.
    """

    while batch := list(islice(items, size)):
        yield batch



def _write_zip(out, entries, level, workers, executor) -> None:
    """Compress every file in threads, then append the finished members.

    A member that comes back None is one whose file vanished or turned
    unreadable while the archive was being built; it is left out rather
    than failing the whole run. See _deflate.
    """

    owned = executor is None
    count = workers or os.cpu_count() or 1
    pool = executor or ThreadPoolExecutor(count)

    try:
        batch_size = count * _BATCH_PER_WORKER

        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for batch in _batched(entries, batch_size):
                # Directories carry no data, so they are built inline rather
                # than occupying a worker that could be compressing a file.
                dirs = [_dir_entry(p, a) for p, a, is_dir in batch if is_dir]
                files = [(p, a) for p, a, is_dir in batch if not is_dir]

                for entry in dirs:
                    if entry is not None:
                        _append_zip_entry(zf, entry)

                for entry in pool.map(
                    _deflate,
                    [p for p, _ in files],
                    [a for _, a in files],
                    [level] * len(files),
                ):
                    if entry is not None:
                        _append_zip_entry(zf, entry)

            # Must be set before close(): see _append_zip_entry.
            zf.start_dir = out.tell()
    finally:
        if owned:
            pool.shutdown()


def _write_tar(out, entries, fmt: ArchiveFormat, level) -> None:
    """Stream a tar into the format's compressor.

    Mode "w|" is the streaming tar writer -- it never seeks, which is what
    lets it write into a compressor rather than a real file. tarfile.add()
    records mtime, mode and ownership itself, so unlike the zip path there
    is nothing to carry over by hand.
    """

    if fmt is ArchiveFormat.TAR_ZST:
        compressor = zstandard.ZstdCompressor(
            level=3 if level is None else level,
            # -1 lets zstandard pick one worker per core; this is where a
            # tar's parallelism has to come from, since the stream itself
            # cannot be split the way zip members can.
            threads=-1,
        ).stream_writer(out)
    else:
        compressor = gzip.GzipFile(
            fileobj=out,
            mode="wb",
            compresslevel=6 if level is None else level,
        )

    with compressor as stream, tarfile.open(fileobj=stream, mode="w|") as tf:
        for path, arcname, _ in entries:
            # recursive=False because the walk already yields every member,
            # with the include/exclude rules applied.
            try:
                tf.add(path, arcname=arcname, recursive=False)
            except OSError:
                # Same policy as the zip path: a file that vanished mid-run
                # is dropped rather than failing the whole backup.
                continue
