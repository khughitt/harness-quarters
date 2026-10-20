"""Cutover window records, target registration and human decisions, run against
throwaway roots. Decision dictionaries here are fixtures standing in for a recorded
reply; nothing in these tests authenticates a human or answers a prompt for a live call."""
import errno
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relay_cutover_bootstrap import state
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
