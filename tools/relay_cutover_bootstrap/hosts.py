"""Cutover hosts: fixed operations behind one fixed entry, owned children, records.

The controller runs Titan main's entry directly and reaches Europa through
`ssh -4 -o BatchMode=yes europa` with one fixed, Zsh-safe remote command. A request is one
bounded JSON object on stdin: schema, mode, operation, a caller-chosen operation ID, the
payload and the controller's package digest. Nothing from it enters a shell string.

The entry validates the whole request before any write, durably records the operation's
start (owner PID and start time) under the cutover root, runs owned child process groups
under the operation's deadline, durably records completion, and only then writes one reply.
A lost reply (EOF or EPIPE) never cancels: the operation finishes or meets its own deadline,
and `operation-status` reconciles it later without rerunning it. Only `operation-cancel`,
an actual signal or the deadline stops it. Replies carry parsed, structured values; raw
child output goes to the operation's private log and environments are never recorded.

Records live in `operations/<operation-id>/` under the root (0700 directories, 0600 files):
`start.json`, `children.json`, `cancel.json`, `done.json` (the reply as sent) and `log`.
Controller-side transport errors go to `operations/transport/<operation-id>.log`. An
operation whose owner died before `done.json` is `owner-lost`: its recorded children may
still run until `operation-cancel` stops them and records it as `interrupted`.

The operations themselves are assembled in `operations.py` from their concern modules."""
import hashlib
import json
import os
import re
import secrets
import select
import shlex
import signal
import subprocess
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import state
from .state import Stop

HOSTS = {"titan": {"remote": False, "codex": True},
         "europa": {"remote": True, "codex": False}}
SSH_OPTIONS = ("-4", "-o", "BatchMode=yes")
ENTRY = "exec /usr/bin/python3 -B ~/d/hq/tools/relay-cutover-host"
ENTRY_PATH = "d/hq/tools/relay-cutover-host"
ROOT = ".local/state/hq/relay-cutover"
# System executables by explicit path; tests replace entries at this Python boundary.
TOOLS = {"python3": "/usr/bin/python3", "ssh": "/usr/bin/ssh", "npm": "/usr/bin/npm",
         "node": "/usr/bin/node", "git": "/usr/bin/git", "systemctl": "/usr/bin/systemctl",
         "niri": "/usr/bin/niri"}
SYSTEM_PATH = ("/usr/bin", "/bin")
MAX_REQUEST = 16384  # below one pipe buffer, so writing a request never blocks
MAX_RESPONSE = 1 << 20
MAX_OUTPUT = 4 << 20
READ_SECONDS = 30
CONTROL_SECONDS = 60  # the controller's bound on one status or cancel exchange
CANCEL_WAIT_SECONDS = 30  # the helper's wait for a cancelled owner to record completion
GRACE_SECONDS = 5
DRAIN_SECONDS = 0.5
POLL_SECONDS = 1
# Deadlines the later window operations take: timer waits and polls, source/target sync,
# dependency installs.
TIMER_WAIT_SECONDS, TIMER_POLL_SECONDS = 3600, 30
SYNC_SECONDS = 600
INSTALL_SECONDS = 900

ENVELOPE = frozenset({"schema", "mode", "operation", "operation_id", "payload",
                      "helper_sha256"})
RESPONSE = frozenset({"schema", "host", "mode", "operation", "operation_id", "status",
                      "result", "error", "log"})
TERMINAL = ("completed", "failed", "cancelled", "timed-out", "interrupted")
STATUSES = TERMINAL + ("refused",)
INTERRUPTS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
WATCHED = (*INTERRUPTS, signal.SIGALRM)
OPERATION_ID = re.compile(r"(titan|europa)-\d{8}T\d{6}Z-[0-9a-f]{12}")


class Refused(Stop):
    """A request refused before any write."""


class Unsettled(Stop):
    """A request whose remote outcome is not known to be final.

    `remote` is the reconciled operation status, or None when the host could not be
    reached; the remote operation may then still be running until its own deadline."""

    def __init__(self, message, *, host, operation_id, remote):
        super().__init__(message)
        self.host, self.operation_id, self.remote = host, operation_id, remote


class Interrupted(Unsettled):
    """A local INT, TERM or HUP stopped a request after an explicit cancel attempt."""


class _Signal(BaseException):
    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


class _Deadline(BaseException):
    pass


class _Expired(Exception):
    pass


@dataclass(frozen=True)
class Operation:
    """One fixed operation: `run(context)` returns its JSON result on this host."""
    run: object
    deadline: float
    mutation: bool
    payload: dict = field(default_factory=dict)  # key -> validator(value) -> bool
    required: frozenset = frozenset()
    hosts: tuple = tuple(HOSTS)


def _text_field(limit):
    return lambda value: (isinstance(value, str) and 0 < len(value) <= limit
                          and value.isprintable())


def _operation_id(value):
    return isinstance(value, str) and OPERATION_ID.fullmatch(value) is not None


def _is_one(value):
    return type(value) is int and value == 1


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _positive(seconds):
    if type(seconds) not in (int, float) or not 0 < seconds < float("inf"):
        raise Stop("timeout must be a positive number of seconds")
    return seconds


def _home():
    home = Path.home()
    if not home.is_absolute():
        raise Stop("HOME must be an absolute path")
    return home


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=state._unique,
                      parse_constant=state._constant)


def _brief(error):
    if isinstance(error, OSError) and error.strerror:
        return f"{error.strerror}: {error.filename}" if error.filename else error.strerror
    return " ".join(str(error).split())[:300]


def _launch(argv, **options):
    return subprocess.Popen(argv, **options)


def helper_digest(package=None) -> str:
    """The digest of a helper package's modules: names and bytes of its *.py files."""
    package = Path(package) if package is not None else Path(__file__).parent
    lines = [f"{path.name} {hashlib.sha256(path.read_bytes()).hexdigest()}"
             for path in sorted(package.glob("*.py"))]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def claude_hold_env(base: dict) -> dict:
    """A copy of base that holds Claude updates for that child; base is never changed."""
    if not isinstance(base, dict):
        raise TypeError("base must be an environment dictionary")
    return {**base, "DISABLE_UPDATES": "1"}


# --- request schema ------------------------------------------------------------------------


def _operations():
    """The assembled operation table. It is imported on use because the concern modules
    that build it import this one; register new operations in operations.py."""
    from .operations import OPERATIONS
    return OPERATIONS


def _spec(name):
    if isinstance(name, str) and name in CONTROL:
        return CONTROL[name]
    if isinstance(name, str) and name in _operations():
        return _operations()[name]
    raise Refused("unknown operation")


def _check_payload(spec, payload):
    if not isinstance(payload, dict):
        raise Refused("payload must be a JSON object")
    if set(payload) - set(spec.payload):
        raise Refused("payload has keys this operation does not take")
    missing = sorted(spec.required - set(payload))
    if missing:
        raise Refused("payload lacks " + ", ".join(missing))
    for key, value in payload.items():
        if not spec.payload[key](value):
            raise Refused(f"payload {key} is invalid")


def _check_envelope(envelope):
    """Validate a request completely; return the host its operation ID names."""
    if not isinstance(envelope, dict) or set(envelope) != ENVELOPE:
        raise Refused("request must be an object holding exactly schema, mode, operation, "
                      "operation_id, payload and helper_sha256")
    if not _is_one(envelope["schema"]):
        raise Refused("request schema must be 1")
    if not isinstance(envelope["mode"], str) or envelope["mode"] not in state.MODES:
        raise Refused("unknown mode")
    spec = _spec(envelope["operation"])
    _check_payload(spec, envelope["payload"])
    if not _operation_id(envelope["operation_id"]):
        raise Refused("operation_id is not an operation id")
    host = envelope["operation_id"].split("-", 1)[0]
    if host not in spec.hosts:
        raise Refused(f"{envelope['operation']} does not run on {host}")
    digest = envelope["helper_sha256"]
    if not isinstance(digest, str) or not state.SHA256.fullmatch(digest):
        raise Refused("helper_sha256 must be a SHA-256 digest")
    return host


# --- controller side -----------------------------------------------------------------------


def _transport_log(home, operation_id):
    directory = home / ROOT / "operations" / "transport"
    state._make_dirs(directory)
    state._check_dir(directory)
    return os.open(directory / f"{operation_id}.log",
                   os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)


def start_request(host: str, mode: str, operation: str, payload: dict, *,
                  timeout: float) -> tuple[str, subprocess.Popen]:
    """Send one validated request and return its operation ID and the owned client.

    The client runs in its own session, so terminal signals reach only the controller.
    Its caller owns it and applies `timeout` while collecting: `request` collects and reaps
    it; a rehearsal may drop it to test disconnection."""
    if not isinstance(host, str) or host not in HOSTS:
        raise Refused("unknown host; expected titan or europa")
    _positive(timeout)
    operation_id = (f"{host}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-"
                    f"{secrets.token_hex(6)}")
    envelope = {"schema": 1, "mode": mode, "operation": operation,
                "operation_id": operation_id, "payload": payload,
                "helper_sha256": helper_digest()}
    _check_envelope(envelope)
    try:
        data = _encode(envelope) + b"\n"
    except (TypeError, ValueError):
        raise Refused("payload is not plain JSON") from None
    if len(data) > MAX_REQUEST:
        raise Refused(f"request exceeds {MAX_REQUEST} bytes")
    home = _home()
    if HOSTS[host]["remote"]:
        argv = [TOOLS["ssh"], *SSH_OPTIONS, host, ENTRY]
    else:
        argv = [TOOLS["python3"], "-B", str(home / ENTRY_PATH)]
    log = _transport_log(home, operation_id)
    try:
        process = _launch(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                          env=dict(os.environ), start_new_session=True, close_fds=True)
    except OSError as error:
        raise Stop(f"{host}: cannot start the transport: {_brief(error)}") from None
    finally:
        os.close(log)
    try:
        process.stdin.write(data)
        process.stdin.flush()
    except BrokenPipeError:
        pass  # collection finds the missing reply and reconciles
    finally:
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
    return operation_id, process


def _await_reply(process, deadline):
    """The client's one reply, or None when the connection ended without a whole one."""
    fd, data = process.stdout.fileno(), bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _Expired()
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        data += chunk
        if len(data) > MAX_RESPONSE:
            raise Stop(f"reply exceeds {MAX_RESPONSE} bytes; reconcile with operation-status")
    try:
        process.wait(timeout=max(0.0, min(GRACE_SECONDS, deadline - time.monotonic())))
    except subprocess.TimeoutExpired:
        pass
    try:
        value = _decode(bytes(data))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _abandon(process):
    """Stop and reap the local client. Closing it is not cancellation of remote work."""
    if process.poll() is None:
        for signum in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                break
            try:
                process.wait(timeout=GRACE_SECONDS)
                break
            except subprocess.TimeoutExpired:
                continue
        process.wait()
    if process.stdout is not None:
        process.stdout.close()


def _check_response(response, host, mode, operation, operation_id):
    if (not isinstance(response, dict) or set(response) != RESPONSE
            or not _is_one(response["schema"]) or response["status"] not in STATUSES):
        raise Stop(f"{host}: the reply does not match schema 1; see the transport log")
    if response["host"] != host:
        raise Stop(f"{host}: the reply came from another host; check the SSH route")
    if response["status"] != "refused" or response["operation_id"] is not None:
        if (response["operation_id"], response["operation"], response["mode"]) != (
                operation_id, operation, mode):
            raise Stop(f"{host}: the reply names another operation")


def _exchange(host, mode, operation, payload, seconds):
    deadline = time.monotonic() + seconds
    operation_id, process = start_request(host, mode, operation, payload, timeout=seconds)
    try:
        response = _await_reply(process, deadline)
    finally:
        _abandon(process)
    if response is None:
        raise Stop(f"{host}: {operation} got no reply; see operations/transport/"
                   f"{operation_id}.log")
    _check_response(response, host, mode, operation, operation_id)
    return response


def _control(host, mode, operation, target, seconds=CONTROL_SECONDS):
    try:
        response = _exchange(host, mode, operation, {"operation_id": target}, seconds)
    except _Expired:
        raise Stop(f"{host}: {operation} got no reply within {seconds:g} s") from None
    if response["status"] != "completed":
        raise Stop(f"{host}: {operation} {response['status']}: {response['error']}")
    return response["result"]


def reconcile_operation(context: dict, operation_id: str) -> dict:
    """The recorded state of one operation on context's host, read without rerunning it."""
    if not _operation_id(operation_id) or operation_id.split("-", 1)[0] != context["host"]:
        raise Stop("operation id does not belong to this host")
    return _control(context["host"], context["mode"], "operation-status", operation_id)


def _settle(host, mode, operation_id, deadline, started):
    """After a lost reply, poll the durable record until it is final or time runs out."""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _Expired()
        try:
            status = _control(host, mode, "operation-status", operation_id,
                              max(1.0, min(CONTROL_SECONDS, remaining)))
        except Stop:
            if time.monotonic() >= deadline:
                raise _Expired() from None
            raise Unsettled(
                f"{host}: operation {operation_id} lost its reply and its status could not "
                "be read; it may still be running until its own deadline. Reconcile with "
                "operation-status before any retry", host=host, operation_id=operation_id,
                remote=None) from None
        if status["state"] in TERMINAL:
            return status["response"]
        if status["state"] == "owner-lost":
            raise Unsettled(
                f"{host}: operation {operation_id} lost its owner before it recorded "
                "completion; its recorded children may still be running. Run "
                "operation-cancel for it to stop them and record the interruption before any "
                "retry", host=host, operation_id=operation_id, remote=status)
        if (status["state"] == "unknown"
                and time.monotonic() > started + READ_SECONDS + GRACE_SECONDS):
            raise Stop(f"{host}: operation {operation_id} has no record there; it never "
                       "started")
        if time.monotonic() + POLL_SECONDS >= deadline:
            raise _Expired()
        time.sleep(POLL_SECONDS)


def _unsettled(host, mode, operation, operation_id, signum):
    """Explicitly cancel after a local deadline or signal, and say what is known."""
    cause = (f"was interrupted by {signal.Signals(signum).name}" if signum
             else "got no final reply within its timeout")
    kind = Interrupted if signum else Unsettled
    if operation in CONTROL:
        return kind(f"{host}: {operation} {cause}", host=host, operation_id=operation_id,
                    remote=None)
    try:
        remote = _control(host, mode, "operation-cancel", operation_id)
    except (Stop, _Signal):
        remote = None
    if remote is None:
        detail = ("operation-cancel did not reach it; it may still be running until its own "
                  "deadline. Reconcile with operation-status before any retry")
    elif remote["state"] == "running":
        detail = ("operation-cancel was requested and it is still running; reconcile with "
                  "operation-status before any retry")
    elif remote["state"] == "owner-lost":
        detail = ("its owner is gone and operation-cancel could not stop all its recorded "
                  "children; inspect them before any retry")
    else:
        detail = f"after operation-cancel it is {remote['state']}"
    return kind(f"{host}: operation {operation_id} ({operation}) {cause}; {detail}",
                host=host, operation_id=operation_id, remote=remote)


@contextmanager
def _raising_signals():
    """While a request runs on the main thread, INT, TERM and HUP become _Signal."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def interrupt(signum, frame):
        raise _Signal(signum)

    previous = {signum: signal.signal(signum, interrupt) for signum in INTERRUPTS}
    try:
        yield
    finally:
        for signum, handler in previous.items():
            if handler is not None:
                signal.signal(signum, handler)


def request(host: str, mode: str, operation: str, payload: dict, *, timeout: float) -> dict:
    """Run one operation on host and return its reply, whatever its status.

    A lost reply is reconciled from the operation's durable record without rerunning it; an
    owner that died before recording completion raises Unsettled naming operation-cancel.
    Past `timeout`, or on a local INT, TERM or HUP, this sends an explicit operation-cancel,
    reconciles and raises Unsettled or Interrupted naming what is known; an unreachable
    host is reported as possibly still running, never as stopped."""
    deadline = time.monotonic() + _positive(timeout)
    with _raising_signals():
        operation_id = None
        try:
            operation_id, process = start_request(host, mode, operation, payload,
                                                  timeout=timeout)
            started = time.monotonic()
            try:
                response = _await_reply(process, deadline)
                _abandon(process)
                if response is None:
                    if operation in CONTROL:
                        raise Stop(f"{host}: {operation} got no reply; see operations/"
                                   f"transport/{operation_id}.log")
                    response = _settle(host, mode, operation_id, deadline, started)
            except _Expired:
                raise _unsettled(host, mode, operation, operation_id, None) from None
            except _Signal as caught:
                raise _unsettled(host, mode, operation, operation_id, caught.signum) from None
            finally:
                _abandon(process)
        except _Signal as caught:
            raise Interrupted(
                f"{host}: {operation} was interrupted again by "
                f"{signal.Signals(caught.signum).name} during cleanup; its remote state is "
                "unknown. Reconcile with operation-status before any retry", host=host,
                operation_id=operation_id, remote=None) from None
    _check_response(response, host, mode, operation, operation_id)
    return response


# --- process ownership on the host ---------------------------------------------------------


def _proc_stat(pid):
    try:
        with open(f"/proc/{pid}/stat") as stream:
            fields = stream.read().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return None
    return {"state": fields[0], "pgrp": int(fields[2]), "session": int(fields[3]),
            "start_time": int(fields[19])}


def _start_time(pid):
    info = _proc_stat(pid)
    if info is None:
        raise Stop(f"process {pid} vanished before it was recorded")
    return info["start_time"]


def _alive(identity):
    info = _proc_stat(identity["pid"])
    return (info is not None and info["start_time"] == identity["start_time"]
            and info["state"] not in ("Z", "X"))


def _send(identity, signum):
    """Signal a process only while it is the recorded one (a pidfd pins its number)."""
    try:
        fd = os.pidfd_open(identity["pid"])
    except ProcessLookupError:
        return False
    try:
        if not _alive(identity):
            return False
        signal.pidfd_send_signal(fd, signum)
        return True
    except ProcessLookupError:
        return False
    finally:
        os.close(fd)


def _members(leader, since):
    """Live processes of the session and group an owned child leads."""
    found = []
    for name in os.listdir("/proc"):
        if name.isdigit():
            info = _proc_stat(name)
            if (info is not None and info["pgrp"] == leader and info["session"] == leader
                    and info["start_time"] >= since and info["state"] not in ("Z", "X")):
                found.append({"pid": int(name), "start_time": info["start_time"]})
    return found


def _stop_members(leader, since):
    """TERM, then KILL, every member; return any that survive both."""
    for signum in (signal.SIGTERM, signal.SIGKILL):
        members = _members(leader, since)
        if not members:
            return []
        for member in members:
            _send(member, signum)
        end = time.monotonic() + GRACE_SECONDS
        while time.monotonic() < end and _members(leader, since):
            time.sleep(0.02)
    return [member["pid"] for member in _members(leader, since)]


def _exited(pid):
    try:
        return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    except ChildProcessError:
        return True


class _Owned:
    """The operation's children: recorded on start, stopped and reaped before completion."""

    def __init__(self, directory):
        self.directory, self.children, self.live = directory, [], {}

    def save(self):
        state.save_record(self.directory / "children.json",
                          {"schema": 1, "children": self.children})

    def stop(self, process, child):
        # The unreaped leader keeps its number, so its group cannot be reused meanwhile.
        if child["start_time"] is not None:
            child["survivors"] = _stop_members(child["pid"], child["start_time"])
        else:
            process.kill()
        try:
            process.wait(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        self.live.pop(process.pid, None)

    def stop_all(self):
        for process, child in list(self.live.values()):
            self.stop(process, child)


def _collect(process, deadline):
    """Read a child's output until it exits or the deadline; True when it exited."""
    streams = {process.stdout.fileno(): bytearray(), process.stderr.fileno(): bytearray()}
    pending, exited_at = set(streams), None
    while pending:
        now = time.monotonic()
        if now >= deadline or (exited_at is not None and now - exited_at > DRAIN_SECONDS):
            break  # past the deadline, or descendants hold the pipes after the child exited
        ready, _, _ = select.select(list(pending), [], [], min(0.05, deadline - now))
        for fd in ready:
            chunk = os.read(fd, 65536)
            if not chunk:
                pending.discard(fd)
            elif len(streams[fd]) < MAX_OUTPUT:
                streams[fd] += chunk[:MAX_OUTPUT - len(streams[fd])]
        if exited_at is None and _exited(process.pid):
            exited_at = time.monotonic()
    while exited_at is None and time.monotonic() < deadline:
        if _exited(process.pid):
            exited_at = time.monotonic()
        else:
            time.sleep(0.02)
    out, err = (bytes(streams[stream.fileno()]) for stream in (process.stdout, process.stderr))
    return out, err, exited_at is not None


def _append(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def _child_path(value):
    remainder, rejected = [], 0
    for entry in value.split(":") if value else ():
        if not entry or not os.path.isabs(entry):
            rejected += 1
            continue
        entry = os.path.normpath(entry)
        if entry not in SYSTEM_PATH and entry not in remainder:
            remainder.append(entry)
    return remainder, rejected


def _child_env(context):
    """The helper's startup environment with the system PATH first and no bytecode."""
    env = dict(os.environ)
    remainder, _ = _child_path(env.get("PATH", ""))
    env["PATH"] = ":".join((*SYSTEM_PATH, *remainder))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_child(context, label, argv, *, env, timeout, cwd=None):
    """Run one owned child group to exit within its timeout and the operation's deadline.

    Its PID and start time are recorded before waiting; any descendants left in its group
    are stopped once it exits; its raw output goes only to the private log. `cwd` names an
    explicit working directory for tools that read it (npm ci installs where it runs)."""
    owned = context["owned"]
    remaining = context["deadline"] - time.monotonic()
    if remaining <= 0:
        raise _Deadline()
    limit = min(timeout, remaining)
    argv = [str(arg) for arg in argv]
    process = _launch(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE, env=env, start_new_session=True, close_fds=True,
                      **({"cwd": str(cwd)} if cwd is not None else {}))
    child = {"label": label, "pid": process.pid, "start_time": None, "started_at": _now(),
             "exit": None}
    owned.live[process.pid] = (process, child)
    try:
        child["start_time"] = _start_time(process.pid)
        owned.children.append(child)
        owned.save()
        out, err, exited = _collect(process, time.monotonic() + limit)
    finally:
        owned.stop(process, child)
    child["exit"] = process.returncode
    owned.save()
    note = "" if exited else f" (stopped after {limit:g} s)"
    _append(Path(context["operation_dir"]) / "log",
            f"== {_now()} {label}: {shlex.join(argv)} -> {process.returncode}{note}\n"
            .encode() + b"-- stdout\n" + out + b"\n-- stderr\n" + err + b"\n")
    if not exited and limit < timeout:
        raise _Deadline()  # the operation's own deadline, not the child's timeout
    if not exited:
        raise Stop(f"{label} did not exit within {limit:g} s; its process group was stopped")
    return subprocess.CompletedProcess(argv, process.returncode, out, err)


# --- the host entry ------------------------------------------------------------------------


def _nodename():
    return os.uname().nodename


def _context(host, mode, operation_id):
    home = _home()
    return {"host": host, "mode": mode, "operation_id": operation_id, "home": str(home),
            "root": str(home / ROOT), "hq": str(home / "d/hq"),
            "familiar": str(home / "d/familiar")}


def _response(context, operation, status, result=None, error=None, log=None):
    return {"schema": 1, "host": context["host"], "mode": context["mode"],
            "operation": operation, "operation_id": context["operation_id"], "status": status,
            "result": result, "error": error, "log": log}


def _observe(directory, start):
    done = directory / "done.json"
    record = state.load_record(done) if os.path.lexists(done) else None
    if record is not None:
        observed = record["response"]["status"]
    else:
        observed = "running" if _alive(start["owner"]) else "owner-lost"
    return {"operation_id": start["operation_id"], "operation": start["operation"],
            "state": observed, "response": record["response"] if record else None,
            "cancel_requested": os.path.lexists(directory / "cancel.json")}


def _recorded(context, target):
    directory = Path(context["root"]) / "operations" / target
    if not os.path.lexists(directory):
        return directory, None
    start = state.load_record(directory / "start.json")
    if start["mode"] != context["mode"]:
        raise Refused(f"operation {target} was recorded in another mode")
    return directory, start


def _status(context, target):
    directory, start = _recorded(context, target)
    if start is None:
        return {"operation_id": target, "operation": None, "state": "unknown",
                "response": None, "cancel_requested": False}
    return _observe(directory, start)


def _cancel(context, target):
    """Stop one recorded operation: signal a live owner, or reconcile a dead one's children."""
    directory, start = _recorded(context, target)
    if start is None:
        return _status(context, target)
    observed = _observe(directory, start)
    if observed["response"] is not None:
        return observed
    if not os.path.lexists(directory / "cancel.json"):
        state.save_record(directory / "cancel.json",
                          {"schema": 1, "operation_id": target, "requested_at": _now(),
                           "request": context["operation_id"]})
    if observed["state"] == "running" and _send(start["owner"], signal.SIGTERM):
        end = time.monotonic() + CANCEL_WAIT_SECONDS
        while (time.monotonic() < end and not os.path.lexists(directory / "done.json")
               and _alive(start["owner"])):
            time.sleep(0.05)
    observed = _observe(directory, start)
    if observed["state"] != "owner-lost":
        return observed
    operations = directory.parent
    with state._locked(operations):
        if not os.path.lexists(directory / "done.json"):
            children = directory / "children.json"
            recorded = state.load_record(children)["children"] if os.path.lexists(children) else []
            survivors = [pid for child in recorded if child["start_time"] is not None
                         for pid in _stop_members(child["pid"], child["start_time"])]
            if survivors:
                return {**observed, "survivors": survivors}
            owner = {**context, "mode": start["mode"], "operation_id": target}
            response = _response(owner, start["operation"], "interrupted", error=(
                "its owner ended without recording completion; operation-cancel stopped its "
                "recorded children"))
            state.save_record(directory / "done.json",
                              {"schema": 1, "response": response, "finished_at": _now(),
                               "reconciled_by": context["operation_id"]})
    return _observe(directory, start)


def _begin(context, operation, spec, payload):
    """Record the start durably, refusing a reused ID or a mutation beside unfinished work."""
    operations = Path(context["root"]) / "operations"
    directory = operations / context["operation_id"]
    try:
        state._make_dirs(operations)
        state._check_dir(operations)
        with state._locked(operations):
            if os.path.lexists(directory):
                raise Refused(f"operation {context['operation_id']} is already recorded; "
                              "query operation-status instead of resending it")
            if spec.mutation:
                for entry in sorted(os.listdir(operations)):
                    if entry == "transport":
                        continue
                    if not OPERATION_ID.fullmatch(entry):
                        raise Refused(f"{operations}: unexplained entry; reconcile it")
                    other = operations / entry
                    if os.path.lexists(other / "done.json"):
                        continue
                    start = state.load_record(other / "start.json")
                    raise Refused(
                        f"operation {entry} ({start['operation']}) is "
                        f"{_observe(other, start)['state']}; reconcile it with "
                        "operation-status or operation-cancel before another mutation")
            state.save_record(directory / "start.json", {
                "schema": 1, "operation_id": context["operation_id"], "operation": operation,
                "mode": context["mode"], "host": context["host"], "mutation": spec.mutation,
                "payload": payload, "deadline_seconds": spec.deadline, "started_at": _now(),
                "owner": {"pid": os.getpid(), "start_time": _start_time(os.getpid())}})
    except Refused:
        raise
    except Stop as error:
        raise Refused(str(error)) from None
    return directory


class _Interrupts:
    """The first INT, TERM, HUP or deadline alarm interrupts the operation; later ones and
    any after it returns are absorbed so that completion is always recorded."""

    def __init__(self):
        self.open, self.previous = True, {}

    def handle(self, signum, frame):
        if self.open:
            self.open = False
            raise _Deadline() if signum == signal.SIGALRM else _Signal(signum)

    def arm(self, seconds):
        for signum in WATCHED:
            self.previous[signum] = signal.signal(signum, self.handle)
        signal.setitimer(signal.ITIMER_REAL, seconds)

    def disarm(self, mask):
        signal.setitimer(signal.ITIMER_REAL, 0)
        for signum, handler in self.previous.items():
            if handler is not None:
                signal.signal(signum, handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)


def _outcome(caught, directory, deadline):
    if isinstance(caught, _Deadline):
        return ("timed-out", None,
                f"its deadline of {deadline:g} s passed; its children were stopped")
    if os.path.lexists(directory / "cancel.json"):
        return "cancelled", None, "cancelled by operation-cancel; its children were stopped"
    return ("cancelled", None,
            f"stopped by {signal.Signals(caught.signum).name}; its children were stopped")


def _invoke(spec, context, directory, mask):
    try:
        # A signal held back while the start was recorded is delivered here, and cancels.
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        return "completed", spec.run(context), None
    except (_Deadline, _Signal) as caught:
        return _outcome(caught, directory, spec.deadline)
    except Stop as stop:
        return "failed", None, str(stop)
    except Exception:
        _append(directory / "log", traceback.format_exc().encode())
        return "failed", None, "unexpected error; see the private log"


def execute(context: dict, operation: str, payload: dict) -> dict:
    """Run one validated operation on this host and return its reply.

    Status and cancel read or reconcile another operation's record. Every other operation
    records its start, runs with its deadline and owned children, then records its reply."""
    spec = _spec(operation)
    _check_payload(spec, payload)
    if operation in CONTROL:
        target = payload["operation_id"]
        if target.split("-", 1)[0] != context["host"]:
            raise Refused("operation id belongs to another host")
        result = (_status if operation == "operation-status" else _cancel)(context, target)
        return _response(context, operation, "completed", result)
    if threading.current_thread() is not threading.main_thread():
        raise Refused("operations run on the main thread, which owns signals and deadlines")
    # Before this, a signal ends the process with nothing recorded; from here it waits
    # until the start record is whole and then cancels the operation.
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, WATCHED)
    try:
        directory = _begin(context, operation, spec, payload)
    except BaseException:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        raise
    owned = _Owned(directory)
    run = {**context, "payload": payload, "operation_dir": str(directory),
           "deadline": time.monotonic() + spec.deadline, "owned": owned}
    interrupts = _Interrupts()
    interrupts.arm(spec.deadline)
    try:
        try:
            status, result, error = _invoke(spec, run, directory, mask)
            interrupts.open = False
        except (_Deadline, _Signal) as caught:  # it landed after the operation returned
            status, result, error = _outcome(caught, directory, spec.deadline)
        owned.stop_all()
        log = directory / "log"
        response = _response(context, operation, status, result, error,
                             str(log) if os.path.lexists(log) else None)
        state.save_record(directory / "done.json",
                          {"schema": 1, "response": response, "finished_at": _now(),
                           "children": owned.children})
    finally:
        interrupts.disarm(mask)
    return response


def _read_request():
    data, end = bytearray(), time.monotonic() + READ_SECONDS
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            raise Refused(f"incomplete request: input did not end within {READ_SECONDS} s")
        ready, _, _ = select.select([0], [], [], remaining)
        if not ready:
            continue
        chunk = os.read(0, 65536)
        if not chunk:
            return bytes(data)
        data += chunk
        if len(data) > MAX_REQUEST:
            raise Refused(f"request exceeds {MAX_REQUEST} bytes")


def _reply(response):
    view = memoryview(_encode(response) + b"\n")
    try:
        while view:
            view = view[os.write(1, view):]
    except OSError:
        pass  # the connection dropped; the durable record already holds this reply


def serve() -> int:
    """The fixed host entry: one bounded request on stdin, one reply on stdout."""
    host, envelope, checked = _nodename(), None, False
    try:
        try:
            envelope = _decode(_read_request())
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise Refused("request is not one JSON object") from None
        target = _check_envelope(envelope)
        checked = True
        if target != host:
            raise Refused("request names another host; check the SSH route")
        if envelope["helper_sha256"] != helper_digest():
            raise Refused("helper-drift: this host's helper package differs from the "
                          "controller's; deliver matching helpers before use")
        response = execute(_context(host, envelope["mode"], envelope["operation_id"]),
                           envelope["operation"], envelope["payload"])
    except Stop as stop:
        context = {"host": host, "mode": envelope["mode"] if checked else None,
                   "operation_id": envelope["operation_id"] if checked else None}
        response = _response(context, envelope["operation"] if checked else None,
                             "refused" if isinstance(stop, Refused) else "failed",
                             error=str(stop))
    _reply(response)
    return {"completed": 0, "refused": 2}.get(response["status"], 1)


CONTROL = {name: Operation(run=None, deadline=0, mutation=False,
                           payload={"operation_id": _operation_id},
                           required=frozenset({"operation_id"}))
           for name in ("operation-status", "operation-cancel")}
