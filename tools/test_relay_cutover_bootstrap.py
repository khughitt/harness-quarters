"""Cutover window records, target registration, human decisions, preparation, quiescence
and the pre-merge abort, run against throwaway roots and the transport tests' fixture hosts.
Decision dictionaries here are fixtures standing in for a recorded reply; nothing in these
tests authenticates a human or answers a prompt for a live call."""
import errno
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import test_relay_cutover_transport as transport
from relay_cutover_bootstrap import hosts, inputs, state, window
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
