"""Cutover window records, target registration, human decisions, preparation, quiescence
and the pre-merge abort, run against throwaway roots and the transport tests' fixture hosts.
Decision dictionaries here are fixtures standing in for a recorded reply; nothing in these
tests authenticates a human or answers a prompt for a live call."""
import contextlib
import errno
import fcntl
import fnmatch
import functools
import hashlib
import io
import itertools
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import test_relay_cutover_transport as transport
from relay_cutover_bootstrap import (cli, finish, hosts, inputs, inventory, recovery,
                                     restoration, smoke, state, surfaces, window)
from relay_cutover_bootstrap import prepare as preparation
from relay_cutover_bootstrap.state import Stop

PREPARED = hashlib.sha256(b"prepared fixture").hexdigest()
# Event kinds that change files or hosts; a refused call must produce none of them.
WRITES = {"open", "mkdir", "link", "replace", "rename", "unlink", "rmdir", "write",
          "spawn", "host"}
SUBJECT = {
    "hosts": ["titan"],
    "socket": "/run/user/1000/niri.wayland-1.sock",
    "surfaces": [{"host": "titan", "pid": 4242, "start_time": 9001,
                  "command": ["/home/operator/d/familiar/bin/familiar", "panel"]}],
    "impact": "the familiar panel closes and reopens",
    "duration_seconds": 10,
}


class Events(list):
    """Filesystem calls under one base as kind:basename, with injectable faults."""

    def __init__(self, base):
        super().__init__()
        self.base, self.faults = str(base), []

    def fail(self, pattern, after=None):
        """Fail calls matching pattern, once an event matching after has happened."""
        self.faults.append((pattern, after))

    def note(self, kind, path):
        path = os.fsdecode(path)
        if not path.startswith(self.base):
            return
        event = f"{kind}:{Path(path).name}"
        for pattern, after in self.faults:
            if fnmatch.fnmatchcase(event, pattern) and (
                    after is None or any(fnmatch.fnmatchcase(seen, after) for seen in self)):
                self.append(event)
                raise OSError(errno.EIO, f"injected fault at {event}")
        self.append(event)

    def first(self, pattern, start=0):
        return next(index for index, event in enumerate(self)
                    if index >= start and fnmatch.fnmatchcase(event, pattern))

    def writes_since(self, mark):
        return [event for event in self[mark:] if event.split(":", 1)[0] in WRITES]


@pytest.fixture
def events(tmp_path, monkeypatch):
    log = Events(tmp_path)
    real = {name: getattr(os, name) for name in (
        "fsync", "open", "write", "mkdir", "unlink", "rmdir", "link", "replace", "rename")}
    written = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC

    def descriptor(fd):
        return os.readlink(f"/proc/self/fd/{fd if isinstance(fd, int) else fd.fileno()}")

    def fsync(fd):
        log.note("fsync", descriptor(fd))
        return real["fsync"](fd)

    def write(fd, data):
        log.note("write", descriptor(fd))
        return real["write"](fd, data)

    def open_(path, flags, *args, **kwargs):
        if flags & written:
            log.note("open", path)
        return real["open"](path, flags, *args, **kwargs)

    def on_path(name):
        def call(path, *args, **kwargs):
            log.note(name, path)
            return real[name](path, *args, **kwargs)
        return call

    def on_destination(name):
        def call(source, destination, *args, **kwargs):
            log.note(name, destination)
            return real[name](source, destination, *args, **kwargs)
        return call

    def spawn(*args, **kwargs):
        log.append(f"spawn:{args[0] if args else kwargs.get('args')}")
        raise AssertionError("state code must not start a child process")

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "write", write)
    monkeypatch.setattr(os, "open", open_)
    for name in ("mkdir", "unlink", "rmdir"):
        monkeypatch.setattr(os, name, on_path(name))
    for name in ("link", "replace", "rename"):
        monkeypatch.setattr(os, name, on_destination(name))
    monkeypatch.setattr(subprocess, "Popen", spawn)
    return log


@pytest.fixture
def root(tmp_path):
    return tmp_path / "state" / "hq" / "relay-cutover"


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def tree(path):
    return {str(item.relative_to(path)): item.read_bytes() if item.is_file() else None
            for item in sorted(path.rglob("*"))}


def window_file(window):
    return Path(window["directory"]) / "window.json"


def with_state(window, name):
    window = {**window, "state": name}
    state.save_record(window_file(window), window)
    return window


def applying(root):
    return with_state(state.new_window(root, PREPARED), "applying")


def settings(tmp_path, name="claude/settings.json"):
    path = tmp_path / "home" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{\n  "hooks": {}\n}\n')
    path.chmod(0o644)
    return path


def write_target(events, target, data):
    events.append("write:target")
    target.write_bytes(data)


def retained(root):
    root.mkdir(parents=True, mode=0o700)
    for name in state.RETAINED:
        if name.endswith("/"):
            (root / name).mkdir(mode=0o700)
            (root / name / "kept").write_text("evidence\n")
        else:
            (root / name).write_text("evidence\n")


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode()).hexdigest()


def recorded(window, attempt="restart-1", subject=SUBJECT, reply="yes, restart them",
             source="session"):
    """A fixture record of an explicit reply, shaped like the operator's decision file."""
    answered = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if source == "session":
        origin = {"type": "session", "session_id": "0198f3c2-session",
                  "ask": "Restart the recorded familiar panel on titan (about 10 s)?",
                  "reply": reply, "answered_at": answered}
    else:
        origin = {"type": "tty", "prompt": "Restart the recorded familiar panel? [y/N]",
                  "response": reply, "answered_at": answered}
    return {"schema": 1, "kind": "desktop", "action": "restart-surfaces",
            "window_id": window["id"], "attempt_id": attempt,
            "subject_sha256": sha(subject), "verdict": "approved", "source": origin}


def consume(window, decision, attempt="restart-1", subject=SUBJECT):
    return state.consume_decision(window, decision, kind="desktop",
                                  action="restart-surfaces", attempt_id=attempt,
                                  subject_sha256=sha(subject))


def authorized_restart(events, window, decision, **kwargs):
    consumed = consume(window, decision, **kwargs)
    events.append("host:restart")
    return consumed


def test_record_validation(tmp_path, monkeypatch):
    directory = tmp_path / "records"
    record = directory / "prepared.json"
    state.save_record(record, {"schema": 1, "value": "kept"})
    assert state.load_record(record) == {"schema": 1, "value": "kept"}
    assert (mode(directory), mode(record)) == (0o700, 0o600)

    for text, fragment in (
        ('{"schema": 2}', "schema 1"), ('{"value": 1}', "schema 1"),
        ('{"schema": true}', "schema 1"), ("[1]", "schema 1"),
        ('{"schema": 1', "invalid JSON"), ('{"schema": 1, "x": NaN}', "invalid JSON"),
        ('{"schema": 1, "verdict": "declined", "verdict": "approved"}', "invalid JSON"),
    ):
        record.write_text(text)
        with pytest.raises(Stop, match=fragment):
            state.load_record(record)
    record.write_bytes(b"\xff\xfe\xfa")
    with pytest.raises(Stop, match="invalid JSON"):
        state.load_record(record)

    state.save_record(record, {"schema": 1})
    record.chmod(0o640)
    with pytest.raises(Stop, match="mode 0640"):
        state.load_record(record)
    record.chmod(0o600)
    directory.chmod(0o755)
    with pytest.raises(Stop, match="mode 0755"):
        state.load_record(record)
    with pytest.raises(Stop, match="mode 0755"):
        state.save_record(record, {"schema": 1})
    directory.chmod(0o700)

    link = directory / "link.json"
    link.symlink_to(record)
    with pytest.raises(Stop, match="symlink"):
        state.load_record(link)
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(directory)
    with pytest.raises(Stop, match="not a directory"):
        state.load_record(linked_parent / "prepared.json")
    (directory / "nested").mkdir(mode=0o700)
    with pytest.raises(Stop, match="not a regular file"):
        state.load_record(directory / "nested")
    with pytest.raises(Stop, match="missing"):
        state.load_record(directory / "absent.json")

    uid = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: uid + 1)
    with pytest.raises(Stop, match="not owned"):
        state.load_record(record)
    monkeypatch.undo()

    for value, fragment in (({"schema": 2}, "schema 1"), ([], "schema 1"),
                            ({"schema": 1, "path": Path("/x")}, "plain JSON"),
                            ({"schema": 1, "x": float("nan")}, "plain JSON")):
        with pytest.raises(Stop, match=fragment):
            state.save_record(record, value)
    assert state.load_record(record) == {"schema": 1}


def test_record_inventory_and_active_window(root, events):
    retained(root)
    kept = tree(root)
    assert state.current_window(root) is None

    window = state.new_window(root, PREPARED)
    assert window == state.current_window(root)
    assert window["state"] == "prepared" and window["prepared_sha256"] == PREPARED
    assert window["mode"] == "live" and window["directory"] == str(root / "windows" / window["id"])
    assert state.load_record(root / "active.json") == {"schema": 1, "window": window["id"]}
    assert (mode(root / "windows"), mode(window["directory"])) == (0o700, 0o700)
    assert (mode(window_file(window)), mode(root / "active.json")) == (0o600, 0o600)
    assert {name: data for name, data in tree(root).items()
            if name.split("/")[0] in {entry.rstrip("/") for entry in state.RETAINED}} == kept

    # One active window: a second allocation refuses and writes nothing.
    mark = len(events)
    with pytest.raises(Stop, match=f"window {window['id']} is prepared"):
        state.new_window(root, PREPARED)
    assert events.writes_since(mark) == []

    for name in ("abort-incomplete", "recovery-required", "inspection-required"):
        with_state(window, name)
        with pytest.raises(Stop, match=f"is {name}"):
            state.new_window(root, PREPARED)

    # An unknown state is never treated as inactive.
    with_state(window, "migrating")
    with pytest.raises(Stop, match="unknown state 'migrating'"):
        state.current_window(root)
    with pytest.raises(Stop, match="unknown state"):
        state.new_window(root, PREPARED)

    # A completed abort permits a fresh window; the old directory stays as it was.
    aborted = with_state(window, "aborted")
    old = tree(Path(aborted["directory"]))
    fresh = state.new_window(root, PREPARED)
    assert fresh["id"] != aborted["id"] and state.current_window(root) == fresh
    assert tree(Path(aborted["directory"])) == old

    # An unfinished window the pointer does not name is an interrupted allocation.
    (root / "active.json").unlink()
    with pytest.raises(Stop, match=f"{fresh['id']}.*not active"):
        state.current_window(root)


@pytest.mark.parametrize("name, kind", [
    ("timers.json", "file"), ("live", "dir"), ("x.preparation", "file"),
    ("familiar-state", "file"), ("operator-env.sh", "dir"), (".active.json.k2j1", "file"),
    ("windows/scratch", "dir"), ("images", "symlink"),
])
def test_record_blocks_unexplained_root_entries(root, events, name, kind):
    retained(root)
    path = root / name
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
    path.parent.mkdir(mode=0o700, exist_ok=True)
    if kind == "dir":
        path.mkdir(mode=0o700)
    elif kind == "file":
        path.write_text("{}\n")
    else:
        path.symlink_to(root / "prep")
    before = tree(root)
    with pytest.raises(Stop, match=re.escape(name.split("/")[-1])):
        state.current_window(root)
    mark = len(events)
    with pytest.raises(Stop, match="reconcil"):
        state.new_window(root, PREPARED)
    assert events.writes_since(mark) == [] and tree(root) == before


def test_record_new_parent_directories_are_synced(tmp_path, root, events):
    window = state.new_window(root, PREPARED)
    identity = window["id"]
    order = [events.first(pattern) for pattern in (
        "mkdir:state", f"fsync:{tmp_path.name}", "mkdir:hq", "fsync:state",
        "mkdir:relay-cutover", "fsync:hq", "mkdir:windows", "fsync:relay-cutover",
        f"mkdir:{identity}", "fsync:windows", "fsync:.window.json.*",
        "replace:window.json", f"fsync:{identity}", "fsync:.active.json.*",
        "replace:active.json")]
    assert order == sorted(order)
    assert "fsync:relay-cutover" in events[events.index("replace:active.json"):]

    state.save_record(Path(window["directory"]) / "hosts" / "europa" / "timers.json",
                      {"schema": 1, "timers": []})
    start = events.index("mkdir:hosts")
    order = [events.first(pattern, start) for pattern in (
        "mkdir:hosts", f"fsync:{identity}", "mkdir:europa", "fsync:hosts",
        "fsync:.timers.json.*", "replace:timers.json", "fsync:europa")]
    assert order == sorted(order)


def test_record_allocation_and_consumption_are_exclusive(root):
    root.mkdir(parents=True, mode=0o700)
    held = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(Stop, match="another invocation"):
            state.new_window(root, PREPARED)
    finally:
        os.close(held)
    assert sorted(os.listdir(root)) == []

    window = state.new_window(root, PREPARED)
    consume(window, recorded(window))
    decisions = Path(window["directory"]) / "decisions"
    held = os.open(decisions, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(Stop, match="another invocation"):
            consume(window, recorded(window, attempt="restart-2", reply="yes, again"),
                    attempt="restart-2")
    finally:
        os.close(held)
    assert sorted(os.listdir(decisions)) == ["restart-1.json"]


def test_target_registration_durability(tmp_path, root, events):
    window = applying(root)
    directory = Path(window["directory"])
    target = settings(tmp_path)
    before = target.read_bytes()
    artifact = directory / "claude.json"

    state.register_target(window, "claude", target, artifact)
    write_target(events, target, b'{\n  "hooks": {"SessionStart": []}\n}\n')

    linked = events.index("link:claude.original")
    assert events.first("fsync:.claude.original.*") < linked
    assert linked < events.index(f"fsync:{window['id']}", linked) < events.index("write:touched.tsv")
    assert events.index("fsync:touched.tsv") < events.index("write:target")
    assert events.first(f"fsync:{window['id']}", events.index("fsync:touched.tsv")) \
        < events.index("write:target")
    original = directory / "claude.original"
    assert original.read_bytes() == before and mode(original) == 0o600
    assert mode(directory / "touched.tsv") == 0o600

    work = settings(tmp_path, "claude-work/settings.json")
    codex = settings(tmp_path, "codex/hooks.json")
    state.register_target(window, "codex", codex, directory / "live" / "codex.json")
    state.register_target(window, "claude-work", work, directory / "claude-work.json")
    assert mode(directory / "live") == 0o700
    assert (directory / "touched.tsv").read_text() == (
        f"claude\t{target}\t{artifact}\n"
        f"codex\t{codex}\t{directory / 'live' / 'codex.json'}\n"
        f"claude-work\t{work}\t{directory / 'claude-work.json'}\n")
    assert state.read_ledger(window) == [
        {"target_id": "claude", "target": str(target), "artifact": str(artifact),
         "original": str(original)},
        {"target_id": "codex", "target": str(codex),
         "artifact": str(directory / "live" / "codex.json"),
         "original": str(directory / "codex.original")},
        {"target_id": "claude-work", "target": str(work),
         "artifact": str(directory / "claude-work.json"),
         "original": str(directory / "claude-work.original")},
    ]

    # Originals are immutable: a second registration of a target refuses untouched.
    ledger = (directory / "touched.tsv").read_bytes()
    mark = len(events)
    with pytest.raises(Stop, match="claude is already registered"):
        state.register_target(window, "claude", target, directory / "claude-again.json")
    assert events.writes_since(mark) == []
    assert (directory / "touched.tsv").read_bytes() == ledger and original.read_bytes() == before


@pytest.mark.parametrize("case, fragment", [
    ("not-applying", "is prepared"), ("unknown-id", "unknown target id"),
    ("symlink-target", "resolved"), ("symlinked-parent", "resolved"),
    ("relative-target", "resolved"), ("missing-target", "missing"),
    ("artifact-outside", "inside the window"), ("artifact-escape", "inside the window"),
    ("artifact-dotdot", "inside the window"), ("artifact-exists", "already exists"),
    ("artifact-ledger", "reserved"), ("artifact-decisions", "reserved"),
    ("artifact-shared", "already registered"), ("stale-window", "changed on disk"),
])
def test_registration_refuses_unsafe_paths(tmp_path, root, events, case, fragment):
    window = applying(root)
    directory = Path(window["directory"])
    target = settings(tmp_path)
    target_id, artifact = "claude-work", directory / "claude-work.json"
    if case == "not-applying":
        window = with_state(window, "prepared")
    elif case == "unknown-id":
        target_id = "claude-personal"
    elif case == "symlink-target":
        link = tmp_path / "home" / "link.json"
        link.symlink_to(target)
        target = link
    elif case == "symlinked-parent":
        (tmp_path / "alias").symlink_to(tmp_path / "home")
        target = tmp_path / "alias" / "claude" / "settings.json"
    elif case == "relative-target":
        target = Path("home/claude/settings.json")
    elif case == "missing-target":
        target = tmp_path / "home" / "absent.json"
    elif case == "artifact-outside":
        artifact = tmp_path / "elsewhere" / "claude-work.json"
    elif case == "artifact-escape":
        (tmp_path / "outside").mkdir()
        (directory / "escape").symlink_to(tmp_path / "outside")
        artifact = directory / "escape" / "claude-work.json"
    elif case == "artifact-dotdot":
        artifact = directory / ".." / "claude-work.json"
    elif case == "artifact-exists":
        artifact.write_text("{}\n")
    elif case == "artifact-ledger":
        artifact = directory / "touched.tsv"
    elif case == "artifact-decisions":
        artifact = directory / "decisions" / "claude-work.json"
    elif case == "artifact-shared":
        state.register_target(window, "claude", settings(tmp_path, "c/settings.json"), artifact)
    elif case == "stale-window":
        window = {**window, "created_at": "2026-10-20T00:00:00+00:00"}
    before = tree(directory)
    mark = len(events)
    with pytest.raises(Stop, match=fragment):
        state.register_target(window, target_id, target, artifact)
    assert events.writes_since(mark) == [] and tree(directory) == before


def test_registration_detects_torn_ledger(tmp_path, root, events):
    window = applying(root)
    directory = Path(window["directory"])
    ledger = directory / "touched.tsv"
    state.register_target(window, "claude", settings(tmp_path), directory / "claude.json")
    codex = settings(tmp_path, "codex/hooks.json")

    for torn, fragment in (
        (f"codex\t{codex}\t{directory}/co", "torn final entry"),
        (f"codex\t{codex}\n", "line 2"),
        (f"codex-personal\t{codex}\t{directory / 'codex.json'}\n", "line 2"),
        (f"codex\trelative/hooks.json\t{directory / 'codex.json'}\n", "line 2"),
        (f"claude\t{codex}\t{directory / 'codex.json'}\n", "line 2"),
        (f"codex\t{codex}\t{directory / 'codex.json'}\n", "codex has no original"),
    ):
        kept = ledger.read_bytes()
        with ledger.open("ab") as stream:
            stream.write(torn.encode())
        damaged = tree(directory)
        with pytest.raises(Stop, match=fragment):
            state.read_ledger(window)
        mark = len(events)
        with pytest.raises(Stop, match=fragment):
            state.register_target(window, "codex", codex, directory / "codex.json")
        # Reconciliation sees the damage; registration never appends after it.
        assert events.writes_since(mark) == [] and tree(directory) == damaged
        ledger.write_bytes(kept)
    assert [entry["target_id"] for entry in state.read_ledger(window)] == ["claude"]


def test_decision_is_bound_and_single_use(root, events):
    window = state.new_window(root, PREPARED)
    directory = Path(window["directory"])
    approved = recorded(window)

    consumed = authorized_restart(events, window, approved)
    assert events.index("link:restart-1.json") < events.index("fsync:decisions") \
        < events.index("host:restart")
    assert consumed == state.load_record(directory / "decisions" / "restart-1.json")
    assert mode(directory / "decisions") == 0o700
    assert mode(directory / "decisions" / "restart-1.json") == 0o600
    assert consumed["decision"] == approved
    assert {key: consumed[key] for key in (
        "window_id", "attempt_id", "kind", "action", "subject_sha256", "prepared_sha256")} == {
        "window_id": window["id"], "attempt_id": "restart-1", "kind": "desktop",
        "action": "restart-surfaces", "subject_sha256": sha(SUBJECT),
        "prepared_sha256": PREPARED}
    assert consumed["decision_sha256"] == sha(approved)
    assert state.load_record(window_file(window)) == window

    mark = len(events)
    with pytest.raises(Stop, match="attempt restart-1 already consumed"):
        authorized_restart(events, window, approved)
    writes_after_replayed_decision = events.writes_since(mark)
    assert writes_after_replayed_decision == []

    # An operator's own terminal answer binds the same way, once.
    tty = recorded(window, attempt="restart-2", source="tty", reply="y")
    assert authorized_restart(events, window, tty, attempt="restart-2")["decision"] == tty
    mark = len(events)
    with pytest.raises(Stop, match="already consumed"):
        authorized_restart(events, window, tty, attempt="restart-2")
    assert events.writes_since(mark) == []
    assert sorted(os.listdir(directory / "decisions")) == ["restart-1.json", "restart-2.json"]


def source(decision, **changes):
    return {**decision, "source": {**decision["source"], **changes}}


def without(decision, key):
    return {**decision, "source": {k: v for k, v in decision["source"].items() if k != key}}


REFUSALS = {
    "absent": (lambda d, w: None, "decision absent"),
    "declined": (lambda d, w: {**d, "verdict": "declined"}, "declined"),
    "verdict-yes": (lambda d, w: {**d, "verdict": "yes"}, "approved or declined"),
    "empty-ask": (lambda d, w: source(d, ask=""), "ask is empty"),
    "blank-reply": (lambda d, w: source(d, reply="  \n"), "reply is empty"),
    "empty-session": (lambda d, w: source(d, session_id=""), "session_id is empty"),
    "no-session": (lambda d, w: without(d, "session_id"), "source"),
    "tty-no-response": (lambda d, w: {**d, "source": {
        "type": "tty", "prompt": "Restart? [y/N]", "response": "",
        "answered_at": d["source"]["answered_at"]}}, "response is empty"),
    "agent-source": (lambda d, w: source(d, type="agent"), "source"),
    "wrong-window": (lambda d, w: {**d, "window_id": "20261019T120000Z-0badf00d"}, "window_id"),
    "pilot-id": (lambda d, w: {**d, "window_id": "pilot-1"}, "window_id"),
    "wrong-subject": (lambda d, w: {**d, "subject_sha256": sha({"hosts": ["europa"]})},
                      "subject_sha256"),
    "wrong-kind": (lambda d, w: {**d, "kind": "smoke-attestation"}, "kind"),
    "wrong-action": (lambda d, w: {**d, "action": "finish"}, "action"),
    "other-attempt": (lambda d, w: {**d, "attempt_id": "restart-9"}, "attempt_id"),
    "stale": (lambda d, w: source(d, answered_at=(
        datetime.fromisoformat(w["created_at"]) - timedelta(days=1)).isoformat()),
        "before this window"),
    "naive-time": (lambda d, w: source(d, answered_at="2026-10-20T12:00:00"), "timezone"),
    "bad-time": (lambda d, w: source(d, answered_at="soon"), "answered_at"),
    "self-granted": (lambda d, w: {**d, "approved": True}, "schema 1"),
    "schema-2": (lambda d, w: {**d, "schema": 2}, "schema 1"),
    "not-object": (lambda d, w: ["approved"], "schema 1"),
}


@pytest.mark.parametrize("case", REFUSALS)
def test_decision_refusals_happen_before_host_use(root, events, case):
    window = state.new_window(root, PREPARED)
    change, fragment = REFUSALS[case]
    decision = change(recorded(window), window)
    before = tree(root)
    mark = len(events)
    with pytest.raises(Stop, match=fragment):
        authorized_restart(events, window, decision)
    assert events.writes_since(mark) == [] and tree(root) == before


@pytest.mark.parametrize("name", ["complete", "aborted", "recovered"])
def test_decision_refuses_finished_window(root, events, name):
    window = with_state(state.new_window(root, PREPARED), name)
    mark = len(events)
    with pytest.raises(Stop, match=f"is {name}"):
        authorized_restart(events, window, recorded(window))
    assert events.writes_since(mark) == []


def test_decision_refuses_stale_window_copy(root, events):
    window = state.new_window(root, PREPARED)
    with_state(window, "quiescing")
    mark = len(events)
    with pytest.raises(Stop, match="changed on disk"):
        authorized_restart(events, window, recorded(window))
    assert events.writes_since(mark) == []


@pytest.mark.parametrize("fault, retry", [
    ("fsync:.claude.original.*", None), ("link:claude.original", None),
    ("fsync:<window>", "already exists without a ledger entry"),
    ("open:touched.tsv", "already exists without a ledger entry"),
    ("write:touched.tsv", "already exists without a ledger entry"),
    ("fsync:touched.tsv", "claude is already registered"),
    ("fsync:<window>@ledger", "claude is already registered"),
])
def test_registration_fault_blocks_target_write(tmp_path, root, events, fault, retry):
    window = applying(root)
    directory = Path(window["directory"])
    target = settings(tmp_path)
    before = target.read_bytes()

    def apply():
        state.register_target(window, "claude", target, directory / "claude.json")
        write_target(events, target, b'{"hooks": {"SessionStart": []}}\n')

    pattern, _, after = fault.replace("<window>", window["id"]).partition("@")
    # "@ledger" selects the window directory's sync after the new ledger entry.
    events.fail(pattern, after={"": None, "ledger": "fsync:touched.tsv"}[after])
    with pytest.raises(OSError, match="injected fault"):
        apply()
    events.faults.clear()
    assert "write:target" not in events and target.read_bytes() == before
    assert not [name for name in os.listdir(directory) if name.startswith(".claude.original.")]

    # An interrupted registration is never adopted or skipped: a retry either starts
    # clean (nothing durable happened) or stops for reconciliation.
    if retry is None:
        apply()
        assert events.index("fsync:touched.tsv") < events.index("write:target")
    else:
        with pytest.raises(Stop, match=retry):
            apply()
        assert "write:target" not in events and target.read_bytes() == before


def test_record_fault_at_rename_keeps_previous_record(root, events):
    window = state.new_window(root, PREPARED)
    path = window_file(window)
    before = path.read_bytes()
    events.fail("replace:window.json")
    with pytest.raises(OSError, match="injected fault"):
        state.save_record(path, {**window, "state": "quiescing"})
    events.faults.clear()
    assert path.read_bytes() == before and os.listdir(path.parent) == ["window.json"]
    assert state.current_window(root) == window

    # An allocation interrupted before its pointer moves is a blocker, never adopted.
    with_state(window, "aborted")
    events.fail("replace:active.json")
    with pytest.raises(OSError, match="injected fault"):
        state.new_window(root, PREPARED)
    events.faults.clear()
    assert state.load_record(root / "active.json")["window"] == window["id"]
    with pytest.raises(Stop, match="is prepared but not active"):
        state.current_window(root)
    with pytest.raises(Stop, match="not active"):
        state.new_window(root, PREPARED)


@pytest.mark.parametrize("loss", ["reply", "fsync:decisions"])
def test_lost_reply_cannot_reuse_consumed_decision(root, events, loss):
    window = state.new_window(root, PREPARED)
    approved = recorded(window)
    if loss == "reply":
        # The approved action ran, then its reply to the agent was lost.
        with pytest.raises(BrokenPipeError):
            authorized_restart(events, window, approved)
            raise BrokenPipeError("reply lost after the authorized restart")
        assert "host:restart" in events
    else:
        # Persistence of the consumed decision has an unknown outcome: it stays spent.
        events.fail("fsync:decisions")
        with pytest.raises(OSError, match="injected fault"):
            authorized_restart(events, window, approved)
        events.faults.clear()
        assert "host:restart" not in events

    # A new invocation loads the durable record and cannot reuse that approval.
    reloaded = state.current_window(root)
    mark = len(events)
    with pytest.raises(Stop, match="already consumed by attempt restart-1"):
        authorized_restart(events, reloaded, {**approved, "attempt_id": "restart-2"},
                           attempt="restart-2")
    with pytest.raises(Stop, match="attempt restart-1 already consumed"):
        authorized_restart(events, reloaded, approved)
    assert events.writes_since(mark) == []

    # Only a new ask and its own reply authorize the new attempt.
    fresh = recorded(reloaded, attempt="restart-2", reply="yes, try once more")
    authorized_restart(events, reloaded, fresh, attempt="restart-2")
    assert events[-1] == "host:restart"


def test_decision_scope_survives_expected_pid_exit(root, events):
    window = state.new_window(root, PREPARED)
    # The subject is the recorded inventory the operator approved, not a live rescan:
    # the recorded panel exiting before its restart leaves that subject, and so the
    # approved command scope, unchanged.
    consumed = authorized_restart(events, window, recorded(window))
    assert consumed["subject_sha256"] == sha(SUBJECT)
    assert state.load_record(Path(window["directory"]) / "decisions" / "restart-1.json") \
        ["subject_sha256"] == sha(SUBJECT)

    # An unrecorded new process changes the inventory: no consumed or old-subject
    # approval admits it, and only a new ask about the new subject can.
    widened = {**SUBJECT, "surfaces": SUBJECT["surfaces"] + [
        {"host": "titan", "pid": 5151, "start_time": 9100,
         "command": ["/home/operator/d/familiar/bin/familiar", "panel"]}]}
    old_subject = recorded(window, attempt="restart-2", reply="yes, restart the panel")
    mark = len(events)
    with pytest.raises(Stop, match="subject_sha256 does not match"):
        authorized_restart(events, window, old_subject, attempt="restart-2", subject=widened)
    assert events.writes_since(mark) == []
    asked = recorded(window, attempt="restart-2", subject=widened, reply="yes, both panels")
    assert authorized_restart(events, window, asked, attempt="restart-2",
                              subject=widened)["subject_sha256"] == sha(widened)


# --- preparation, quiescence and the pre-merge abort -------------------------------------

SESSION = "0199f5a1-7c2e-7d3b-9a41-5b6c7d8e9f01"
HOSTS = ("titan", "europa")
TOOLS = Path(__file__).resolve().parent
BOOTSTRAP = TOOLS / "relay-cutover-bootstrap"
needs_zsh = pytest.mark.skipif(not transport.ZSH.is_file(), reason="the remote login shell is Zsh")
SECRETS = (transport.ENV_SECRET, transport.OUTPUT_SECRET, "opus[1m]", "alwaysThinkingEnabled",
           "Bash(git status:*)")


@pytest.fixture
def cutover(tmp_path, monkeypatch):
    """Both fixture hosts with staged reviewed inputs; the controller runs from Titan's main."""
    world = transport.World(tmp_path, monkeypatch)
    world.stage_cutover()
    monkeypatch.setattr(window, "CHECKOUT", world.home("titan") / "d/hq")
    yield world
    world.close()


def cutover_root(world, host="titan"):
    return world.root(host)


def staged(world, host):
    """The reviewed inputs and retained records preparation must never rewrite."""
    root = world.root(host)
    paths = [root / name for name in ("claude-work.after.json", "expected-images.sha256",
                                      "live-before.sha256")]
    for name in ("inputs", "prep", "images"):
        paths += sorted((root / name).rglob("*"))
    return {str(path.relative_to(root)): path.read_bytes() for path in paths if path.is_file()}


def changes(before, after):
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def codes(blockers):
    """Blocker codes from the controller's host-prefixed blockers."""
    return {blocker.split(": ")[1] for blocker in blockers}


def raw_codes(blockers):
    """Blocker codes from one host operation's own blockers."""
    return {blocker.split(": ")[0] for blocker in blockers}


def observed(world, tool=None, since=0):
    return [call for call in world.lines("observed")[since:]
            if tool is None or call["tool"] == tool]


def timer_calls(world, since=0):
    return [(call["host"], call["args"][0]) for call in observed(world, "quiesce-timers", since)]


def decision_for(opened, attempt="run-1"):
    """A fixture of the operator's terminal answer for this run's desktop restart."""
    subject = {"hosts": list(HOSTS), "surfaces": ["familiar-niri-watch", "niri-desktop"]}
    answered = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {"schema": 1, "kind": "desktop", "action": window.RUN_ACTION,
              "window_id": opened["id"], "attempt_id": attempt, "subject_sha256": sha(subject),
              "verdict": "approved", "source": {
                  "type": "tty", "response": "y", "answered_at": answered,
                  "prompt": "Restart the familiar surfaces on titan and europa? [y/N]"}}
    return state.consume_decision(opened, record, kind="desktop", action=window.RUN_ACTION,
                                  attempt_id=attempt, subject_sha256=sha(subject))


def opened_with_decision(world):
    prepared = preparation.prepare(SESSION)
    opened = window.open_window(prepared)
    return prepared, opened, decision_for(opened)


def inputs_check(world, monkeypatch, number):
    """Titan's inputs-check inside this process, with the fixture's git for provenance."""
    monkeypatch.setitem(hosts.TOOLS, "git", world.config["tools"]["git"])
    response = transport._execute("titan", "inputs-check", {"commits": True}, number)
    assert response["status"] == "completed", response["error"]
    return response["result"]


def timers_active(world):
    return {host: world.units(host)["familiar-reap.timer"]["active"] for host in HOSTS}


def test_prepare_layout_entries_are_explained(root):
    retained(root)
    (root / "prepared.json").write_text("{}\n")
    for name in ("inputs", "quiesce"):
        (root / name).mkdir(mode=0o700)
    assert {"prepared.json", "inputs/", "quiesce/"} <= set(state.LAYOUT)
    assert state.current_window(root) is None


@needs_zsh
@pytest.mark.parametrize("checkout", ["native", "candidate"])
def test_prepare_preserves_filter_owned_picks(cutover, monkeypatch, checkout):
    if checkout == "candidate":
        # The controller runs from a worktree whose own settings are candidate images: the
        # targets and pick keys still come from each host's manifest-verified files.
        monkeypatch.setattr(window, "CHECKOUT", cutover.candidate_checkout())
    reviewed = {host: staged(cutover, host) for host in HOSTS}
    before = {host: cutover.snapshot(host) for host in HOSTS}
    prepared = preparation.prepare(SESSION)

    root = cutover_root(cutover)
    assert state.load_record(root / "prepared.json") == prepared
    keys = list(transport.CLAUDE_KEYS)
    assert prepared["filter"]["keys"] == keys
    assert prepared["controller"]["session_id"] == SESSION
    assert prepared["controller"]["checkout"] == str(window.CHECKOUT)
    assert prepared["manifest"]["generation"] == "g1"
    for host in HOSTS:
        assert set(prepared["hosts"][host]["targets"]) == (
            {"claude", "claude-work", "codex", "codex-work"} if host == "titan"
            else {"claude", "claude-work"})
        for target_id in ("claude", "claude-work"):
            data = cutover.target(host, target_id).read_bytes()
            current_before = json.loads(data)
            reviewed_before = json.loads(cutover.member(host, target_id, "before").read_bytes())
            recorded = prepared["hosts"][host]["targets"][target_id]
            assert inputs.nonpick(current_before, keys) == inputs.nonpick(reviewed_before, keys)
            recorded_picks_and_absence = (recorded["picks"], recorded["absent"])
            current_picks_and_absence = ({key: current_before[key] for key in keys
                                          if key in current_before},
                                         [key for key in keys if key not in current_before])
            assert recorded_picks_and_absence == current_picks_and_absence
            assert recorded["sha256"] == hashlib.sha256(data).hexdigest()
            assert recorded["path"] == os.path.realpath(cutover.target(host, target_id))
    personal = prepared["hosts"]["titan"]["targets"]["claude"]
    # The live picks make the raw hashes differ from the reviewed source; that is not drift.
    assert personal["sha256"] != personal["reviewed"]["before"]
    assert personal["picks"] == {"model": "opus[1m]", "effortLevel": "high",
                                 "modelSettings": {"opus[1m]": {"thinking": {"budget": 32000}}}}
    work = prepared["hosts"]["europa"]["targets"]["claude-work"]
    assert (work["picks"], work["absent"]) == ({"model": "sonnet"},
                                               ["modelSettings", "effortLevel"])
    assert prepared["hosts"]["titan"]["sessions"] == prepared["hosts"]["europa"]["sessions"] == []

    # Reviewed originals stay as staged, no after-image is serialized, and preparation wrote
    # only its own record beside the operation records.
    assert {host: staged(cutover, host) for host in HOSTS} == reviewed
    assert {host: changes(before[host], cutover.snapshot(host)) for host in HOSTS} == {
        "titan": [".local/state/hq/relay-cutover/prepared.json"], "europa": []}
    assert transport.RELAY_HOOK.encode() not in (root / "prepared.json").read_bytes()
    assert stat.S_IMODE((root / "prepared.json").stat().st_mode) == 0o600
    assert state.current_window(root) is None  # preparation opens no window


NESTED = {"tier": ["a", {"\u00fc": None, "n": 1.5}], "on": False}


@needs_zsh
@pytest.mark.parametrize("change", ["nested", "deleted", "added"])
@pytest.mark.parametrize("key", transport.CLAUDE_KEYS)
def test_pick_drift_accepts_every_filter_key(cutover, monkeypatch, key, change):
    target_id = "claude-work" if change == "added" else "claude"
    current = json.loads(cutover.target("titan", target_id).read_bytes())
    if change == "deleted":
        del current[key]
    else:
        current[key] = NESTED
    cutover.write_target(target_id, current)
    result = inputs_check(cutover, monkeypatch, 1)
    assert result["blockers"] == []
    recorded = result["targets"][target_id]
    keys = transport.CLAUDE_KEYS
    assert recorded["picks"] == {name: current[name] for name in keys if name in current}
    assert recorded["absent"] == [name for name in keys if name not in current]


@needs_zsh
def test_pick_keys_come_from_the_manifest_filter(cutover, monkeypatch):
    current = json.loads(cutover.target("titan", "claude").read_bytes())
    current["outputStyle"] = "terse"
    cutover.write_target("claude", current)

    def check(number):
        return inputs_check(cutover, monkeypatch, number)

    # The filter's own list does not own outputStyle: a non-pick edit.
    assert raw_codes(check(1)["blockers"]) == {"input-review-required"}
    # A changed filter is never used until a reviewed manifest names its bytes.
    cutover.write_filter(transport.CLAUDE_KEYS + ("outputStyle",))
    result = check(2)
    assert raw_codes(result["blockers"]) == {"input-manifest"}
    assert "harness-state-clean" in result["blockers"][0]
    cutover.write_manifest()
    result = check(3)
    assert result["blockers"] == []
    assert result["filter"]["keys"] == [*transport.CLAUDE_KEYS, "outputStyle"]
    assert result["targets"]["claude"]["picks"]["outputStyle"] == "terse"
    # A filter that stops owning effortLevel turns the live effort pick into drift.
    del current["outputStyle"]
    cutover.write_target("claude", current)
    cutover.write_filter(("model", "modelSettings"))
    cutover.write_manifest()
    result = check(4)
    assert raw_codes(result["blockers"]) == {"input-review-required"}
    assert "(effortLevel)" in result["blockers"][0]


def _append_hook(value):
    value["hooks"]["PreToolUse"].append({"matcher": "Edit", "hooks": [
        {"type": "command", "command": "~/private/unreviewed-hook"}]})


NONPICK = {
    "hooks": ("claude", _append_hook, "hooks"),
    "statusLine": ("claude", lambda value: value["statusLine"].update(refreshInterval=5),
                   "statusLine"),
    "new-key": ("claude-work", lambda value: value.update(cleanupPeriodDays=7),
                "cleanupPeriodDays"),
    "codex-hooks": ("codex", lambda value: value["hooks"].pop("Stop"), "hooks"),
}


@needs_zsh
@pytest.mark.parametrize("case", sorted(NONPICK))
def test_nonpick_drift_names_original_image_review(cutover, case):
    target_id, edit, key = NONPICK[case]
    value = json.loads(cutover.target("titan", target_id).read_bytes())
    edit(value)
    cutover.write_target(target_id, value)
    kept = {host: staged(cutover, host) for host in HOSTS}
    with pytest.raises(window.Failed) as raised:
        preparation.prepare(SESSION)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("inputs-check", "titan", "blocked")
    review = [blocker for blocker in failed.blockers if "input-review-required" in blocker]
    assert len(review) == 1 and f"{target_id}:" in review[0] and f"({key})" in review[0]
    assert "Task 6" in review[0] and "docs/plans/2026-10-19-relay-cutover.md" in review[0]
    assert failed.next_command[0] == "prepare"
    # Nothing is adopted: no prepared record, no new generation, the reviewed inputs as staged.
    root = cutover_root(cutover)
    assert not (root / "prepared.json").exists()
    assert sorted(os.listdir(root / "inputs")) == ["designated.json", "g1"]
    assert {host: staged(cutover, host) for host in HOSTS} == kept
    assert "unreviewed-hook" not in str(failed) + "".join(failed.blockers)


def _unlink(name):
    return lambda world: world.root("titan").joinpath(name).unlink()


def _restaged(change):
    return lambda world: world.write_manifest(change=change)


def _member_path(target_id, role, path):
    def change(manifest):
        manifest["targets"][target_id][role]["path"] = path
    return _restaged(change)


def _garbage(target_id, role, data):
    def arrange(world):
        world.member("titan", target_id, role).write_bytes(data)
        world.member("europa", target_id, role).write_bytes(data)
        world.write_manifest()
    return arrange


def _symlinked(world):
    path = world.member("titan", "claude", "artifact")
    shutil.copy2(path, path.with_name("claude.copy.json"))
    path.unlink()
    path.symlink_to("claude.copy.json")


MANIFEST = {
    "undesignated": (_unlink("inputs/designated.json"), "input-manifest"),
    "unknown-generation": (lambda world: transport._stage(
        world.root("titan"), "inputs/designated.json",
        b'{"schema": 1, "generation": "g9"}\n'), "input-manifest"),
    "corrupt-manifest": (lambda world: world.root("titan").joinpath(
        "inputs/g1/manifest.json").write_bytes(b'{"schema": 1,'), "input-manifest"),
    "loose-manifest": (lambda world: world.root("titan").joinpath(
        "inputs/g1/manifest.json").chmod(0o644), "input-manifest"),
    "missing-pin": (_restaged(lambda manifest: manifest["pins"].pop("relay_commit")),
                    "input-manifest"),
    "wrong-pin": (_restaged(lambda manifest: manifest["pins"].update(familiar_pre="1" * 40)),
                  "input-manifest"),
    "missing-target": (_restaged(lambda manifest: manifest["targets"].pop("codex-work")),
                       "input-manifest"),
    "missing-member": (_unlink("prep/codex.json"), "input-member"),
    "corrupt-image": (lambda world: world.member("titan", "claude", "after").write_bytes(
        world.member("titan", "claude", "after").read_bytes() + b" "), "input-member"),
    "unparsable-image": (_garbage("claude-work", "after", b"not json\n"), "input-member"),
    "not-an-artifact": (_garbage("codex", "artifact", b'{"schema": 1}\n'), "input-member"),
    "absolute-path": (_member_path("claude", "artifact", "/etc/hostname"), "input-member"),
    "escaping-path": (_member_path("claude", "artifact", "prep/../../../../etc/hostname"),
                      "input-member"),
    "tool-owned-path": (_member_path("claude", "artifact", "operations/x.json"),
                        "input-member"),
    "symlinked-member": (_symlinked, "input-member"),
}


@needs_zsh
@pytest.mark.parametrize("case", sorted(MANIFEST))
def test_manifest_refusals(cutover, case):
    arrange, code = MANIFEST[case]
    arrange(cutover)
    kept = staged(cutover, "titan")
    with pytest.raises(window.Failed) as raised:
        preparation.prepare(SESSION)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("inputs-check", "titan", "blocked")
    assert code in codes(failed.blockers), failed.blockers
    assert not (cutover_root(cutover) / "prepared.json").exists()
    assert staged(cutover, "titan") == kept
    assert observed(cutover, "quiesce-timers") == []


def _provenance(target_id, role, proof):
    def change(manifest):
        if proof is None:
            del manifest["targets"][target_id][role]["provenance"]
        else:
            manifest["targets"][target_id][role]["provenance"] = proof
    return _restaged(change)


def _unrecorded(world):
    digest = hashlib.sha256(world.member("titan", "claude-work", "before").read_bytes()).hexdigest()
    path = world.root("titan") / "live-before.sha256"
    path.write_text("".join(line + "\n" for line in path.read_text().splitlines()
                            if not line.startswith(digest)))


def _other_bytes(world):
    world.config["blobs"][f"{transport.FIXTURE_COMMIT}:claude/settings.json"] = str(
        world.member("titan", "codex", "before"))
    world.save()


COMMIT = {"type": "commit", "path": "claude/settings.json"}
PROVENANCE = {
    "mutable-ref": _provenance("claude", "before", {**COMMIT, "commit": "main"}),
    "short-commit": _provenance("claude", "before", {**COMMIT, "commit": "5e1f0c2"}),
    "unknown-commit": _provenance("claude", "before", {**COMMIT, "commit": "7" * 40}),
    "other-bytes": _other_bytes,
    "not-recorded": _unrecorded,
    "unexplained-record": _provenance("claude-work", "before", {
        "type": "digest-record", "record": "operator-env.sh"}),
    "unproven-after": _provenance("codex", "after", None),
    "task-note": _provenance("codex", "after", {"type": "task-note", "note": "review: accept"}),
}


@needs_zsh
@pytest.mark.parametrize("case", sorted(PROVENANCE))
def test_manifest_provenance_refusals(cutover, case):
    PROVENANCE[case](cutover)
    with pytest.raises(window.Failed) as raised:
        preparation.prepare(SESSION)
    failed = raised.value
    assert (failed.step, failed.host) == ("inputs-check", "titan")
    review = [blocker for blocker in failed.blockers if "input-review-required" in blocker]
    assert review and all("Task 6" in blocker for blocker in review), failed.blockers
    assert not (cutover_root(cutover) / "prepared.json").exists()


@needs_zsh
def test_run_input_recheck_accepts_pick_only_drift(cutover):
    prepared = preparation.prepare(SESSION)
    recorded = (cutover_root(cutover) / "prepared.json").read_bytes()
    keys = transport.CLAUDE_KEYS
    personal = json.loads(cutover.target("titan", "claude").read_bytes())
    personal["model"] = {"id": "sonnet", "variants": ["1m"]}
    del personal["modelSettings"]
    work = json.loads(cutover.target("titan", "claude-work").read_bytes())
    work["effortLevel"] = "low"
    for target_id, value in (("claude", personal), ("claude-work", work)):
        cutover.write_target(target_id, value)

    result = preparation.recheck(prepared)
    assert result["eligible"] and result["blockers"] == []
    for host in HOSTS:
        for target_id, value in (("claude", personal), ("claude-work", work)):
            current = result["targets"][host][target_id]
            reviewed = json.loads(cutover.member(host, target_id, "before").read_bytes())
            assert inputs.nonpick(value, keys) == inputs.nonpick(reviewed, keys)
            assert (current["picks"], current["absent"]) == (
                {key: value[key] for key in keys if key in value},
                [key for key in keys if key not in value])
    # The run-time recheck reads; the preparation record stays as written.
    assert (cutover_root(cutover) / "prepared.json").read_bytes() == recorded

    personal["statusLine"] = {"type": "command", "command": "~/elsewhere"}
    cutover.write_target("claude", personal)
    with pytest.raises(window.Failed) as raised:
        preparation.recheck(prepared)
    assert raised.value.step == "eligibility"
    assert any("input-review-required" in blocker and "Task 6" in blocker
               for blocker in raised.value.blockers)


@needs_zsh
def test_system_toolchain_wins_over_nvm(cutover, monkeypatch):
    nvm = cutover.home("titan") / ".nvm/versions/node/v22.11.0/bin"
    for name in ("npm", "node"):
        transport._write(nvm / name, "#!/usr/bin/python3 -S\n"
                         f"import json\nopen({cutover.config['observed']!r}, 'a').write("
                         "json.dumps({'host': 'nvm', 'tool': 'nvm', 'args': []}) + '\\n')\n"
                         "print('11.6.2')\n", 0o755)
    monkeypatch.setenv("PATH", f"{nvm}:{os.environ['PATH']}")
    prepared = preparation.prepare(SESSION)
    for host in HOSTS:
        install = prepared["hosts"][host]["install"]
        npm = prepared["hosts"][host]["toolchain"]["npm"]
        install_env = {"PATH": install["path"]}
        assert install_env["PATH"].split(":")[0] == "/usr/bin"
        assert install_env["PATH"].split(":")[:2] == ["/usr/bin", "/bin"]
        assert str(nvm) in install_env["PATH"].split(":")[2:]  # kept, after the system
        npm_executable, npm_version = install["npm"], npm["version"]
        assert npm_executable == npm["path"] == cutover.config["tools"]["npm"]
        assert npm_version == "12.2.1" and npm["package_version"] == "12.2.1"
    assert observed(cutover, "nvm") == []
    calls = observed(cutover, "npm")
    assert calls and all(call["path_head"] == "/usr/bin" for call in calls)
    system_node = shutil.which("node", path="/usr/bin:/bin")
    if system_node:  # npm's env shebang resolves the system node, never nvm's
        assert all(call["env_node"] == system_node for call in calls)
    # Production values: the fixed system npm, and PATH rebuilt with /usr/bin first.
    assert (hosts.TOOLS["npm"], hosts.TOOLS["node"]) == ("/usr/bin/npm", "/usr/bin/node")
    assert hosts._child_env({})["PATH"].split(":")[0] == "/usr/bin"


def _touch_tool(name):
    def arrange(world):
        with open(os.path.realpath(world.config["tools"][name]), "a") as stream:
            stream.write("# a changed build\n")
    return arrange


TOOLCHAIN = {
    "npm-11": (lambda world: world.behave("titan", npm_version="11.6.2"), "titan", "toolchain"),
    "node-changed": (_touch_tool("node"), "titan", "toolchain"),
    "git-changed": (_touch_tool("git"), "titan", "toolchain"),
    "python-changed": (lambda world: world.write_manifest(change=lambda manifest: manifest[
        "hosts"]["europa"]["toolchain"]["python3"].update(sha256="0" * 64)), "europa",
                       "toolchain"),
    "cache-in-checkout": (lambda world: world.behave("europa", npm_cache=str(
        world.home("europa") / "d/hq/.cache/npm")), "europa", "caches"),
}


@needs_zsh
@pytest.mark.parametrize("case", sorted(TOOLCHAIN))
def test_toolchain_drift_refuses_prepare(cutover, case):
    arrange, host, kind = TOOLCHAIN[case]
    arrange(cutover)
    with pytest.raises(window.Failed) as raised:
        preparation.prepare(SESSION)
    failed = raised.value
    assert (failed.host, failed.status) == (host, "blocked")
    assert kind in codes(failed.blockers), failed.blockers
    assert not (cutover_root(cutover) / "prepared.json").exists()
    assert transport.OUTPUT_SECRET not in str(failed) + "".join(failed.blockers)


@needs_zsh
def test_toolchain_drift_after_prepare_blocks_check(cutover):
    prepared = preparation.prepare(SESSION)
    assert preparation.check(prepared)["eligible"]
    _touch_tool("git")(cutover)
    result = preparation.check(prepared)
    assert not result["eligible"]
    assert {blocker.split(": ")[0] for blocker in result["blockers"]
            if "toolchain" in blocker and "git" in blocker} == {"titan", "europa"}
    with pytest.raises(window.Failed, match="eligibility"):
        preparation.recheck(prepared)


def _sessions(world):
    claude = os.path.realpath(world.home("titan") / ".local/bin/claude")
    world.spec("titan")["rows"] += [
        {"pid": 3900301, "start_time": 31, "comm": "claude", "exe": claude, "argv": ["claude"],
         "held": False},
        {"pid": 3900302, "start_time": 32, "comm": "claude", "exe": claude,
         "argv": ["claude", "--resume", "private-session"], "held": True}]
    europa = os.path.realpath(world.home("europa") / ".local/bin/claude")
    world.spec("europa")["rows"] += [
        {"pid": 3900311, "start_time": 41, "comm": "claude", "exe": europa, "argv": ["claude"],
         "held": False}]
    world.save()


@needs_zsh
def test_prepare_allows_ordinary_claude_sessions(cutover):
    _sessions(cutover)
    prepared = preparation.prepare(SESSION)  # no refusal, and no hold is demanded of them
    assert [(entry["pid"], entry["held"]) for entry in prepared["hosts"]["titan"]["sessions"]] \
        == [(3900301, False), (3900302, True)]
    assert [entry["pid"] for entry in prepared["hosts"]["europa"]["sessions"]] == [3900311]
    result = preparation.check(prepared)
    assert result["eligible"] and result["blockers"] == []
    assert [entry["pid"] for entry in result["sessions"]["titan"]] == [3900301, 3900302]

    # The run's strict no-live check refuses them, with no caller exemption.
    with pytest.raises(window.Failed) as raised:
        window.require_no_live("live")
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("no-live", "titan", "blocked")
    assert any("3900301" in blocker for blocker in failed.blockers)
    assert "private-session" not in str(failed) + "".join(failed.blockers)

    # Quiescing the window refuses at the same check, before any timer is touched.
    mark = len(cutover.lines("observed"))
    opened = window.open_window(prepared)
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, decision_for(opened))
    assert (raised.value.step, raised.value.host) == ("no-live", "titan")
    assert timer_calls(cutover, mark) == []
    assert state.current_window(cutover_root(cutover))["state"] == "aborted"
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}


@needs_zsh
def test_prepare_check_is_read_only(cutover):
    prepared = preparation.prepare(SESSION)
    root = cutover_root(cutover)
    before = {host: cutover.snapshot(host) for host in HOSTS}
    units = {host: cutover.units(host) for host in HOSTS}
    mark = len(cutover.lines("observed"))
    result = preparation.check(prepared)
    assert result["eligible"] and result["blockers"] == []
    report = window.status()
    assert report["window"] is None and report["prepared"]["sha256"] == \
        window.prepared_sha256(prepared)
    # Only private operation records were written: no target, source, dependency, timer,
    # service, desktop or window change.
    assert {host: changes(before[host], cutover.snapshot(host)) for host in HOSTS} == {
        "titan": [], "europa": []}
    assert {host: cutover.units(host) for host in HOSTS} == units
    tools = {call["tool"] for call in observed(cutover, since=mark)}
    assert "quiesce-timers" not in tools and "relay-cutover" not in tools
    assert not any(call["args"][:1] == ["app-server"] for call in observed(cutover, "codex", mark))
    assert state.current_window(root) is None
    assert not (root / "quiesce").exists()


@needs_zsh
def test_quiesce_stops_daemons_and_refreshes_snapshots(cutover):
    codex = os.path.realpath(cutover.home("titan") / ".local/bin/codex")
    cutover.spec("titan")["rows"] += [
        {"pid": 3900401, "start_time": 51, "comm": "codex", "exe": codex,
         "argv": ["codex", "app-server", "--listen"], "daemon": "personal"},
        {"pid": 3900402, "start_time": 52, "comm": "codex", "exe": codex,
         "argv": ["codex", "app-server", "--listen"], "daemon": "work"}]
    cutover.save()
    prepared = preparation.prepare(SESSION)
    # Daemons are not sessions: preparation records them like any live harness process.
    assert [entry["pid"] for entry in prepared["hosts"]["titan"]["sessions"]] == [3900401, 3900402]
    targets = {host: {target_id: cutover.target(host, target_id).read_bytes()
                      for target_id in transport.TARGET_PATHS} for host in HOSTS}
    opened = window.open_window(prepared)
    mark = len(cutover.lines("observed"))
    quiescent = window.quiesce_window(prepared, decision_for(opened))

    assert quiescent["state"] == "quiescing" and quiescent["id"] == opened["id"]
    assert quiescent == state.current_window(cutover_root(cutover))
    assert set(quiescent["quiescent"]["hosts"]) == set(HOSTS)
    calls = [(call["host"], call["tool"], call["args"][0])
             for call in observed(cutover, since=mark)]
    assert calls == [
        ("titan", "codex", "app-server"), ("titan", "codex", "app-server"),
        ("titan", "preflight", "preflight"), ("titan", "preflight", "preflight"),
        ("europa", "preflight", "preflight"),
        ("titan", "quiesce-timers", "record"), ("titan", "quiesce-timers", "stop"),
        ("europa", "quiesce-timers", "record"), ("europa", "quiesce-timers", "stop"),
        ("titan", "quiesce-timers", "wait"), ("europa", "quiesce-timers", "wait"),
        ("titan", "preflight", "preflight"), ("titan", "preflight", "preflight"),
        ("europa", "preflight", "preflight"),
        ("titan", "relay-cutover", "familiar-source"), ("titan", "relay-cutover", "familiar-check"),
        ("europa", "relay-cutover", "familiar-source"),
        ("europa", "relay-cutover", "familiar-check")]
    # Only the supported daemon stop, once per home, held, with no broad kill.
    daemons = [call for call in observed(cutover, "codex", mark)]
    assert [(call["args"], call["codex_home"], call["hold"]) for call in daemons] == [
        (["app-server", "daemon", "stop"], None, "1"),
        (["app-server", "daemon", "stop"], str(cutover.home("titan") / ".codex-work"), "1")]
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    for host in HOSTS:
        root, home = cutover.root(host), cutover.home(host)
        host_record = root / "quiesce" / opened["id"] / "timers.json"
        kept = Path(opened["directory"]) / "hosts" / host / "timers.json"
        copy = state.load_record(kept)
        assert copy["sha256"] == hashlib.sha256(host_record.read_bytes()).hexdigest()
        assert copy["sha256"] == quiescent["timers"][host]["sha256"]
        assert transport._tree_of(root / "familiar-state") == transport._tree_of(
            home / ".local/state/familiar")
        assert "observe/after-preparation.json" not in transport._tree_of(
            root / "quiesce" / opened["id"] / "preparation" / "familiar-state")
    # Nothing familiar or settings-related has changed yet.
    assert {host: {target_id: cutover.target(host, target_id).read_bytes()
                   for target_id in transport.TARGET_PATHS} for host in HOSTS} == targets


@needs_zsh
def test_quiesce_daemon_survivors_block(cutover):
    codex = os.path.realpath(cutover.home("titan") / ".local/bin/codex")
    cutover.spec("titan")["rows"].append(
        {"pid": 3900501, "start_time": 61, "comm": "codex", "exe": codex,
         "argv": ["codex", "app-server"], "daemon": "personal"})
    cutover.behave("titan", daemon="survive")
    prepared, opened, consumed = opened_with_decision(cutover)
    mark = len(cutover.lines("observed"))
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("codex-daemon-stop", "titan", "blocked")
    assert any("3900501" in blocker for blocker in failed.blockers)
    assert "nothing was killed" in failed.error
    cutover.reload()
    assert [row["pid"] for row in cutover.spec("titan")["rows"]].count(3900501) == 1
    assert timer_calls(cutover, mark) == []
    assert state.current_window(cutover_root(cutover))["state"] == "aborted"


@needs_zsh
def test_second_host_failure_aborts_both(cutover):
    cutover.behave("europa", timers={"record": "fail"})
    prepared, opened, consumed = opened_with_decision(cutover)
    snapshots = {host: transport._tree_of(cutover.root(host) / "familiar-state") for host in HOSTS}
    mark = len(cutover.lines("observed"))
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("timer-record", "europa", "failed")
    assert failed.log.startswith("europa:") and failed.log.endswith("/log")
    assert "aborted" in failed.observed
    assert timer_calls(cutover, mark) == [
        ("titan", "record"), ("titan", "stop"), ("europa", "record"), ("titan", "restore")]
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "aborted"
    assert record["abort"]["hosts"]["titan"]["complete"] is True
    assert record["abort"]["hosts"]["europa"]["timers"] == {"recorded": False}
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    assert (cutover.root("titan") / "quiesce" / opened["id"] / "timers.restored.json").is_file()
    assert {host: transport._tree_of(cutover.root(host) / "familiar-state")
            for host in HOSTS} == snapshots
    assert transport.OUTPUT_SECRET not in str(failed)
    # A completed abort permits a fresh window; its directory stays.
    fresh = state.new_window(cutover_root(cutover), window.prepared_sha256(prepared))
    assert fresh["id"] != opened["id"] and Path(opened["directory"]).is_dir()


@needs_zsh
@pytest.mark.parametrize("fault", ["fail-after", "partial"])
def test_abort_completes_after_an_interrupted_timer_record(cutover, fault):
    # Europa's helper leaves a loose record (whole or torn) and fails before its reply.
    cutover.behave("europa", timers={"record": fault})
    prepared, opened, consumed = opened_with_decision(cutover)
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, consumed)
    assert (raised.value.step, raised.value.host) == ("timer-record", "europa")
    assert raised.value.next_command == ["run"] and "aborted" in raised.value.observed
    root = cutover_root(cutover)
    record = state.current_window(root)
    assert record["state"] == "aborted"
    europa = record["abort"]["hosts"]["europa"]
    assert europa["complete"] is True and europa["timers"]["stopped"] is False
    directory = cutover.root("europa") / "quiesce" / opened["id"]
    assert not (directory / "timers.json").exists()
    assert (directory / "abort" / "timers.json").is_file()
    assert state.load_record(directory / "timers.restored.json")["stopped"] is False
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    # Nothing is left to block the next window on either host.
    cutover.behave("europa", timers={})
    result = preparation.check(prepared)
    assert result["eligible"], result["blockers"]
    state.new_window(root, window.prepared_sha256(prepared))


@needs_zsh
@pytest.mark.parametrize("name", ["SIGTERM", "SIGINT", "SIGHUP"])
def test_quiesce_signal_aborts_every_recorded_host(cutover, name):
    cutover.behave("europa", timers={"wait": "signal"}, signal=name)
    prepared, opened, consumed = opened_with_decision(cutover)
    handlers = {signum: signal.getsignal(signum) for signum in hosts.INTERRUPTS}
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host) == ("timer-wait", "europa")
    assert failed.status == "interrupted" and name in failed.error
    assert {signum: signal.getsignal(signum) for signum in hosts.INTERRUPTS} == handlers
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "aborted" and record["failure"]["step"] == "timer-wait"
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    # The remote wait was cancelled explicitly, never by dropping its connection.
    operations = cutover.root("europa") / "operations"
    waits = [path.parent for path in operations.glob("*/start.json")
             if state.load_record(path)["operation"] == "timer-wait"]
    assert len(waits) == 1 and (waits[0] / "cancel.json").is_file()
    assert state.load_record(waits[0] / "done.json")["response"]["status"] == "cancelled"


@needs_zsh
def test_quiesce_second_signal_leaves_abort_incomplete(cutover):
    cutover.behave("europa", timers={"wait": "signal"})
    cutover.behave("titan", timers={"restore": "signal"})
    prepared, opened, consumed = opened_with_decision(cutover)
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, consumed)
    failed = raised.value
    assert failed.status == "interrupted" and "abort-incomplete" in failed.observed
    assert failed.next_command == ["recover"]
    root = cutover_root(cutover)
    record = state.current_window(root)
    assert record["state"] == "abort-incomplete"
    assert record["abort"]["hosts"]["titan"]["complete"] is False
    assert "europa" not in record["abort"]["hosts"] or not record["abort"]["hosts"]["europa"][
        "complete"]
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    with pytest.raises(Stop, match="abort-incomplete"):
        state.new_window(root, window.prepared_sha256(prepared))
    # Reconciliation and a completed abort clear it.
    cutover.behave("titan", timers={})
    outcome = window.abort_window(record)
    assert outcome["state"] == "aborted"
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}


@needs_zsh
def test_abort_incomplete_requires_reconciliation(cutover):
    cutover.behave("europa", timers={"stop": "fail-after", "restore": "fail"})
    prepared, opened, consumed = opened_with_decision(cutover)
    with pytest.raises(window.Failed) as raised:
        window.quiesce_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host) == ("timer-stop", "europa")
    assert "abort-incomplete" in failed.observed and "europa" in failed.observed
    assert failed.next_command == ["recover"]
    root = cutover_root(cutover)
    record = state.current_window(root)
    assert record["state"] == "abort-incomplete"
    assert record["abort"]["hosts"]["titan"]["complete"] is True
    assert record["abort"]["hosts"]["europa"]["complete"] is False
    assert timers_active(cutover) == {"titan": "active", "europa": "inactive"}
    with pytest.raises(Stop, match="abort-incomplete"):
        state.new_window(root, window.prepared_sha256(prepared))
    report = window.status()
    assert report["window"]["state"] == "abort-incomplete" and report["next"] == ["recover"]

    cutover.behave("europa", timers={})
    outcome = window.abort_window(record)
    assert outcome["state"] == "aborted" and outcome["hosts"]["europa"]["complete"] is True
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    # The incomplete attempt stays on the record as evidence.
    earlier = state.current_window(root)["earlier_aborts"]
    assert len(earlier) == 1 and earlier[0]["hosts"]["europa"]["complete"] is False
    with pytest.raises(Stop, match="is aborted"):
        window.abort_window(state.current_window(root))
    state.new_window(root, window.prepared_sha256(prepared))


QUIESCE_DRIVER = r"""
import sys
sys.path.insert(0, @TOOLS@)
from datetime import datetime, timezone
from relay_cutover_bootstrap import hosts, state, window
hosts.TOOLS["ssh"] = @SSH@
prepared = state.load_record(window._root() / "prepared.json")
opened = window.open_window(prepared)
record = {"schema": 1, "kind": "desktop", "action": window.RUN_ACTION, "window_id": opened["id"],
          "attempt_id": "run-1", "subject_sha256": "0" * 64, "verdict": "approved",
          "source": {"type": "tty", "prompt": "Restart? [y/N]", "response": "y",
                     "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}}
consumed = state.consume_decision(opened, record, kind="desktop", action=window.RUN_ACTION,
                                  attempt_id="run-1", subject_sha256="0" * 64)
window.quiesce_window(prepared, consumed)
"""


@needs_zsh
def test_abort_after_sigkill_reconciles_first(cutover):
    prepared = preparation.prepare(SESSION)
    cutover.behave("europa", timers={"wait": "latch"})
    script = transport._write(cutover.fixture / "quiesce_driver.py", QUIESCE_DRIVER.replace(
        "@TOOLS@", repr(str(TOOLS))).replace("@SSH@", repr(str(cutover.ssh))))
    driver = subprocess.Popen([sys.executable, "-B", str(script)], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=dict(os.environ))
    try:
        transport._until(lambda: ("europa", "wait") in timer_calls(cutover), seconds=60)
        driver.kill()
        driver.communicate(timeout=30)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait()
    root = cutover_root(cutover)
    record = state.current_window(root)
    assert record["state"] == "quiescing"
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    with pytest.raises(Stop, match="is quiescing"):
        state.new_window(root, window.prepared_sha256(prepared))
    assert window.status()["next"] == ["recover"]

    # The next invocation reconciles first: the remote wait still runs until cancelled.
    outcome = window.abort_window(record)
    assert outcome["state"] == "aborted"
    cancelled = outcome["hosts"]["europa"]["cancelled"]
    assert len(cancelled) == 1 and cancelled[0]["operation"] == "timer-wait"
    assert cancelled[0]["state"] == "cancelled"
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    state.new_window(root, window.prepared_sha256(prepared))


def _dead_identity():
    process = subprocess.Popen(["/usr/bin/sleep", "30"])
    identity = {"pid": process.pid, "start_time": hosts._start_time(process.pid)}
    process.kill()
    process.wait()
    return identity, process


def test_abort_prepared_window_after_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = window._root()
    prepared = {"schema": 1, "prepared_at": "2026-10-20T12:00:00+00:00", "fixture": True}
    state.save_record(root / "prepared.json", prepared)
    opened = window.open_window(prepared)
    assert opened["state"] == "prepared"
    assert opened["owner"]["pid"] == os.getpid()
    assert state.load_record(Path(opened["directory"]) / "prepared.json") == prepared

    # A live invocation's window is never aborted from another one.
    sleeper = subprocess.Popen(["/usr/bin/sleep", "30"])
    try:
        alive = with_state({**opened, "owner": {"pid": sleeper.pid, "start_time":
                                                hosts._start_time(sleeper.pid)}}, "prepared")
        with pytest.raises(Stop, match=f"pid {sleeper.pid}"):
            window.abort_window(alive)
    finally:
        sleeper.kill()
        sleeper.wait()

    # A crash before any mutation leaves `prepared`; it blocks a fresh window until this
    # transition aborts it without contacting either host.
    dead, _ = _dead_identity()
    crashed = with_state({**opened, "owner": dead}, "prepared")
    with pytest.raises(Stop, match="is prepared"):
        state.new_window(root, window.prepared_sha256(prepared))
    assert window.status()["next"] == ["recover"]
    outcome = window.abort_window(crashed)
    assert outcome["state"] == "aborted" and outcome["hosts"] == {}
    assert state.current_window(root)["state"] == "aborted"
    assert not (root / "operations").exists()
    state.new_window(root, window.prepared_sha256(prepared))


ZSH_SCRIPT = r"""
typeset KEEP='original value'
typeset -i COUNT=7
setopt NO_NOMATCH
options_before=$(setopt)
@COMMAND@
rc=$?
options_after=$(setopt)
same=changed
[[ $options_before == $options_after ]] && same=same
print -r -- "after rc=$rc KEEP=$KEEP COUNT=$COUNT options=$same"
"""

CLI_DRIVER = r"""
import sys
from pathlib import Path
sys.path.insert(0, @TOOLS@)
from relay_cutover_bootstrap import cli, hosts, window
hosts.TOOLS["ssh"] = @SSH@
window.CHECKOUT = Path(@CHECKOUT@)
sys.exit(cli.main(sys.argv[1:]))
"""


def _zsh(command, env):
    result = subprocess.run([str(transport.ZSH), "-f", "-c",
                             ZSH_SCRIPT.replace("@COMMAND@", command)],
                            env=env, capture_output=True, text=True, timeout=120)
    fields = {}
    for line in result.stderr.splitlines()[1:]:
        if line.startswith("  ") and ": " in line:
            key, value = line.strip().split(": ", 1)
            fields.setdefault(key, value)
    return result, fields


@needs_zsh
def test_failure_returns_to_zsh(cutover):
    env = {key: os.environ[key] for key in ("USER", "HOME", "PATH", "LANG", "XDG_RUNTIME_DIR",
                                            "FIXTURE_ENV_SECRET") if key in os.environ}
    assert os.access(BOOTSTRAP, os.X_OK)
    assert BOOTSTRAP.read_text().startswith("#!/usr/bin/python3 -B\n")

    # The thin executable itself: nothing is prepared yet, so check stops before any host.
    result, fields = _zsh(f"{shlex.quote(str(BOOTSTRAP))} check", env)
    assert result.stdout.splitlines()[-1] == \
        "after rc=1 KEEP=original value COUNT=7 options=same"
    assert result.stderr.splitlines()[0] == "relay-cutover-bootstrap: check stopped"
    assert (fields["step"], fields["host"], fields["status"], fields["log"]) == (
        "prepared-record", "titan", "missing", "none")
    assert fields["next"] == (f"{TOOLS / 'relay-cutover-bootstrap'} prepare "
                              "--controller-session <native-session-id>")
    assert not (cutover_root(cutover) / "prepared.json").exists()

    # A failed Europa step: step, host, status, private log and one next command, nothing
    # private, and the same Zsh, variables and options afterwards.
    cutover.behave("europa", npm_version="11.6.2")
    driver = transport._write(cutover.fixture / "cli_driver.py", CLI_DRIVER.replace(
        "@TOOLS@", repr(str(TOOLS))).replace("@SSH@", repr(str(cutover.ssh))).replace(
        "@CHECKOUT@", repr(str(window.CHECKOUT))))
    result, fields = _zsh(f"{shlex.quote(sys.executable)} -B {shlex.quote(str(driver))} "
                          f"prepare --controller-session {SESSION}", env)
    assert result.stdout.splitlines()[-1] == \
        "after rc=1 KEEP=original value COUNT=7 options=same"
    assert result.stderr.splitlines()[0] == "relay-cutover-bootstrap: prepare stopped"
    assert (fields["step"], fields["host"], fields["status"]) == ("inventory", "europa", "blocked")
    assert fields["log"].startswith("europa:") and fields["log"].endswith("/log")
    log = Path(fields["log"].removeprefix("europa:"))
    assert log.is_file() and cutover.root("europa") in log.parents
    assert fields["observed"] == "nothing was changed; no window is open"
    assert fields["next"] == (f"{window.CHECKOUT / 'tools/relay-cutover-bootstrap'} prepare "
                              f"--controller-session {SESSION}")
    assert "npm 12.2.1" in result.stderr
    for secret in SECRETS:
        assert secret not in result.stdout + result.stderr
    assert not (cutover_root(cutover) / "prepared.json").exists()


def _opened(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    prepared = {"schema": 1, "prepared_at": "2026-10-20T12:00:00+00:00", "fixture": True}
    state.save_record(window._root() / "prepared.json", prepared)
    return prepared, window.open_window(prepared)


def test_abort_refuses_past_the_pre_merge_boundary(tmp_path, monkeypatch):
    prepared, opened = _opened(tmp_path, monkeypatch)
    for name in ("recovery-required", "recovering", "migrated-surfaces-pending",
                 "ready-for-smokes", "finishing", "inspection-required"):
        with pytest.raises(Stop, match="use recover"):
            window.abort_window(with_state(opened, name))
    # Applying is pre-merge only until familiar mutation is recorded or a target registers.
    merging = with_state({**opened, "familiar": {"started_at": "2026-10-20T12:01:00+00:00"}},
                         "applying")
    with pytest.raises(Stop, match="familiar or a target changed"):
        window.abort_window(merging)
    applying = with_state({key: value for key, value in opened.items()}, "applying")
    target = settings(tmp_path)
    state.register_target(applying, "claude", target, Path(applying["directory"]) / "c.json")
    with pytest.raises(Stop, match="familiar or a target changed"):
        window.abort_window(applying)
    # A stale copy of the record is refused rather than acted on.
    with pytest.raises(Stop, match="not the active one"):
        window.abort_window(opened)
    assert not (window._root() / "operations").exists()


def test_quiesce_requires_this_runs_consumed_decision(tmp_path, monkeypatch):
    prepared, opened = _opened(tmp_path, monkeypatch)
    consumed = decision_for(opened)
    unconsumed = consumed["decision"]
    restart = {**consumed, "action": "restart-surfaces"}
    for decision, fragment in ((unconsumed, "consumed"), (restart, "consumed"),
                               ({**consumed, "window_id": "20261019T120000Z-0badf00d"},
                                "does not belong"), (None, "does not belong")):
        with pytest.raises(window.Failed, match=fragment) as raised:
            window.quiesce_window(prepared, decision)
        assert raised.value.observed == "nothing was changed"
    with pytest.raises(window.Failed, match="another preparation"):
        window.quiesce_window({**prepared, "fixture": False}, consumed)
    other = with_state({**opened, "owner": {"pid": 1, "start_time": 1}}, "prepared")
    with pytest.raises(window.Failed, match="another invocation"):
        window.quiesce_window(prepared, consumed)
    with_state({**other, "owner": opened["owner"]}, "quiescing")
    with pytest.raises(window.Failed, match="is quiescing"):
        window.quiesce_window(prepared, consumed)
    assert not (window._root() / "operations").exists()


# --- the run: six dry runs, the familiar transition and the verified migration -----------

PICK_TEXT = "Grüße ✓"


def _interleaved():
    """Live targets as the operator's files hold them, the same on both hosts: picks before
    and after other keys, nested and non-ASCII pick values, absent pick keys and formatting
    that differs from both the installer's and the guard helper's."""
    personal = {"model": "opus[1m]", **transport.REVIEWED["claude"], "effortLevel": "höch",
                "modelSettings": {"opus[1m]": {"thinking": {"budget": 32000}, "label": PICK_TEXT,
                                               "tiers": [1, 2.5, None, False]}}}
    work = {**transport.REVIEWED["claude-work"], "model": "opus"}
    return {"claude": json.dumps(personal, indent=4).encode(),
            "claude-work": json.dumps(work, separators=(",", ":")).encode(),
            "codex": json.dumps(transport.REVIEWED["codex"], indent=4).encode(),
            "codex-work": transport._encode_json(transport.REVIEWED["codex-work"])}


def _requests(patch, world):
    """Every host request in order, with the window record as it stood when each was sent."""
    log, real, root = [], hosts.request, cutover_root(world)

    def record(host, mode, operation, payload, *, timeout):
        log.append({"event": "send", "host": host, "operation": operation, "payload": payload,
                    "window": state.current_window(root)})
        response = real(host, mode, operation, payload, timeout=timeout)
        log.append({"event": "reply", "host": host, "operation": operation,
                    "status": response["status"]})
        return response

    patch.setattr(hosts, "request", record)
    return log


def _sends(log, operation=None):
    return [(index, entry) for index, entry in enumerate(log) if entry["event"] == "send"
            and (operation is None or entry["operation"] == operation)]


def _drain(fd):
    """What the run wrote to its terminal: the preview, the ask and the echoed answer."""
    os.set_blocking(fd, False)
    data = b""
    while True:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        data += chunk
    return data.decode("utf-8", "replace")


def _option(call, name):
    return call["args"][call["args"].index(name) + 1]


def _europa_polled(world, pre):
    """True once Europa's check of familiar's source against the merge has failed once."""
    return lambda: any(call["host"] == "europa" and call["args"][:1] == ["familiar-source"]
                       and call["args"][2] != pre and call["exit"] != 0
                       for call in observed(world, "relay-cutover"))


def run_decision(prepared, opened, attempt=None):
    """A fixture of the operator's terminal answer to this run's desktop subject."""
    attempt = attempt or window.RUN_ATTEMPT
    subject = window.run_subject(prepared)
    record = {"schema": 1, "kind": "desktop", "action": window.RUN_ACTION,
              "window_id": opened["id"], "attempt_id": attempt, "subject_sha256": sha(subject),
              "verdict": "approved", "source": {
                  "type": "tty", "prompt": "Restart these familiar surfaces? Type yes:",
                  "response": "yes",
                  "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}}
    return state.consume_decision(opened, record, kind="desktop", action=window.RUN_ACTION,
                                  attempt_id=attempt, subject_sha256=sha(subject))


@pytest.fixture(scope="class")
def migrated(tmp_path_factory):
    """One whole run through the CLI, answered on a terminal, whose evidence the class's tests
    read: interleaved live picks, a Dropbox that delivers familiar's merge to Europa only
    after Europa first checked for it, and every request with the window as it stood."""
    with pytest.MonkeyPatch.context() as patch:
        world = transport.World(tmp_path_factory.mktemp("migrated"), patch)
        try:
            world.stage_cutover()
            live = _interleaved()
            for target_id, data in live.items():
                world.write_target(target_id, data)
            patch.setattr(window, "CHECKOUT", world.home("titan") / "d/hq")
            # Titan's shell routes a build cache at preparation and elsewhere at the run.
            patch.setenv("CACHE_DIR", str(world.tmp / "prepared-cache"))
            prepared = preparation.prepare(SESSION)
            patch.setenv("CACHE_DIR", str(world.tmp / "unprepared-cache"))
            marks = {"observed": len(world.lines("observed")),
                     "probes": len(world.lines("probes"))}
            requests = _requests(patch, world)
            world.start_dropbox(hold=_europa_polled(world, world.pins["familiar_pre"]))
            master, slave = os.openpty()
            patch.setattr(cli, "TTY", os.ttyname(slave))
            os.write(master, b"yes\n")
            out, err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = cli.main(["run"])
                terminal = _drain(master)
            finally:
                os.close(master)
                os.close(slave)
            yield SimpleNamespace(world=world, prepared=prepared, live=live, marks=marks,
                                  requests=requests, code=code, out=out.getvalue(),
                                  err=err.getvalue(), terminal=terminal,
                                  window=state.current_window(cutover_root(world)))
        finally:
            world.close()


@needs_zsh
class TestRun:
    """A whole bootstrap run through the verified migration checkpoint."""

    def test_bootstrap_run_takes_its_terminal_decision(self, migrated):
        assert migrated.code == 0, migrated.err
        record = migrated.window
        assert record["state"] == "ready-for-smokes"
        subject = window.run_subject(migrated.prepared)
        assert record["surfaces"] == subject
        # The same consumed decision restarted the surfaces after the verified checkpoint.
        attempts = record["desktop"]["attempts"]
        assert [(entry["attempt_id"], entry["outcome"]) for entry in attempts] == [
            (window.RUN_ATTEMPT, "complete")] and attempts[0]["subject"] == subject
        consumed = state.load_record(Path(record["directory"]) / "decisions"
                                     / f"{window.RUN_ATTEMPT}.json")
        assert (consumed["kind"], consumed["action"], consumed["subject_sha256"]) == (
            "desktop", window.RUN_ACTION, sha(subject))
        source = consumed["decision"]["source"]
        assert source["type"] == "tty" and source["response"] == "yes"
        assert source["prompt"] in migrated.terminal
        assert record["decision"]["attempt_id"] == window.RUN_ATTEMPT
        # The bounded preview names each host's surfaces, their processes and the impact.
        assert record["id"] in migrated.terminal and window.IMPACT in migrated.terminal
        for host in HOSTS:
            for surface in migrated.prepared["hosts"][host]["desktop"]["surfaces"]:
                assert surface["name"] in migrated.terminal
                assert all(str(process["pid"]) in migrated.terminal
                           for process in surface["processes"])
        assert migrated.terminal.index(window.IMPACT) < migrated.terminal.index(source["prompt"])
        # The handoff names what holds until finish and one next command.
        out = migrated.out
        assert "ready-for-smokes" in out and "paused" in out
        assert "surfaces restarted" in out
        for host in HOSTS:
            for name, process in surfaces.restarted(record, surfaces.FORWARD)[host].items():
                assert f"{name} pid {process['pid']}" in out
        assert "do not change or save Claude model or effort defaults" in out
        assert "avoid cl, clw" in out
        assert out.splitlines()[-1] == "  next: " + cli.command_line(
            ["record-smoke", "--observe", "titan"])
        assert shlex.join(smoke.resume_argv(migrated.prepared, "personal")) in out
        for secret in SECRETS + (PICK_TEXT, "höch"):
            assert secret not in out + migrated.err + migrated.terminal

    def test_six_dry_runs_precede_merge(self, migrated):
        log, pins = migrated.requests, migrated.world.pins
        assert [(entry["host"], entry["payload"]["target_id"])
                for _, entry in _sends(log, "target-dry")] == [
            ("titan", "claude"), ("titan", "claude-work"), ("titan", "codex"),
            ("titan", "codex-work"), ("europa", "claude"), ("europa", "claude-work")]
        verdicts = [index for index, entry in enumerate(log) if entry["event"] == "reply"
                    and entry["operation"] == "target-dry"]
        assert len(verdicts) == 6 and {log[index]["status"] for index in verdicts} == {"completed"}
        merges = _sends(log, "familiar-merge")
        assert len(merges) == 1
        merge_start_index, merge = merges[0]
        last_dry_verdict_index = verdicts[-1]
        assert last_dry_verdict_index < merge_start_index
        # Between the seal and the merge: the frozen bytes recheck unchanged, both hosts closed.
        assert [(entry["host"], entry["operation"]) for index, entry in _sends(log)
                if last_dry_verdict_index < index < merge_start_index] == [
            ("titan", "target-verify"), ("europa", "target-verify"), ("titan", "no-live"),
            ("europa", "no-live")]
        # The immutable tip is merged, marked first, after the seal of the effective inputs.
        assert merge["payload"] == {"window_id": migrated.window["id"],
                                    "pre": pins["familiar_pre"],
                                    "tip": pins["familiar_feature_tip"]}
        at_merge = merge["window"]
        assert at_merge["state"] == "applying"
        assert {key: at_merge["familiar"][key] for key in ("pre", "tip")} == {
            "pre": pins["familiar_pre"], "tip": pins["familiar_feature_tip"]}
        assert "merge" not in at_merge["familiar"]
        sealed = at_merge["sealed"]
        assert sealed["effective_inputs_sha256"] == sha(sealed["inputs"])
        assert sealed["inputs"]["prepared_sha256"] == window.prepared_sha256(migrated.prepared)
        assert sealed == migrated.window["sealed"]
        assert all(entry["window"].get("sealed") is None and "familiar" not in entry["window"]
                   for index, entry in _sends(log) if index <= last_dry_verdict_index)
        homes = [migrated.world.home(host) for host in HOSTS]
        merged = migrated.window["familiar"]["merge"]
        assert [transport.familiar_head(home) for home in homes] == [merged, merged]
        assert transport._git(homes[0] / "d/familiar", "rev-list", "--parents", "-n", "1",
                              merged).split() == [merged, pins["familiar_pre"],
                                                  pins["familiar_feature_tip"]]
        assert migrated.window["familiar"]["parents"] == [pins["familiar_pre"],
                                                          pins["familiar_feature_tip"]]

    def test_interleaved_picks_use_installer_bytes(self, migrated):
        world, sealed = migrated.world, migrated.window["sealed"]["inputs"]["hosts"]
        assert {host: list(sealed[host]) for host in HOSTS} == {
            "titan": ["claude", "claude-work", "codex", "codex-work"],
            "europa": ["claude", "claude-work"]}
        for host in HOSTS:
            for target_id, result in sealed[host].items():
                dry_copy = Path(result["copy"])
                plan = json.loads(Path(result["plan"]["path"]).read_bytes())
                planned_after, = [change["after"] for change in plan["changes"]
                                  if change["path"] == str(dry_copy)]
                expected_bytes = world.target(host, target_id).read_bytes()
                assert expected_bytes == dry_copy.read_bytes() == planned_after.encode("utf-8")
                assert hashlib.sha256(expected_bytes).hexdigest() == result["expected"]["sha256"]
                assert Path(result["frozen"]["path"]).read_bytes() == migrated.live[target_id]
                value = json.loads(expected_bytes)
                # Neither the controller's serialization of that value nor the guard helper's.
                for indent in (2, 4):
                    assert expected_bytes != (json.dumps(value, indent=indent,
                                                         ensure_ascii=False) + "\n").encode()
        personal = world.target("titan", "claude").read_bytes()
        value, live = json.loads(personal), json.loads(migrated.live["claude"])
        order = list(value)
        assert order.index("model") < order.index("hooks")
        assert order.index("alwaysThinkingEnabled") < order.index("effortLevel") < \
            order.index("modelSettings")
        keys = migrated.prepared["filter"]["keys"]
        assert {key: value[key] for key in keys} == {key: live[key] for key in keys}
        assert PICK_TEXT.encode() in personal and b"\\u00" not in personal
        work = json.loads(world.target("titan", "claude-work").read_bytes())
        assert list(work)[0] == "model" and work["model"] == "opus"
        assert "effortLevel" not in work and "modelSettings" not in work
        for target_id in ("codex", "codex-work"):
            assert Path(sealed["titan"][target_id]["copy"]).name == "hooks.json"
            reviewed = json.loads(world.member("titan", target_id, "after").read_bytes())
            assert sha(json.loads(world.target("titan", target_id).read_bytes())) == sha(reviewed)

    def test_all_target_bootstrap_single_writer(self, migrated):
        world, log = migrated.world, migrated.requests
        applies = [entry for _, entry in _sends(log, "target-apply")]
        apply_hosts = [entry["host"] for entry in applies]
        target_order = [entry["payload"]["target_id"] for entry in applies]
        assert apply_hosts == ["titan"] * 4
        assert target_order == ["claude", "claude-work", "codex", "codex-work"]
        # Both hosts are checked closed right before each write; the migration is marked
        # verified only after every host's targets, source, dependencies and evidence passed.
        sends = [entry for _, entry in _sends(log)]
        for index, entry in enumerate(sends):
            if entry["operation"] == "target-apply":
                assert [(sent["host"], sent["operation"]) for sent in sends[index - 2:index]] \
                    == [("titan", "no-live"), ("europa", "no-live")]
        last = max(index for index, entry in enumerate(sends)
                   if entry["operation"] == "target-apply")
        assert [(entry["host"], entry["operation"], entry["window"]["state"])
                for entry in sends[last + 1:last + 5]] == [
            ("titan", "target-verify", "applying"), ("titan", "familiar-verify", "applying"),
            ("europa", "target-verify", "applying"), ("europa", "familiar-verify", "applying")]
        # Only after that checkpoint did the surfaces restart, one at a time.
        assert [(entry["host"], entry["operation"], entry["window"]["state"])
                for entry in sends[last + 5:]] == [
            (host, "surface-restart", "migrated-surfaces-pending") for host in HOSTS
            for _ in surfaces.SURFACES]
        assert migrated.window["verified"]["hosts"]["europa"]["familiar"]["relay"] == {
            "version": "0.1.1", "commit": world.pins["relay_commit"]}
        # Each target is planned and applied once, on Titan only, with the relay flags.
        live = [call for call in observed(world, "installer") if call["phase"] == "live"]
        assert [(call["host"], call["target_id"], call["apply"]) for call in live] == [
            ("titan", target_id, applying) for target_id in target_order
            for applying in (False, True)]
        home = world.home("titan")
        for call in live:
            harness = "codex" if call["target_id"].startswith("codex") else "claude-code"
            assert (_option(call, "--harness"), _option(call, "--retire"),
                    _option(call, "--node")) == (harness, "familiar", "/usr/bin/node")
            assert _option(call, "--evidence") == str(
                home / f"d/ops/docs/runbooks/relay-guard-evidence-{harness}.json")
            assert _option(call, "--subscribers") == str(home / ".config/relay/subscribers.json")
            assert _option(call, "--target") == str(world.target("titan", call["target_id"]))
        guards = [call for call in observed(world, "relay-cutover") if "ledger" in call]
        assert [(call["host"], _option(call, "--target")) for call in guards] == [
            ("titan", str(world.target("titan", target_id)))
            for target_id in ("claude", "claude-work")]
        # One writer per harness: familiar's hooks are retired and relay's entry is the only
        # hook, on Titan and in Europa's synchronized, verified Claude copies.
        relay = f"{transport.RELAY_HOOK} --harness fixture PreToolUse"
        for host in HOSTS:
            for target_id in inputs.relevant(host):
                value = json.loads(world.target(host, target_id).read_bytes())
                commands = [hook["command"] for groups in value["hooks"].values()
                            for group in groups for hook in group["hooks"]]
                assert commands == [relay]
        verifies = [entry for _, entry in _sends(log, "target-verify")
                    if entry["payload"]["verify"]]
        assert [(entry["host"], entry["payload"]["wait"]) for entry in verifies] == [
            ("titan", False), ("europa", True)]
        ledger = state.read_ledger(migrated.window)
        assert [entry["target_id"] for entry in ledger] == target_order
        for entry in ledger:
            artifact = Path(entry["artifact"])
            assert artifact.parent == Path(migrated.window["directory"]) / "live"
            assert [change["path"] for change in json.loads(artifact.read_bytes())["changes"]] \
                == [entry["target"]]
            assert mode(artifact) == 0o600
            assert Path(entry["original"]).read_bytes() == migrated.live[entry["target_id"]]

    def test_europa_claude_uses_local_installer(self, migrated):
        world, home = migrated.world, migrated.world.home("europa")
        europa = [call for call in observed(world, "installer") if call["host"] == "europa"]
        assert sorted({call["target_id"] for call in europa}) == ["claude", "claude-work"]
        assert {(call["phase"], call["hold"]) for call in europa} == {("dry", "1")}
        assert {call["script"] for call in europa} == {
            os.path.realpath(home / "d/hq/relay/bin/relay")}
        for call in europa:
            assert _option(call, "--evidence") == str(
                home / "d/ops/docs/runbooks/relay-guard-evidence-claude-code.json")
            assert _option(call, "--subscribers") == str(home / ".config/relay/subscribers.json")
            assert Path(_option(call, "--target")).is_relative_to(world.root("europa") / "dry")
        sealed = migrated.window["sealed"]["inputs"]["hosts"]
        members = migrated.prepared["helpers"]["members"]
        runtime = home / ".local/share/relay/v0.1.1/node_modules/relay/bin/relay.js"
        for target_id, result in sealed["europa"].items():
            assert result["identities"] == {
                "installer": members["hq:relay/bin/relay"],
                "relay_cutover": members["hq:tools/relay-cutover"],
                "evidence": members["ops:docs/runbooks/relay-guard-evidence-claude-code.json"],
                "runtime": transport._digest(runtime),
                "subscribers": transport._digest(home / ".config/relay/subscribers.json")}
            # Both hosts' installers agree byte for byte on each shared Claude target.
            assert result["expected"]["sha256"] == sealed["titan"][target_id]["expected"][
                "sha256"]
            assert result["frozen"]["sha256"] == sealed["titan"][target_id]["frozen"]["sha256"]

    def test_sync_before_install(self, migrated):
        world, merge = migrated.world, migrated.window["familiar"]["merge"]
        calls = observed(world, since=migrated.marks["observed"])
        for host in HOSTS:
            installs = [index for index, call in enumerate(calls) if call["host"] == host
                        and call["tool"] == "npm" and call["args"][:1] == ["ci"]]
            checks = [index for index, call in enumerate(calls) if call["host"] == host
                      and call["args"] == ["familiar-source", "--head", merge]]
            assert len(installs) == 1 and checks and checks[0] < installs[0]
            install = calls[installs[0]]
            record = migrated.prepared["hosts"][host]
            assert install["cwd"] == str(world.home(host) / "d/familiar")
            # Installs pin the prepared, revalidated cache prefixes, never the current ones.
            assert install["cache"] == record["caches"]["prefixes"]["npm"]
            assert install["cache_dir"] == record["caches"]["prefixes"].get("CACHE_DIR")
            assert install["cache_dir"] == (str(world.tmp / "prepared-cache")
                                            if host == "titan" else None)
            assert (install["path_head"], install["hold"]) == ("/usr/bin", "1")
            proof = migrated.window["dependencies"][host]
            assert proof["relay"] == {"version": "0.1.1",
                                      "commit": world.pins["relay_commit"]}
            assert proof["cache"]["npm"] == record["caches"]["prefixes"]["npm"]
            # The install ran only after this host's check against the merge passed; Europa's
            # first check ran before Dropbox delivered the merge, so it waited and checked again.
            before = [calls[index]["exit"] for index in checks if index < installs[0]]
            assert before[-1] == 0
            if host == "europa":
                assert before[0] != 0 and len(before) >= 2
        # Both hosts are checked closed right before each host's install step.
        sends = [entry for _, entry in _sends(migrated.requests)]
        installs = [index for index, entry in enumerate(sends)
                    if entry["operation"] == "familiar-install"]
        assert [sends[index]["host"] for index in installs] == list(HOSTS)
        for index in installs:
            assert [(sent["host"], sent["operation"]) for sent in sends[index - 2:index]] == [
                ("titan", "no-live"), ("europa", "no-live")]
        titan_install = next(index for index, call in enumerate(calls) if call["tool"] == "npm"
                             and call["args"][:1] == ["ci"])
        assert all(call["host"] == "titan" for call in calls[:titan_install]
                   if call["tool"] == "npm" and call["args"][:1] == ["ci"])

    def test_registration_before_guard_write(self, migrated):
        world = migrated.world
        by_path = {str(world.target("titan", target_id)): target_id
                   for target_id in transport.TARGET_PATHS}
        first = {}
        for call in observed(world):
            if call["host"] != "titan" or "ledger" not in call:
                continue
            first.setdefault(by_path[_option(call, "--target")], call)
        assert list(first) == ["claude", "claude-work", "codex", "codex-work"]
        sealed = migrated.window["sealed"]["inputs"]["hosts"]["titan"]
        directory = Path(migrated.window["directory"])
        for target_id, call in first.items():
            # Claude's first write is its guard retirement; Codex's is the installer's apply.
            assert call["tool"] == ("relay-cutover" if target_id.startswith("claude")
                                    else "installer")
            assert target_id in call["ledger"]["entries"]
            assert target_id in call["ledger"]["originals"]
            original = (directory / f"{target_id}.original").read_bytes()
            assert original == migrated.live[target_id]
            assert hashlib.sha256(original).hexdigest() == sealed[target_id]["frozen"]["sha256"]

    def test_bootstrap_probes_exit_before_final_no_live(self, migrated):
        world = migrated.world
        calls = observed(world, since=migrated.marks["observed"])
        quiesce = next(index for index, call in enumerate(calls) if call["tool"] == "codex"
                       and call["args"][:1] == ["app-server"])
        recorded = next(index for index, call in enumerate(calls)
                        if call["tool"] == "quiesce-timers" and call["args"][0] == "record")
        stopped = next(index for index, call in enumerate(calls)
                       if call["tool"] == "quiesce-timers" and call["args"][0] == "stop")
        probes = [index for index, call in enumerate(calls) if call["tool"] == "claude"]
        # Every held version and doctor probe, on both hosts and in both homes, ran first.
        assert {(calls[index]["host"], calls[index]["args"][0],
                 calls[index]["config_dir"] is not None) for index in probes} == {
            (host, probe, work) for host in HOSTS for probe in ("--version", "doctor")
            for work in (False, True)}
        assert all(calls[index]["hold"] == "1" for index in probes)
        assert max(probes) < quiesce
        # Each left a descendant alive until collected; none was alive at the final no-live.
        lingered = world.lines("probes")[migrated.marks["probes"]:]
        assert len(lingered) == len(probes) and {entry["mode"] for entry in lingered} == {
            "linger"}
        final = [call for call in calls[quiesce:recorded] if call["tool"] == "preflight"]
        assert [call["host"] for call in final] == ["titan", "titan", "europa"]
        assert all(call["probes"] == [] for call in final)
        assert all(transport._gone(entry["pid"], entry["start_time"]) for entry in lingered)
        # Timers stop only after that check.
        assert recorded < stopped


    def test_post_resume_pick_drift_refuses_restore(self, migrated):
        """After the verified migration the operator resumed Claude and changed a model pick,
        which the handoff forbids until finish. Choosing rollback then stops for inspection
        before any write: no target, source or dependency changes and nothing is force-copied.
        It runs last in this class because it changes the class's world."""
        world = migrated.world
        assert "do not change or save Claude model or effort defaults" in migrated.out
        root = cutover_root(world)
        record = state.current_window(root)
        assert record["state"] == "ready-for-smokes"
        value = json.loads(world.target("titan", "claude").read_bytes())
        value["model"] = "sonnet"
        world.write_target("claude", json.dumps(value, indent="\t").encode() + b"\n")
        live = Path(record["directory"]) / "live"
        before = (_targets(world), _heads(world), _modules(world), transport._tree_of(live))
        mark = len(world.lines("observed"))
        with pytest.raises(window.Failed) as raised:
            recovery.restore_window(record)
        failed = raised.value
        assert (failed.step, failed.host, failed.status) == ("target-check", "titan", "blocked")
        assert "claude" in failed.error and "sonnet" not in failed.error
        assert "stopped pending inspection" in failed.observed
        assert "Do not open Claude or Codex" in failed.observed
        assert failed.next_command == ["recover"]
        record = state.current_window(root)
        assert record["state"] == "inspection-required"
        assert record["recovery"]["check"]["claude"]["verdict"] == "unknown"
        assert {target_id: entry["verdict"] for target_id, entry in
                record["recovery"]["check"].items() if target_id != "claude"} == {
            "claude-work": "relay-applied", "codex": "relay-applied", "codex-work": "relay-applied"}
        assert (_targets(world), _heads(world), _modules(world),
                transport._tree_of(live)) == before
        assert not any(event.startswith(("restore:", "rollback:")) or "git-" in event
                       for event in _recovery_events(world, mark))
        report = window.status()
        assert report["next"] == ["recover"] and "stopped pending inspection" in report["detail"]


@needs_zsh
def test_bootstrap_surviving_probe_refuses_before_mutation(cutover):
    prepared = preparation.prepare(SESSION)
    cutover.behave("europa", probe="survive")
    opened = window.open_window(prepared)
    consumed = run_decision(prepared, opened)
    mark = len(cutover.lines("observed"))
    with pytest.raises(window.Failed) as raised:
        window.run_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("no-live", "europa", "blocked")
    survivors = [entry for entry in cutover.lines("probes") if entry["mode"] == "survive"]
    assert survivors
    # No caller-child exemption: the tool's own surviving probes block, and none is killed.
    assert all(not transport._gone(entry["pid"], entry["start_time"]) for entry in survivors)
    assert all(any(str(entry["pid"]) in blocker for blocker in failed.blockers)
               for entry in survivors)
    calls = observed(cutover, since=mark)
    assert not any(call["tool"] == "codex" and call["args"][:1] == ["app-server"]
                   for call in calls)
    assert timer_calls(cutover, mark) == []
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "aborted" and record["abort"]["hosts"] == {}
    assert failed.next_command == ["run"]


def _after(name, change):
    """Run `change(world)` once the window's named step has returned."""
    def arrange(world, monkeypatch):
        step = getattr(window, name)

        def wrapped(*args):
            result = step(*args)
            change(world)
            return result
        monkeypatch.setattr(window, name, wrapped)
    return arrange


def _restage(world):
    world.write_manifest(generation="g2", hosts=("europa",))


def _europa_evidence(world):
    path = world.home("europa") / "d/ops/docs/runbooks/relay-guard-evidence-claude-code.json"
    path.write_text(json.dumps({"harness": "claude-code", "version": "2.1.999"}) + "\n")


def _reformat_codex(world):
    world.write_target("codex", json.dumps(transport.REVIEWED["codex"]).encode(),
                       hosts=("titan",))


MISMATCH = {
    "europa-bytes": ({"installer": {"dry:claude-work": "drift"}}, None,
                     ("target-dry", "europa"), "planned"),
    "cross-host": ({"installer": {"dry:claude": "variant"}}, None, ("target-dry", "europa"),
                   "differ between titan and europa"),
    "manifest": ({}, _after("quiesce_window", _restage), ("target-dry", "europa"),
                 "input-manifest"),
    "evidence": ({}, _after("quiesce_window", _europa_evidence), ("target-dry", "europa"),
                 "evidence"),
    "frozen": ({}, _after("dry_targets", _reformat_codex), ("target-frozen", "titan"),
               "after the freeze"),
}


@needs_zsh
@pytest.mark.parametrize("case", sorted(MISMATCH))
def test_dry_mismatch_aborts_before_merge(cutover, monkeypatch, case):
    behavior, arrange, where, fragment = MISMATCH[case]
    cutover.behave("europa", **behavior)
    if arrange is not None:
        arrange(cutover, monkeypatch)
    prepared = preparation.prepare(SESSION)
    log = _requests(monkeypatch, cutover)
    snapshots = {host: transport._tree_of(cutover.root(host) / "familiar-state") for host in HOSTS}
    opened = window.open_window(prepared)
    consumed = run_decision(prepared, opened)
    with pytest.raises(window.Failed) as raised:
        window.run_window(prepared, consumed)
    targets = {host: {target_id: cutover.target(host, target_id).read_bytes()
                      for target_id in transport.TARGET_PATHS} for host in HOSTS}
    failed = raised.value
    assert (failed.step, failed.host) == where and fragment in failed.error, failed.error
    assert "aborted" in failed.observed and failed.next_command == ["run"]
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "aborted" and "familiar" not in record
    assert {host: record["abort"]["hosts"][host]["complete"] for host in HOSTS} == {
        "titan": True, "europa": True}
    assert record.get("earlier_aborts", []) == []  # aborted once, never again by the run
    # Both timer and snapshot windows are undone; familiar stays at PRE and no live target,
    # ledger entry or merge marker was written.
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    assert {host: transport._tree_of(cutover.root(host) / "familiar-state")
            for host in HOSTS} == snapshots
    assert [transport.familiar_head(cutover.home(host)) for host in HOSTS] == [
        cutover.pins["familiar_pre"]] * 2
    expected = {host: {target_id: transport._encode_json(transport.LIVE[target_id]())
                       for target_id in transport.TARGET_PATHS} for host in HOSTS}
    if case == "frozen":  # the test's own write after the freeze, and nothing else
        expected["titan"]["codex"] = json.dumps(transport.REVIEWED["codex"]).encode()
    assert targets == expected
    assert not (Path(record["directory"]) / "touched.tsv").exists()
    assert not any(entry["operation"] in ("familiar-merge", "familiar-install", "target-apply")
                   for _, entry in _sends(log))
    assert not any("merge" in call for call in observed(cutover, "git"))
    assert not any(call["phase"] == "live" for call in observed(cutover, "installer"))
    # The dry evidence stays for inspection.
    assert len(list((cutover.root("titan") / "dry" / record["id"]).iterdir())) == 4
    assert transport.OUTPUT_SECRET not in str(failed)


@needs_zsh
def test_sync_timeout_requires_recovery(cutover):
    cutover.config["sync"]["budget"] = 1.0  # familiar's merge never reaches Europa here
    cutover.save()
    prepared = preparation.prepare(SESSION)
    opened = window.open_window(prepared)
    consumed = run_decision(prepared, opened)
    with pytest.raises(window.Failed) as raised:
        window.run_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("familiar-install", "europa", "failed")
    assert "did not reach" in failed.error
    assert failed.next_command == ["recover"]
    assert "Do not open Claude or Codex" in failed.observed
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "recovery-required" and record["failure"]["host"] == "europa"
    merged = record["familiar"]["merge"]
    assert transport.familiar_head(cutover.home("titan")) == merged
    assert transport.familiar_head(cutover.home("europa")) == cutover.pins["familiar_pre"]
    installs = [call["host"] for call in observed(cutover, "npm") if call["args"][:1] == ["ci"]]
    assert installs == ["titan"] and list(record["dependencies"]) == ["titan"]
    assert state.read_ledger(record) == []
    assert {host: {target_id: cutover.target(host, target_id).read_bytes()
                   for target_id in transport.TARGET_PATHS} for host in HOSTS} == {
        host: {target_id: transport._encode_json(transport.LIVE[target_id]())
               for target_id in transport.TARGET_PATHS} for host in HOSTS}
    # Timers stay paused for recovery; the pre-merge abort can no longer undo this window.
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    with pytest.raises(Stop, match="use recover"):
        window.abort_window(record)
    assert window.status()["next"] == ["recover"]


@needs_zsh
def test_sync_wait_rechecks_closure_before_install(cutover):
    """A Claude session opened on Europa while its install waits for the merge to arrive stops
    the install: closure is checked again after the wait, right before npm ci."""
    polled, opened = _europa_polled(cutover, cutover.pins["familiar_pre"]), []
    claude = os.path.realpath(cutover.home("europa") / ".local/bin/claude")

    def hold():
        if not opened and polled():
            config = json.loads(cutover.config_path.read_text())
            config["hosts"]["europa"]["rows"].append({
                "pid": 3900701, "start_time": 81, "comm": "claude", "exe": claude,
                "argv": ["claude"], "held": False})
            temp = cutover.config_path.with_name("config.json.dropbox")
            temp.write_text(json.dumps(config, indent=2))
            os.replace(temp, cutover.config_path)  # fixture tools never read a partial file
            opened.append(True)
        return bool(opened)

    prepared = preparation.prepare(SESSION)
    cutover.start_dropbox(hold=hold)
    opened_window = window.open_window(prepared)
    consumed = run_decision(prepared, opened_window)
    with pytest.raises(window.Failed) as raised:
        window.run_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("familiar-install", "europa", "failed")
    assert "3900701" in failed.error and failed.next_command == ["recover"]
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "recovery-required" and opened
    # Europa's source did reach the merge; only the session it found then stopped the install.
    merged = record["familiar"]["merge"]
    assert [transport.familiar_head(cutover.home(host)) for host in HOSTS] == [merged, merged]
    installs = [call["host"] for call in observed(cutover, "npm") if call["args"][:1] == ["ci"]]
    assert installs == ["titan"] and list(record["dependencies"]) == ["titan"]
    assert state.read_ledger(record) == []


@needs_zsh
def test_dry_precondition_after_quiesce_aborts(cutover, monkeypatch):
    """dry_targets refuses a window whose prepared record it cannot read; in a run, that
    refusal after quiescence still takes the pre-merge abort on every recorded host."""
    def corrupt(world):
        current = state.current_window(cutover_root(world))
        (Path(current["directory"]) / "prepared.json").write_bytes(b"{not json")

    _after("quiesce_window", corrupt)(cutover, monkeypatch)
    prepared = preparation.prepare(SESSION)
    opened = window.open_window(prepared)
    consumed = run_decision(prepared, opened)
    with pytest.raises(window.Failed) as raised:
        window.run_window(prepared, consumed)
    failed = raised.value
    assert (failed.step, failed.host) == ("target-dry", "titan")
    assert "prepared.json" in failed.error
    assert "aborted" in failed.observed and failed.next_command == ["run"]
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "aborted" and "familiar" not in record
    assert {host: record["abort"]["hosts"][host]["complete"] for host in HOSTS} == {
        "titan": True, "europa": True}
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    assert not (cutover.root("titan") / "dry" / record["id"]).exists()
    # The abort ran once: no earlier abort record, and no dry run was sent.
    assert record.get("earlier_aborts", []) == []
    assert not any(attempt["step"] == "target-dry" for attempt in record["attempts"])


@needs_zsh
def test_bootstrap_run_needs_the_operator_decision(cutover, monkeypatch, capsys):
    prepared = preparation.prepare(SESSION)
    mark, root = len(cutover.lines("observed")), cutover_root(cutover)

    def run(*argv):
        code = cli.main(["run", *argv])
        stderr = capsys.readouterr().err
        record = state.current_window(root)
        assert code == 1 and record["state"] == "aborted" and record["abort"]["hosts"] == {}
        return stderr, record

    # Without a terminal, run stops before any change: it is operator-run, from an ordinary
    # terminal, and no decision file can stand in for the operator's answer.
    monkeypatch.setattr(cli, "TTY", str(cutover.tmp / "no-terminal"))
    stderr, first = run()
    assert "run stopped" in stderr and "step: decision" in stderr
    assert "operator-run" in stderr and "ordinary terminal" in stderr
    assert "every Claude and Codex session closed" in stderr
    assert "decision-file" not in stderr and "decision file" not in stderr
    # A declined answer on the terminal authorizes nothing.
    master, slave = os.openpty()
    try:
        monkeypatch.setattr(cli, "TTY", os.ttyname(slave))
        os.write(master, b"no\n")
        stderr, second = run()
    finally:
        os.close(master)
        os.close(slave)
    assert "declined" in stderr and second["id"] != first["id"]
    monkeypatch.setattr(cli, "TTY", str(cutover.tmp / "no-terminal"))

    def recorded_reply(window_id, action, attempt, subject, name):
        return transport._stage(cutover.tmp, name, json.dumps({
            "schema": 1, "kind": "desktop", "action": action, "window_id": window_id,
            "attempt_id": attempt, "subject_sha256": sha(subject), "verdict": "approved",
            "source": {"type": "session", "session_id": SESSION, "ask": "Restart the surfaces?",
                       "reply": "yes",
                       "answered_at": datetime.now(timezone.utc).isoformat()}}).encode())

    # run takes no decision file at all: the option does not exist and no window opens.
    stale = recorded_reply(first["id"], window.RUN_ACTION, window.RUN_ATTEMPT,
                           window.run_subject(prepared), "run-decision.json")
    with pytest.raises(SystemExit) as raised:
        cli.main(["run", "--decision-file", str(stale)])
    assert raised.value.code == 2
    assert "unrecognized arguments: --decision-file" in capsys.readouterr().err
    assert state.current_window(root) == second
    # The decision-file route stays for a window that already exists, as Task 6's
    # restart-surfaces needs: a record for another window is refused, a matching one consumed.
    opened = window.open_window(prepared)
    subject = {"hosts": ["titan"], "surfaces": ["familiar-niri-watch"]}
    other = recorded_reply(first["id"], "restart-surfaces", "restart-1", subject, "other.json")
    with pytest.raises(Stop, match="window_id"):
        cli.acquire_decision(opened, action="restart-surfaces", attempt_id="restart-1",
                             subject=subject, decision_file=str(other))
    mine = recorded_reply(opened["id"], "restart-surfaces", "restart-1", subject, "mine.json")
    consumed = cli.acquire_decision(opened, action="restart-surfaces", attempt_id="restart-1",
                                    subject=subject, decision_file=str(mine))
    assert consumed["subject_sha256"] == sha(subject)
    assert consumed["decision"]["source"]["type"] == "session"
    assert window.abort_window(state.current_window(root))["hosts"] == {}
    assert observed(cutover, since=mark) == [] and not (root / "quiesce").exists()


# --- recovery: the restoration core and reconciliation of an interrupted run ---------------


class Killed(BaseException):
    """Stands in for SIGKILL at a durable point: no handler runs and the window keeps the last
    record it saved."""


def _dies_once(real, when):
    """A window save that dies at the first save whose changes `when` names, before it lands."""
    fired = []

    def save(record, **changes):
        if not fired and when(changes):
            fired.append(True)
            raise Killed()
        return real(record, **changes)

    return save


def _killed_at(monkeypatch, when):
    """The run dies at the first window save whose changes `when` names."""
    monkeypatch.setattr(window, "_save", _dies_once(window._save, when))


def _failed_run(world, monkeypatch=None, kill=None):
    """A whole run that stops past familiar's mark, by a fault or by `kill`."""
    prepared = preparation.prepare(SESSION)
    opened = window.open_window(prepared)
    consumed = run_decision(prepared, opened)
    if kill is not None:
        _killed_at(monkeypatch, kill)
    with pytest.raises((window.Failed, Killed)) as raised:
        window.run_window(prepared, consumed)
    return raised.value, state.current_window(cutover_root(world))


def _targets(world):
    return {host: {target_id: world.target(host, target_id).read_bytes()
                   for target_id in transport.TARGET_PATHS} for host in HOSTS}


def _heads(world):
    return {host: transport.familiar_head(world.home(host)) for host in HOSTS}


def _modules(world):
    return {host: transport._tree_of(world.home(host) / "d/familiar/node_modules")
            for host in HOSTS}


def _tree(world, commit):
    return transport._git(world.home("titan") / "d/familiar", "rev-parse", f"{commit}^{{tree}}")


def _parents(world, commit):
    return transport._git(world.home("titan") / "d/familiar", "rev-list", "--parents", "-n", "1",
                          commit).split()[1:]


def _recovery_events(world, since):
    """Host effects in order, from the fixture tools' own observations: timer stops, service
    waits and restores, target restores and relay rollbacks, Git history changes, Codex daemon
    stops, surface TERMs and spawns, service starts, and any npm, Claude or preflight launch."""
    names = {str(world.target("titan", target_id)): target_id
             for target_id in transport.TARGET_PATHS}
    timers = {"stop": "timer-stopped", "wait": "service-inactive", "restore": "timer-restored"}
    found = []
    for call in observed(world, since=since):
        tool, host = call["tool"], call["host"]
        if tool == "quiesce-timers":
            found.append(f"{host}:{timers.get(call['args'][0], call['args'][0])}")
        elif tool == "relay-cutover" and call["args"][:1] == ["restore"]:
            found.append(f"restore:{names[_option(call, '--target')]}")
        elif tool == "installer":
            found.append(f"{call['phase']}:{call['target_id']}")
        elif tool == "git" and ("git" in call or "merge" in call):
            found.append(f"{host}:git-{'-'.join(call.get('git') or ['merge'])}")
        elif tool in ("npm", "claude", "preflight"):
            found.append(f"{host}:launched-{tool}")
        elif tool == "codex":
            found.append(f"{host}:codex-{call['args'][0]}")
        elif tool == "signal":
            found.append(f"{host}:surface-stopped")
        elif tool == "niri" and call["args"][:3] == ["msg", "action", "spawn-sh"]:
            found.append(f"{host}:surface-started")
        elif tool == "systemctl" and call["args"][1:2] == ["start"]:
            found.append(f"{host}:service-started")
    return found


def _restores(events):
    return [event for event in events if event.startswith(("restore:", "rollback:"))]


def _mutations(world):
    """Every mutating operation either host has recorded."""
    return sorted(path.parent.name for host in HOSTS
                  for path in (world.root(host) / "operations").glob("*/start.json")
                  if state.load_record(path)["mutation"])


def _operations(world):
    return {path.parent.name: state.load_record(path)["operation"] for host in HOSTS
            for path in (world.root(host) / "operations").glob("*/start.json")}


@needs_zsh
def test_recovery_requiesces_before_restore(cutover):
    """All four targets were applied, then Europa's verification failed, and a failed finish had
    already restored both hosts' timers. Recovery stops both timers again from their original
    records and waits for both services before any restore, then returns every target, familiar's
    source and both hosts' dependencies to native, offline, with timers left paused."""
    cutover.behave("europa", fail=["verify"])
    cutover.start_dropbox()
    native = (_targets(cutover), _modules(cutover))
    failed, record = _failed_run(cutover)
    assert (failed.step, failed.host) == ("target-verify", "europa")
    assert record["state"] == "recovery-required"
    assert sorted(record["applied"]) == sorted(transport.TARGET_PATHS)
    merge, pre = record["familiar"]["merge"], cutover.pins["familiar_pre"]
    cutover.behave("europa", fail=[])
    for host in HOSTS:  # what a failed finish leaves: both hosts' timers restored
        restored = cutover.request(host, "timer-restore", {
            "window_id": record["id"], "record_sha256": record["timers"][host]["sha256"],
            "stopped": True})
        assert restored["status"] == "completed" and restored["result"]["restored"]
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    kept = {host: (transport._tree_of(cutover.home(host) / ".local/state/familiar"),
                   transport._tree_of(cutover.root(host) / "familiar-state")) for host in HOSTS}
    mark = len(cutover.lines("observed"))

    result = recovery.restore_window(record)
    events = _recovery_events(cutover, mark)
    assert events.index("europa:service-inactive") < events.index("restore:claude")
    first = next(index for index, event in enumerate(events) if event.startswith("rollback:"))
    assert events[:first] == [
        "titan:codex-app-server", "titan:codex-app-server", "titan:timer-stopped",
        "europa:timer-stopped", "titan:service-inactive", "europa:service-inactive"]
    assert _restores(events) == [f"{kind}:{target_id}" for target_id in
                                 reversed(list(transport.TARGET_PATHS))
                                 for kind in ("rollback", "restore")]
    assert events[first + 8:] == ["titan:git-revert"]
    # Offline and without Claude: no npm, fetch, reset, Claude or forward preflight.
    assert not any(":launched-" in event for event in events)
    restored_target_bytes, original_target_bytes = _targets(cutover), native[0]
    assert restored_target_bytes == original_target_bytes
    assert _modules(cutover) == native[1]
    revert = result["revert"]
    assert _heads(cutover) == {"titan": revert, "europa": revert}
    assert _parents(cutover, revert) == [merge] and _tree(cutover, revert) == _tree(cutover, pre)
    assert (result["class"], result["state"]) == ("restored", "recovering")
    assert {stage: result["stages"][stage] for stage in ("native-surfaces", "original-timers")} \
        == {"native-surfaces": "pending", "original-timers": "pending"}
    assert "Do not open Claude or Codex" in result["observed"] and result["next"] == ["recover"]
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "recovering"
    assert {host: record["recovery"]["timers"][host]["was_restored"] for host in HOSTS} == {
        "titan": True, "europa": True}
    assert [(entry["host"], entry["action"]) for entry in record["recovery"]["actions"]] == [
        *[("titan", "target-restore")] * 4, ("titan", "reverted"),
        ("titan", "dependency-restore"), ("europa", "dependency-restore")]
    report = window.status()
    assert report["next"] == ["recover"] and "still pending" in report["detail"]
    assert "Do not open Claude or Codex" in report["detail"]
    # No old familiar state is imported; its snapshot stays as evidence.
    assert {host: (transport._tree_of(cutover.home(host) / ".local/state/familiar"),
                   transport._tree_of(cutover.root(host) / "familiar-state"))
            for host in HOSTS} == kept
    # Source recovery ends this window: nothing merges the tip again from the recovered commit.
    again = cutover.request("titan", "familiar-merge", {
        "window_id": record["id"], "pre": pre, "tip": cutover.pins["familiar_feature_tip"]})
    assert again["status"] == "failed" and "not at PRE" in again["error"]
    assert _heads(cutover)["titan"] == revert


@needs_zsh
def test_missing_merge_record_uses_actual_parents(cutover, monkeypatch):
    """The run died after git committed the merge but before the window recorded it.
    Reconciliation finds the merge from its actual parents and blocks fresh sessions; recovery
    records it before reverting it once, stops while Europa's source has not synchronized, and
    then completes from actual state with no second revert."""
    cutover.config["sync"]["budget"] = 1.0  # nothing delivers Titan's source to Europa yet
    cutover.save()
    native = (_targets(cutover), _modules(cutover))
    root = cutover_root(cutover)
    pre, tip = cutover.pins["familiar_pre"], cutover.pins["familiar_feature_tip"]
    _, record = _failed_run(cutover, monkeypatch,
                            kill=lambda changes: "merge" in changes.get("familiar", {}))
    assert record["state"] == "applying" and "merge" not in record["familiar"]
    head = transport.familiar_head(cutover.home("titan"))
    assert _parents(cutover, head) == [pre, tip]
    # Its outcome is unrecorded: restart-surfaces reconciles first; sessions stay closed.
    report = window.status()
    assert report["next"] == ["restart-surfaces"] and "Do not open Claude or Codex" in report[
        "detail"]

    report = recovery.reconcile_window(record)
    assert (report["class"], report["next"]) == ("recovery-required", ["recover"])
    assert report["familiar"]["class"] == "merged" and report["familiar"]["merge"] == head
    assert report["familiar"]["discovered"] is True
    assert "Do not open Claude or Codex" in report["observed"]
    record = state.current_window(root)
    assert record["state"] == "recovery-required"
    assert record["failure"]["status"] == "unverified"

    # History nobody recorded stops recovery for inspection, before any Git write.
    familiar = cutover.home("titan") / "d/familiar"
    transport._commit_on(familiar, "later.txt", "a commit after the merge\n")
    with pytest.raises(window.Failed) as raised:
        recovery.restore_window(record)
    failed = raised.value
    assert (failed.step, failed.status) == ("familiar-reconcile", "blocked")
    assert "stopped pending inspection" in failed.observed
    assert state.current_window(root)["state"] == "inspection-required"
    assert [call for call in observed(cutover, "git") if "git" in call] == []
    transport._git(familiar, "reset", "-q", "--hard", head)  # the operator's inspection
    # The revert commits, then recovery dies before recording it.
    monkeypatch.setattr(recovery, "_save", _dies_once(recovery._save, lambda changes: (
        (changes.get("recovery") or {}).get("familiar") or {}).get("revert")))
    with pytest.raises(Killed):
        recovery.restore_window(state.current_window(root))
    record = state.current_window(root)
    assert "revert" not in record["recovery"]["familiar"]
    reverted = transport.familiar_head(cutover.home("titan"))
    assert _parents(cutover, reverted) == [head]

    with pytest.raises(window.Failed) as raised:
        recovery.restore_window(record)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("dependency-restore", "europa", "failed")
    assert "did not reach" in failed.error and failed.next_command == ["recover"]
    assert "Do not open Claude or Codex" in failed.observed
    record = state.current_window(root)
    assert record["state"] == "recovering"
    recovered = record["recovery"]["familiar"]
    assert (recovered["merge"], recovered["discovered"]) == (head, True)
    revert = recovered["revert"]
    assert revert == reverted and recovered["action"] == "none"  # adopted, never reverted again
    assert _parents(cutover, revert) == [head] and _tree(cutover, revert) == _tree(cutover, pre)
    assert _heads(cutover) == {"titan": revert, "europa": pre}

    cutover.start_dropbox()
    mark = len(cutover.lines("observed"))
    result = recovery.restore_window(record)
    assert result["class"] == "restored" and result["revert"] == revert
    assert _heads(cutover) == {"titan": revert, "europa": revert}
    assert not any("git-" in event for event in _recovery_events(cutover, mark))
    assert [call["git"] for call in observed(cutover, "git") if "git" in call] == [["revert"]]
    assert (_targets(cutover), _modules(cutover)) == native
    record = state.current_window(root)
    assert record["recovery"]["actions"] == []  # its one revert was found, not recorded, here
    assert [entry["step"] for entry in record["recovery"]["failures"]] == [
        "familiar-reconcile", "dependency-restore"]


def _recover_decision(world, record, response="yes"):
    """This recovery's desktop decision, as recover takes it at its start: the desktop-only
    preview's subject, the operator's terminal answer consumed and its subject bound."""
    offered = surfaces.preview(record, surfaces.RECOVER_ACTION)
    consumed = state.consume_decision(
        record, _tty(record, surfaces.RECOVER_ACTION, offered["attempt_id"], offered["subject"],
                     response), kind="desktop", action=surfaces.RECOVER_ACTION,
        attempt_id=offered["attempt_id"], subject_sha256=offered["sha256"])
    bound = surfaces.bind(state.current_window(cutover_root(world)), consumed,
                          offered["subject"])
    return bound, consumed


@needs_zsh
def test_recovery_works_after_version_hold_breach(cutover):
    """Claude moved past its reviewed evidence on both hosts after the live plan for claude
    refused, leaving only its guard retired, and Codex updated on Titan. The full recover reads
    neither that evidence nor the new version, launches no Claude, stops the Codex daemons with
    the release now installed, restores everything by its byte, Git and dependency proofs,
    restarts the surfaces from a desktop-only preview and restores the original timers."""
    cutover.behave("titan", installer={"live:claude": "plan-fail"})
    cutover.start_dropbox()
    native = (_targets(cutover), _modules(cutover))
    failed, record = _failed_run(cutover)
    assert (failed.step, failed.host) == ("target-apply", "titan")
    assert [entry["target_id"] for entry in state.read_ledger(record)] == ["claude"]
    assert "applied" not in record
    cutover.reload()
    cutover.behave("titan", installer={})
    cutover.move_claude()  # the hold breach: a new version, the evidence left behind
    codex = cutover.move_codex()
    for host in HOSTS:
        cutover.behave(host, preflight={"evidence": "fail"})
    mark, before = len(cutover.lines("observed")), _operations(cutover)
    # The run's consent never covers recovery's restarts.
    run = state.load_record(Path(record["directory"]) / "decisions" / f"{window.RUN_ATTEMPT}.json")
    with pytest.raises(window.Failed, match="earlier run's or retry's consent") as raised:
        recovery.recover_window(record, run)
    assert raised.value.observed == "nothing was changed" and _operations(cutover) == before
    record, consumed = _recover_decision(cutover, record)

    result = recovery.recover_window(record, consumed)
    assert result["class"] == "recovered", result
    ran = {name: operation for name, operation in _operations(cutover).items()
           if name not in before}
    assert set(ran.values()) <= {
        "pending-operations", "codex-daemon-stop", "recovery-no-live", "timer-requiesce",
        "timer-wait", "target-check", "target-restore", "target-verify", "familiar-reconcile",
        "familiar-restore", "dependency-restore", "surface-preview", "surface-restart",
        "timer-restore", "service-run"}  # no inventory, inputs-check or preflight
    # The surfaces stage read only the desktop: no forward inventory or Claude diagnostics.
    assert {"surface-preview", "surface-restart", "timer-restore", "service-run"} <= set(
        ran.values())
    stops = [call for call in observed(cutover, "codex", mark)]
    assert [call["binary"] for call in stops] == [str(codex)] * 2
    assert state.current_window(cutover_root(cutover))["recovery"]["codex"] == {
        "path": str(cutover.home("titan") / ".local/bin/codex"), "real": str(codex),
        "sha256": transport._digest(codex), "prepared": False}
    assert not any(state.load_record(cutover.root(name.split("-", 1)[0]) / "operations" / name
                                     / "start.json")["payload"]["verify"]
                   for name, operation in ran.items() if operation == "target-verify")
    events = _recovery_events(cutover, mark)
    assert not any(":launched-" in event for event in events)
    # The run's own held probes show these launches are observed when they happen.
    assert {"titan:launched-claude", "europa:launched-preflight"} <= set(
        _recovery_events(cutover, 0))
    assert _restores(events) == ["restore:claude"]  # its guard images, with no relay rollback
    assert (_targets(cutover), _modules(cutover)) == native
    revert = result["window"]["recovery"]["restored"]["revert"]
    assert _heads(cutover) == {"titan": revert, "europa": revert}
    stages = [_stage(event) for event in events]
    assert stages == sorted(stages) and set(stages) == {1, 2, 3, 4, 5, 6}
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    assert result["state"] == "recovered" and window.status()["next"] == ["check"]


# The full recover's six stages, by the host effect each leaves.
STAGE = {"codex-app-server": 1, "timer-stopped": 2, "service-inactive": 2, "git-revert": 4,
         "surface-stopped": 5, "surface-started": 5, "timer-restored": 6, "service-started": 6}


def _stage(event):
    head, _, tail = event.partition(":")
    return 3 if head in ("restore", "rollback") else STAGE[tail]


def _signal_when(condition, signum, seconds=60.0):
    """From another thread, send signum to this process once condition holds."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            os.kill(os.getpid(), signum)
            return
        time.sleep(0.02)


@needs_zsh
def test_recovery_signal_is_retried_by_reconciliation(cutover):
    """A SIGTERM while Europa's dependency restore waits for its source cancels that operation
    explicitly. Reconciliation then finds nothing running, and the retry completes from actual
    state, repeating no guard restore, rollback, revert or dependency replacement."""
    cutover.behave("titan", installer={"live:claude-work": "apply-fail"})
    sync = {"allowed": True}
    cutover.start_dropbox(hold=lambda: sync["allowed"])
    native = (_targets(cutover), _modules(cutover))
    failed, record = _failed_run(cutover)
    assert (failed.step, failed.host) == ("target-apply", "titan")
    assert [entry["target_id"] for entry in state.read_ledger(record)] == ["claude",
                                                                            "claude-work"]
    assert list(record["applied"]) == ["claude"]  # claude-work was planned, never applied
    cutover.behave("titan", installer={})
    known = {cutover.pins["familiar_pre"], record["familiar"]["merge"]}
    sync["allowed"] = False
    waiting = lambda: any(  # noqa: E731
        call["host"] == "europa" and call["args"][:1] == ["familiar-source"]
        and call["args"][2] not in known and call["exit"] != 0
        for call in observed(cutover, "relay-cutover"))
    root, mark = cutover_root(cutover), len(cutover.lines("observed"))
    handlers = {signum: signal.getsignal(signum) for signum in hosts.INTERRUPTS}
    sender = threading.Thread(target=_signal_when, args=(waiting, signal.SIGTERM))
    sender.start()
    try:
        with pytest.raises(window.Failed) as raised:
            recovery.restore_window(record)
    finally:
        sender.join(timeout=90)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("dependency-restore", "europa",
                                                         "interrupted")
    assert "SIGTERM" in failed.error and failed.next_command == ["recover"]
    assert {signum: signal.getsignal(signum) for signum in hosts.INTERRUPTS} == handlers
    record = state.current_window(root)
    assert record["state"] == "recovering"
    assert record["recovery"]["failure"]["status"] == "interrupted"
    # The remote restore was cancelled explicitly, before it changed Europa's dependencies.
    restores = [name for name, operation in _operations(cutover).items()
                if operation == "dependency-restore" and name.startswith("europa-")]
    assert len(restores) == 1
    directory = cutover.root("europa") / "operations" / restores[0]
    assert (directory / "cancel.json").is_file()
    assert state.load_record(directory / "done.json")["response"]["status"] == "cancelled"
    assert "relay/package.json" in _modules(cutover)["europa"]
    titan = cutover.home("titan") / "d/familiar/node_modules"
    assert _modules(cutover)["titan"] == native[1]["titan"]
    untouched = os.stat(titan).st_ctime_ns, os.stat(titan).st_ino

    report = recovery.reconcile_window(record)
    assert (report["class"], report["blockers"], report["next"]) == ("recovering", [],
                                                                     ["recover"])
    assert "Do not open Claude or Codex" in report["observed"]
    sync["allowed"] = True
    result = recovery.restore_window(state.current_window(root))
    assert result["class"] == "restored"
    events = _recovery_events(cutover, mark)
    assert _restores(events) == ["restore:claude-work", "rollback:claude", "restore:claude"]
    assert [event for event in events if "git-" in event] == ["titan:git-revert"]
    assert (os.stat(titan).st_ctime_ns, os.stat(titan).st_ino) == untouched
    assert (_targets(cutover), _modules(cutover)) == native
    record = state.current_window(root)
    assert [(entry["host"], entry["action"]) for entry in record["recovery"]["actions"]] == [
        ("titan", "target-restore"), ("titan", "target-restore"), ("titan", "reverted"),
        ("titan", "dependency-restore"), ("europa", "dependency-restore")]


def _unsettled_wait(world, record, *, kill_owner):
    """One of this window's own operations left unfinished on Europa: a timer wait still
    running, or one whose owner was killed while its recorded child still runs."""
    world.behave("europa", timers={"wait": "latch"})
    mark = len(world.lines("observed"))
    operation_id, client = hosts.start_request("europa", "live", "timer-wait", {
        "window_id": record["id"], "record_sha256": record["timers"]["europa"]["sha256"]},
        timeout=60)
    transport._until(lambda: any(call["host"] == "europa" and call["args"][:1] == ["wait"]
                                 for call in observed(world, "quiesce-timers", mark)))
    hosts._abandon(client)  # closing the client is not cancellation: the wait keeps running
    directory = world.root("europa") / "operations" / operation_id
    if kill_owner:
        owner = state.load_record(directory / "start.json")["owner"]
        os.kill(owner["pid"], signal.SIGKILL)
        transport._until(lambda: transport._gone(owner["pid"], owner["start_time"]))
    return operation_id, directory


def _settle_wait(world, directory, killed):
    """Release the fixture wait and let its child, or the whole operation, finish."""
    Path(world.config["latch"]).touch()
    if killed:
        for child in state.load_record(directory / "children.json")["children"]:
            transport._until(lambda: transport._gone(child["pid"], child["start_time"]))
    else:
        transport._until(lambda: (directory / "done.json").exists())


@needs_zsh
@pytest.mark.parametrize("unsettled", [None, "running", "owner-lost"])
def test_reconcile_promotes_only_a_verified_migration(cutover, monkeypatch, unsettled):
    """The run died writing its verified checkpoint. Reconciliation proves the migration from
    actual state on both hosts, reading only, and only then names the surface retry. Beside one
    of this window's own operations still running, or whose owner died while its child runs, it
    never promotes: it cancels nothing, requires recovery and names the complete command."""
    cutover.start_dropbox()
    _, record = _failed_run(cutover, monkeypatch, kill=lambda changes: changes.get(
        "state") == "migrated-surfaces-pending")
    assert record["state"] == "applying" and "verified" not in record
    assert "failure" not in record and len(record["applied"]) == 4
    # Status alone never promotes: it names restart-surfaces, which reconciles first, and
    # keeps sessions closed until the migration is verified or recovered.
    report = window.status()
    assert report["next"] == ["restart-surfaces"] and "Do not open Claude or Codex" in report[
        "detail"]
    assert "restart-surfaces reconciles actual state first" in report["detail"]
    if unsettled is not None:
        operation_id, directory = _unsettled_wait(cutover, record,
                                                  kill_owner=unsettled == "owner-lost")
    mark, mutations = len(cutover.lines("observed")), _mutations(cutover)
    try:
        report = recovery.reconcile_window(record)
    finally:
        if unsettled is not None:
            cancelled = (directory / "cancel.json").exists()
            _settle_wait(cutover, directory, unsettled == "owner-lost")
    if unsettled is not None:
        following = ["restart-surfaces"] if unsettled == "running" else ["recover"]
        assert not cancelled  # reconciliation cancelled nothing
        assert (report["class"], report["next"]) == ("recovery-required", following)
        assert any(operation_id in blocker and unsettled in blocker
                   for blocker in report["blockers"])
        assert operation_id in report["observed"]
        assert cli.command_line(["recover"]) in report["observed"]
        assert "Do not open Claude or Codex" in report["observed"]
        record = state.current_window(cutover_root(cutover))
        assert record["state"] == "recovery-required" and "verified" not in record
        assert record["failure"]["status"] == "unsettled"
        assert _mutations(cutover) == mutations
        assert window.status()["next"] == following
        if unsettled == "owner-lost":
            # Its recorded child is gone but its owner never recorded completion: only recover's
            # cancel settles it, so reconciling again changes nothing.
            again = recovery.reconcile_window(record)
            assert (again["class"], again["next"]) == ("recovery-required", ["recover"])
            assert state.current_window(cutover_root(cutover))["failure"]["status"] == "unsettled"
            return
        # Settled, the same window reconciles again from restart-surfaces, which promotes the
        # verified migration and restarts the surfaces under the operator's terminal answer.
        # No controller could prove its row before the promotion, so no agent's session decision
        # is taken for it.
        preview = _cli(cutover, monkeypatch, ["restart-surfaces", "--preview"])
        assert preview.code == 0, preview.stdout
        assert "not yet verified from actual state" in preview.stdout
        decision = _decision_from_preview(cutover, record, preview, "restart.json")
        refused = _cli(cutover, monkeypatch, ["restart-surfaces", "--decision-file", decision])
        assert refused.code == 1 and "step: controller-check" in refused.stdout
        assert state.current_window(cutover_root(cutover))["state"] == "recovery-required"
        result = _cli(cutover, monkeypatch, ["restart-surfaces"], answer=b"yes\n")
        assert result.code == 0, result.stdout
        record = state.current_window(cutover_root(cutover))
        assert record["state"] == "ready-for-smokes" and record["verified"]["reconciled"]
        assert [entry["status"] for entry in record["reconciled"]] == ["unsettled"]
        assert "failure" not in record
        return
    assert (report["class"], report["next"]) == ("verified", ["restart-surfaces"])
    record = state.current_window(cutover_root(cutover))
    assert record["state"] == "migrated-surfaces-pending"
    assert record["verified"]["reconciled"] is True and set(record["verified"]["hosts"]) == {
        "titan", "europa"}
    assert record["familiar"]["merge"] == transport.familiar_head(cutover.home("titan"))
    assert _recovery_events(cutover, mark) == [] and _mutations(cutover) == mutations
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    assert window.status()["next"] == ["restart-surfaces"]


@needs_zsh
def test_reconcile_unverified_run_blocks_fresh_sessions(cutover, monkeypatch, capsys):
    """The run died after Titan applied codex but before the window recorded it. With Europa
    unreachable its operations are unknown, so reconciliation cannot verify the migration: it
    requires recovery, blocks fresh sessions and names the complete recover command. A remote
    operation still running blocks every recovery mutation; once it finishes, recovery restores
    codex from its unrecorded apply."""
    cutover.start_dropbox()
    native = (_targets(cutover), _modules(cutover))
    root = cutover_root(cutover)
    _, record = _failed_run(cutover, monkeypatch,
                            kill=lambda changes: "codex" in changes.get("applied", {}))
    assert record["state"] == "applying" and sorted(record["applied"]) == ["claude",
                                                                           "claude-work"]
    assert [entry["target_id"] for entry in state.read_ledger(record)] == [
        "claude", "claude-work", "codex"]
    cutover.config["unreachable"] = True
    cutover.save()
    report = recovery.reconcile_window(record)
    assert (report["class"], report["next"]) == ("recovery-required", ["restart-surfaces"])
    assert any(blocker.startswith("europa:") for blocker in report["blockers"])
    record = state.current_window(root)
    assert record["state"] == "recovery-required" and "verified" not in record
    assert record["failure"]["status"] == "unsettled" and "europa" in record["failure"]["error"]
    assert window.status()["next"] == ["restart-surfaces"]
    cutover.config["unreachable"] = False
    cutover.save()
    # Settled now, it reconciles again (no mutation was taken): codex-work was never applied,
    # so the migration is unverified and only recover remains.
    report = recovery.reconcile_window(record)
    assert (report["class"], report["next"]) == ("recovery-required", ["recover"])
    record = state.current_window(root)
    assert record["failure"]["status"] == "unverified" and "codex-work" in record["failure"][
        "error"]
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert cli.command_line(["recover"]) in out and "Do not open Claude or Codex" in out

    # A remote operation still running blocks every recovery mutation until it finishes.
    latch = cutover.tmp / "latch"
    operation_id, client = hosts.start_request(
        "europa", "live", "fixture-step", {"latch": str(latch), "seconds": 60}, timeout=60)
    try:
        transport._until(lambda: cutover.lines("pids"))
        mutations = _mutations(cutover)
        with pytest.raises(window.Failed) as raised:
            recovery.restore_window(record)
        assert raised.value.status == "unsettled" and raised.value.next_command == ["status"]
        assert any(operation_id in blocker and "running" in blocker
                   for blocker in raised.value.blockers)
        assert _mutations(cutover) == mutations
        latch.touch()
        transport._until(lambda: (cutover.root("europa") / "operations" / operation_id
                                  / "done.json").exists())
    finally:
        latch.touch()
        hosts._abandon(client)

    mark = len(cutover.lines("observed"))
    result = recovery.restore_window(state.current_window(root))
    assert result["class"] == "restored"
    assert _restores(_recovery_events(cutover, mark)) == [
        "rollback:codex", "restore:codex", "rollback:claude-work", "restore:claude-work",
        "rollback:claude", "restore:claude"]
    assert (_targets(cutover), _modules(cutover)) == native
    restored = state.current_window(root)["recovery"]["targets"]
    assert restored["codex"]["from"] == "relay-applied" and restored["codex"]["rollback"]


@needs_zsh
def test_recover_pre_merge_incomplete_abort_follows_abort_only(cutover):
    cutover.behave("europa", timers={"stop": "fail-after", "restore": "fail"})
    prepared, opened, consumed = opened_with_decision(cutover)
    with pytest.raises(window.Failed):
        window.quiesce_window(prepared, consumed)
    root = cutover_root(cutover)
    record = state.current_window(root)
    assert record["state"] == "abort-incomplete" and recovery.pre_merge(record)
    report = recovery.reconcile_window(record)
    assert (report["class"], report["next"]) == ("abort", ["recover"])
    assert state.current_window(root) == record
    cutover.behave("europa", timers={})
    before = _operations(cutover)
    result = recovery.restore_window(record)
    assert (result["class"], result["state"], result["next"]) == ("abort", "aborted", ["run"])
    assert {operation for name, operation in _operations(cutover).items()
            if name not in before} <= {"pending-operations", "timer-restore", "snapshot-abort"}
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    with pytest.raises(Stop, match="nothing to recover"):
        recovery.restore_window(state.current_window(root))


def test_service_run_wait_and_result(cutover, monkeypatch):
    """service-run starts the recorded timer's service only once this window's timers are
    restored, waits while it runs and requires success; service-check only reads and waits.
    Neither kills a service still running past its bound."""
    numbers = itertools.count(1)
    monkeypatch.setitem(hosts.TOOLS, "systemctl", cutover.config["tools"]["systemctl"])

    def run(operation, payload):
        return transport._execute("titan", operation, payload, next(numbers))

    recorded = run("timer-record", {"window_id": transport.WINDOW})["result"]
    payload = {"window_id": transport.WINDOW, "record_sha256": recorded["sha256"]}
    assert run("timer-stop", payload)["status"] == "completed"
    paused = run("service-run", payload)
    assert paused["status"] == "failed" and "paused" in paused["error"]
    assert "familiar-reap.service" not in cutover.units("titan")
    assert run("timer-restore", {**payload, "stopped": True})["status"] == "completed"

    cutover.behave("titan", service={"polls": 3})
    mark = len(cutover.lines("observed"))
    started = run("service-run", payload)
    assert started["status"] == "completed", started["error"]
    assert {key: started["result"][key] for key in (
        "service", "started", "active_state", "result", "exec_main_status")} == {
        "service": "familiar-reap.service", "started": True, "active_state": "inactive",
        "result": "success", "exec_main_status": "0"}
    calls = [call["args"][1] for call in observed(cutover, "systemctl", mark)]
    assert calls == ["start", "show", "show", "show", "show"]  # three reads while it ran
    assert cutover.units("titan")["familiar-reap.service"]["runs"] == 1
    checked = run("service-check", payload)
    assert checked["status"] == "completed" and checked["result"]["started"] is False
    assert cutover.units("titan")["familiar-reap.service"]["runs"] == 1

    cutover.behave("titan", service={"result": "exit-code", "status": 1})
    failed = run("service-run", payload)
    assert failed["status"] == "failed"
    assert "Result=exit-code" in failed["error"] and "ExecMainStatus=1" in failed["error"]
    assert run("service-check", payload)["status"] == "failed"
    cutover.behave("titan", service={"start": "fail"})
    refused = run("service-run", payload)
    assert refused["status"] == "failed" and "exited 1" in refused["error"]
    monkeypatch.setattr(restoration, "SERVICE_SECONDS", 0.2)
    cutover.behave("titan", service={"polls": 1000})
    running = run("service-run", payload)
    assert running["status"] == "failed" and "still activating" in running["error"]
    assert "nothing was killed" in running["error"]
    for response in (failed, refused, running):
        assert transport.OUTPUT_SECRET not in response["error"]


# --- familiar's surfaces: the consent-bound restart, its retry and the full recover ---------

COMMANDS = {"familiar-niri-watch": "~/d/familiar/bin/familiar-niri watch",
            "niri-desktop": "qs -d -p ~/d/familiar/integrations/niri-desktop"}
ABSENT = {"state": "explained-absent", "absence_reason": "europa runs no niri session",
          "socket": None, "surfaces": [{"name": name, "configured": [], "processes": []}
                                       for name in surfaces.SURFACES]}


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    """The fixture hosts' desktops and transport, with nothing staged: a surface restart needs
    only the recorded inventory, niri and the process table."""
    world = transport.World(tmp_path, monkeypatch)
    monkeypatch.setattr(window, "CHECKOUT", world.home("titan") / "d/hq")
    yield world
    world.close()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tty(record, action, attempt, subject, response="yes"):
    """A fixture of the operator's terminal answer to this attempt's own prompt."""
    return {"schema": 1, "kind": "desktop", "action": action, "window_id": record["id"],
            "attempt_id": attempt, "subject_sha256": sha(subject),
            "verdict": "approved" if response in cli.APPROVE else "declined",
            "source": {"type": "tty", "prompt": f"Restart these familiar surfaces ({action} "
                       f"{attempt})? Type yes:", "response": response, "answered_at": _now()}}


def _session(record, action, attempt, digest, reply="yes, restart them", verdict="approved"):
    """A fixture of an agent's record of the actual session ask and the human's reply."""
    return {"schema": 1, "kind": "desktop", "action": action, "window_id": record["id"],
            "attempt_id": attempt, "subject_sha256": digest, "verdict": verdict,
            "source": {"type": "session", "session_id": SESSION,
                       "ask": f"Restart familiar's pending surfaces on titan and europa (about "
                              f"30 s per host) for {attempt}?", "reply": reply,
                       "answered_at": _now()}}


def _pending_window(world, *, absent=()):
    """A window at its verified migration checkpoint, built from fixture records alone: the
    run's desktop subject recorded and its decision consumed, every surface still pending."""
    subject = {"action": window.RUN_ACTION,
               "hosts": {host: ABSENT if host in absent else world.desktop(host)
                         for host in HOSTS},
               "impact": window.IMPACT, "duration_seconds": window.DURATION_SECONDS}
    prepared = _fixture_prepared(world)
    opened = state.new_window(world.root("titan"), window.prepared_sha256(prepared))
    state.save_record(Path(opened["directory"]) / window.PREPARED, prepared)
    record = {**opened, "state": "migrated-surfaces-pending", "owner": window._me(),
              "attempts": [{"host": host, "step": "timer-stop", "at": _now()} for host in HOSTS],
              "surfaces": subject, "familiar": {"merge": "1" * 40},
              "verified": {"at": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(
                  timespec="seconds"), "hosts": {}}}
    state.save_record(window_file(record), record)
    consumed = state.consume_decision(
        record, _tty(record, window.RUN_ACTION, window.RUN_ATTEMPT, subject), kind="desktop",
        action=window.RUN_ACTION, attempt_id=window.RUN_ATTEMPT, subject_sha256=sha(subject))
    return record, consumed


def _retry(world, reply="yes, restart the pending surfaces"):
    """A restart-surfaces retry's decision as the CLI takes it: the subject previewed, the
    recorded session reply consumed, and its subject bound in the window."""
    root = world.root("titan")
    record = state.current_window(root)
    offered = surfaces.preview(record, surfaces.RESTART_ACTION)
    consumed = state.consume_decision(
        record, _session(record, surfaces.RESTART_ACTION, offered["attempt_id"],
                         offered["sha256"], reply),
        kind="desktop", action=surfaces.RESTART_ACTION, attempt_id=offered["attempt_id"],
        subject_sha256=offered["sha256"])
    return surfaces.bind(state.current_window(root), consumed, offered["subject"]), consumed, \
        offered


def _rechecks(monkeypatch):
    """A retry's recheck of the verified migration, recorded in place of the run's own gate,
    which the full-run tests exercise."""
    calls = []
    monkeypatch.setattr(window, "verified_migration",
                        lambda record, merge, step=None: calls.append(merge) or {})
    return calls


def _spawned(world, since=0):
    return [(host, command) for host, command, _ in transport._niri_spawns(world, since)]


def _cli(world, monkeypatch, argv, answer=None):
    """One in-process CLI invocation, its stdout and stderr together. With `answer` it has the
    operator's terminal, a pty answering once; without, it has none."""
    master = slave = None
    if answer is None:
        monkeypatch.setattr(cli, "TTY", str(world.tmp / "no-terminal"))
    else:
        master, slave = os.openpty()
        monkeypatch.setattr(cli, "TTY", os.ttyname(slave))
        os.write(master, answer)
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            code = cli.main(argv)
        terminal = _drain(master) if master is not None else ""
    finally:
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
    return SimpleNamespace(code=code, stdout=stream.getvalue(), terminal=terminal)


PREVIEWED = re.compile(r"attempt_id (\S+), subject_sha256 ([0-9a-f]{64})")


def _decision_from_preview(world, record, preview, name, **reply):
    """What an agent writes after the preview: the subject's fields and the actual session ask
    and reply, in a private decision file."""
    attempt, digest = PREVIEWED.search(preview.stdout).groups()
    data = json.dumps(_session(record, surfaces.RESTART_ACTION, attempt, digest, **reply))
    return str(transport._stage(world.tmp, name, data.encode()))


def test_exited_pid_is_expected(desktop):
    """Titan's recorded watcher exited after the run's consent. Its restart only starts its
    recorded command; every other surface gets TERM first; the approved subject stays the
    recording the decision bound."""
    record, consumed = _pending_window(desktop)
    recorded = record["surfaces"]["hosts"]
    watcher = transport._process_of(recorded["titan"], "familiar-niri-watch")
    spec = desktop.spec("titan")
    spec["rows"] = [row for row in spec["rows"] if row["pid"] != watcher["pid"]]
    desktop.save()
    mark = len(desktop.lines("observed"))

    result = surfaces.restart_surfaces(record, consumed)
    assert result["state"] == "ready-for-smokes"
    termed = [("titan", "niri-desktop"), ("europa", "familiar-niri-watch"),
              ("europa", "niri-desktop")]
    assert transport._term_signals(desktop, mark) == [
        (host, transport._process_of(recorded[host], name)["pid"]) for host, name in termed]
    assert transport._niri_spawns(desktop, mark) == [
        (host, COMMANDS[name], recorded[host]["socket"]) for host in HOSTS
        for name in surfaces.SURFACES]
    current = state.current_window(desktop.root("titan"))
    done = current["desktop"]["phases"]["forward"]
    assert (done["titan"]["familiar-niri-watch"]["exited"],
            done["titan"]["familiar-niri-watch"]["stopped"]) == (True, None)
    for host, name in termed:
        assert done[host][name]["stopped"] == transport._process_of(recorded[host], name)
    # Each validated replacement became its surface's recorded process.
    for host in HOSTS:
        for name in surfaces.SURFACES:
            replacement = done[host][name]["replacement"]
            assert transport._process_of(current["desktop"]["hosts"][host], name) == \
                replacement == result["restarted"][host][name]
            assert replacement in [{key: row[key] for key in ("pid", "start_time", "argv")}
                                   for row in desktop.surface_rows(host)]
    # The decision's subject is the recording it approved; the exit changed neither.
    [attempt] = current["desktop"]["attempts"]
    assert (attempt["attempt_id"], attempt["outcome"]) == (window.RUN_ATTEMPT, "complete")
    assert attempt["subject"] == record["surfaces"]
    assert sha(attempt["subject"]) == consumed["subject_sha256"]
    # The run's one decision authorized its one restart.
    with pytest.raises(window.Failed) as raised:
        surfaces.restart_surfaces(current, consumed)
    assert raised.value.status == "refused" and "verified migration" in raised.value.error
    report = window.status()
    assert report["next"] == ["record-smoke", "--observe", "titan"]
    assert "restarted familiar's surfaces" in report["detail"]


def test_explained_absence_is_never_started(desktop):
    record, consumed = _pending_window(desktop, absent=("europa",))
    rows = desktop.on_disk("europa")["rows"]
    mark = len(desktop.lines("observed"))
    result = surfaces.restart_surfaces(record, consumed)
    assert result["state"] == "ready-for-smokes"
    assert {host for host, _ in transport._term_signals(desktop, mark)} == {"titan"}
    assert {host for host, _ in _spawned(desktop, mark)} == {"titan"}
    assert desktop.lines("ssh_log") == []  # nothing even asked Europa
    assert desktop.on_disk("europa")["rows"] == rows and result["restarted"]["europa"] == {}
    # A retry or recovery offers nothing there either.
    assert surfaces.pending(result["window"], surfaces.RECOVERY) == {
        "titan": list(surfaces.SURFACES), "europa": []}


def test_partial_restart_retry(desktop, monkeypatch):
    """Europa's panel spawn fails during the run's restart. Only that surface stays pending: the
    migration needs no recovery, and a retry with a fresh decision rechecks the migration and
    starts only the missing surface."""
    record, consumed = _pending_window(desktop)
    recorded = record["surfaces"]["hosts"]
    desktop.behave("europa", spawn={"niri-desktop": "fail"})
    with pytest.raises(window.Failed) as raised:
        surfaces.restart_surfaces(record, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("surface-restart", "europa", "failed")
    assert "migrated, surfaces pending" in failed.observed
    assert "pending: europa niri-desktop" in failed.observed
    assert "Do not open Claude or Codex" not in failed.observed
    assert failed.next_command == ["restart-surfaces"]
    current = state.current_window(desktop.root("titan"))
    assert current["state"] == "migrated-surfaces-pending"
    done = current["desktop"]["phases"]["forward"]
    assert {host: sorted(names) for host, names in done.items()} == {
        "titan": sorted(surfaces.SURFACES), "europa": ["familiar-niri-watch"]}
    assert current["desktop"]["failure"]["step"] == "surface-restart"
    report = window.status()
    assert report["next"] == ["restart-surfaces"]
    assert "pending: europa niri-desktop" in report["detail"]
    assert "Do not open Claude or Codex" not in report["detail"]
    # The run's decision is spent: a retry needs its own.
    with pytest.raises(window.Failed, match="run's one restart"):
        surfaces.restart_surfaces(current, consumed)

    desktop.reload()
    desktop.behave("europa", spawn={})
    checks = _rechecks(monkeypatch)
    current, retry, offered = _retry(desktop)
    # The retry's subject is the recording with the replacements already made, asking only
    # for the surface still missing.
    assert offered["attempt_id"] == "restart-1"
    assert offered["subject"]["restart"] == {"titan": [], "europa": ["niri-desktop"]}
    assert offered["subject"]["hosts"] == current["desktop"]["hosts"]
    assert offered["observed"].keys() == {"europa"}
    mark = len(desktop.lines("observed"))
    result = surfaces.restart_surfaces(current, retry)
    assert checks == ["1" * 40]  # the verified migration, rechecked before any desktop
    assert result["state"] == "ready-for-smokes"
    # Its recorded panel had exited (TERM went out before the failed spawn): it only starts.
    assert transport._term_signals(desktop, mark) == []
    assert transport._niri_spawns(desktop, mark) == [
        ("europa", COMMANDS["niri-desktop"], recorded["europa"]["socket"])]
    final = state.current_window(desktop.root("titan"))
    assert [(entry["attempt_id"], entry["outcome"]) for entry in final["desktop"]["attempts"]] \
        == [(window.RUN_ATTEMPT, "stopped"), ("restart-1", "complete")]
    assert final["desktop"]["phases"]["forward"]["europa"]["niri-desktop"]["exited"] is True
    assert window.status()["next"] == ["record-smoke", "--observe", "titan"]


def test_restart_signal_keeps_surfaces_pending(desktop, monkeypatch):
    """A SIGTERM while Europa starts its watcher cancels that operation explicitly. The
    operation still journals the replacement it started, the window keeps only the surfaces
    pending, and the retry adopts that replacement instead of starting it twice."""
    record, consumed = _pending_window(desktop)
    recorded = record["surfaces"]["hosts"]
    desktop.behave("europa", spawn={"familiar-niri": "latch"})
    operations = desktop.root("europa") / "operations"
    mark = len(desktop.lines("observed"))

    def interrupt():
        transport._until(lambda: ("europa", COMMANDS["familiar-niri-watch"]) in _spawned(
            desktop, mark), seconds=60)
        os.kill(os.getpid(), signal.SIGTERM)
        transport._until(lambda: list(operations.glob("*/cancel.json")), seconds=60)
        Path(desktop.config["latch"]).touch()

    handlers = {signum: signal.getsignal(signum) for signum in hosts.INTERRUPTS}
    sender = threading.Thread(target=interrupt)
    sender.start()
    try:
        with pytest.raises(window.Failed) as raised:
            surfaces.restart_surfaces(record, consumed)
    finally:
        Path(desktop.config["latch"]).touch()
        sender.join(timeout=90)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("surface-restart", "europa",
                                                         "interrupted")
    assert "SIGTERM" in failed.error and "migrated, surfaces pending" in failed.observed
    assert "Do not open Claude or Codex" not in failed.observed
    assert {signum: signal.getsignal(signum) for signum in hosts.INTERRUPTS} == handlers
    current = state.current_window(desktop.root("titan"))
    assert current["state"] == "migrated-surfaces-pending"
    assert set(current["desktop"]["phases"]["forward"]) == {"titan"}
    [cancel] = operations.glob("*/cancel.json")
    response = state.load_record(cancel.parent / "done.json")["response"]
    assert response["status"] == "completed"  # it finished starting before it replied
    started = response["result"]["replacement"]
    assert transport._surface_journal(desktop, "europa", record["id"])["entries"][
        "forward:familiar-niri-watch"]["replacement"] == started

    desktop.reload()
    desktop.behave("europa", spawn={})
    _rechecks(monkeypatch)
    current, retry, _ = _retry(desktop)
    mark = len(desktop.lines("observed"))
    result = surfaces.restart_surfaces(current, retry)
    assert result["state"] == "ready-for-smokes"
    adopted = state.current_window(desktop.root("titan"))["desktop"]["phases"]["forward"][
        "europa"]["familiar-niri-watch"]
    assert (adopted["adopted"], adopted["replacement"]) == (True, started)
    assert transport._niri_spawns(desktop, mark) == [
        ("europa", COMMANDS["niri-desktop"], recorded["europa"]["socket"])]
    assert transport._term_signals(desktop, mark) == [
        ("europa", transport._process_of(recorded["europa"], "niri-desktop")["pid"])]


def test_session_decision_required_without_tty(desktop, monkeypatch):
    """restart-surfaces without a terminal or a decision file stops with instructions before any
    change; its preview is read-only and names the decision's fields. The agent's recorded
    session reply and the operator's terminal answer are consumed as the same scoped record,
    each once; a declined, replayed, partial or unanswered reply authorizes nothing. recover is
    operator-run: no terminal, no recovery, and it takes no decision file."""
    record, _ = _pending_window(desktop)
    root = desktop.root("titan")
    _rechecks(monkeypatch)
    _prove(desktop)  # the resumed controller's first step: its session decisions need it
    record = state.current_window(root)
    operations = sorted(os.listdir(root / "operations"))

    def unchanged():
        return (window_file(record).read_bytes(),
                sorted(os.listdir(Path(record["directory"]) / "decisions")),
                desktop.on_disk("titan")["rows"], desktop.on_disk("europa")["rows"])

    before, mark = unchanged(), len(desktop.lines("observed"))
    stopped = _cli(desktop, monkeypatch, ["restart-surfaces"])
    assert stopped.code == 1 and "restart-surfaces stopped" in stopped.stdout
    assert "--decision-file" in stopped.stdout and "restart-surfaces --preview" in stopped.stdout
    assert "observed: nothing was changed" in stopped.stdout
    assert unchanged() == before and desktop.lines("observed")[mark:] == []
    assert sorted(os.listdir(root / "operations")) == operations

    preview = _cli(desktop, monkeypatch, ["restart-surfaces", "--preview"])
    assert preview.code == 0, preview.stdout
    assert unchanged() == before and transport._term_signals(desktop) == []
    attempt, digest = PREVIEWED.search(preview.stdout).groups()
    assert attempt == "restart-1"
    assert digest == surfaces.preview(record, surfaces.RESTART_ACTION)["sha256"]
    for host in HOSTS:
        for surface in record["surfaces"]["hosts"][host]["surfaces"]:
            assert f"{surface['name']} (pid {surface['processes'][0]['pid']}" in preview.stdout
    assert preview.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["restart-surfaces", "--decision-file", cli.DECISION_PLACEHOLDER])

    # Partial or declined replies refuse before any host is touched.
    refusals = {
        "truncated.json": (b'{"schema": 1, "kind": "desktop", "action": "restart-sur',
                           "not one JSON decision record"),
        "no-reply.json": (json.dumps(_session(record, surfaces.RESTART_ACTION, attempt, digest,
                                              reply="   ")).encode(), "reply is empty"),
        "declined.json": (json.dumps(_session(record, surfaces.RESTART_ACTION, attempt, digest,
                                              reply="no, not now", verdict="declined")).encode(),
                          "declined"),
    }
    for name, (data, fragment) in refusals.items():
        path = transport._stage(desktop.tmp, name, data)
        result = _cli(desktop, monkeypatch, ["restart-surfaces", "--decision-file", str(path)])
        assert result.code == 1 and fragment in result.stdout, (name, result.stdout)
        assert transport._term_signals(desktop) == [] and transport._niri_spawns(desktop) == []
    assert sorted(os.listdir(Path(record["directory"]) / "decisions")) == [
        f"{window.RUN_ATTEMPT}.json"]

    # The agent's record of the actual ask and reply: Europa's panel fails to start.
    desktop.behave("europa", spawn={"niri-desktop": "fail"})
    path = _decision_from_preview(desktop, record, preview, "session.json")
    first = _cli(desktop, monkeypatch, ["restart-surfaces", "--decision-file", path])
    assert first.code == 1 and "migrated, surfaces pending" in first.stdout
    assert "Do not open Claude or Codex" not in first.stdout
    assert "do not change or save Claude model or effort defaults" in first.stdout
    assert f"next: {cli.command_line(['restart-surfaces'])}" in first.stdout
    assert len(transport._niri_spawns(desktop)) == 4
    # Replayed, the same file authorizes nothing: its attempt is spent, and so is its reply.
    desktop.reload()
    desktop.behave("europa", spawn={})
    replayed = _cli(desktop, monkeypatch, ["restart-surfaces", "--decision-file", path])
    assert replayed.code == 1 and "attempt_id does not match" in replayed.stdout
    moved = json.loads(Path(path).read_text())
    current = state.current_window(root)
    moved.update(attempt_id="restart-2",
                 subject_sha256=surfaces.preview(current, surfaces.RESTART_ACTION)["sha256"])
    again = transport._stage(desktop.tmp, "replayed.json", json.dumps(moved).encode())
    reused = _cli(desktop, monkeypatch, ["restart-surfaces", "--decision-file", str(again)])
    assert reused.code == 1 and "reply was already consumed by attempt restart-1" in reused.stdout
    assert len(transport._niri_spawns(desktop)) == 4

    # The operator's own terminal: an empty answer authorizes nothing; "yes" does, once.
    empty = _cli(desktop, monkeypatch, ["restart-surfaces"], answer=b"\n")
    assert empty.code == 1 and "no answer was given" in empty.stdout
    answered = _cli(desktop, monkeypatch, ["restart-surfaces"], answer=b"yes\n")
    assert answered.code == 0, answered.stdout
    # Its bounded preview asked only about the one surface still pending.
    assert "titan: nothing restarts" in answered.terminal
    assert "    niri-desktop (" in answered.terminal
    assert "familiar-niri-watch" not in answered.terminal
    assert state.current_window(root)["state"] == "ready-for-smokes"
    assert len(transport._niri_spawns(desktop)) == 5
    decisions = Path(record["directory"]) / "decisions"
    session, tty = (state.load_record(decisions / name)
                    for name in ("restart-1.json", "restart-2.json"))
    assert session.keys() == tty.keys()
    scope = ("schema", "window_id", "kind", "action", "prepared_sha256")
    assert {key: session[key] for key in scope} == {key: tty[key] for key in scope}
    assert (session["decision"]["source"]["type"], tty["decision"]["source"]["type"]) == (
        "session", "tty")

    # recover is operator-run: without a terminal it stops before any change, and no decision
    # file stands in for the operator.
    with_state(state.current_window(root), "recovery-required")
    mark = len(desktop.lines("observed"))
    refused = _cli(desktop, monkeypatch, ["recover"])
    assert refused.code == 1 and "recover is operator-run" in refused.stdout
    assert "observed: nothing was changed" in refused.stdout
    assert desktop.lines("observed")[mark:] == []
    with pytest.raises(SystemExit) as raised:
        _cli(desktop, monkeypatch, ["recover", "--decision-file", path])
    assert raised.value.code == 2


def test_unverified_migration_keeps_the_mixed_hooks_ban(desktop, monkeypatch):
    """A migration that failed before its verified checkpoint is no surface-only failure:
    restart-surfaces refuses before any ask or host, and the window keeps the ban on opening
    Claude or Codex with the complete recover command."""
    record, consumed = _pending_window(desktop)
    failure = {"step": "target-verify", "host": "europa", "status": "blocked",
               "error": "claude do not hold the sealed bytes", "log": None, "at": _now()}
    unverified = with_state({**record, "failure": failure}, "recovery-required")
    result = _cli(desktop, monkeypatch, ["restart-surfaces"], answer=b"yes\n")
    assert result.code == 1 and "desktop consent" not in result.terminal  # never asked
    assert "Do not open Claude or Codex" in result.stdout
    assert f"next: {cli.command_line(['recover'])}" in result.stdout
    assert not (desktop.root("titan") / "operations").exists()
    with pytest.raises(window.Failed) as raised:
        surfaces.restart_surfaces(unverified, consumed)
    assert raised.value.status == "refused" and raised.value.next_command == ["recover"]
    report = window.status()
    assert report["next"] == ["recover"] and "Do not open Claude or Codex" in report["detail"]
    assert state.current_window(desktop.root("titan")) == unverified


def test_pilot_true_spawn_needs_its_consent(desktop):
    """A pilot spawns only the fixed `true`, through each named host's trusted niri socket, with
    its own invocation's consumed decision for exactly that subject, once."""
    root = desktop.root("titan")
    pilot = state.new_window(root, PREPARED, mode="pilot")
    sockets = {host: desktop.desktop(host)["socket"] for host in HOSTS}
    subject = surfaces.probe_subject(pilot, sockets)
    assert subject["command"] == ["true"] and set(subject["hosts"]) == set(HOSTS)
    unconsumed = _tty(pilot, surfaces.PROBE_ACTION, "probe-1", subject)
    with pytest.raises(window.Failed, match="consumed decision"):
        surfaces.probe(pilot, unconsumed, sockets)
    other = state.consume_decision(pilot, _tty(pilot, "restart-surfaces", "probe-0", subject,
                                               response="y"),
                                   kind="desktop", action="restart-surfaces",
                                   attempt_id="probe-0", subject_sha256=sha(subject))
    with pytest.raises(window.Failed, match="consumed decision"):
        surfaces.probe(pilot, other, sockets)
    consumed = state.consume_decision(pilot, unconsumed, kind="desktop",
                                      action=surfaces.PROBE_ACTION, attempt_id="probe-1",
                                      subject_sha256=sha(subject))
    with pytest.raises(window.Failed, match="consumed decision"):  # another subject
        surfaces.probe(pilot, consumed, {"titan": sockets["titan"]})
    assert transport._niri_spawns(desktop) == []
    rows = {host: desktop.on_disk(host)["rows"] for host in HOSTS}
    result = surfaces.probe(state.current_window(root), consumed, sockets)
    assert {host: entry["acknowledged"] for host, entry in result["hosts"].items()} == {
        host: True for host in HOSTS}
    assert transport._niri_spawns(desktop) == [(host, "true", sockets[host]) for host in HOSTS]
    assert {host: desktop.on_disk(host)["rows"] for host in HOSTS} == rows
    assert transport._term_signals(desktop) == []
    [probed] = state.current_window(root)["probes"]
    assert (probed["attempt_id"], probed["subject"], set(probed["results"])) == (
        "probe-1", subject, set(HOSTS))
    with pytest.raises(window.Failed, match="already ran"):
        surfaces.probe(state.current_window(root), consumed, sockets)
    # A live window has no fixed spawn.
    with_state(state.current_window(root), "aborted")
    live = state.new_window(root, PREPARED)
    with pytest.raises(window.Failed, match="only in an open pilot"):
        surfaces.probe(live, consumed, sockets)
    assert len(transport._niri_spawns(desktop)) == 2


@needs_zsh
def test_surface_failure_is_pending(cutover, monkeypatch):
    """A whole run whose migration verified, then Europa's panel failed to start. Only the
    surfaces are pending: live hooks stay the verified ones, the handoff names the paused timers,
    the retry and safe resume rather than the mixed-hooks ban, a second run repeats nothing, and
    restart-surfaces with the agent's session decision rechecks the migration and starts only
    the missing surface."""
    cutover.start_dropbox()
    cutover.behave("europa", spawn={"niri-desktop": "fail"})
    preparation.prepare(SESSION)
    root = cutover_root(cutover)
    failed_surface_result = _cli(cutover, monkeypatch, ["run"], answer=b"yes\n")
    assert failed_surface_result.code == 1, failed_surface_result.stdout
    status = window.status()["window"]
    assert status["state"] == "migrated-surfaces-pending"
    record = state.current_window(root)
    sealed = record["sealed"]["inputs"]["hosts"]
    verified_live_hooks_before = {host: {target_id: entry["expected"]["sha256"]
                                         for target_id, entry in sealed[host].items()}
                                  for host in HOSTS}
    live_hooks_after = {host: {target_id: transport._digest(cutover.target(host, target_id))
                               for target_id in inputs.relevant(host)} for host in HOSTS}
    assert live_hooks_after == verified_live_hooks_before
    assert "Do not open Claude or Codex" not in failed_surface_result.stdout
    out = failed_surface_result.stdout
    assert "run stopped" in out and "step: surface-restart" in out and "host: europa" in out
    assert "migrated, surfaces pending" in out and "pending: europa niri-desktop" in out
    assert "familiar-reap.timer stays paused on titan and europa until finish" in out
    assert "may resume, only with the held commands printed here" in out
    prepared = recovery._prepared(record)
    assert shlex.join(smoke.resume_argv(prepared, "personal")) in out
    assert shlex.join(smoke.resume_argv(prepared, "work")) in out
    assert "do not change or save Claude model or effort defaults" in out
    assert out.splitlines()[-1] == f"  next: {cli.command_line(['restart-surfaces'])}"
    for secret in SECRETS + (transport.OUTPUT_SECRET,):
        assert secret not in out
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}

    # A second run finds the verified migration and repeats none of its writes.
    mutations = _mutations(cutover)
    again = _cli(cutover, monkeypatch, ["run"])
    assert again.code == 0, again.stdout
    assert "already verified its migration; nothing was repeated" in again.stdout
    assert "do not change or save Claude model or effort defaults" in again.stdout
    assert again.stdout.splitlines()[-1] == f"  next: {cli.command_line(['restart-surfaces'])}"
    assert _mutations(cutover) == mutations and state.current_window(root) == record

    # The agent's session decision needs the resumed controller's proof first; with it, the
    # agent previews, asks in the session and passes the recorded reply.
    cutover.reload()
    cutover.behave("europa", spawn={})
    unproven = _cli(cutover, monkeypatch, ["restart-surfaces", "--decision-file",
                                           str(cutover.tmp / "absent.json")])
    assert unproven.code == 1 and "step: controller-check" in unproven.stdout
    assert unproven.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--observe", "titan"])
    first = _cli(cutover, monkeypatch, ["status"]).stdout
    assert "first: resume the controller" in first and cli.command_line(
        ["record-smoke", "--observe", "titan"]) in first
    proving = _cli(cutover, monkeypatch, ["record-smoke", "--observe", "titan"])
    # A failed proof attempt first: the resumed controller has no row yet.
    assert proving.code == 1 and "step: controller-check" in proving.stdout
    _prove(cutover)
    record = state.current_window(root)
    preview = _cli(cutover, monkeypatch, ["restart-surfaces", "--preview"])
    assert preview.code == 0, preview.stdout
    assert "titan: nothing restarts" in preview.stdout and "    niri-desktop (" in preview.stdout
    decision = _decision_from_preview(cutover, record, preview, "restart.json")
    requests, mark = _requests(monkeypatch, cutover), len(cutover.lines("observed"))
    retried = _cli(cutover, monkeypatch, ["restart-surfaces", "--decision-file", decision])
    assert retried.code == 0, retried.stdout
    sends = [(entry["host"], entry["operation"], entry["payload"].get("verify"))
             for _, entry in _sends(requests)]
    # The invocation reads Europa's desktop for the subject the reply approved, consumes it,
    # settles its hosts, rechecks the verified migration, and only then starts the panel.
    assert sends == [
        ("europa", "surface-preview", None),
        ("titan", "pending-operations", None), ("europa", "pending-operations", None),
        ("titan", "target-verify", True), ("titan", "familiar-verify", None),
        ("europa", "target-verify", True), ("europa", "familiar-verify", None),
        ("europa", "surface-restart", None)]
    assert _spawned(cutover, mark) == [("europa", COMMANDS["niri-desktop"])]
    assert transport._term_signals(cutover, mark) == []
    record = state.current_window(root)
    assert record["state"] == "ready-for-smokes"
    assert {host: {target_id: transport._digest(cutover.target(host, target_id))
                   for target_id in inputs.relevant(host)} for host in HOSTS} == \
        verified_live_hooks_before
    # The controller is proven, so the smokes' receipts come next.
    assert retried.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--preview", "--receipt", smoke.RECEIPT_PLACEHOLDER])


@needs_zsh
def test_recover_six_stages_and_partial_timer_retry(cutover, monkeypatch):
    """All four targets were applied, then Europa's verification failed. recover, answered on the
    operator's terminal at its start, runs its six stages in order: Codex daemons and no-live,
    timers stopped again, targets, source and dependencies, the surfaces restarted with this
    recovery's own consent, then the original timers and their service. Europa's timer restore
    fails once after Titan's succeeded; the next recover stops Titan's timer again before
    anything else and completes without restarting any surface again."""
    cutover.behave("europa", fail=["verify"])
    cutover.start_dropbox()
    native = (_targets(cutover), _modules(cutover))
    failed, record = _failed_run(cutover)
    assert (failed.step, failed.host) == ("target-verify", "europa")
    root = cutover_root(cutover)
    cutover.reload()
    cutover.behave("europa", fail=[], timers={"restore": "fail"})
    before, mark = _operations(cutover), len(cutover.lines("observed"))

    first = _cli(cutover, monkeypatch, ["recover"], answer=b"yes\n")
    assert first.code == 1, first.stdout
    assert "recover stopped" in first.stdout and "step: timer-restore" in first.stdout
    assert "host: europa" in first.stdout and "Do not open Claude or Codex" in first.stdout
    assert first.stdout.splitlines()[-1] == f"  next: {cli.command_line(['recover'])}"
    # The desktop-only preview the operator approved named every surface it restarts.
    assert surfaces.RECOVERY_IMPACT in first.terminal
    for host in HOSTS:
        for surface in record["surfaces"]["hosts"][host]["surfaces"]:
            assert f"pid {surface['processes'][0]['pid']}" in first.terminal
    events = _recovery_events(cutover, mark)
    stages = [_stage(event) for event in events]
    assert stages == sorted(stages) and set(stages) == {1, 2, 3, 4, 5, 6}
    assert [event for event in events if _stage(event) == 5] == [
        f"{host}:surface-{kind}" for host in HOSTS for _ in surfaces.SURFACES
        for kind in ("stopped", "started")]
    assert [event for event in events if _stage(event) == 6] == [
        "titan:timer-restored", "europa:timer-restored"]
    assert not any(":launched-" in event for event in events)
    ran = {_operations(cutover)[name] for name in set(_operations(cutover)) - set(before)}
    assert not ran & {"inventory", "inputs-check", "no-live"}  # desktop-only, no preflight
    record = state.current_window(root)
    assert record["state"] == "recovering"
    consumed = state.load_record(Path(record["directory"]) / "decisions" / "recover-1.json")
    assert (consumed["kind"], consumed["action"], consumed["decision"]["source"]["type"]) == (
        "desktop", "recover", "tty")
    assert {host: sorted(names) for host, names in
            record["desktop"]["phases"]["recovery"].items()} == {
        host: sorted(surfaces.SURFACES) for host in HOSTS}
    assert list(record["recovery"]["original_timers"]) == ["titan"]
    assert timers_active(cutover) == {"titan": "active", "europa": "inactive"}
    report = window.status()
    assert report["next"] == ["recover"] and "restarted familiar's surfaces" in report["detail"]
    assert "Do not open Claude or Codex" in report["detail"]

    cutover.reload()
    cutover.behave("europa", timers={})
    mark = len(cutover.lines("observed"))
    second = _cli(cutover, monkeypatch, ["recover"], answer=b"")
    assert second.code == 0, second.stdout
    assert "desktop consent" not in second.terminal  # nothing left to restart, nothing asked
    assert _recovery_events(cutover, mark) == [
        "titan:codex-app-server", "titan:codex-app-server", "titan:timer-stopped",
        "europa:timer-stopped", "titan:service-inactive", "europa:service-inactive",
        "titan:timer-restored", "europa:timer-restored", "titan:service-started",
        "europa:service-started"]
    record = state.current_window(root)
    assert record["state"] == "recovered"
    assert record["recovery"]["timers"]["titan"]["was_restored"] is True
    assert sorted(os.listdir(Path(record["directory"]) / "decisions")) == [
        "recover-1.json", f"{window.RUN_ATTEMPT}.json"]
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    assert {host: cutover.units(host)["familiar-reap.service"]["runs"] for host in HOSTS} == {
        "titan": 1, "europa": 1}
    assert (_targets(cutover), _modules(cutover)) == native
    assert "native recovery complete" in second.stdout and "fresh native sessions may start" in \
        second.stdout
    assert window.status()["next"] == ["check"]


def test_changed_context_needs_a_new_inventory_and_decision(desktop, monkeypatch):
    """Niri restarted on Titan after the run's consent, so its socket changed. The run's restart
    stops there for inspection before any signal or spawn, leaving only the surfaces pending.
    The retry's preview offers Titan's new inventory; an approval of the old recording does not
    admit it, the new decision does, and the restart then uses that inventory."""
    record, consumed = _pending_window(desktop)
    recorded = record["surfaces"]["hosts"]
    transport._restarted_niri(desktop, None)
    desktop.save()
    mark = len(desktop.lines("observed"))
    with pytest.raises(window.Failed) as raised:
        surfaces.restart_surfaces(record, consumed)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("surface-restart", "titan", "failed")
    assert "changed context" in failed.error and "socket is not the recorded one" in failed.error
    assert "migrated, surfaces pending" in failed.observed
    assert "Do not open Claude or Codex" not in failed.observed
    assert transport._term_signals(desktop, mark) == [] and _spawned(desktop, mark) == []
    current = state.current_window(desktop.root("titan"))
    assert current["state"] == "migrated-surfaces-pending"
    assert current["desktop"]["phases"] == {}

    _rechecks(monkeypatch)
    offered = surfaces.preview(current, surfaces.RESTART_ACTION)
    new = offered["subject"]["hosts"]["titan"]
    assert new["socket"].endswith("niri.wayland-1.3900900.sock")
    assert new == {**recorded["titan"], "socket": new["socket"]}
    assert offered["subject"]["hosts"]["europa"] == recorded["europa"]
    assert offered["observed"]["titan"]["changes"] == [
        "the trusted niri socket is not the recorded one"]
    stale = {**offered["subject"], "hosts": recorded}
    with pytest.raises(Stop, match="subject_sha256 does not match"):
        state.consume_decision(current, _session(current, surfaces.RESTART_ACTION,
                                                 offered["attempt_id"], sha(stale)),
                               kind="desktop", action=surfaces.RESTART_ACTION,
                               attempt_id=offered["attempt_id"], subject_sha256=offered["sha256"])
    current, retry, _ = _retry(desktop)
    result = surfaces.restart_surfaces(current, retry)
    assert result["state"] == "ready-for-smokes"
    assert transport._niri_spawns(desktop, mark) == [
        (host, COMMANDS[name], new["socket"] if host == "titan" else recorded[host]["socket"])
        for host in HOSTS for name in surfaces.SURFACES]
    final = state.current_window(desktop.root("titan"))["desktop"]["hosts"]["titan"]
    assert final["socket"] == new["socket"]


def test_recheck_drift_needs_inspection(desktop, monkeypatch):
    """A retry's recheck of the verified migration that cannot reach a host leaves only the
    surfaces pending; one that finds the migration changed restarts nothing and needs inspection
    and recover, with the ban on opening Claude or Codex."""
    record, _ = _pending_window(desktop)
    outcome = {"status": "unsettled"}

    def recheck(record, merge, step=None):
        raise window.Failed("target-verify", "europa", outcome["status"],
                            "claude do not hold the sealed bytes after waiting for "
                            "synchronization")

    monkeypatch.setattr(window, "verified_migration", recheck)
    current, retry, _ = _retry(desktop)
    mark = len(desktop.lines("observed"))
    with pytest.raises(window.Failed) as raised:
        surfaces.restart_surfaces(current, retry)
    assert "migrated, surfaces pending" in raised.value.observed
    assert raised.value.next_command == ["status"]
    assert state.current_window(desktop.root("titan"))["state"] == "migrated-surfaces-pending"

    outcome["status"] = "blocked"
    current, retry, _ = _retry(desktop, reply="yes, try the pending surfaces once more")
    with pytest.raises(window.Failed) as raised:
        surfaces.restart_surfaces(current, retry)
    failed = raised.value
    assert (failed.step, failed.host, failed.status) == ("target-verify", "europa", "blocked")
    assert "Do not open Claude or Codex until recover completes" in failed.observed
    assert failed.next_command == ["recover"]
    assert transport._term_signals(desktop, mark) == [] and _spawned(desktop, mark) == []
    assert state.current_window(desktop.root("titan"))["state"] == "inspection-required"
    report = window.status()
    assert report["next"] == ["recover"]
    assert "stopped pending inspection at target-verify on europa (blocked)" in report["detail"]


# --- safe resume, the controller's fresh row, smoke receipts and finish ----------------------

CLAUDE_PIN = transport.PINS["claude_version"]
CODEX_PIN = transport.PINS["codex_version"]
CONTROLLER_PID, CONTROLLER_START = 3996001, 400
BYPASS = ("--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust",
          "--dangerously-skip-permissions", "--yolo", "--full-auto", "never",
          "bypassPermissions", "--approve-for-me")
ALIASES = ("cl", "clw", "co", "cor", "cowor")
FULL_CLAUDE = ("start-idle", "allow-working", "attribution-denial", "needs-approval",
               "turn-done", "idle-needs-input", "projection-recovery", "normal-exit",
               "abrupt-death")
SHORT = ("start-idle", "attribution-denial", "normal-exit")
REFUSAL = ("relay-guard: refusing: the commit message names an AI co-author (Co-Authored-By: "
           "Claude); remove the attribution")


def _identity(world, host, harness):
    home = world.home(host)
    found = (inventory._resolve(home / ".local/bin/claude", home / ".local/share/claude/versions",
                                inventory.CLAUDE_FAMILY) if harness == "claude" else
             inventory._resolve(home / ".local/bin/codex",
                                home / ".codex/packages/standalone/releases",
                                inventory.CODEX_FAMILY))
    return {key: found[key] for key in ("path", "real", "sha256")}


def _fixture_prepared(world, claude=CLAUDE_PIN):
    """The prepared fields resume commands and receipts read, from the fixture hosts' own
    executables: each host's home and Claude identity, Titan's Codex, the controller's
    native session and the reviewed pins."""
    record = {host: {"home": str(world.home(host)), "claude": {
        **_identity(world, host, "claude"), "versions": {"personal": claude, "work": claude}}}
        for host in HOSTS}
    codex = {**_identity(world, "titan", "codex"), "version": CODEX_PIN}
    record["titan"]["codex"] = codex
    return {"schema": 1, "prepared_at": _now(),
            "controller": {"session_id": SESSION, "checkout": str(window.CHECKOUT),
                           "codex": codex},
            "pins": {**transport.PINS, "claude_version": claude}, "hosts": record}


def _ready_window(world, *, mode="live", prepared=None):
    """A window whose migration verified five seconds ago and whose surfaces restarted, built
    from fixture records: timers recorded and stopped on both hosts, no smoke recorded yet."""
    prepared = prepared or _fixture_prepared(world)
    opened = state.new_window(world.root("titan"), window.prepared_sha256(prepared), mode=mode)
    state.save_record(Path(opened["directory"]) / window.PREPARED, prepared)
    at = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(timespec="seconds")
    desktops = {host: world.desktop(host) for host in HOSTS}
    record = {**opened, "state": "ready-for-smokes",
              "attempts": [{"host": host, "step": "timer-stop", "at": at} for host in HOSTS],
              "timers": {host: {"sha256": "0" * 64, "recorded_at": at} for host in HOSTS},
              "surfaces": {"action": window.RUN_ACTION, "hosts": desktops,
                           "impact": window.IMPACT, "duration_seconds": window.DURATION_SECONDS},
              "familiar": {"merge": "1" * 40}, "verified": {"at": at, "hosts": {}},
              "desktop": {"hosts": desktops, "phases": {"forward": {
                  host: {surface["name"]: {"replacement": surface["processes"][0]}
                         for surface in desktops[host]["surfaces"]} for host in HOSTS}},
                  "attempts": [], "completed": {"forward": at}}}
    state.save_record(window_file(record), record)
    return record, prepared


class Registry:
    """One test's relay registry and familiar intent on the fixture hosts."""

    def __init__(self, world):
        self.world = world
        self.rows = {host: {} for host in HOSTS}
        self.dead = {host: set() for host in HOSTS}
        self.intent = {host: set() for host in HOSTS}
        for host in HOSTS:  # an empty registry and intent until a session starts
            self.flush(host)

    def put(self, host, harness, session, pid, start, cwd, state_name="idle", *,
            updated=None, dead=False, intent=True, **fields):
        row = transport.agent(harness, session, host=host, pid=pid, start=start, cwd=cwd,
                              state=state_name, updated=updated, **fields)
        self.rows[host][row["id"]] = row
        (self.dead[host].add if dead else self.dead[host].discard)(row["id"])
        (self.intent[host].add if intent else self.intent[host].discard)(session)
        self.flush(host)
        return row

    def drop(self, host, harness, session):
        self.rows[host].pop(f"{harness}:{session}", None)
        self.intent[host].discard(session)
        self.flush(host)

    def flush(self, host):
        self.world.relay(host, list(self.rows[host].values()), self.dead[host])
        self.world.intent(host, sorted(self.intent[host]))


def _controller_up(world, registry, **fields):
    """The resumed controller: a held Codex process in the personal home and its fresh row."""
    world.harness_row("titan", "codex", CONTROLLER_PID, CONTROLLER_START)
    return registry.put("titan", "codex", SESSION, CONTROLLER_PID, CONTROLLER_START,
                        str(world.home("titan")), **fields)


def _prove(world, registry=None):
    """The resumed controller up and its fresh row proven through record-smoke's own route."""
    registry = registry or Registry(world)
    _controller_up(world, registry)
    result = smoke.observe_step(state.current_window(world.root("titan")), "titan")
    assert result["controller"] is not None
    return registry


def _seen(world, host, cwd=None):
    """One recorded observation through record-smoke's own route; its evidence reference."""
    return smoke.observe_step(state.current_window(world.root("titan")), host, cwd)["ref"]


def _ms(at, seconds=0):
    return int((datetime.fromisoformat(at) + timedelta(seconds=seconds)).timestamp() * 1000)


def _receipt(record, host, harness, home, session, pid, cwd, cases, *, matrix="short",
             version=CLAUDE_PIN, human=None):
    return {"schema": 1, "window_id": record["id"], "prepared_sha256": record["prepared_sha256"],
            "host": host, "harness": harness, "home": home, "session_id": session,
            "row_id": f"{harness}:{session}", "pid": pid, "cwd": cwd,
            "versions": {"installed": version, "evidence": version}, "matrix": matrix,
            "cases": cases, "human": human or ({"trust": "approved", "permission": "approved"}
                                               if matrix == "full" else {"trust": "approved"})}


def _passed(*refs, **fields):
    return {"verdict": "passed", "evidence": list(refs), **fields}


def _denial(ref):
    return _passed(ref, outcome="refused", refusal=REFUSAL)


def _short(world, registry, record, host, harness, home, session, pid, start, *, name=None):
    """A short smoke (start, the attribution denial, exit) in its own scratch repo."""
    cwd = world.scratch(name or f"{harness}-{home}", host)
    row_harness = "claude" if harness == "claude-code" else "codex"
    world.harness_row(host, row_harness, pid, start)
    registry.put(host, harness, session, pid, start, cwd, "idle")
    started = _seen(world, host, cwd)
    registry.put(host, harness, session, pid, start, cwd, "done")
    denied = _seen(world, host, cwd)
    registry.drop(host, harness, session)
    world.drop_row(host, pid)
    exited = _seen(world, host, cwd)
    version = CLAUDE_PIN if harness == "claude-code" else CODEX_PIN
    return _receipt(record, host, harness, home, session, pid, cwd, {
        "start-idle": _passed(started), "attribution-denial": _denial(denied),
        "normal-exit": _passed(exited)}, version=version)


SESSIONS = {name: f"0199f5a1-{index:04x}-7000-8000-00000000{index:04x}"
            for index, name in enumerate(("claude", "abrupt", "work", "europa", "europa-work",
                                          "codex", "codex-work", "codex-abrupt", "other"), 1)}


def _full_claude(world, registry, record):
    """Titan's personal Claude full smoke, observed step by step as the runbook runs it."""
    cwd, sid, abrupt = world.scratch("claude-personal"), SESSIONS["claude"], SESSIONS["abrupt"]
    pid, start, second = 3997001, 800, 3997002
    world.harness_row("titan", "claude", pid, start)
    base = _ms(record["verified"]["at"], 10)
    put = functools.partial(registry.put, "titan", "claude-code", sid, pid, start, cwd)
    put("idle", updated=base)
    started = _seen(world, "titan", cwd)
    Path(cwd, "allowed.marker").touch()
    put("working", updated=base + 1000)
    working = _seen(world, "titan", cwd)
    put("done", updated=base + 2000)
    denied = _seen(world, "titan", cwd)
    put("needs-approval", updated=base + 3000)
    approval = _seen(world, "titan", cwd)
    put("done", updated=base + 4000)
    done = _seen(world, "titan", cwd)
    put("needs-input", updated=base + 4000 + 61000)
    idle = _seen(world, "titan", cwd)
    put("needs-input", updated=base + 65000, intent=False)  # intent.json moved aside
    moved = _seen(world, "titan", cwd)
    put("needs-input", updated=base + 65000)  # familiar reap recovered the projection
    recovered = _seen(world, "titan", cwd)
    registry.drop("titan", "claude-code", sid)
    world.drop_row("titan", pid)
    exited = _seen(world, "titan", cwd)
    registry.put("titan", "claude-code", abrupt, second, 802, cwd, "idle", updated=base + 70000,
                 dead=True)  # kill -9 of the second session's recorded PID
    dead = _seen(world, "titan", cwd)
    registry.drop("titan", "claude-code", abrupt)  # relay reap, then familiar reap
    gone = _seen(world, "titan", cwd)
    return _receipt(record, "titan", "claude-code", "personal", sid, pid, cwd, {
        "start-idle": _passed(started), "allow-working": _passed(working),
        "attribution-denial": _denial(denied), "needs-approval": _passed(approval),
        "turn-done": _passed(done), "idle-needs-input": _passed(idle),
        "projection-recovery": _passed(moved, recovered), "normal-exit": _passed(exited),
        "abrupt-death": _passed(dead, gone, session_id=abrupt, pid=second)}, matrix="full")


def _full_codex(world, registry, record):
    """Titan's personal Codex full smoke: Claude's cases but the idle prompt, on Codex rows."""
    cwd, sid, abrupt = (world.scratch("codex-personal"), SESSIONS["codex"],
                        SESSIONS["codex-abrupt"])
    pid, start, second = 3997101, 820, 3997102
    world.harness_row("titan", "codex", pid, start)
    base = _ms(record["verified"]["at"], 10)
    put = functools.partial(registry.put, "titan", "codex", sid, pid, start, cwd)
    put("idle", updated=base)
    started = _seen(world, "titan", cwd)
    Path(cwd, "allowed.marker").touch()
    put("working", updated=base + 1000)
    working = _seen(world, "titan", cwd)
    put("done", updated=base + 2000)
    denied = _seen(world, "titan", cwd)
    put("needs-approval", updated=base + 3000)
    approval = _seen(world, "titan", cwd)
    put("done", updated=base + 4000)
    done = _seen(world, "titan", cwd)
    put("done", updated=base + 5000, intent=False)
    moved = _seen(world, "titan", cwd)
    put("done", updated=base + 5000)
    recovered = _seen(world, "titan", cwd)
    registry.drop("titan", "codex", sid)
    world.drop_row("titan", pid)
    exited = _seen(world, "titan", cwd)
    registry.put("titan", "codex", abrupt, second, 822, cwd, "idle", updated=base + 7000,
                 dead=True)
    dead = _seen(world, "titan", cwd)
    registry.drop("titan", "codex", abrupt)
    gone = _seen(world, "titan", cwd)
    return _receipt(record, "titan", "codex", "personal", sid, pid, cwd, {
        "start-idle": _passed(started), "allow-working": _passed(working),
        "attribution-denial": _denial(denied), "needs-approval": _passed(approval),
        "turn-done": _passed(done), "projection-recovery": _passed(moved, recovered),
        "normal-exit": _passed(exited),
        "abrupt-death": _passed(dead, gone, session_id=abrupt, pid=second)},
        matrix="full", version=CODEX_PIN)


def _attestation(record, attempt, digest, reply="yes, I gave those answers myself",
                 verdict="approved", kind=None):
    """An agent's record of the actual session ask about a receipt's human verdicts and the
    human's reply."""
    return {"schema": 1, "kind": kind or smoke.KIND, "action": smoke.ACTION,
            "window_id": record["id"], "attempt_id": attempt, "subject_sha256": digest,
            "verdict": verdict, "source": {
                "type": "session", "session_id": SESSION, "reply": reply, "answered_at": _now(),
                "ask": f"Did you yourself approve this home's trust review and answer its "
                       f"permission prompt ({attempt})?"}}


def _record_receipt(world, receipt):
    current = state.current_window(world.root("titan"))
    attempt = smoke.next_attempt(current)
    consumed = state.consume_decision(current, _attestation(current, attempt, sha(receipt)),
                                      kind=smoke.KIND, action=smoke.ACTION, attempt_id=attempt,
                                      subject_sha256=sha(receipt))
    smoke.record_smoke(state.current_window(world.root("titan")), receipt, consumed)
    return consumed


def _refused(world, receipt, fragment):
    with pytest.raises(window.Failed) as raised:
        smoke.check_receipt(state.current_window(world.root("titan")), receipt)
    failed = raised.value
    assert (failed.step, failed.status) == ("receipt", "refused"), failed
    assert fragment in failed.error, (fragment, failed.error)
    return failed


def _private_file(world, name, value):
    return str(transport._stage(world.tmp, name, json.dumps(value).encode()))


def test_resume_has_no_bypass_flags(tmp_path):
    """The printed commands are concrete held argv, Zsh-quoted: the controller's Codex resume
    with its captured session, the work home's own launch for its hook review, held Claude
    launches for every home on both hosts and the smoke sessions' runbook flags. None is an
    alias, a placeholder or a bypass."""
    homes = {host: tmp_path / f"{host} home's" for host in HOSTS}
    release = homes["titan"] / ".codex/packages/standalone/releases/0.163.0-x/bin/codex"
    release.parent.mkdir(parents=True)
    release.write_text("#!/bin/sh\n")
    (homes["titan"] / ".codex-work").mkdir()
    (homes["titan"] / ".codex").mkdir(exist_ok=True)
    (homes["titan"] / ".codex-link").symlink_to(homes["titan"] / ".codex")
    claude = {host: str(homes[host] / ".local/share/claude/versions/2.1.304") for host in HOSTS}
    codex = {"path": str(homes["titan"] / ".local/bin/codex"), "real": str(release),
             "sha256": "a" * 64, "version": CODEX_PIN}
    prepared = {"controller": {"session_id": SESSION, "codex": codex},
                "pins": dict(transport.PINS),
                "hosts": {host: {"home": str(homes[host]), "claude": {
                    "path": str(homes[host] / ".local/bin/claude"), "real": claude[host],
                    "sha256": "b" * 64, "versions": {"personal": CLAUDE_PIN, "work": CLAUDE_PIN}}}
                    for host in HOSTS}}
    prepared["hosts"]["titan"]["codex"] = codex
    resume_args = smoke.resume_argv(prepared, "personal")
    assert resume_args == [
        "env", "DISABLE_UPDATES=1", f"CODEX_HOME={os.path.realpath(homes['titan'] / '.codex')}",
        str(release), "--no-daemon", "resume", SESSION]
    assert "--dangerously-bypass-approvals-and-sandbox" not in resume_args
    assert "DISABLE_UPDATES=1" in resume_args
    assert smoke.resume_argv(prepared, "work") == [
        "env", "DISABLE_UPDATES=1",
        f"CODEX_HOME={os.path.realpath(homes['titan'] / '.codex-work')}", str(release),
        "--no-daemon"]
    with pytest.raises(Stop):
        smoke.resume_argv(prepared, "europa")
    commands = smoke.commands(prepared)
    labels = [label for label, _ in commands]
    assert len(labels) == len(set(labels)) == 12
    for label, argv in commands:
        assert argv[0] == "env" and "DISABLE_UPDATES=1" in argv, label
        assert not set(argv) & set(BYPASS) and not any("<" in word for word in argv), label
        assert not set(argv) & set(ALIASES), label
        executable = next(word for word in argv[1:] if word.startswith("/"))
        assert executable in (str(release), claude["titan"], claude["europa"]), label
    by_label = dict(commands)
    assert by_label["titan Codex personal: resume the controller"] == resume_args
    for host in HOSTS:
        assert by_label[f"{host} Claude personal"] == [
            "env", "-u", "CLAUDE_CONFIG_DIR", "DISABLE_UPDATES=1", claude[host]]
        assert by_label[f"{host} Claude work"] == [
            "env", "DISABLE_UPDATES=1", f"CLAUDE_CONFIG_DIR={homes[host] / '.claude-work'}",
            claude[host]]
        for home in ("personal", "work"):
            assert by_label[f"{host} Claude {home} smoke"] == [
                *by_label[f"{host} Claude {home}"], "--permission-mode", "manual"]
    for home in ("personal", "work"):
        assert by_label[f"titan Codex {home} smoke"] == [
            *smoke.resume_argv(prepared, home)[:4], "--no-daemon", "--sandbox",
            "workspace-write", "--ask-for-approval", "on-request"]
    # Each printed line is one Zsh word list: Zsh reads back exactly the argv.
    lines = smoke.command_lines(prepared)
    printed = [line.strip() for line in lines if line.startswith("      ")]
    assert printed == [shlex.join(argv) for _, argv in commands]
    for text, (_, argv) in zip(printed, commands):
        echoed = subprocess.run([str(transport.ZSH), "-f", "-c", "print -rl -- " + text],
                                capture_output=True, text=True, check=True).stdout
        assert echoed.splitlines() == argv


def test_current_row_is_fresh(desktop, monkeypatch):
    """The first smoke step proves the controller's own row before anything else: its native
    session's root Codex row, live on Titan, held by the prepared Codex executable and updated
    since the verified migration. A missing, stale, dead, foreign or unknown row stops with the
    safe resume path and records nothing."""
    record, prepared = _ready_window(desktop)
    registry = Registry(desktop)
    missing = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "titan"])
    assert missing.code == 1 and "step: controller-check" in missing.stdout
    assert "codex:" + SESSION in missing.stdout and "no row" in missing.stdout
    assert "trust or startup blocker" in missing.stdout
    assert "not configuration edits" in missing.stdout
    assert shlex.join(smoke.resume_argv(prepared, "personal")) in missing.stdout
    assert missing.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--observe", "titan"])
    current = state.current_window(desktop.root("titan"))
    assert "controller" not in current.get("smokes", {})
    assert current["state"] == "ready-for-smokes" and window_file(record).read_bytes() != b""

    row = _controller_up(desktop, registry)
    seen = smoke.observe(current, "titan")
    observation = seen["observation"]
    assert observation == state.load_record(Path(seen["ref"]["path"]))
    smoke.check_controller(seen["window"], observation)
    verified = _ms(record["verified"]["at"])

    def stale(value):
        value["agents"][row["id"]]["updated_at"] = verified - 1000

    def dead(value):
        value["agents"][row["id"]]["liveness"] = "dead"

    def foreign(value):
        value["agents"][row["id"]]["process"]["host"] = "europa"

    def unknown(value):
        for entry in value["processes"]:
            if entry["pid"] == CONTROLLER_PID:
                entry.update(known=False, exe="/usr/bin/codex")

    def replaced(value):
        value["agents"][row["id"]]["process"]["start"] = str(CONTROLLER_START + 1)

    def worker(value):
        value["agents"][row["id"]]["scope"] = "worker"

    def other_session(value):
        value["agents"][f"codex:{SESSIONS['other']}"] = value["agents"].pop(row["id"])

    def pilot(value):
        value["mode"] = "pilot"

    for change, fragment in ((stale, "predates"), (dead, "not live"), (foreign, "europa"),
                             (unknown, "prepared Codex"), (replaced, "prepared Codex"),
                             (worker, "root"), (other_session, "no row"), (pilot, "mode")):
        changed = json.loads(json.dumps(observation))
        change(changed)
        with pytest.raises(window.Failed) as raised:
            smoke.check_controller(state.current_window(desktop.root("titan")), changed)
        assert raised.value.step == "controller-check" and fragment in raised.value.error, (
            change.__name__, raised.value.error)

    # The CLI's first observation proves it once; later observations read only their host.
    registry.put("titan", "codex", SESSION, CONTROLLER_PID, CONTROLLER_START,
                 str(desktop.home("titan")), updated=verified - 1000)
    old = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "titan"])
    assert old.code == 1 and "predates" in old.stdout
    registry.put("titan", "codex", SESSION, CONTROLLER_PID, CONTROLLER_START,
                 str(desktop.home("titan")))
    proven = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "europa"])
    assert proven.code == 0, proven.stdout
    assert f"controller: codex:{SESSION} pid {CONTROLLER_PID} on titan" in proven.stdout
    proof = state.current_window(desktop.root("titan"))["smokes"]["controller"]
    assert (proof["row_id"], proof["pid"], proof["start"]) == (
        f"codex:{SESSION}", CONTROLLER_PID, str(CONTROLLER_START))
    hosts_seen = [entry["host"] for entry in sorted(
        state.current_window(desktop.root("titan"))["smokes"]["observations"].values(),
        key=lambda entry: entry["seq"])]
    assert hosts_seen[-2:] == ["titan", "europa"]
    count = len(state.current_window(desktop.root("titan"))["smokes"]["observations"])
    again = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "europa"])
    assert again.code == 0 and "on titan, live and updated" not in again.stdout
    assert f"controller: codex:{SESSION} pid {CONTROLLER_PID} is proven" in again.stdout
    assert len(state.current_window(desktop.root("titan"))["smokes"]["observations"]) == \
        count + 1  # Europa's alone: the proof is not made again
    # The SSH route to Europa is declined: that observer check stays pending, nothing passes.
    desktop.reload()
    desktop.config["unreachable"] = True
    desktop.save()
    seen = state.current_window(desktop.root("titan"))["smokes"]["observations"]
    declined = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "europa"])
    assert declined.code == 1 and "host: europa" in declined.stdout
    assert "stays pending" in declined.stdout
    assert declined.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--observe", "europa"])
    assert state.current_window(desktop.root("titan"))["smokes"]["observations"] == seen


@needs_zsh
def test_receipt_is_bound_to_real_cases(desktop):
    """A receipt passes only on observations this window recorded for that very session:
    every required case, each case's own state, row, process, scratch repo and order, the
    prepared versions and the human's own verdicts. Each binding below refuses on its own."""
    record, prepared = _ready_window(desktop)
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    receipt = _full_claude(desktop, registry, record)
    digest = smoke.check_receipt(state.current_window(desktop.root("titan")), receipt)
    assert digest == sha(receipt)

    def variant(**changes):
        changed = json.loads(json.dumps(receipt))
        for path, value in changes.items():
            keys = path.split("__")
            target = changed
            for key in keys[:-1]:
                target = target[key]
            if value is KeyError:
                del target[keys[-1]]
            else:
                target[keys[-1]] = value
        return changed

    cases = receipt["cases"]
    other = SESSIONS["other"]
    for changed, fragment in (
            (variant(window_id="20261019T000000Z-deadbeef"), "not this live window"),
            (variant(prepared_sha256="f" * 64), "another preparation"),
            (variant(home="work"), "short"),
            (variant(host="europa", harness="codex"), "not a smoke this cutover requires"),
            (variant(session_id=other, row_id=f"claude-code:{other}"), "no row"),
            (variant(row_id=f"codex:{receipt['session_id']}"), "root row"),
            (variant(versions__installed="2.1.305 (Claude Code)"),
             "installed and evidence version"),
            (variant(cwd=desktop.scratch("elsewhere")), "cwd"),
            (variant(pid=receipt["pid"] + 9), "pid"),
            (variant(session_id=SESSION, row_id=f"claude-code:{SESSION}"), "live controller"),
            (variant(**{"cases__abrupt-death__pid": CONTROLLER_PID}), "live controller"),
            (variant(**{"cases__abrupt-death__session_id": SESSION}), "live controller"),
            (variant(**{"cases__turn-done": KeyError}), "missing: turn-done"),
            (variant(**{"cases__surprise": _passed()}), "unexpected: surprise"),
            (variant(**{"cases__needs-approval__verdict": "failed"}), "failed"),
            (variant(**{"cases__allow-working": cases["start-idle"]}), "working"),
            (variant(**{"cases__projection-recovery__evidence":
                        cases["projection-recovery"]["evidence"][::-1]}), "after"),
            (variant(**{"cases__abrupt-death__evidence":
                        cases["abrupt-death"]["evidence"][::-1]}), "dead"),
            (variant(**{"cases__normal-exit": cases["start-idle"]}), "still has its row"),
            (variant(**{"cases__attribution-denial__outcome": "not-attempted"}),
             "never attempted"),
            (variant(**{"cases__attribution-denial__outcome": "git-identity-error"}),
             "Git identity"),
            (variant(**{"cases__attribution-denial__refusal": "error: commit failed"}),
             "relay-guard: refusing"),
            (variant(human={"trust": "approved"}), "trust and permission"),
            (variant(human__permission="declined"), "declined"),
            (variant(human__permission="unanswered"), "unanswered"),
            (variant(human__permission="auto-review"), "automatic"),
            (variant(human__trust=KeyError), "trust and permission"),
            (variant(**{"cases__start-idle__evidence": [{
                "path": cases["start-idle"]["evidence"][0]["path"], "sha256": "0" * 64}]}),
             "another digest")):
        _refused(desktop, changed, fragment)

    # Evidence counts only by its recorded content, never by its name or place.
    first = cases["start-idle"]["evidence"][0]
    copy = Path(desktop.tmp, Path(first["path"]).name)
    shutil.copy2(first["path"], copy)
    _refused(desktop, variant(**{"cases__start-idle__evidence": [
        {"path": str(copy), "sha256": first["sha256"]}]}), "not an observation this window")
    original = Path(first["path"]).read_bytes()
    Path(first["path"]).write_bytes(original.replace(b'"idle"', b'"idle" '))
    _refused(desktop, receipt, "changed since it was recorded")
    Path(first["path"]).unlink()
    _refused(desktop, receipt, "missing or unreadable")
    transport._stage(Path(first["path"]).parent, Path(first["path"]).name, original)

    # A row from before the verified migration is stale; under 60 s idle is no idle prompt.
    sid, pid, cwd = receipt["session_id"], receipt["pid"], receipt["cwd"]
    desktop.harness_row("titan", "claude", pid, 800)
    put = functools.partial(registry.put, "titan", "claude-code", sid, pid, 800, cwd)
    put("idle", updated=_ms(record["verified"]["at"], -30))
    _refused(desktop, variant(**{"cases__start-idle": _passed(_seen(desktop, "titan", cwd))}),
             "predates")
    put("needs-input", updated=_ms(record["verified"]["at"], 10) + 4000 + 30000)
    _refused(desktop, variant(**{"cases__idle-needs-input":
                                 _passed(_seen(desktop, "titan", cwd))}), "60 s")
    # An unheld process is no held smoke.
    desktop.drop_row("titan", pid)
    desktop.harness_row("titan", "claude", pid, 800, held=False)
    put("idle", updated=_ms(record["verified"]["at"], 10))
    _refused(desktop, variant(**{"cases__start-idle": _passed(_seen(desktop, "titan", cwd))}),
             "held")
    desktop.drop_row("titan", pid)
    registry.drop("titan", "claude-code", sid)
    # A denial that met a Git identity error or committed cannot pass.
    for args in (("config", "--unset", "user.name"), ("config", "--unset", "user.email")):
        subprocess.run(["/usr/bin/git", "-C", cwd, *args], check=True)
    _refused(desktop, variant(**{"cases__attribution-denial": _denial(
        _seen(desktop, "titan", cwd))}), "Git identity")
    subprocess.run(["/usr/bin/git", "-C", cwd, "-c", "user.name=x", "-c", "user.email=x@x",
                    "commit", "-q", "--allow-empty", "-m", "probe"], check=True)
    _refused(desktop, variant(**{"cases__attribution-denial": _denial(
        _seen(desktop, "titan", cwd))}), "commit")

    # The receipt itself records once, with the decision that attested it.
    consumed = _record_receipt(desktop, receipt)
    stored = state.current_window(desktop.root("titan"))["smokes"]["receipts"][
        "titan/claude-code/personal"]
    assert stored["receipt"] == receipt and stored["attempt_id"] == consumed["attempt_id"]
    assert stored["decision_sha256"] == consumed["decision_sha256"]
    with pytest.raises(window.Failed, match="already recorded"):
        _record_receipt(desktop, receipt)


@needs_zsh
def test_short_receipts_cover_each_home(desktop):
    """Each work home and both Europa homes need their own short receipt: Europa's are bound to
    Europa's own observations, both Codex homes need their own human trust review, and no
    session serves two homes."""
    record, prepared = _ready_window(desktop)
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    europa = _short(desktop, registry, record, "europa", "claude-code", "personal",
                    SESSIONS["europa"], 3998001, 900)
    assert smoke.check_receipt(state.current_window(desktop.root("titan")), europa)
    _record_receipt(desktop, europa)
    titan_refs = _short(desktop, registry, record, "titan", "codex", "work",
                        SESSIONS["codex-work"], 3998101, 910)
    # Titan's observations are no evidence for Europa's other home.
    moved = {**titan_refs, "host": "europa", "harness": "claude-code",
             "row_id": f"claude-code:{SESSIONS['codex-work']}",
             "versions": {"installed": CLAUDE_PIN, "evidence": CLAUDE_PIN}}
    _refused(desktop, moved, "observed on titan")
    _refused(desktop, {**titan_refs, "versions": {"installed": CLAUDE_PIN,
                                                  "evidence": CLAUDE_PIN}},
             "installed and evidence version")
    _refused(desktop, {**titan_refs, "human": {}}, "trust")
    _refused(desktop, {**titan_refs, "human": {"trust": "approved", "permission": "approved"}},
             "trust")
    _refused(desktop, {**titan_refs, "matrix": "full"}, "short")
    _record_receipt(desktop, titan_refs)
    # The personal Codex home is not covered by the work home's review or session.
    reused = {**titan_refs, "home": "personal", "matrix": "full"}
    _refused(desktop, reused, "already used")
    with pytest.raises(window.Failed) as raised:
        smoke.validate_smokes(state.current_window(desktop.root("titan")))
    assert raised.value.status == "blocked"
    for slot in ("titan Claude personal (full)", "titan Codex personal (full)",
                 "titan Claude work (short)", "europa Claude work (short)"):
        assert slot in raised.value.error
    assert "europa Claude personal" not in raised.value.error
    assert "titan Codex work" not in raised.value.error


def test_human_attestation_is_required(desktop, monkeypatch):
    """record-smoke records a receipt only with the human's own answer about its trust and
    permission verdicts: an actual session ask and reply in a decision file, or the operator's
    terminal answer. Without either it stops with instructions; declined, unanswered, altered,
    replayed or mis-kinded answers and human fields that are not approved record nothing."""
    record, _ = _ready_window(desktop)
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    receipt = _short(desktop, registry, record, "titan", "claude-code", "work",
                     SESSIONS["work"], 3999001, 950)
    path = _private_file(desktop, "receipt.json", receipt)
    root = desktop.root("titan")

    def recorded_now():
        return state.current_window(root).get("smokes", {}).get("receipts", {})

    stopped = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", path])
    assert stopped.code == 1 and "record-smoke stopped" in stopped.stdout
    assert "--preview" in stopped.stdout and "--decision-file" in stopped.stdout
    assert "ask the user in the session" in stopped.stdout
    assert recorded_now() == {}
    assert not list((Path(record["directory"]) / "decisions").glob("smoke-*"))

    before = window_file(record).read_bytes()
    preview = _cli(desktop, monkeypatch, ["record-smoke", "--preview", "--receipt", path])
    assert preview.code == 0, preview.stdout
    assert window_file(record).read_bytes() == before
    attempt, digest = PREVIEWED.search(preview.stdout).groups()
    assert (attempt, digest) == ("smoke-1", sha(receipt))
    assert f"kind {smoke.KIND}, action {smoke.ACTION}" in preview.stdout
    assert "trust approved" in preview.stdout and "yourself" in preview.stdout
    assert preview.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--receipt", path, "--decision-file", cli.DECISION_PLACEHOLDER])

    for name, decision, fragment in (
            ("declined.json", _attestation(record, attempt, digest, reply="no, an agent did it",
                                           verdict="declined"), "declined"),
            ("empty.json", _attestation(record, attempt, digest, reply="  "), "reply is empty"),
            ("desktop.json", _attestation(record, attempt, digest, kind="desktop"),
             "kind does not match"),
            ("other.json", _attestation(record, attempt, "e" * 64), "subject_sha256")):
        result = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", path,
                                             "--decision-file", _private_file(desktop, name,
                                                                              decision)])
        assert result.code == 1 and fragment in result.stdout, (name, result.stdout)
        assert recorded_now() == {}
    with pytest.raises(SystemExit) as raised:
        _cli(desktop, monkeypatch, ["record-smoke", "--receipt", path, "--yes"])
    assert raised.value.code == 2
    with pytest.raises(SystemExit):
        _cli(desktop, monkeypatch, ["record-smoke", "--receipt", path, "--approved"])

    # Human fields that are not approved never pass, whatever the decision says.
    unanswered = {**receipt, "human": {"trust": "unanswered"}}
    other_path = _private_file(desktop, "unanswered.json", unanswered)
    result = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", other_path,
                                         "--decision-file", _private_file(
                                             desktop, "approve-unanswered.json", _attestation(
                                                 record, attempt, sha(unanswered)))])
    assert result.code == 1 and "unanswered" in result.stdout and recorded_now() == {}

    session = _private_file(desktop, "session.json", _attestation(record, attempt, digest))
    done = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", path, "--decision-file",
                                       session])
    assert done.code == 0, done.stdout
    assert "recorded titan Claude work (short)" in done.stdout
    assert "avoid cl, clw" in done.stdout
    stored = recorded_now()["titan/claude-code/work"]
    consumed = state.load_record(Path(record["directory"]) / "decisions" / "smoke-1.json")
    assert (consumed["kind"], consumed["action"], consumed["subject_sha256"]) == (
        smoke.KIND, smoke.ACTION, sha(receipt))
    assert consumed["decision"]["source"]["type"] == "session"
    assert stored["attempt_id"] == "smoke-1" and stored["receipt"] == receipt
    replayed = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", path, "--decision-file",
                                           session])
    assert replayed.code == 1 and "already recorded" in replayed.stdout

    # The operator's own terminal: "no" declines; "yes" attests once.
    europa = _short(desktop, registry, record, "europa", "claude-code", "work",
                    SESSIONS["europa-work"], 3999101, 960)
    europa_path = _private_file(desktop, "europa.json", europa)
    declined = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", europa_path],
                    answer=b"no\n")
    assert declined.code == 1 and "declined" in declined.stdout
    answered = _cli(desktop, monkeypatch, ["record-smoke", "--receipt", europa_path],
                    answer=b"yes\n")
    assert answered.code == 0, answered.stdout
    assert "trust approved" in answered.terminal and "yourself" in answered.terminal
    assert SESSIONS["europa-work"] in answered.terminal
    tty = state.load_record(Path(record["directory"]) / "decisions" / "smoke-2.json")
    assert tty["decision"]["source"]["type"] == "tty" and tty["kind"] == smoke.KIND
    assert set(recorded_now()) == {"titan/claude-code/work", "europa/claude-code/work"}


def test_handoff_freezes_claude_picks(desktop, monkeypatch):
    """From the verified migration until finish, every handoff names both hosts and both
    homes, freezes Claude's model and effort defaults, and allows only the printed held
    launches, naming cl and clw. Preparation and a parked wait carry no such restriction."""
    root = desktop.root("titan")
    prepared = _fixture_prepared(desktop)

    def frozen(text, current):
        assert "titan (Claude personal and work, Codex personal and work)" in text
        assert "europa (Claude personal and work)" in text
        assert "do not change or save Claude model or effort defaults" in text
        assert "/model or /effort" in text
        assert "avoid cl, clw" in text and "unheld Claude or IDE clients" in text
        assert "update or install commands" in text
        assert "familiar-reap.timer stays paused on titan and europa until finish" in text
        for _, argv in smoke.commands(recovery._prepared(current)):
            assert shlex.join(argv) in text

    record, _ = _pending_window(desktop)
    status = _cli(desktop, monkeypatch, ["status"])
    assert status.code == 0, status.stdout
    frozen(status.stdout, record)
    assert "Do not open Claude or Codex" not in status.stdout
    assert status.stdout.splitlines()[-1] == "  next: " + cli.command_line(["restart-surfaces"])
    again = _cli(desktop, monkeypatch, ["run"])
    assert again.code == 0, again.stdout
    assert "already verified its migration" in again.stdout
    frozen(again.stdout, record)
    # Smokes and finish wait for the surfaces.
    # The handoff's first step is the controller's proof, which alone runs before the surfaces.
    lines = status.stdout.splitlines()
    assert lines[lines.index(next(line for line in lines if line.startswith("  observed:"))) + 1] \
        .startswith("  first: resume the controller with its held command below, then prove its "
                    "fresh row with " + cli.command_line(["record-smoke", "--observe", "titan"]))
    assert "restart-surfaces --decision-file" in status.stdout
    early = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "europa"])
    assert early.code == 1 and "surfaces" in early.stdout
    frozen(early.stdout, record)
    assert early.stdout.splitlines()[-1] == "  next: " + cli.command_line(["restart-surfaces"])
    scratch = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "titan", "--cwd",
                                          str(desktop.tmp)])
    assert scratch.code == 1 and "only the controller's proof" in scratch.stdout
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    proven = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "titan"])
    assert proven.code == 0 and f"controller: codex:{SESSION}" in proven.stdout
    assert state.current_window(root)["state"] == "migrated-surfaces-pending"
    assert f"controller: codex:{SESSION} pid {CONTROLLER_PID} is proven" in _cli(
        desktop, monkeypatch, ["status"]).stdout
    unfinished = _cli(desktop, monkeypatch, ["finish"])
    assert unfinished.code == 1 and "surfaces" in unfinished.stdout
    assert unfinished.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["restart-surfaces"])
    with_state(state.current_window(root), "recovered")

    ready, _ = _ready_window(desktop)
    status = _cli(desktop, monkeypatch, ["status"])
    frozen(status.stdout, ready)
    assert status.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--observe", "titan"])
    # The window's end releases it; a parked preparation never had it.
    with_state(state.current_window(root), "complete")
    state.save_record(root / window.PREPARED, prepared)
    parked = _cli(desktop, monkeypatch, ["status"])
    assert parked.code == 0, parked.stdout
    assert "avoid cl" not in parked.stdout and "model or effort" not in parked.stdout
    assert "ordinary Claude and Codex use stays allowed, including cl, clw" in parked.stdout


def test_finish_refuses_incomplete_receipts(desktop, monkeypatch):
    """finish needs every required receipt before it contacts any host; a pilot window's
    receipts never finish anything, and an unproven hold sends finish to full recovery."""
    record, _ = _ready_window(desktop)
    requests = _requests(monkeypatch, desktop)
    before = window_file(record).read_bytes()
    result = _cli(desktop, monkeypatch, ["finish"])
    finish_called_with_incomplete_receipts = any(
        entry["operation"] in ("timer-restore", "service-run") for _, entry in _sends(requests))
    assert not finish_called_with_incomplete_receipts
    assert requests == [] and window_file(record).read_bytes() == before
    assert result.code == 1 and "6 required smoke receipt(s) are missing" in result.stdout
    assert "familiar-reap.timer stays paused on titan and europa" in result.stdout
    assert result.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--observe", "titan"])
    with_state(state.current_window(desktop.root("titan")), "recovered")

    pilot, _ = _ready_window(desktop, mode="pilot")
    with pytest.raises(window.Failed, match="pilot"):
        finish.finish_window(pilot)
    with_state(state.current_window(desktop.root("titan")), "recovered")

    # Claude moved after the bootstrap: finish stops before any timer, for full recovery.
    ready, _ = _ready_window(desktop)
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    checked = []
    monkeypatch.setattr(smoke, "validate_smokes", lambda current: checked.append(current["id"]))
    desktop.move_claude()
    with pytest.raises(window.Failed) as raised:
        finish.finish_window(state.current_window(desktop.root("titan")))
    failed = raised.value
    assert (failed.step, failed.status) == ("hold", "breach") and checked == [ready["id"]]
    assert failed.next_command == ["recover"]
    assert not any(entry["operation"] in ("timer-restore", "service-run", "target-verify")
                   for _, entry in _sends(requests))
    current = state.current_window(desktop.root("titan"))
    assert current["state"] == "recovery-required" and not recovery.reconcilable(current)


def test_smoke_hold_breach_stops_new_smokes(desktop, monkeypatch):
    """Claude moved on a host after the bootstrap: the first observation that sees it stops new
    smokes, reports the paused timers and names ordinary-shell full recovery. Nothing forward
    runs from there; recovery itself never needs the obsolete evidence."""
    record, _ = _ready_window(desktop)
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    receipt = _short(desktop, registry, record, "titan", "claude-code", "work",
                     SESSIONS["work"], 3999201, 970)
    desktop.move_claude()
    breach = _cli(desktop, monkeypatch, ["record-smoke", "--observe", "europa"])
    assert breach.code == 1 and "step: hold" in breach.stdout and "host: europa" in breach.stdout
    for fragment in ("stop new smokes", "familiar-reap.timer stays paused on titan and europa",
                     "ordinary shell", "every Claude and Codex session"):
        assert fragment in breach.stdout, fragment
    assert breach.stdout.splitlines()[-1] == "  next: " + cli.command_line(["recover"])
    current = state.current_window(desktop.root("titan"))
    assert current["state"] == "recovery-required" and current["failure"]["step"] == "hold"
    assert not recovery.reconcilable(current)
    report = window.status()
    assert report["next"] == ["recover"] and "stop new smokes" in report["detail"]
    assert "paused on titan, europa" in report["detail"]
    path = _private_file(desktop, "late.json", receipt)
    late = _cli(desktop, monkeypatch, ["record-smoke", "--preview", "--receipt", path])
    assert late.code == 1 and late.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["recover"])
    refused = _cli(desktop, monkeypatch, ["finish"])
    assert refused.code == 1 and refused.stdout.splitlines()[-1] == "  next: " + \
        cli.command_line(["recover"])
    assert current.get("smokes", {}).get("receipts", {}) == {}


@needs_zsh
def test_selected_evidenced_version_can_advance_before_window(cutover):
    """Claude moved before the window. Stale proof never passes: preparation refuses until the
    reviewed evidence for the newly selected version is staged, then accepts that version with
    no code pinned to 2.1.304, and a window's receipts must name the version it prepared."""
    cutover.move_claude("2.1.305")
    with pytest.raises(window.Failed) as raised:
        preparation.prepare(SESSION)
    assert any("2.1.305" in blocker and "2.1.304" in blocker
               for blocker in raised.value.blockers)
    assert not (cutover_root(cutover) / window.PREPARED).exists()
    for host in HOSTS:
        transport._write(cutover.home(host) /
                         "d/ops/docs/runbooks/relay-guard-evidence-claude-code.json",
                         json.dumps({"harness": "claude-code", "version": "2.1.305"}) + "\n")
    cutover.pins["claude_version"] = "2.1.305 (Claude Code)"
    cutover.write_manifest(generation="g2")
    prepared = preparation.prepare(SESSION)
    assert prepared["pins"]["claude_version"] == "2.1.305 (Claude Code)"
    for host in HOSTS:
        claude = prepared["hosts"][host]["claude"]
        assert claude["versions"] == {"personal": "2.1.305 (Claude Code)",
                                      "work": "2.1.305 (Claude Code)"}
        assert claude["real"].endswith("/versions/2.1.305")
    assert all(any(word.endswith("/versions/2.1.305") for word in argv)
               for label, argv in smoke.commands(prepared) if "Claude" in label)
    record, _ = _ready_window(cutover, prepared=prepared)
    stale = _receipt(record, "europa", "claude-code", "work", SESSIONS["europa-work"], 4000001,
                     "/nonexistent", {name: _passed() for name in SHORT})
    _refused(cutover, stale, "installed and evidence version 2.1.305 (Claude Code)")
    fresh = {**stale, "versions": {"installed": "2.1.305 (Claude Code)",
                                   "evidence": "2.1.305 (Claude Code)"}}
    failed = _refused(cutover, fresh, "evidence")
    assert "installed and evidence version" not in failed.error
    _refused(cutover, {**fresh, "window_id": "20261019T000000Z-0ldw1nd0"}, "not this live window")


@needs_zsh
def test_final_check_names_bounded_refresh(cutover, monkeypatch):
    """Before each request to close sessions, check is the fresh held check on both hosts. Its
    instructions keep ordinary use allowed while parked, reuse the proof for unchanged
    versions, name only Task 9 Steps 5–7 when Claude moved and a new pilot only for changed
    helper or toolchain bytes. The agent refreshes and reviews; the tool runs no loop."""
    prepared = _cli(cutover, monkeypatch, ["prepare", "--controller-session", SESSION])
    assert prepared.code == 0, prepared.stdout

    def bounded(text):
        assert "ordinary Claude and Codex use stays allowed, including cl, clw" in text
        assert "immediately before each request to close every Claude and Codex session" in text
        assert "held version and doctor probes" in text and "titan and europa" in text
        assert "unchanged versions keep the existing proof" in text
        assert "repeat only Task 9 Steps 5–7" in text and "Steps 1" not in text
        assert "rerun the pilot only if helper or toolchain bytes changed" in text
        assert "surface" in text and "run prepare again" in text
        assert "the agent performs and reviews any refresh" in text
        assert "this tool runs no refresh or retry loop" in text
        assert "avoid cl" not in text and "model or effort" not in text

    bounded(prepared.stdout)
    before = _operations(cutover)
    checked = _cli(cutover, monkeypatch, ["check"])
    assert checked.code == 0, checked.stdout
    bounded(checked.stdout)
    ran = [_operations(cutover)[name] for name in set(_operations(cutover)) - set(before)]
    assert sorted(ran) == ["inputs-check", "inputs-check", "inventory", "inventory"]
    status = _cli(cutover, monkeypatch, ["status"])
    bounded(status.stdout)

    record = (cutover_root(cutover) / window.PREPARED).read_bytes()
    cutover.move_claude("2.1.305")
    before = _operations(cutover)
    moved = _cli(cutover, monkeypatch, ["check"])
    assert moved.code == 1 and "check stopped" in moved.stdout
    assert "2.1.305" in moved.stdout
    bounded(moved.stdout)
    ran = [_operations(cutover)[name] for name in set(_operations(cutover)) - set(before)]
    assert sorted(ran) == ["inputs-check", "inputs-check", "inventory", "inventory"]
    assert (cutover_root(cutover) / window.PREPARED).read_bytes() == record


def record_finished(root):
    return (state.current_window(root).get("finish") or {}).get("completed")


@needs_zsh
def test_partial_finish_keeps_original_timers(cutover, monkeypatch):
    """finish after every receipt: with a resumed session's model pick changed, the fresh checks
    still verify hooks and statusLine. A declined SSH route stops before any change; Europa's
    timer restore failing after Titan's, a service still running and a failed service each
    stop with the timers named. Every retry reconciles actual timers and services and never
    replaces the original timer records, rewrites rollback originals or touches hooks or
    source. The last one verifies closure and releases the hold."""
    cutover.start_dropbox()
    prepared = preparation.prepare(SESSION)
    opened = window.open_window(prepared)
    migrated = window.run_window(prepared, run_decision(prepared, opened))
    assert migrated["state"] == "ready-for-smokes"
    root = cutover_root(cutover)
    registry = Registry(cutover)
    _controller_up(cutover, registry)
    proof = smoke.observe_step(state.current_window(root), "titan")
    assert proof["controller"] is not None
    # The receipts themselves are the unit tests' concern: here they are taken as validated,
    # with the two full smokes' abruptly killed sessions recorded for the closure check.
    checked = []
    monkeypatch.setattr(smoke, "validate_smokes", lambda current: checked.append(current["id"]))
    current = state.current_window(root)
    receipts = {f"titan/{harness}/personal": {"receipt": {
        "host": "titan", "harness": harness, "cases": {"abrupt-death": {
            "session_id": SESSIONS[name]}}}} for harness, name in (
        ("claude-code", "abrupt"), ("codex", "codex-abrupt"))}
    window._save(current, smokes={**current["smokes"], "receipts": receipts})
    registry.put("titan", "claude-code", SESSIONS["abrupt"], 4100001, 5, "/tmp", dead=True)

    # 0. Europa's panel died during the smokes: finish stops before any timer for a consented
    # retry, which restarts only that panel and keeps the receipts.
    panel = transport._process_of(state.current_window(root)["desktop"]["hosts"]["europa"],
                                  "niri-desktop")
    cutover.drop_row("europa", panel["pid"])
    dead = _cli(cutover, monkeypatch, ["finish"])
    assert dead.code == 1 and "step: surface-check" in dead.stdout
    assert "host: europa" in dead.stdout and "niri-desktop is exited" in dead.stdout
    assert dead.stdout.splitlines()[-1] == "  next: " + cli.command_line(["restart-surfaces"])
    assert state.current_window(root)["state"] == "ready-for-smokes"
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    assert [call for call in observed(cutover, "quiesce-timers")
            if call["args"][0] == "restore"] == []
    preview = _cli(cutover, monkeypatch, ["restart-surfaces", "--preview"])
    decision = _decision_from_preview(cutover, state.current_window(root), preview,
                                      "panel.json")
    retried = _cli(cutover, monkeypatch, ["restart-surfaces", "--decision-file", decision])
    assert retried.code == 0, retried.stdout
    cutover.reload()
    assert state.current_window(root)["state"] == "ready-for-smokes"
    assert state.current_window(root)["smokes"]["receipts"] == receipts

    value = json.loads(cutover.target("titan", "claude").read_bytes())
    value["model"] = "sonnet"  # a resumed session saved a pick despite the handoff
    cutover.write_target("claude", json.dumps(value, indent="\t").encode() + b"\n")
    directory = Path(migrated["directory"])

    def rollback():
        return {path.name: path.read_bytes() for path in sorted(directory.glob("*.original"))
                + sorted((directory / "live").iterdir())}

    def timer_records():
        found = {str(path): path.read_bytes() for host in HOSTS for path in [
            cutover.root(host) / "quiesce" / migrated["id"] / "timers.json",
            directory / "hosts" / host / "timers.json"]}
        assert len(found) == 4
        return found

    timer_records_before, originals = timer_records(), rollback()
    targets_now = _targets(cutover)
    mark = len(cutover.lines("observed"))

    def attempt():
        result = _cli(cutover, monkeypatch, ["finish"])
        cutover.reload()
        return result

    # 1. The SSH route to Europa is declined: nothing changes anywhere.
    cutover.config["unreachable"] = True
    cutover.save()
    declined = attempt()
    assert declined.code == 1 and "host: europa" in declined.stdout
    assert state.current_window(root)["state"] == "ready-for-smokes"
    assert timers_active(cutover) == {"titan": "inactive", "europa": "inactive"}
    assert declined.stdout.splitlines()[-1] == "  next: " + cli.command_line(["finish"])
    # 2. Titan's timer restores, then Europa's restore fails.
    cutover.config["unreachable"] = False
    cutover.behave("europa", timers={"restore": "fail"})
    partial = attempt()
    assert partial.code == 1 and "step: timer-restore" in partial.stdout
    assert "host: europa" in partial.stdout
    assert "restored on titan" in partial.stdout and "still paused on europa" in partial.stdout
    assert state.current_window(root)["state"] == "finishing"
    assert timers_active(cutover) == {"titan": "active", "europa": "inactive"}
    timer_records_after = timer_records()
    assert timer_records_after == timer_records_before
    report = window.status()
    assert report["next"] == ["finish"] and "still paused on europa" in report["detail"]
    # 3. Europa's service is still running past its bound; 4. it then fails.
    cutover.behave("europa", timers={}, service={"polls": 10_000})
    cutover.config["service"]["budget"] = 0.3
    cutover.save()
    running = attempt()
    assert running.code == 1 and "step: service-run" in running.stdout
    assert "still activating" in running.stdout and "nothing was killed" in running.stdout
    cutover.behave("europa", service={"result": "exit-code", "status": 1})
    cutover.config["service"]["budget"] = 20.0
    cutover.save()
    failing = attempt()
    assert failing.code == 1 and "Result=exit-code" in failing.stdout
    assert state.current_window(root)["state"] == "finishing"
    assert timer_records() == timer_records_before
    # 5. A recorded dead row still present stops closure; once reaped, finish completes.
    # A declined user-systemd start on Europa leaves the service, and finish, pending.
    cutover.behave("europa", service={"start": "fail"})
    refused = attempt()
    assert refused.code == 1 and "step: service-run" in refused.stdout
    assert "exited 1" in refused.stdout and refused.stdout.splitlines()[-1] == "  next: " + \
        cli.command_line(["finish"])
    assert record_finished(root) is None
    cutover.behave("europa", service={})
    blocked = attempt()
    assert blocked.code == 1 and "step: closure" in blocked.stdout
    assert SESSIONS["abrupt"] in blocked.stdout
    registry.drop("titan", "claude-code", SESSIONS["abrupt"])
    done = attempt()
    assert done.code == 0, done.stdout
    record = state.current_window(root)
    assert record["state"] == "complete" and checked
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    for host in HOSTS:
        service = record["finish"]["services"][host]
        assert (service["result"], service["exec_main_status"]) == ("success", "0")
        assert record["finish"]["timers"][host]["restored"] is True
    assert record["finish"]["closure"]["controller"] == "kept"
    assert timer_records() == timer_records_before and rollback() == originals
    assert _targets(cutover) == targets_now  # the changed pick stays; no hook was rewritten
    events = _recovery_events(cutover, mark)
    assert not any(event.startswith(("restore:", "rollback:", "live:", "dry:"))
                   or ":git-" in event or ":launched-" in event or "surface-" in event
                   for event in events), events
    # Each attempt past the declined one restored both hosts again from the same records.
    assert [event for event in events if event.endswith(":timer-restored")] == [
        "titan:timer-restored", "europa:timer-restored"] * 6
    for fragment in ("finish", "complete", "Result=success ExecMainStatus=0",
                     "held sessions keep DISABLE_UPDATES=1 until they exit",
                     "cl, clw and Claude model or effort changes are allowed again"):
        assert fragment in done.stdout, fragment
    assert "avoid cl" not in done.stdout and "warning:" not in done.stdout
    for host in HOSTS:
        assert f"{host}: familiar's surfaces: familiar-niri-watch restarted, niri-desktop " \
            "restarted" in done.stdout
    assert "changed nothing" in declined.stdout
    assert window.status()["window"]["state"] == "complete"


@needs_zsh
def test_finish_gate_revalidates_every_recorded_receipt(desktop):
    """finish's receipt gate passes on the six real receipts, and re-validates each one it
    holds: an observation altered after recording, or an edited attestation record, blocks it."""
    record, _ = _ready_window(desktop)
    registry = Registry(desktop)
    _controller_up(desktop, registry)
    receipts = [_full_claude(desktop, registry, record), _full_codex(desktop, registry, record),
                _short(desktop, registry, record, "titan", "claude-code", "work",
                       SESSIONS["work"], 3998201, 930),
                _short(desktop, registry, record, "titan", "codex", "work",
                       SESSIONS["codex-work"], 3998301, 940),
                _short(desktop, registry, record, "europa", "claude-code", "personal",
                       SESSIONS["europa"], 3998401, 950),
                _short(desktop, registry, record, "europa", "claude-code", "work",
                       SESSIONS["europa-work"], 3998501, 960)]
    for receipt in receipts:
        _record_receipt(desktop, receipt)
    current = state.current_window(desktop.root("titan"))
    assert set(current["smokes"]["receipts"]) == {f"{host}/{harness}/{home}" for host, harness,
                                                  home in smoke.REQUIRED}
    smoke.validate_smokes(current)  # all six pass, each against its recorded observations
    assert window.status()["next"] == ["finish"]

    evidence = Path(receipts[1]["cases"]["turn-done"]["evidence"][0]["path"])
    original = evidence.read_bytes()
    evidence.write_bytes(original.replace(b'"done"', b'"done" '))
    with pytest.raises(window.Failed) as raised:
        smoke.validate_smokes(current)
    assert raised.value.step == "receipt" and "changed since it was recorded" in \
        raised.value.error
    evidence.write_bytes(original)
    smoke.validate_smokes(current)

    stored = current["smokes"]["receipts"]["europa/claude-code/work"]
    attestation = Path(current["directory"]) / "decisions" / f"{stored['attempt_id']}.json"
    consumed = json.loads(attestation.read_bytes())
    consumed["decision"]["source"]["reply"] = "yes (an agent answered for me)"
    attestation.write_bytes(json.dumps(consumed, indent=2).encode() + b"\n")
    with pytest.raises(window.Failed) as raised:
        smoke.validate_smokes(current)
    assert (raised.value.step, raised.value.status) == ("receipts", "blocked")
    assert "europa/claude-code/work" in raised.value.error
    assert "attestation decision is missing or changed" in raised.value.error


def test_finish_surface_retry_from_ready_for_smokes(desktop, monkeypatch):
    """After the surfaces restarted, a dead panel is retried by restart-surfaces with fresh
    consent: only the surface not running as restarted, the smoke receipts kept, the window
    ready for smokes again. The operator's terminal needs no controller proof; an agent's
    session decision does. Healthy surfaces leave nothing to retry."""
    record, _ = _ready_window(desktop)
    root = desktop.root("titan")
    checks = _rechecks(monkeypatch)
    recorded = record["desktop"]["hosts"]
    watcher = transport._process_of(recorded["titan"], "familiar-niri-watch")
    smokes = {"receipts": {"titan/claude-code/work": {"receipt": {"session_id": "kept"},
                                                      "attempt_id": "smoke-1"}},
              "observations": {}}
    record = window._save(record, smokes=smokes)
    desktop.drop_row("titan", watcher["pid"])
    mark = len(desktop.lines("observed"))

    preview = _cli(desktop, monkeypatch, ["restart-surfaces", "--preview"])
    assert preview.code == 0, preview.stdout
    assert "    familiar-niri-watch (" in preview.stdout and "niri-desktop (" not in preview.stdout
    assert "europa: nothing restarts" in preview.stdout
    assert "not yet verified" not in preview.stdout
    decision = _decision_from_preview(desktop, record, preview, "retry.json")
    unproven = _cli(desktop, monkeypatch, ["restart-surfaces", "--decision-file", decision])
    assert unproven.code == 1 and "step: controller-check" in unproven.stdout
    assert transport._niri_spawns(desktop, mark) == []
    # The operator's own terminal answer needs no proof.
    answered = _cli(desktop, monkeypatch, ["restart-surfaces"], answer=b"yes\n")
    assert answered.code == 0, answered.stdout
    assert checks == ["1" * 40]  # the verified migration, rechecked first
    assert _spawned(desktop, mark) == [("titan", COMMANDS["familiar-niri-watch"])]
    assert transport._term_signals(desktop, mark) == []
    current = state.current_window(root)
    assert current["state"] == "ready-for-smokes" and current["smokes"] == smokes
    replacement = current["desktop"]["phases"]["forward"]["titan"]["familiar-niri-watch"]
    assert (replacement["exited"], replacement["attempt"]) == (True, "restart-1")
    assert current["desktop"]["phases"]["forward"]["europa"] == record["desktop"]["phases"][
        "forward"]["europa"]
    assert answered.stdout.splitlines()[-1] == "  next: " + cli.command_line(
        ["record-smoke", "--observe", "titan"])

    # Healthy, nothing is retried and nothing is asked.
    healthy = _cli(desktop, monkeypatch, ["restart-surfaces"], answer=b"yes\n")
    assert healthy.code == 1 and "nothing to retry" in healthy.stdout
    assert "desktop consent" not in healthy.terminal
    # Europa's panel dies next: the agent proves its controller, and its session decision
    # restarts only that panel.
    desktop.drop_row("europa", transport._process_of(
        current["desktop"]["hosts"]["europa"], "niri-desktop")["pid"])
    _prove(desktop)
    preview = _cli(desktop, monkeypatch, ["restart-surfaces", "--preview"])
    decision = _decision_from_preview(desktop, state.current_window(root), preview, "agent.json")
    mark = len(desktop.lines("observed"))
    retried = _cli(desktop, monkeypatch, ["restart-surfaces", "--decision-file", decision])
    assert retried.code == 0, retried.stdout
    assert _spawned(desktop, mark) == [("europa", COMMANDS["niri-desktop"])]
    final = state.current_window(root)
    assert final["state"] == "ready-for-smokes"
    assert final["smokes"]["receipts"] == smokes["receipts"]
    assert [(entry["attempt_id"], entry["outcome"]) for entry in final["desktop"]["attempts"]] \
        == [("restart-1", "complete"), ("restart-2", "complete")]


@needs_zsh
def test_smoke_hold_breach_recovers_to_native(cutover, monkeypatch):
    """Claude moved during the smokes of a migrated window whose surfaces restarted and whose
    smokes are recorded. Full recover, answered on the operator's terminal, still reaches
    native: targets, source and dependencies restored, familiar's surfaces restarted from them,
    the original timers and their service back, and no Claude launched despite the obsolete
    evidence."""
    cutover.start_dropbox()
    native = (_targets(cutover), _modules(cutover))
    prepared = preparation.prepare(SESSION)
    opened = window.open_window(prepared)
    migrated = window.run_window(prepared, run_decision(prepared, opened))
    assert migrated["state"] == "ready-for-smokes"
    root = cutover_root(cutover)
    registry = Registry(cutover)
    _controller_up(cutover, registry)
    _record_receipt(cutover, _short(cutover, registry, migrated, "titan", "claude-code",
                                    "work", SESSIONS["work"], 3999301, 980))
    cutover.move_claude()
    breach = _cli(cutover, monkeypatch, ["record-smoke", "--observe", "europa"])
    assert breach.code == 1 and "step: hold" in breach.stdout
    record = state.current_window(root)
    assert record["state"] == "recovery-required" and record["smokes"]["receipts"]
    assert record["desktop"]["completed"]["forward"]
    # The operator closes every session, then recovers from an ordinary terminal.
    cutover.drop_row("titan", CONTROLLER_PID)
    cutover.reload()
    mark = len(cutover.lines("observed"))
    recovered = _cli(cutover, monkeypatch, ["recover"], answer=b"yes\n")
    assert recovered.code == 0, recovered.stdout
    assert surfaces.RECOVERY_IMPACT in recovered.terminal
    record = state.current_window(root)
    assert record["state"] == "recovered"
    assert {host: sorted(names) for host, names in
            record["desktop"]["phases"]["recovery"].items()} == {
        host: sorted(surfaces.SURFACES) for host in HOSTS}
    assert timers_active(cutover) == {"titan": "active", "europa": "active"}
    assert {host: cutover.units(host)["familiar-reap.service"]["runs"] for host in HOSTS} == {
        "titan": 1, "europa": 1}
    assert (_targets(cutover), _modules(cutover)) == native
    head = transport.familiar_head(cutover.home("titan"))
    assert _tree(cutover, head) == _tree(cutover, cutover.pins["familiar_pre"])
    events = _recovery_events(cutover, mark)
    assert not any(":launched-" in event for event in events), events
    assert observed(cutover, "claude", mark) == [] and observed(cutover, "preflight", mark) == []
    assert "native recovery complete" in recovered.stdout
