"""No-replace restore and the release rule (spec §3.4.1)."""
import os

import pytest

from session_archive.quarantine import (QUARANTINE, inodes, leftovers, quarantine_dir, release,
                                        remove_empty_dirs, rename_noreplace)
from session_archive.testing import write


def test_rename_noreplace_moves(tmp_path):
    src = write(tmp_path / "a", b"a")
    rename_noreplace(src, tmp_path / "b")
    assert (tmp_path / "b").read_bytes() == b"a" and not src.exists()


@pytest.mark.parametrize("as_dir", [False, True])
def test_rename_noreplace_refuses_existing_target(tmp_path, as_dir):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    if as_dir:
        write(src / "inner", b"s")
        write(dst / "other", b"d")
    else:
        write(src, b"s")
        write(dst, b"d")
    with pytest.raises(FileExistsError):
        rename_noreplace(src, dst)
    assert src.exists() and dst.exists()
    assert (dst / "other" if as_dir else dst).read_bytes() == b"d"


def test_rename_noreplace_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        rename_noreplace(tmp_path / "absent", tmp_path / "b")


def test_release_rule_a_same_inode(tmp_path):
    live = write(tmp_path / "live", b"x")
    entry = tmp_path / "entry"
    os.link(live, entry)
    assert release(entry, live, lambda path: pytest.fail("preserve must not run"))
    assert not entry.exists() and live.exists()


def test_release_rule_b(tmp_path):
    entry = write(tmp_path / "entry", b"x")
    assert not release(entry, tmp_path / "gone", lambda path: False)
    assert entry.exists()
    assert release(entry, tmp_path / "gone", lambda path: True)
    assert not entry.exists()


def test_release_rule_b_when_live_is_another_file(tmp_path):
    entry = write(tmp_path / "entry", b"x")
    live = write(tmp_path / "live", b"fragment")
    assert not release(entry, live, lambda path: False)
    assert entry.exists()


def test_leftovers_and_cleanup(tmp_path):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    assert leftovers([home]) == []
    (qdir / "p" / "s").mkdir(parents=True)
    assert leftovers([home]) == []          # empty directories are not leftovers
    write(qdir / "p" / "s" / "f", b"x")
    assert leftovers([home, home]) == [home / QUARANTINE]
    (qdir / "p" / "s" / "f").unlink()
    remove_empty_dirs(qdir / "p" / "s", home / QUARANTINE)
    assert (home / QUARANTINE).is_dir() and not qdir.exists()


def test_inodes_cover_directory_members(tmp_path):
    f = write(tmp_path / "d" / "x", b"x")
    info = os.stat(f)
    assert (info.st_dev, info.st_ino) in inodes([tmp_path / "d"])


@pytest.mark.parametrize("through_parent", [False, True])
def test_release_keeps_bytes_reached_only_through_live_symlink(tmp_path, through_parent):
    entry = write(tmp_path / "quarantine" / "entry", b"only copy")
    if through_parent:
        (tmp_path / "live-dir").symlink_to(entry.parent, target_is_directory=True)
        live = tmp_path / "live-dir" / "entry"
    else:
        live = tmp_path / "live"
        live.symlink_to(entry)
    assert not release(entry, live, lambda path: False)
    assert entry.read_bytes() == live.read_bytes() == b"only copy"


@pytest.mark.parametrize("kind", ["symlink", "directory-symlink", "fifo"])
def test_leftovers_include_nonregular_entries(tmp_path, kind):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    qdir.mkdir(parents=True)
    entry = qdir / "entry"
    if kind == "fifo":
        os.mkfifo(entry)
    elif kind == "directory-symlink":
        target = tmp_path / "empty"
        target.mkdir()
        entry.symlink_to(target, target_is_directory=True)
    else:
        entry.symlink_to(tmp_path / "missing")
    assert leftovers([home]) == [home / QUARANTINE]


def test_leftovers_refuse_a_symlink_root(tmp_path):
    home = tmp_path / "h"
    home.mkdir()
    empty = tmp_path / "empty"
    empty.mkdir()
    root = home / QUARANTINE
    root.symlink_to(empty, target_is_directory=True)
    assert leftovers([home]) == [root]


def test_cleanup_preserves_stop_when_top_is_stop(tmp_path):
    stop = tmp_path / QUARANTINE
    stop.mkdir()
    remove_empty_dirs(stop, stop)
    assert stop.is_dir()


@pytest.mark.parametrize("path_form", ["sibling", "dotdot", "symlink"])
def test_cleanup_refuses_paths_outside_stop(tmp_path, path_form):
    stop = tmp_path / QUARANTINE
    other = tmp_path / "other"
    stop.mkdir()
    other.mkdir()
    top = other
    if path_form == "dotdot":
        top = stop / ".." / "other"
    elif path_form == "symlink":
        top = stop / "link"
        top.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError):
        remove_empty_dirs(top, stop)
    assert other.is_dir() and stop.is_dir()
