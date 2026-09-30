"""The quarantine rules of spec §3.4.1: restore never replaces, and an entry is released
only when its bytes are preserved."""
import ctypes
import errno
import os
import stat
from contextlib import ExitStack
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .capture import open_nofollow

QUARANTINE = "session-archive-quarantine"
AT_FDCWD = -100
RENAME_NOREPLACE = 1
_libc = ctypes.CDLL(None, use_errno=True)


def rename_noreplace(src: Path, dst: Path) -> None:
    """renameat2(RENAME_NOREPLACE): atomic, and fails with EEXIST instead of replacing dst."""
    _rename_at(AT_FDCWD, src, AT_FDCWD, dst)


def _rename_at(src_fd: int, src, dst_fd: int, dst) -> None:
    if _libc.renameat2(src_fd, os.fsencode(src), dst_fd, os.fsencode(dst), RENAME_NOREPLACE) != 0:
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
    """Every entry's inode, including nested directories; never follow symlinks."""
    found = set()
    for path in paths:
        fd = open_nofollow(path, os.O_PATH)
        try:
            _collect_inodes(fd, found)
        finally:
            os.close(fd)
    return found


def _collect_inodes(fd: int, found: set[tuple[int, int]]) -> None:
    info = os.fstat(fd)
    found.add((info.st_dev, info.st_ino))
    if not stat.S_ISDIR(info.st_mode):
        return
    directory = os.open(".", os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                child = os.open(entry.name, os.O_PATH | os.O_NOFOLLOW, dir_fd=directory)
                try:
                    _collect_inodes(child, found)
                finally:
                    os.close(child)
    finally:
        os.close(directory)


def release(entry: Path, live_path: Path, preserve: Callable[[Path], bool]) -> bool:
    """Remove a quarantined file only when (a) its inode is still reachable at live_path or
    (b) preserve(entry) confirms the archive holds its exact bytes. False keeps it."""
    with ExitStack() as cleanup:
        parent = open_nofollow(entry.parent, os.O_RDONLY | os.O_DIRECTORY)
        cleanup.callback(os.close, parent)
        held = os.lstat(entry.name, dir_fd=parent)
        try:
            fd = open_nofollow(live_path, os.O_PATH)
            try:
                live = os.fstat(fd)
            finally:
                os.close(fd)
        except (FileNotFoundError, NotADirectoryError):
            live = None
        same_live = live is not None and os.path.samestat(live, held)
        if not same_live:
            if not preserve(entry):
                return False
        # Preserve may inspect open inodes. Pin the entry afterwards so our own O_PATH
        # descriptor cannot masquerade as a writer during that inspection.
        try:
            entry_fd = (os.open(entry.name, os.O_PATH | os.O_NOFOLLOW, dir_fd=parent)
                        if same_live else open_nofollow(entry, os.O_PATH))
        except (FileNotFoundError, NotADirectoryError):
            return False
        cleanup.callback(os.close, entry_fd)
        pinned = os.fstat(entry_fd)
        if (not os.path.samestat(pinned, held)
                or (not same_live and (pinned.st_size, pinned.st_mtime_ns)
                    != (held.st_size, held.st_mtime_ns))):
            return False
        private = f".release-{uuid4().hex}"
        try:
            _rename_at(parent, entry.name, parent, private)
        except FileNotFoundError:
            return False
        current = os.stat(private, dir_fd=parent, follow_symlinks=False)
        if (not os.path.samestat(current, held)
                or (not same_live and (current.st_size, current.st_mtime_ns)
                    != (held.st_size, held.st_mtime_ns))):
            try:
                _rename_at(parent, private, parent, entry.name)
            except FileExistsError:
                pass  # Keep the claimed entry in quarantine beside the recreated name.
            return False
        os.unlink(private, dir_fd=parent)
        return True


def remove_empty_dirs(top: Path, stop: Path) -> None:
    """Remove empty directories under and including top, then empty parents up to stop."""
    top, stop = Path(os.path.abspath(top)), Path(os.path.abspath(stop))
    relative = top.relative_to(stop)
    if top == stop:
        return
    if top.is_symlink():
        raise ValueError("cleanup path is a symlink")
    with ExitStack() as cleanup:
        try:
            fd = open_nofollow(stop, os.O_RDONLY | os.O_DIRECTORY)
        except FileNotFoundError:
            return
        cleanup.callback(os.close, fd)
        parents = []
        for name in relative.parts:
            parents.append((fd, name))
            try:
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                break
            cleanup.callback(os.close, fd)
        else:
            _remove_empty_children(fd)
        for parent, name in reversed(parents):
            if not _rmdir(name, parent):
                break


def _remove_empty_children(fd: int) -> None:
    with os.scandir(fd) as entries:
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            try:
                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                continue
            try:
                _remove_empty_children(child)
            finally:
                os.close(child)
            _rmdir(entry.name, fd)


def _rmdir(name: str, parent: int) -> bool:
    try:
        os.rmdir(name, dir_fd=parent)
    except FileNotFoundError:
        return True
    except OSError as error:
        if error.errno in (errno.ENOTEMPTY, errno.EEXIST):
            return False
        raise
    return True
