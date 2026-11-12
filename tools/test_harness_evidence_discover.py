"""Discovery conformance from obs test_place.py at fe61869f0041eff423ed495d10845ef3cf3d5638.
Index facts and candidate selection remain in obs; this module reads paths and metadata only.
"""
import importlib
import fnmatch
import glob
import json
import os
from pathlib import Path
import re
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


def old_lookup(name, session_id):
    """Literal old glob and stem predicate, independent of the producer helper."""
    uuid = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    match = re.search(rf"-({uuid})(?:_({uuid}))?$", Path(name).stem)
    return fnmatch.fnmatchcase(name, f"rollout-*-{glob.escape(session_id)}*.jsonl") and (
        Path(name).stem.endswith("-" + session_id)
        or (match is not None and match.group(1) == session_id))


@pytest.mark.parametrize("name, expected", [
    ("rollout-t-T.jsonl", ["T"]),
    ("rollout-t-thread-x.jsonl", ["thread-x", "x"]),
    ("rollout-t-[]*?.jsonl", ["[]*?"]),
    ("rollout-t--T.jsonl", ["-T", "T"]),
    ("rollout--T.jsonl", ["T"]),
    ("rollout-T.jsonl", []),
    ("rollout-t-.jsonl", []),
    ("rollout-.jsonl", []),
])
def test_filename_lookup_preserves_suffix_candidates(name, expected):
    fact = api().filename_lookup("codex", Path(name))
    assert fact == {"session_ids": expected, "basis": "convention", "rule": "rollout_name_lookup"}
    for query in {*expected, "t-T", "t-thread-x", "thread", "T*", "[]", "missing"}:
        assert (query in fact["session_ids"]) == old_lookup(name, query), (name, query)


@pytest.mark.parametrize("name", [
    f"rollout-2026-10-01T09-00-00-{THREAD}.jsonl",
    f"rollout-2026-10-01T09-00-00-{THREAD}_{SEGMENT}.jsonl",
    f"rollout-{THREAD}.jsonl",
    f"rollout-{THREAD}_{SEGMENT}.jsonl",
    f"rollout--{THREAD}_{SEGMENT}.jsonl",
    "rollout-t-x-x.jsonl",
])
def test_filename_lookup_equals_old_predicate_for_every_possible_match(name):
    fact = api().filename_lookup("codex", Path(name))
    stem = Path(name).stem
    # Every old suffix match begins after a hyphen; only the UUID branch adds a
    # possible non-suffix match. Include excluded prefixes and explicit negatives.
    queries = {stem[i + 1:] for i, char in enumerate(stem) if char == "-" and stem[i + 1:]}
    queries.update({THREAD, SEGMENT, "missing", "x", "x-x", "0000000000a2", "*", "?", "[a]"})
    expected = sorted(query for query in queries if old_lookup(name, query))
    assert fact == {"session_ids": expected, "basis": "convention", "rule": "rollout_name_lookup"}
    assert all((query in fact["session_ids"]) == old_lookup(name, query) for query in queries)


@pytest.mark.parametrize("harness, name", [
    ("claude-code", "rollout-t-T.jsonl"), ("codex", "other-t-T.jsonl"),
    ("codex", "rollout-t-T.txt"), ("codex", "rollout-t-T.jsonl.bak"),
])
def test_filename_lookup_is_null_outside_codex_rollout_names(harness, name):
    assert api().filename_lookup(harness, Path(name)) is None


def test_discover_publishes_lookup_on_files_and_aliases_without_claiming_identity(tmp_path):
    root = tmp_path / ".codex/sessions"
    root.mkdir(parents=True)
    source = root / "rollout-t-T.jsonl"
    source.write_bytes(b"not transcript content\n")
    alias = root / "rollout-t-thread-x.jsonl"
    alias.symlink_to(source)
    objs = run_json(["discover", "--root", f"codex={root}"], tmp_path)
    assert objs[1]["filename_lookup"] == {
        "session_ids": ["T"], "basis": "convention", "rule": "rollout_name_lookup"}
    assert objs[0]["aliases"][0]["filename_lookup"] == {
        "session_ids": ["thread-x", "x"], "basis": "convention", "rule": "rollout_name_lookup"}
    assert objs[1]["filename_identity"] is None
    assert objs[0]["aliases"][0]["filename_identity"] is None
    assert (objs[-1]["roots"], objs[-1]["files"]) == (1, 1)


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
        assert obj["decoder"]["version"] == "8"
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
        if obj["harness"] == "codex":
            assert obj["filename_identity"]["thread"] in obj["filename_lookup"]["session_ids"]
        else:
            assert obj["filename_lookup"]["rule"] == "claude_name_lookup"
            assert obj["path_facts"]["ref"].startswith(obj["place"]["home"] + ":")
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
    assert objs[0]["aliases"] == objs[1]["aliases"] == []


def test_discover_exposes_known_and_dangling_aliases_without_counting_files(tmp_path):
    root = tmp_path / ".codex/sessions"
    root.mkdir(parents=True)
    source = root / "source.jsonl"
    source.write_bytes(b"not transcript content\n")
    alias = root / f"rollout-time-{THREAD}_{SEGMENT}.jsonl"
    alias.symlink_to(source)
    dangling = root / "dangling.jsonl"
    dangling.symlink_to(root / "missing.jsonl")
    objs = run_json(["discover", "--root", f"codex={root}"], tmp_path)
    assert objs[0]["files"] == objs[-1]["files"] == 1
    assert objs[0]["bytes"] == source.stat().st_size
    assert [o["path"] for o in objs if o["object"] == "file"] == [str(source)]
    assert all(alias.pop("path_facts") is None for alias in objs[0]["aliases"])
    lookup = objs[0]["aliases"][1].pop("filename_lookup")
    assert lookup["basis"] == "convention" and lookup["rule"] == "rollout_name_lookup"
    assert THREAD in lookup["session_ids"] and f"{THREAD}_{SEGMENT}" in lookup["session_ids"]
    assert objs[0]["aliases"] == [
        {"path": str(dangling), "place": {"harness": "codex", "home": "codex",
         "profile": "personal", "store": "live", "relpath": "sessions/dangling.jsonl"},
         "filename_identity": None, "filename_lookup": None},
        {"path": str(alias), "place": {"harness": "codex", "home": "codex",
         "profile": "personal", "store": "live", "relpath": f"sessions/{alias.name}"},
         "filename_identity": {"thread": THREAD, "segment": SEGMENT, "basis": "convention"}}]


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
    assert THREAD in file["filename_lookup"]["session_ids"]
    assert (objs[-1]["roots"], objs[-1]["files"]) == (1, 1)


@pytest.mark.parametrize("operation", ["stat", "lstat"])
@pytest.mark.parametrize("failure, state", [(PermissionError(13, "denied"), "unreadable"),
                                            (FileNotFoundError(2, "gone"), "vanished"),
                                            (OSError(5, "I/O failure"), "unreadable")])
def test_initial_metadata_failure_keeps_enumerated_candidate(tmp_path, monkeypatch, capsys,
                                                           operation, failure, state):
    from harness_evidence import __main__ as cli
    root = tmp_path / ".codex/sessions"
    root.mkdir(parents=True)
    path = root / f"rollout-time-{THREAD}.jsonl"
    path.write_text("{}\n")
    alias = root / "alias.jsonl"
    alias.symlink_to(path)
    target = os if operation == "lstat" else Path
    original = getattr(target, operation)
    calls = []

    def failed_metadata(held, *args, **kwargs):
        if Path(held) == path and kwargs.get("follow_symlinks") is not False:
            calls.append(held)
            raise failure
        return original(held, *args, **kwargs)

    monkeypatch.setattr(target, operation, failed_metadata)
    assert cli.main(["discover", "--root", f"codex={root}"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    objs = [json.loads(line) for line in captured.out.splitlines()]
    assert [o["object"] for o in objs] == ["root", "file", "discover_end"]
    assert calls
    file = objs[1]
    assert file["path"] == str(path) and file["state"] == state and file["error"]
    assert [file[k] for k in ("device", "inode", "size", "mtime_ns")] == [None] * 4
    assert file["filename_identity"]["thread"] == THREAD
    assert THREAD in file["filename_lookup"]["session_ids"]
    assert (objs[0]["files"], objs[0]["bytes"], objs[-1]["files"]) == (1, 0, 1)
    if state == "unreadable":
        assert (objs[0]["state"], objs[0]["listing"], objs[0]["errors"]) == ("unreadable", "partial", 1)
    listing = api().list_files(api().roots(None, [("codex", root)]), 10**20)
    assert listing.files == [path] and listing.aliases == [alias] and listing.skipped_by_mtime == 0
