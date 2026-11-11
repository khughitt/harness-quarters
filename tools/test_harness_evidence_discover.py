"""Discovery conformance from obs test_place.py at fe61869f0041eff423ed495d10845ef3cf3d5638.
Index facts and candidate selection remain in obs; this module reads paths and metadata only.
"""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pytest

from harness_evidence_testing import FIXTURES, PATHS, materialize

TOOLS = Path(__file__).resolve().parent
THREAD = "01900000-0000-7000-8000-0000000000a2"
SEGMENT = "01900000-0000-7000-8000-0000000000b1"


def api():
    return importlib.import_module("harness_evidence.discover")


def clean_env(home):
    home.mkdir(exist_ok=True)
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home)}


def run_json(args, tmp_path, env=None):
    proc = subprocess.run([sys.executable, str(TOOLS / "harness-evidence"), *args],
                          cwd=tmp_path, env=clean_env(tmp_path / "user-home") if env is None else env,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    return [json.loads(line) for line in proc.stdout.splitlines()]


class PlaceTest(unittest.TestCase):
    def setUp(self):
        self.sp = api()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = materialize("home", self.tmp)
        self.roots = self.sp.roots(self.home)

    def path(self, short):
        return self.home / PATHS[short].split("/", 1)[1]

    def test_roots_names_and_profiles(self):
        self.assertEqual([(r.home, r.store, r.profile) for r in self.roots], [
            ("claude", "live", "personal"), ("claude-work", "live", "work"),
            ("codex", "live", "personal"), ("codex", "archived", "personal"),
            ("codex-work", "live", "work"), ("codex-work", "archived", "work")])
        self.assertEqual([r.harness for r in self.roots], ["claude-code"] * 2 + ["codex"] * 4)
        elsewhere = self.tmp / "elsewhere" / "-w-linked"
        elsewhere.mkdir(parents=True)
        linked = self.home / ".claude/projects/-w-linked/c0000000-0000-4000-8000-0000000000aa.jsonl"
        shutil.copy2(self.path("CA"), elsewhere / linked.name)
        linked.parent.symlink_to(elsewhere)
        listing = self.sp.list_files(self.roots, None)
        self.assertEqual([r["state"] for r in listing.roots], ["searched"] * 5 + ["absent"])
        self.assertEqual(listing.roots[-1]["files"], 0)
        expected = [self.path(key) for key in ("CA", "AG", "CW", "CW2", "XP", "XC", "XG", "XA", "XW")]
        self.assertEqual(sorted(listing.files), sorted(expected + [linked]))
        self.assertEqual(listing.aliases, [])
        self.assertEqual(listing.skipped_by_mtime, 0)
        os.utime(self.path("XA"), (1_000_000, 1_000_000))
        later = self.sp.list_files(self.roots, 2_000_000_000)
        self.assertNotIn(self.path("XA"), later.files)
        self.assertEqual(later.skipped_by_mtime, 1)
        self.assertEqual(later.roots[3]["files"], 0)

    def test_unreadable_root(self):
        if os.geteuid() == 0:
            self.skipTest("root lists a mode-0 directory")
        root = self.home / ".codex-work/sessions"
        root.chmod(0)
        self.addCleanup(root.chmod, 0o755)
        listing = self.sp.list_files(self.roots, None)
        self.assertEqual(listing.roots[4]["state"], "unreadable")
        self.assertEqual((listing.roots[4]["errors"], listing.roots[4]["listing"]), (1, "failed"))
        self.assertNotIn(self.path("XW"), listing.files)

    def test_partial_listing_counts_its_errors(self):
        if os.geteuid() == 0:
            self.skipTest("root lists a mode-0 directory")
        day = self.path("XP").parent
        day.chmod(0)
        self.addCleanup(day.chmod, 0o755)
        entry = self.sp.list_files(self.roots, None).roots[2]
        self.assertEqual((entry["state"], entry["listing"], entry["errors"]),
                         ("unreadable", "partial", 1))
        self.assertEqual(len(entry["first_errors"]), 1)

    def test_root_under_unreadable_parent_is_unreadable_not_absent(self):
        if os.geteuid() == 0:
            self.skipTest("root reaches through a mode-0 directory")
        parent = self.home / ".codex-work"
        parent.chmod(0)
        self.addCleanup(parent.chmod, 0o755)
        entries = self.sp.list_files(self.roots, None).roots
        self.assertEqual([e["state"] for e in entries[4:]], ["unreadable", "unreadable"])
        self.assertEqual(entries[4]["listing"], "failed")

    def test_symlink_is_alias(self):
        link = self.home / ".claude-work/projects/-w-link" / self.path("CW").name
        link.parent.mkdir()
        link.symlink_to(self.path("CW"))
        listing = self.sp.list_files(self.roots, None)
        self.assertEqual(listing.aliases, [link])
        self.assertNotIn(link, listing.files)
        self.path("CW").unlink()
        self.assertEqual(self.sp.list_files(self.roots, None).aliases, [link])

    def test_place_of(self):
        place = self.sp.place_of(self.path("XA"), self.roots)
        self.assertEqual((place.harness, place.home, place.profile, place.store, place.relpath),
                         ("codex", "codex", "personal", "archived", PATHS["XA"].split("/", 2)[2]))
        self.assertEqual(self.sp.place_of(self.path("XA"), self.roots, "replayed").store, "replayed")
        gone = self.home / ".claude/projects/-w-x/gone.jsonl"
        self.assertEqual(self.sp.place_of(gone, self.roots).relpath, "projects/-w-x/gone.jsonl")
        with self.assertRaises(ValueError):
            self.sp.place_of(self.tmp / "elsewhere.jsonl", self.roots)


def test_filename_identity_reads_thread_and_segment():
    assert api().filename_identity("codex", Path(f"rollout-2026-10-01T09-00-00-{THREAD}_{SEGMENT}.jsonl")) == {
        "thread": THREAD, "segment": SEGMENT, "basis": "convention"}
    assert api().filename_identity("codex", Path(f"rollout-2026-10-01T09-00-00-{THREAD}.jsonl")) == {
        "thread": THREAD, "segment": None, "basis": "convention"}


@pytest.mark.parametrize("harness, name", [
    ("claude-code", f"rollout-2026-10-01T09-00-00-{THREAD}.jsonl"),
    ("codex", f"other-{THREAD}.jsonl"), ("codex", "rollout-no-identity.jsonl"),
    ("codex", f"rollout-2026-10-01T09-00-00-{THREAD}.txt"),
])
def test_filename_identity_rejects_other_names(harness, name):
    assert api().filename_identity(harness, Path(name)) is None


def test_explicit_roots_replace_homes(tmp_path):
    root = FIXTURES / "home/.codex/sessions"
    objs = run_json(["discover", "--home", str(FIXTURES / "home"), "--root", f"codex={root}"], tmp_path)
    assert [o["path"] for o in objs if o["object"] == "root"] == [str(root)]
    assert {o["harness"] for o in objs if o["object"] == "file"} == {"codex"}
    assert objs[-1]["object"] == "discover_end"
    assert (objs[-1]["roots"], objs[-1]["files"]) == (1, 3)
    assert api().roots(tmp_path, []) == []


def test_discover_reads_no_obs_environment(tmp_path):
    env = clean_env(tmp_path / "empty-home")
    env.update(OBS_CODEX_SESSIONS=str(FIXTURES / "home/.codex/sessions"),
               OBS_CLAUDE_PROJECTS=str(FIXTURES / "home/.claude/projects"))
    objs = run_json(["discover"], tmp_path, env)
    assert objs[-1]["files"] == 0
    assert objs[-1]["roots"] == 6
    assert all(o["state"] == "absent" for o in objs[:-1])


def test_discover_objects_include_provenance_place_and_stat(tmp_path):
    objs = run_json(["discover", "--home", str(FIXTURES / "home")], tmp_path)
    assert [o["object"] for o in objs] == ["root"] * 6 + ["file"] * 9 + ["discover_end"]
    for obj in objs:
        assert obj["schema"] == "harness-evidence/1"
        assert obj["decoder"]["version"] == "2"
        assert obj["decoder"]["revision"]
        assert obj["decoder"] == objs[0]["decoder"]
    for obj in objs[6:-1]:
        path = Path(obj["path"])
        info = path.stat()
        assert (obj["device"], obj["inode"], obj["size"], obj["mtime_ns"]) == (
            info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        dot, rel = path.relative_to(FIXTURES / "home").as_posix().split("/", 1)
        assert obj["place"] == {
            "harness": obj["harness"], "home": dot[1:],
            "profile": "work" if dot.endswith("-work") else "personal",
            "store": "archived" if rel.startswith("archived_sessions/") else "live", "relpath": rel}
        assert obj["state"] == "listed"
        assert (obj["filename_identity"] is not None) == (obj["harness"] == "codex")
    assert objs[-1]["files"] == 9


def test_listing_prunes_claude_and_does_not_follow_codex_directory_links(tmp_path):
    home = tmp_path / "home"
    for rel in (".claude/projects/root.jsonl", ".claude/projects/project/valid.jsonl",
                ".claude/projects/project/session/wrong.jsonl",
                ".claude/projects/project/session/subagents/child.jsonl",
                ".claude/projects/project/session/subagents/deep/wrong.jsonl",
                "elsewhere/external.jsonl"):
        path = home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")
    root = home / ".codex/sessions"
    root.mkdir(parents=True)
    (root / "linked").symlink_to(home / "elsewhere")
    assert api().list_files(api().roots(home), None).files == [
        home / ".claude/projects/project/session/subagents/child.jsonl",
        home / ".claude/projects/project/valid.jsonl"]


def test_non_directory_and_absent_roots_remain_explicit(tmp_path):
    not_dir = tmp_path / "sessions"
    not_dir.write_text("not a directory")
    objs = run_json(["discover", "--root", f"codex={not_dir}",
                     "--root", f"claude-code={tmp_path / 'absent'}"], tmp_path)
    assert objs[0]["state"] == "unreadable"
    assert (objs[0]["listing"], objs[0]["errors"]) == ("failed", 1)
    assert objs[0]["first_errors"]
    assert objs[1]["state"] == "absent"
    assert (objs[-1]["roots"], objs[-1]["files"]) == (2, 0)


@pytest.mark.parametrize("value", ["codex", "codex=", "=sessions", "other=sessions"])
def test_invalid_explicit_root_fails(tmp_path, value):
    proc = subprocess.run([sys.executable, str(TOOLS / "harness-evidence"), "discover", "--root", value],
                          cwd=tmp_path, env=clean_env(tmp_path / "user-home"), capture_output=True, text=True)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "root" in proc.stderr


@pytest.mark.parametrize("failure, state", [(FileNotFoundError("gone"), "vanished"),
                                            (PermissionError("denied"), "unreadable")])
def test_file_stat_failure_emits_null_metadata_and_terminal_count(tmp_path, monkeypatch, capsys, failure, state):
    from harness_evidence import __main__ as cli
    discover = api()
    root = tmp_path / ".codex/sessions"
    root.mkdir(parents=True)
    path = root / f"rollout-time-{THREAD}.jsonl"
    path.write_text("{}\n")
    listing = discover.list_files(discover.roots(None, [("codex", root)]), None)
    monkeypatch.setattr(discover, "list_files", lambda *_: listing)
    real_stat = Path.stat

    def changed_stat(held, *args, **kwargs):
        if held == path:
            raise failure
        return real_stat(held, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", changed_stat)
    assert cli.main(["discover", "--root", f"codex={root}"]) == 0
    objs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    file = objs[1]
    assert file["state"] == state
    assert file["error"]
    assert [file[key] for key in ("device", "inode", "size", "mtime_ns")] == [None] * 4
    assert file["filename_identity"]["thread"] == THREAD
    assert (objs[-1]["roots"], objs[-1]["files"]) == (1, 1)
