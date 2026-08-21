from pathlib import Path
from typing import Optional, Union
from concurrent.futures import ThreadPoolExecutor

from .typings import NestedContainer, PathLike
from .enums import ArchiveFormat
from .errors import ValidationError
from .iter_tools import iter_flat_cont, to_frozenset
from .files_tools import atomic_write, resolve_path
from ._archive_tools import (
    HAS_ZSTD,
    _iter_entries,
    _write_tar,
    _write_zip,
)


def backup_folder(
    src: PathLike,
    dest: PathLike,
    *,
    format: Union[ArchiveFormat, str] = ArchiveFormat.ZIP,
    include: Optional[NestedContainer[str]] = None,
    exclude: Optional[NestedContainer[str]] = None,
    level: Optional[int] = None,
    workers: Optional[int] = None,
    executor: Optional[ThreadPoolExecutor] = None,
    follow_symlinks: bool = False,
    hidden: bool = False,
    fsync: bool = True,
    ) -> Path:

    """Archive the folder at `src` into `dest`, and return the archive path.

    `dest` may name the archive itself, or an existing directory to put it
    in -- in which case it is named after `src` with the format's extension.
    The archive is written through atomic_write, so an interrupted backup
    leaves no half-file behind and never replaces a previous archive with a
    truncated one.

    `include`/`exclude` are glob patterns (a single one, a list, or any
    nesting of them), matched against each entry's path relative to `src`
    and against its bare name -- so both "logs/*.tmp" and "*.tmp" work.
    `exclude` wins over `include`, and an excluded directory is skipped
    without being walked at all. With no `include`, everything not excluded
    is archived.

    Hidden entries are left out unless `hidden=True` -- anything whose name
    starts with a dot, plus whatever carries the hidden attribute on
    Windows. A hidden directory is not descended into either, so a .git or
    .venv costs one check rather than a walk of everything inside it.

    Empty directories are left out too, and so is one whose entire contents
    were filtered away: a directory is recorded only when a file inside it
    is actually being archived. Extracting therefore reproduces the files
    and the paths they need, not the shape of the source tree.

    `format` picks the container, see ArchiveFormat:

      ZIP (default)  every file compressed independently, so the work
                     parallelises across `workers` threads -- zlib releases
                     the GIL, which is what makes that scale (~11x on 20
                     cores) with no free-threaded interpreter needed.
      TAR_ZST        one stream, parallelised inside zstandard instead;
                     reaches gzip's ratio several times faster. Needs the
                     `zstd` extra.
      TAR_GZ         one stream, gzip, no parallelism available at all.

    `level` defaults per format (6 for zip and gzip, 3 for zstd). Higher
    trades time for size; on zstd the jump to 19 costs far more than it
    saves and is rarely worth it.

    `workers` defaults to os.cpu_count(). Pass `executor` to reuse a pool
    you already own instead of letting this build and tear one down.

    Files are read, compressed and written in batches rather than all at
    once, so peak memory tracks the batch rather than the size of the tree.
    """

    src = resolve_path(src, strict=True)
    dest = resolve_path(dest)

    if not src.is_dir():
        raise ValidationError(f"backup_folder: {str(src)!r} is not a directory")

    fmt = ArchiveFormat(format)
    dest_path = dest / f"{src.name}.{fmt.value}" if dest.is_dir() else dest

    if fmt is ArchiveFormat.TAR_ZST and not HAS_ZSTD:
        raise ImportError(
            "To use this feature, all required packages must be installed.\n"
            "Run: pip install 'pytrove[zstd]'\n"
            "\n"
            "Required : 'zstandard'\n"
            "Missing  : 'zstandard'"
        )

    includes = to_frozenset(iter_flat_cont(include))
    excludes = to_frozenset(iter_flat_cont(exclude))
    entries = _iter_entries(str(src), includes, excludes, follow_symlinks, hidden)

    with atomic_write(dest_path, binary=True, fsync=fsync) as out:
        if fmt is ArchiveFormat.ZIP:
            _write_zip(out, entries, level or 6, workers, executor)
        else:
            _write_tar(out, entries, fmt, level)

    return dest_path


__all__ = "backup_folder",

