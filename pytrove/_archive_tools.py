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
from pathlib import Path
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
    skip: Optional[Path] = None,
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

    `skip` is the archive being written. When it lands inside the tree
    being walked, it and the temp file it is being written through are
    both left out -- otherwise the archive records itself, half-finished,
    at whatever length it happened to have reached. Writing to the same
    name repeatedly would then grow it on every run, each archive
    swallowing the last.
    """

    stack = [root]
    emitted = set()

    # atomic_write names its temp file ".{archive}.<random>.tmp" beside the
    # destination, so both the finished archive and the one in flight have
    # to be recognised.
    # Empty when there is nothing to skip, which makes the guard below fall
    # through on its first test rather than needing a None check per entry.
    skip_path = os.path.normcase(str(skip)) if skip is not None else ""
    skip_temp = f".{skip.name}." if skip is not None else ""

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

            if skip_path and (
                os.path.normcase(entry.path) == skip_path
                or (entry.name.startswith(skip_temp) and entry.name.endswith(".tmp"))
            ):
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


# First bytes that identify each container, for detecting a format from the
# file rather than trusting its extension.
_MAGIC = (
    (b"PK\x03\x04", ArchiveFormat.ZIP),
    (b"PK\x05\x06", ArchiveFormat.ZIP),   # an empty archive
    (b"\x1f\x8b", ArchiveFormat.TAR_GZ),
    (b"\x28\xb5\x2f\xfd", ArchiveFormat.TAR_ZST),
)


def _detect_format(path: str) -> ArchiveFormat:
    """Identify an archive by its leading bytes, falling back to its suffix.

    Content beats extension because the extension is a claim, not a fact --
    a .zip that is really a tar.gz should extract, and one renamed to hide
    what it is should not be trusted on the strength of its name.
    """

    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except OSError:
        head = b""

    for magic, fmt in _MAGIC:
        if head.startswith(magic):
            return fmt

    lower = path.lower()

    for suffix, fmt in ((".zip", ArchiveFormat.ZIP),
                        (".tar.zst", ArchiveFormat.TAR_ZST),
                        (".tar.gz", ArchiveFormat.TAR_GZ),
                        (".tgz", ArchiveFormat.TAR_GZ)):
        if lower.endswith(suffix):
            return fmt

    raise ValueError(f"extract_archive: cannot tell what format {path!r} is")


def _safe_target(dest: Path, arcname: str) -> Optional[Path]:
    """Resolve `arcname` under `dest`, or None if it would escape.

    An archive is untrusted input, and member names are attacker-controlled
    strings, not paths that have been checked by anything. A name like
    "../../etc/cron.d/x" or "C:/Windows/System32/x" extracts outside the
    destination entirely -- the "Zip Slip" class of bug, and CVE-2007-4559
    for tarfile, whose extractall() offered no protection at all before the
    filters added in 3.12.

    The check resolves the candidate and confirms `dest` is genuinely one
    of its parents, which catches traversal spelled any way -- "..", a
    drive letter, backslashes, or a mix of them.

    A leading "/" is stripped rather than rejected, so "/etc/passwd" lands
    at dest/etc/passwd. That is what tar itself does with an absolute
    member, and it keeps the data instead of dropping it while still
    containing it. What cannot be made to fit -- anything that resolves
    outside even after that -- is refused.

    The resolved path is what comes back, so a name like "a/../b.txt"
    writes dest/b.txt without also creating an "a" directory nothing
    needed.
    """

    name = arcname.replace("\\", "/").strip("/")

    if not name or (len(name) > 1 and name[1] == ":"):
        return None

    try:
        resolved = (dest / name).resolve()
    except OSError:
        return None

    return resolved if resolved == dest or dest in resolved.parents else None


def _extract_zip(src: Path, dest: Path, include, exclude, workers, executor) -> None:
    """Inflate members in threads, reading their bytes on one thread.

    The compressed bytes are read serially from a single handle -- so no
    lock is needed on it -- and only the inflate and the write happen in
    parallel, both of which release the GIL. Measured 1.95x on 20 cores;
    far less than compression's 11x because extracting 10k files is
    dominated by the write syscalls, not by the CPU.

    Reading is batched for the same reason it is on the writing side:
    Executor.map submits its whole iterable at once, so an unbatched run
    would hold every compressed member in memory before writing one.
    """

    owned = executor is None
    count = workers or os.cpu_count() or 1
    pool = executor or ThreadPoolExecutor(count)

    def write(item):
        target, compress_type, blob = item
        data = zlib.decompress(blob, -15) if compress_type == zipfile.ZIP_DEFLATED else blob
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "wb") as out:
            out.write(data)

    try:
        with zipfile.ZipFile(src) as zf:
            infos = zf.infolist()
            fp = zf.fp

            def pending():
                for info in infos:
                    target = _safe_target(dest, info.filename)

                    if target is None:
                        continue

                    if info.filename.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                        continue

                    if exclude and _matches(info.filename, exclude):
                        continue
                    if include and not _matches(info.filename, include):
                        continue

                    # The local header's length varies with the name and
                    # extra field, so the data offset can only be found by
                    # reading it -- the central directory records where the
                    # header starts, not where the data does.
                    fp.seek(info.header_offset)  # type: ignore[union-attr]
                    header = fp.read(30)  # type: ignore[union-attr]
                    name_len = int.from_bytes(header[26:28], "little")
                    extra_len = int.from_bytes(header[28:30], "little")
                    fp.seek(info.header_offset + 30 + name_len + extra_len)  # type: ignore[union-attr]

                    yield target, info.compress_type, fp.read(info.compress_size)  # type: ignore[union-attr]

            items = pending()

            while batch := list(islice(items, count * _BATCH_PER_WORKER)):
                list(pool.map(write, batch))
    finally:
        if owned:
            pool.shutdown()


def _extract_tar(src: Path, dest: Path, fmt: ArchiveFormat, include, exclude, workers, executor) -> None:
    """Read the tar stream serially, write its members in threads.

    A tar is one stream, so nothing about reading it can be parallelised --
    but the writes can, and on a tree of many small files those are most of
    the cost. Measured 1.86x.

    Only regular files and directories are extracted. Symlinks, hardlinks
    and device nodes are skipped: a symlink member can point anywhere, and
    a later member writing "through" it lands outside the destination even
    though its own name looked safe.
    """

    owned = executor is None
    count = workers or os.cpu_count() or 1
    pool = executor or ThreadPoolExecutor(count)

    def write(item):
        target, data = item
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "wb") as out:
            out.write(data)

    if fmt is ArchiveFormat.TAR_ZST:
        raw = open(src, "rb")
        stream = zstandard.ZstdDecompressor().stream_reader(raw)
    else:
        raw = None
        stream = gzip.open(src, "rb")

    try:
        with tarfile.open(fileobj=stream, mode="r|") as tf:
            def pending():
                for member in tf:
                    target = _safe_target(dest, member.name)

                    if target is None:
                        continue

                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue

                    if not member.isfile():
                        continue

                    if exclude and _matches(member.name, exclude):
                        continue
                    if include and not _matches(member.name, include):
                        continue

                    handle = tf.extractfile(member)

                    if handle is not None:
                        yield target, handle.read()

            items = pending()

            while batch := list(islice(items, count * _BATCH_PER_WORKER)):
                list(pool.map(write, batch))
    finally:
        if owned:
            pool.shutdown()

        stream.close()

        if raw is not None:
            raw.close()
