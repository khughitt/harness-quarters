"""Quiescing one cutover host before familiar or settings change, and undoing it.

These are fixed host operations run by `hosts.execute`; the window orchestration lives in
`window.py`. Each takes the controller's window ID and keeps its records on this host under
`quiesce/<window-id>/` in the cutover root (0700 directories, 0600 files):

- `timers.json`: `tools/quiesce-timers record` output for familiar-reap.timer, made 0600 and
  fsynced with its directory before the reply, so before any stop, and again before any later
  read. `timers.restored.json` marks a completed restore; a record of timers this window never
  stopped is instead kept under `abort/` and marked restored.
- `snapshots.json`: the registered moves of the preparation snapshots `familiar-state` and
  `familiar-node_modules.pre`, written before the first move. A moved snapshot is kept at
  `preparation/<name>`; a fresh copy is made under `copy/<name>`, fsynced, renamed into the
  root's name and compared with its live tree. An abort returns each kept snapshot to its name
  and retains refreshed or partial copies under `abort/`.

The Codex daemons stop only through `codex app-server daemon stop` for each Titan home (in
recovery, with the release installed at the recorded path even if it changed), and a surviving
Claude or Codex process is reported for inspection, never killed. Strict no-live
reads this user's whole process table and the existing relay preflight with no exemption.
Every operation here but `pending-operations` is live only: a pilot queries real timers through
the inventory and never changes them. Children run through `hosts._run_child`; their raw output
stays in the private log."""
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

from . import hosts, inventory, state
from .state import Stop

TIMER = inventory.UNIT
QUIESCE = "quiesce"
RECORD, RESTORED, MOVES = "timers.json", "timers.restored.json", "snapshots.json"
# Each retained preparation snapshot and the live tree it copies, relative to HOME.
SNAPSHOTS = (("familiar-state", ".local/state/familiar"),
             ("familiar-node_modules.pre", "d/familiar/node_modules"))
TIMER_RECORD_KEYS = {"timer", "service", "enabled", "active"}
CHILD_SECONDS = 120
NO_LIVE_SECONDS = 300
SNAPSHOT_SECONDS = 900
TIMER_WAIT_DEADLINE = hosts.TIMER_WAIT_SECONDS + 120


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _window_id(value):
    return isinstance(value, str) and state.WINDOW_ID.fullmatch(value) is not None


def _sha(value):
    return isinstance(value, str) and state.SHA256.fullmatch(value) is not None


def _commit(value):
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef"
                                                               for c in value)


def _directory(context):
    return Path(context["root"]) / QUIESCE / context["payload"]["window_id"]


def _held_env(context):
    return hosts.claude_hold_env(hosts._child_env(context))


# --- processes ---------------------------------------------------------------------------


def _harness_processes(context):
    """Every Claude or Codex process of this user, known executable or not."""
    home = Path(context["home"])
    harnesses = {"claude": inventory._resolve(home / ".local/bin/claude",
                                              home / ".local/share/claude/versions",
                                              inventory.CLAUDE_FAMILY)}
    if hosts.HOSTS[context["host"]]["codex"]:
        harnesses["codex"] = inventory._resolve(home / ".local/bin/codex",
                                                home / ".codex/packages/standalone/releases",
                                                inventory.CODEX_FAMILY)
    report = inventory._processes(context, inventory._process_rows(), harnesses)
    return sorted(report["known"] + report["unknown"], key=lambda entry: entry["pid"])


def codex_daemon_stop(context):
    """Stop both Titan homes' Codex app-server daemons with the supported CLI.

    Forward, the executable must be the one recorded at preparation. With `recovery`, drift
    blocks forward progress but never restoration: the stop runs whatever standalone Codex
    release is installed at the recorded path and reports its identity."""
    home = Path(context["home"])
    codex = inventory._resolve(home / ".local/bin/codex",
                               home / ".codex/packages/standalone/releases",
                               inventory.CODEX_FAMILY)
    prepared = codex["familiar"] and codex["sha256"] == context["payload"]["codex_sha256"]
    if not context["payload"].get("recovery") and not prepared:
        raise Stop("~/.local/bin/codex is not the Codex executable recorded at preparation; "
                   "prepare again")
    if not codex["familiar"]:
        raise Stop("~/.local/bin/codex does not resolve to a standalone Codex release owned by "
                   "this user; nothing was run; inspect it")
    stopped = []
    for name, codex_home in (("personal", None), ("work", home / ".codex-work")):
        env = _held_env(context)
        env.pop("CODEX_HOME", None)
        if codex_home is not None:
            env["CODEX_HOME"] = str(codex_home)
        result = hosts._run_child(context, f"codex-{name}-daemon-stop",
                                  [codex["real"], "app-server", "daemon", "stop"], env=env,
                                  timeout=CHILD_SECONDS)
        if result.returncode != 0:
            raise Stop(f"codex app-server daemon stop for the {name} home exited "
                       f"{result.returncode}; see the private log")
        stopped.append(name)
    survivors = [entry for entry in _harness_processes(context) if entry["harness"] == "codex"]
    return {"stopped": stopped, "survivors": survivors,
            "executable": {"path": codex["path"], "real": codex["real"],
                           "sha256": codex["sha256"], "prepared": prepared}}


def no_live(context):
    """Strict no-live: this user's process table and relay-cutover's own check."""
    home, env = Path(context["home"]), _held_env(context)
    # That helper finds claude and codex on PATH: the fixed executables' directory comes first.
    env["PATH"] = f"{home / '.local/bin'}:{env['PATH']}"
    for key in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        env.pop(key, None)
    harnesses = ("claude-code", "codex") if hosts.HOSTS[context["host"]]["codex"] else (
        "claude-code",)
    preflight = {}
    for harness in harnesses:
        result = hosts._run_child(
            context, f"no-live-{harness}",
            [hosts.TOOLS["python3"], "-B", Path(context["hq"]) / "tools/relay-cutover",
             "preflight", "--harness", harness], env=env, timeout=inventory.PREFLIGHT_SECONDS)
        preflight[harness] = inventory._preflight_checks(result, harness)["no-live"]
    return {"live": _harness_processes(context), "preflight": preflight}


def pending_operations(context):
    """Operations on this host that have not recorded completion, other than this one, each with
    its mode and the window it names, if any. Any window's caller, or none, may ask."""
    operations = Path(context["root"]) / "operations"
    found = []
    if not os.path.lexists(operations):
        return {"operations": found}
    for entry in sorted(os.listdir(operations)):
        directory = operations / entry
        if (entry == "transport" or entry == context["operation_id"]
                or os.path.lexists(directory / "done.json")):
            continue
        if not hosts.OPERATION_ID.fullmatch(entry) or not os.path.lexists(
                directory / "start.json"):
            found.append({"operation_id": entry, "operation": None, "state": "unrecorded",
                          "window_id": None, "mode": None})
            continue
        start = state.load_record(directory / "start.json")
        found.append({"operation_id": entry, "operation": start["operation"],
                      "state": hosts._observe(directory, start)["state"],
                      "window_id": start["payload"].get("window_id"), "mode": start["mode"]})
    return {"operations": found}


# --- timers ------------------------------------------------------------------------------


def _timers(context, label, command, record, *extra, timeout=CHILD_SECONDS):
    argv = [hosts.TOOLS["python3"], "-B", Path(context["hq"]) / "tools/quiesce-timers", command,
            "--state", record, *extra]
    result = hosts._run_child(context, label, argv, env=hosts._child_env(context),
                              timeout=timeout)
    if result.returncode != 0:
        raise Stop(f"quiesce-timers {command} exited {result.returncode}; see the private log")


def _unrestored(root):
    """Window IDs whose timer record on this host was never restored."""
    base = Path(root) / QUIESCE
    if not os.path.lexists(base):
        return []
    return [name for name in sorted(os.listdir(base))
            if os.path.lexists(base / name / RECORD) and not os.path.lexists(
                base / name / RESTORED)]


def _durable(path):
    """Make the helper's record private and durable with its directory; return its bytes.

    quiesce-timers writes the record non-atomically with the umask's mode, so a record left by
    an interrupted helper may be loose or torn; it is made private here before any read."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise Stop(f"{path}: the timer record cannot be opened ({hosts._brief(error)}); "
                   "inspect it") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise Stop(f"{path}: the timer record is not this user's regular file")
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read()
    finally:
        os.close(fd)
    state._sync(path.parent)
    return data


def _parse_timers(data):
    try:
        value = json.loads(data, object_pairs_hook=state._unique, parse_constant=state._constant)
    except (UnicodeDecodeError, ValueError):
        value = None
    timers = value.get("timers") if isinstance(value, dict) else None
    if (not isinstance(timers, list) or len(timers) != 1 or not isinstance(timers[0], dict)
            or set(timers[0]) != TIMER_RECORD_KEYS or timers[0]["timer"] != TIMER
            or not all(isinstance(timers[0][key], str) for key in TIMER_RECORD_KEYS)):
        raise Stop(f"the timer record does not hold exactly {TIMER}; inspect it")
    return timers


def _recorded(context, expected=None):
    """This window's timer record on this host, made private and durable before it is read."""
    path = _directory(context) / RECORD
    if not os.path.lexists(path):
        return path, None
    data = _durable(path)
    if expected is not None and _sha256(data) != expected:
        raise Stop("the timer record differs from the one this window recorded; inspect it")
    return path, data


def timer_record(context):
    window_id = context["payload"]["window_id"]
    others = [name for name in _unrestored(context["root"]) if name != window_id]
    if others:
        raise Stop(f"window {others[0]} paused timers on this host and never restored them; "
                   "recover it first")
    directory = _directory(context)
    state._make_dirs(directory)
    state._check_dir(directory)
    path = directory / RECORD
    if os.path.lexists(path):
        raise Stop(f"timers are already recorded for window {window_id}; abort or recover it")
    _timers(context, "timer-record", "record", path, TIMER)
    data = _durable(path)
    return {"path": str(path), "sha256": _sha256(data), "timers": _parse_timers(data)}


def timer_stop(context):
    path, data = _recorded(context, context["payload"]["record_sha256"])
    if data is None:
        raise Stop("no timer record for this window here; record before stopping")
    _timers(context, "timer-stop", "stop", path)
    return {"stopped": [TIMER]}


def timer_wait(context):
    path, data = _recorded(context, context["payload"]["record_sha256"])
    if data is None:
        raise Stop("no timer record for this window here; record before waiting")
    _timers(context, "timer-wait", "wait", path, "--timeout", str(hosts.TIMER_WAIT_SECONDS),
            "--poll", str(hosts.TIMER_POLL_SECONDS), timeout=hosts.TIMER_WAIT_SECONDS + 60)
    return {"inactive": [TIMER]}


def timer_restore(context):
    """Return this host's timers to this window's record; without one, nothing was paused.

    `stopped` says whether this window ever asked this host to stop its timers. When it never
    did, nothing here is paused: the record, whole or torn by an interrupted helper, is kept
    as abort evidence and marked restored rather than replayed. A stopped host's record must
    parse, or the restore stops for inspection."""
    path, data = _recorded(context, context["payload"].get("record_sha256"))
    if data is None:
        return {"recorded": False}
    if not context["payload"]["stopped"]:
        retained = _retain(path, path.parent / "abort", RECORD)
        state.save_record(path.parent / RESTORED, {
            "schema": 1, "restored_at": hosts._now(), "sha256": _sha256(data),
            "stopped": False, "retained": str(retained)})
        return {"recorded": True, "restored": False, "stopped": False,
                "retained": str(retained)}
    _parse_timers(data)
    _timers(context, "timer-restore", "restore", path)
    state.save_record(path.parent / RESTORED, {"schema": 1, "restored_at": hosts._now(),
                                               "sha256": _sha256(data), "stopped": True})
    return {"recorded": True, "restored": True}


# --- snapshots ---------------------------------------------------------------------------


def _raise(error):
    raise error


def _source(path):
    info = os.lstat(path) if os.path.lexists(path) else None
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise Stop(f"{path} is not a directory; inspect it before the window")
    return path


def _tree(path, digest=True):
    """Each entry under path (excluding path itself): type, mode, bytes or link target."""
    entries = []
    for directory, names, files in os.walk(_source(path), onerror=_raise):
        names.sort()
        for name in sorted(names + files):
            full = os.path.join(directory, name)
            relative = os.path.relpath(full, path)
            info = os.lstat(full)
            if stat.S_ISLNK(info.st_mode):
                entries.append([relative, "link", os.readlink(full)])
            elif stat.S_ISDIR(info.st_mode):
                entries.append([relative, "dir", stat.S_IMODE(info.st_mode)])
            elif stat.S_ISREG(info.st_mode):
                content = None
                if digest:
                    with open(full, "rb") as stream:
                        content = hashlib.file_digest(stream, "sha256").hexdigest()
                entries.append([relative, "file", stat.S_IMODE(info.st_mode), content])
            else:
                raise Stop(f"{path}: {relative} is a special file; inspect it before the window")
    return {"entries": len(entries),
            "sha256": _sha256(json.dumps(entries).encode()) if digest else None}


# Why familiar off PRE blocks every fresh window, on either host (ruling R47).
OFF_PRE = ("no window runs from here: a recovered merge ends this cutover, as a completed one "
           "does, and a new attempt needs newly reviewed pins and inputs")


def _familiar_native(context, pre):
    """Blockers when familiar is not at PRE with a clean tree, or its dependencies do not check
    native: read by relay-cutover's own familiar-source and familiar-check."""
    relay_cutover, found = Path(context["hq"]) / "tools/relay-cutover", []
    for label, args, what in (
            ("familiar-source", ["--head", pre],
             f"familiar is not at the approved PRE {pre[:12]} with a clean tree"),
            ("familiar-check", ["--expect", "native"],
             "familiar's dependencies do not check native")):
        try:
            result = hosts._run_child(context, f"readiness-{label}", [
                hosts.TOOLS["python3"], "-B", relay_cutover, label, *args],
                env=hosts._child_env(context), timeout=CHILD_SECONDS)
            failed = result.returncode != 0
        except (Stop, OSError) as error:
            what, failed = f"relay-cutover {label} did not run ({hosts._brief(error)})", True
        if failed:
            found.append(f"familiar-native: {what} (relay-cutover {label}; see the private log); "
                         f"{OFF_PRE}")
    return found


def readiness(context, familiar_pre):
    """Read-only blockers for a fresh window on this host: unexplained root state, timers an
    earlier window left paused, missing or uncopyable preparation snapshots and, unless the
    payload names the active window (a run's own gate, whose quiescence repeats the check),
    familiar off its approved PRE `familiar_pre`."""
    root, home, blockers = Path(context["root"]), Path(context["home"]), []
    try:
        state.current_window(root)
    except Stop as stop:
        blockers.append(f"retained-state: {stop}")
    active = context["payload"].get("active")
    for name in _unrestored(root):
        if name != active:
            blockers.append(f"quiesce-record: window {name} paused timers on this host and "
                            "never restored them; recover it")
    for name, source in SNAPSHOTS:
        try:
            info = os.lstat(root / name)
        except FileNotFoundError:
            info = None
        if info is None or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            blockers.append(f"snapshots: the preparation snapshot {name} is not this user's "
                            "directory in the cutover root")
        try:
            _tree(home / source, digest=False)
        except (Stop, OSError) as error:
            blockers.append(f"snapshots: {hosts._brief(error)}")
    if active is None:
        blockers += _familiar_native(context, familiar_pre)
    return blockers


def _copy_file(source, destination):
    shutil.copy2(source, destination, follow_symlinks=False)
    fd = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _copy(source, destination):
    """A durable copy that keeps symlinks, modes and times, like `cp -a`."""
    shutil.copytree(source, destination, symlinks=True,
                    copy_function=lambda src, dst: _copy_file(src, dst))
    for directory, _, _ in os.walk(destination, topdown=False, onerror=_raise):
        state._sync(directory)
    state._sync(Path(destination).parent)


def _move(source, destination):
    os.rename(source, destination)
    state._sync(Path(source).parent)
    state._sync(Path(destination).parent)


def snapshot_refresh(context):
    """Keep the preparation snapshots and refresh them from the now quiescent live trees."""
    root, home, directory = Path(context["root"]), Path(context["home"]), _directory(context)
    if not os.path.lexists(directory / RECORD):
        raise Stop("timers are not recorded for this window here; quiesce them first")
    if os.path.lexists(directory / MOVES):
        raise Stop("snapshots already moved for this window; abort it rather than refresh again")
    relay_cutover = Path(context["hq"]) / "tools/relay-cutover"
    for label, args in (("familiar-source", ["--head", context["payload"]["familiar_pre"]]),
                        ("familiar-check", ["--expect", "native"])):
        result = hosts._run_child(context, label, [hosts.TOOLS["python3"], "-B", relay_cutover,
                                                   label, *args],
                                  env=hosts._child_env(context), timeout=CHILD_SECONDS)
        if result.returncode != 0:
            raise Stop(f"relay-cutover {label} found familiar not native; see the private log")
    moves = []
    for name, source in SNAPSHOTS:
        info = os.lstat(root / name) if os.path.lexists(root / name) else None
        if info is None or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise Stop(f"the preparation snapshot {name} is not this user's directory")
        _tree(home / source, digest=False)
        moves.append({"name": name, "live": str(home / source), "state": "registered"})
    record = {"schema": 1, "window_id": context["payload"]["window_id"], "moves": moves}
    state.save_record(directory / MOVES, record)  # registered before anything moves
    for folder in ("preparation", "copy"):
        state._make_dirs(directory / folder)
    for move in moves:
        name, live = move["name"], Path(move["live"])
        _move(root / name, directory / "preparation" / name)
        move["state"] = "preserved"
        state.save_record(directory / MOVES, record)
        _copy(live, directory / "copy" / name)
        _move(directory / "copy" / name, root / name)
        os.chmod(root / name, 0o700)
        move["state"] = "refreshed"
        state.save_record(directory / MOVES, record)
        observed, copied = _tree(live), _tree(root / name)
        if observed != copied:
            raise Stop(f"the refreshed {name} differs from its live tree; inspect it")
        move.update(state="verified", entries=copied["entries"], sha256=copied["sha256"])
        state.save_record(directory / MOVES, record)
    return {"moves": moves}


def _retain(path, directory, name):
    state._make_dirs(directory)
    target, number = directory / name, 1
    while os.path.lexists(target):
        number += 1
        target = directory / f"{name}.{number}"
    _move(path, target)
    return target


def snapshot_abort(context):
    """Return every moved preparation snapshot; keep refreshed and partial copies aside."""
    root, directory = Path(context["root"]), _directory(context)
    if not os.path.lexists(directory / MOVES):
        return {"moves": {name: "untouched" for name, _ in SNAPSHOTS}}
    record = state.load_record(directory / MOVES)
    outcome = {}
    for move in record["moves"]:
        name = move["name"]
        current, kept = root / name, directory / "preparation" / name
        partial = directory / "copy" / name
        if os.path.lexists(partial):
            _retain(partial, directory / "abort", f"{name}.partial")
        if os.path.lexists(kept):
            if os.path.lexists(current):
                _retain(current, directory / "abort", name)
            _move(kept, current)
            outcome[name] = "returned"
        elif os.path.lexists(current):
            outcome[name] = "untouched"
        else:
            outcome[name] = "lost"
    record["aborted"] = {"at": hosts._now(), "moves": outcome}
    state.save_record(directory / MOVES, record)
    lost = sorted(name for name, result in outcome.items() if result == "lost")
    if lost:
        raise Stop(f"the preparation snapshot {lost[0]} is in neither its place nor this "
                   f"window's preparation directory; inspect {directory}")
    return {"moves": outcome}


_WINDOW = {"window_id": _window_id}
_RECORD = {**_WINDOW, "record_sha256": _sha}
_REQUIRED = frozenset({"window_id"})

OPERATIONS = {
    "codex-daemon-stop": hosts.Operation(
        run=codex_daemon_stop, deadline=2 * CHILD_SECONDS + 60, mutation=True,
        payload={**_WINDOW, "codex_sha256": _sha, "recovery": lambda value: type(value) is bool},
        required=frozenset({"window_id", "codex_sha256"}),
        hosts=("titan",)),
    "no-live": hosts.Operation(run=no_live, deadline=NO_LIVE_SECONDS, mutation=False,
                               payload=_WINDOW),
    "pending-operations": hosts.Operation(run=pending_operations, deadline=60, mutation=False,
                                          payload=_WINDOW, modes=hosts.BOTH),
    "timer-record": hosts.Operation(run=timer_record, deadline=CHILD_SECONDS + 60,
                                    mutation=True, payload=_WINDOW, required=_REQUIRED),
    "timer-stop": hosts.Operation(run=timer_stop, deadline=CHILD_SECONDS + 60, mutation=True,
                                  payload=_RECORD, required=frozenset(_RECORD)),
    "timer-wait": hosts.Operation(run=timer_wait, deadline=TIMER_WAIT_DEADLINE, mutation=False,
                                  payload=_RECORD, required=frozenset(_RECORD)),
    "timer-restore": hosts.Operation(
        run=timer_restore, deadline=CHILD_SECONDS + 60, mutation=True,
        payload={**_RECORD, "stopped": lambda value: type(value) is bool},
        required=frozenset({"window_id", "stopped"})),
    "snapshot-refresh": hosts.Operation(
        run=snapshot_refresh, deadline=SNAPSHOT_SECONDS, mutation=True,
        payload={**_WINDOW, "familiar_pre": _commit},
        required=frozenset({"window_id", "familiar_pre"})),
    "snapshot-abort": hosts.Operation(run=snapshot_abort, deadline=SNAPSHOT_SECONDS,
                                      mutation=True, payload=_WINDOW, required=_REQUIRED),
}
