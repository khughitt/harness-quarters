"""The quarantine rules of spec §3.4.1: restore never replaces, and an entry is released
only when its bytes are preserved."""
import ctypes
import os
import stat
from pathlib import Path
from typing import Callable

from .capture import open_nofollow, walk_files

QUARANTINE = "session-archive-quarantine"
AT_FDCWD = -100
RENAME_NOREPLACE = 1
_libc = ctypes.CDLL(None, use_errno=True)


def rename_noreplace(src: Path, dst: Path) -> None:
    """renameat2(RENAME_NOREPLACE): atomic, and fails with EEXIST instead of replacing dst."""
    if _libc.renameat2(AT_FDCWD, os.fsencode(src), AT_FDCWD, os.fsencode(dst), RENAME_NOREPLACE) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(dst))


def quarantine_dir(home: Path, run_id: str) -> Path:
    return home / QUARANTINE / run_id


def leftovers(homes) -> list[Path]:
    """Quarantine roots holding any nondirectory entry stop the next prune (§3.4.4)."""
    found = []
    for home in sorted(set(homes)):
        root = home / QUARANTINE
        try:
            info = root.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode) or _has_entries(root):
            found.append(root)
    return found


def _has_entries(root: Path) -> bool:
    stack = [root]
    while stack:
        directory = stack.pop()
        fd = open_nofollow(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with os.scandir(fd) as entries:
                for entry in entries:
                    if not entry.is_dir(follow_symlinks=False):
                        return True
                    stack.append(directory / entry.name)
        finally:
            os.close(fd)
    return False


def inodes(paths) -> set[tuple[int, int]]:
    found = set()
    for path in paths:
        for member in ([path, *walk_files(path)] if path.is_dir() else [path]):
            info = os.stat(member, follow_symlinks=False)
            found.add((info.st_dev, info.st_ino))
    return found


def release(entry: Path, live_path: Path, preserve: Callable[[Path], bool]) -> bool:
    """Remove a quarantined file only when (a) its inode is still reachable at live_path or
    (b) preserve(entry) confirms the archive holds its exact bytes. False keeps it."""
    held = os.stat(entry, follow_symlinks=False)
    try:
        fd = open_nofollow(live_path, os.O_PATH)
        try:
            live = os.fstat(fd)
        finally:
            os.close(fd)
    except (FileNotFoundError, NotADirectoryError):
        live = None
    if live is not None and (live.st_dev, live.st_ino) == (held.st_dev, held.st_ino):
        os.unlink(entry)
        return True
    if preserve(entry):
        os.unlink(entry)
        return True
    return False


def remove_empty_dirs(top: Path, stop: Path) -> None:
    """Remove empty directories under and including top, then empty parents up to stop."""
    top, stop = top.resolve(), stop.resolve()
    top.relative_to(stop)
    if top == stop:
        return
    if top.is_dir():
        for dirpath, _dirnames, _filenames in os.walk(top, topdown=False):
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    parent = top.parent
    while parent != stop and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
