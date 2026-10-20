"""Protected cutover state: windows, the touched-target ledger and consumed decisions.

Records live under the private cutover root as 0700 directories and 0600 files owned
by this user. Every write is atomic or exclusive and syncs its parent directory,
including each directory it creates, before returning. Reads refuse symlinks, other
owners, loose modes and anything but a schema 1 JSON object."""
import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

STATES = ("prepared", "quiescing", "applying", "migrated-surfaces-pending",
          "ready-for-smokes", "finishing", "complete", "aborting", "aborted",
          "abort-incomplete", "recovery-required", "recovering", "recovered",
          "inspection-required")
# A window in one of these states no longer blocks a fresh one; its directory stays.
TERMINAL = ("complete", "aborted", "recovered")
MODES = ("live", "pilot")
TARGET_IDS = ("claude", "claude-work", "codex", "codex-work")
KINDS = ("desktop", "smoke-attestation")
# The original cutover's explained state: inventory to preserve, never a window.
# Directories end in "/". Anything else at the top level needs reconciliation.
RETAINED = (
    "section1-abort.l0b7qF/", "operator-env.sh", "prep/", "task7/", "rehearsal/",
    "familiar-rehearsal/", "familiar-rehearsal-v2/",
    "expected-images.sha256", "live-before.sha256", "preparation-backups.json",
    "targets.txt",                                    # preparation manifests
    "images/", "claude-work.after.json",              # image directory
    "familiar-node_modules.pre/", "familiar-state/",  # retained original backups
)
LAYOUT = ("windows/", "active.json")
WINDOW_KEYS = ("schema", "id", "mode", "state", "directory", "created_at",
               "prepared_sha256")
DECISION_KEYS = {"schema", "kind", "action", "window_id", "attempt_id",
                 "subject_sha256", "verdict", "source"}
SOURCE_KEYS = {"tty": {"type", "prompt", "response", "answered_at"},
               "session": {"type", "session_id", "ask", "reply", "answered_at"}}
RESERVED = ("window.json", "touched.tsv", "decisions")
SHA256 = re.compile(r"[0-9a-f]{64}")
WINDOW_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")
ATTEMPT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class Stop(Exception):
    pass


def _is_one(value):
    return type(value) is int and value == 1


def _owned(info, path, mode):
    if info.st_uid != os.geteuid():
        raise Stop(f"{path}: not owned by this user")
    if mode is not None and stat.S_IMODE(info.st_mode) != mode:
        raise Stop(f"{path}: mode {stat.S_IMODE(info.st_mode):04o}, expected {mode:04o}")


def _check_dir(path):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise Stop(f"{path}: missing") from None
    if not stat.S_ISDIR(info.st_mode):
        raise Stop(f"{path}: not a directory (symlinks are refused)")
    _owned(info, path, 0o700)


def _read(path, mode=0o600):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        raise Stop(f"{path}: missing") from None
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise Stop(f"{path}: is a symlink") from None
        raise
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise Stop(f"{path}: not a regular file")
        _owned(info, path, mode)
    except BaseException:
        os.close(fd)
        raise
    with os.fdopen(fd, "rb") as stream:
        return stream.read()


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _make_dirs(path):
    missing = []
    while not os.path.lexists(path):
        missing.append(path)
        path = path.parent
    for directory in reversed(missing):
        os.mkdir(directory, 0o700)
        # The new entry is durable in its parent before anything is written inside it.
        _sync(directory.parent)


@contextmanager
def _locked(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop(f"{directory}: another invocation holds it; retry after it exits") from None
        yield
    finally:
        os.close(fd)


def _temp(path, data):
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        os.unlink(name)
        raise
    return Path(name)


def _atomic_write(path, data):
    temp = _temp(path, data)
    try:
        os.replace(temp, path)
        _sync(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _exclusive_write(path, data):
    temp = _temp(path, data)
    try:
        try:
            os.link(temp, path)
        except FileExistsError:
            raise Stop(f"{path}: already exists") from None
        _sync(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode()).hexdigest()


def _unique(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate key")
    return dict(pairs)


def _constant(name):
    raise ValueError(f"non-finite number {name}")


def _timestamp(value, label):
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise Stop(f"{label} is not an ISO 8601 time") from None
    if moment.tzinfo is None:
        raise Stop(f"{label} needs a timezone")
    return moment


def load_record(path: Path) -> dict:
    path = Path(path)
    _check_dir(path.parent)
    data = _read(path)
    try:
        value = json.loads(data, object_pairs_hook=_unique, parse_constant=_constant)
    except ValueError as error:
        raise Stop(f"{path}: invalid JSON ({error})") from None
    if not isinstance(value, dict) or not _is_one(value.get("schema")):
        raise Stop(f"{path}: expected a schema 1 JSON object")
    return value


def save_record(path: Path, value: dict) -> None:
    path = Path(path)
    if not isinstance(value, dict) or not _is_one(value.get("schema")):
        raise Stop(f"{path}: refusing a record that is not a schema 1 object")
    try:
        data = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                + "\n").encode()
    except (TypeError, ValueError) as error:
        raise Stop(f"{path}: record is not plain JSON ({error})") from None
    _make_dirs(path.parent)
    _check_dir(path.parent)
    if os.path.lexists(path):
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):
            raise Stop(f"{path}: not a regular file")
        _owned(info, path, 0o600)
    _atomic_write(path, data)


def _check_window(window):
    if (not isinstance(window, dict) or not set(WINDOW_KEYS) <= window.keys()
            or not _is_one(window["schema"])):
        raise Stop("window record lacks its schema 1 fields")
    identity, directory = window["id"], window["directory"]
    if (not isinstance(identity, str) or not WINDOW_ID.fullmatch(identity)
            or window["mode"] not in MODES or not isinstance(directory, str)
            or not os.path.isabs(directory) or Path(directory).name != identity
            or not isinstance(window["prepared_sha256"], str)
            or not SHA256.fullmatch(window["prepared_sha256"])):
        raise Stop("window record has invalid identity fields")
    if not isinstance(window["state"], str) or window["state"] not in STATES:
        raise Stop(f"window {identity}: unknown state {window['state']!r}; inspect it")
    _timestamp(window["created_at"], f"window {identity} created_at")


def _load_window(windows, name):
    if not WINDOW_ID.fullmatch(name):
        raise Stop(f"{windows}: unexplained entry {name}; reconcile it")
    window = load_record(windows / name / "window.json")
    _check_window(window)
    if window["id"] != name or window["directory"] != str(windows / name):
        raise Stop(f"{windows / name}: record names another window; reconcile it")
    return window


def current_window(root: Path) -> dict | None:
    """The window the active pointer names, after refusing unexplained root state."""
    root = Path(root)
    if not root.is_absolute():
        raise Stop(f"{root}: cutover root must be absolute")
    if not os.path.lexists(root):
        return None
    _check_dir(root)
    names = RETAINED + LAYOUT
    blockers = []
    for entry in sorted(os.listdir(root)):
        info = os.lstat(root / entry)
        if not ((stat.S_ISDIR(info.st_mode) and entry + "/" in names)
                or (stat.S_ISREG(info.st_mode) and entry in names)):
            blockers.append(entry)
    if blockers:
        raise Stop(f"{root}: unexplained state needs reconciliation: {', '.join(blockers)}")
    windows = {}
    if os.path.lexists(root / "windows"):
        _check_dir(root / "windows")
        for name in sorted(os.listdir(root / "windows")):
            windows[name] = _load_window(root / "windows", name)
    active = None
    if os.path.lexists(root / "active.json"):
        pointer = load_record(root / "active.json")
        if set(pointer) != {"schema", "window"} or pointer["window"] not in windows:
            raise Stop(f"{root / 'active.json'}: does not name a recorded window; reconcile it")
        active = windows[pointer["window"]]
    for name, window in windows.items():
        if window is not active and window["state"] not in TERMINAL:
            raise Stop(f"window {name} is {window['state']} but not active; reconcile it")
    return active


def new_window(root: Path, prepared_sha256: str, *, mode: str = "live") -> dict:
    """Allocate a unique window directory and make it the single active window."""
    root = Path(root)
    if not root.is_absolute():
        raise Stop(f"{root}: cutover root must be absolute")
    if not isinstance(prepared_sha256, str) or not SHA256.fullmatch(prepared_sha256):
        raise Stop("prepared_sha256 must be a lowercase SHA-256 digest")
    if mode not in MODES:
        raise Stop(f"unknown window mode {mode!r}")
    _make_dirs(root)
    _check_dir(root)
    with _locked(root):
        current = current_window(root)
        if current is not None and current["state"] not in TERMINAL:
            raise Stop(f"window {current['id']} is {current['state']}; reconcile, abort "
                       "or recover it before a new window")
        windows = root / "windows"
        _make_dirs(windows)
        now = datetime.now(timezone.utc)
        identity = f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        directory = windows / identity
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            raise Stop(f"{directory}: window id collision; retry") from None
        _sync(windows)
        window = {"schema": 1, "id": identity, "mode": mode, "state": "prepared",
                  "directory": str(directory),
                  "created_at": now.isoformat(timespec="seconds"),
                  "prepared_sha256": prepared_sha256}
        save_record(directory / "window.json", window)
        save_record(root / "active.json", {"schema": 1, "window": identity})
    return window


def _current(window):
    _check_window(window)
    directory = Path(window["directory"])
    if directory.parent.name != "windows":
        raise Stop(f"{directory}: not a window directory")
    if current_window(directory.parent.parent) != window:
        raise Stop(f"window {window['id']}: record changed on disk or is not active; "
                   "reload it")
    return directory


def read_ledger(window: dict) -> list[dict]:
    """Registered targets in order; a torn or unexplained entry is a blocker."""
    _check_window(window)
    directory = Path(window["directory"])
    path = directory / "touched.tsv"
    if not os.path.lexists(path):
        return []
    try:
        text = _read(path).decode()
    except UnicodeDecodeError:
        raise Stop(f"{path}: unreadable entry; reconcile the ledger before any target "
                   "write or restore") from None
    if text and not text.endswith("\n"):
        raise Stop(f"{path}: torn final entry; reconcile the ledger before any target "
                   "write or restore")
    entries = []
    for number, line in enumerate(text.split("\n")[:-1], 1):
        fields = line.split("\t")
        if (len(fields) != 3 or fields[0] not in TARGET_IDS
                or not all(os.path.isabs(field) for field in fields[1:])
                or fields[0] in (entry["target_id"] for entry in entries)):
            raise Stop(f"{path}: line {number} is not a complete entry; reconcile the ledger")
        original = directory / f"{fields[0]}.original"
        info = os.lstat(original) if os.path.lexists(original) else None
        if info is None or not stat.S_ISREG(info.st_mode):
            raise Stop(f"{path}: line {number}: {fields[0]} has no original; reconcile it")
        _owned(info, original, 0o600)
        entries.append({"target_id": fields[0], "target": fields[1],
                        "artifact": fields[2], "original": str(original)})
    return entries


def _append(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
                 | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise Stop(f"{path}: not a regular file")
        _owned(info, path, 0o600)
        if os.write(fd, data) != len(data):
            raise Stop(f"{path}: short append; reconcile the ledger")
        os.fsync(fd)
    finally:
        os.close(fd)
    _sync(path.parent)


def register_target(window: dict, target_id: str, target: Path, artifact: Path) -> None:
    """Durably keep the target's original and append its ledger entry before any write."""
    directory = _current(window)
    if window["state"] != "applying":
        raise Stop(f"window {window['id']} is {window['state']}; targets register only "
                   "while applying")
    if target_id not in TARGET_IDS:
        raise Stop(f"unknown target id {target_id!r}")
    target, artifact = Path(target), Path(artifact)
    if not target.is_absolute() or os.path.realpath(target) != str(target):
        raise Stop(f"{target_id}: target must be its resolved absolute path")
    real = os.path.realpath(directory)
    if (not artifact.is_absolute() or os.path.normpath(artifact) != str(artifact)
            or not artifact.is_relative_to(directory)
            or os.path.realpath(artifact.parent)
            != os.path.join(real, *artifact.parent.relative_to(directory).parts)):
        raise Stop(f"{artifact}: artifact must be a plain path inside the window directory")
    relative = artifact.relative_to(directory)
    if (relative.parts[0] in RESERVED or artifact.suffix != ".json"
            or artifact.name.endswith(".original")):
        raise Stop(f"{artifact}: artifact uses a reserved window name")
    if any(field in str(path) for path in (target, artifact) for field in "\t\n"):
        raise Stop(f"{target_id}: ledger paths cannot hold tabs or newlines")
    for entry in read_ledger(window):
        if entry["target_id"] == target_id:
            raise Stop(f"{target_id} is already registered in this window")
        if entry["artifact"] == str(artifact):
            raise Stop(f"{artifact}: artifact is already registered for {entry['target_id']}")
    original = directory / f"{target_id}.original"
    for path in (original, artifact):
        if os.path.lexists(path):
            raise Stop(f"{path}: already exists without a ledger entry; reconcile it")
    data = _read(target, mode=None)
    _make_dirs(artifact.parent)
    _exclusive_write(original, data)
    _append(directory / "touched.tsv",
            "\t".join((target_id, str(target), str(artifact))).encode() + b"\n")


def _check_source(source, window):
    if (not isinstance(source, dict) or not isinstance(source.get("type"), str)
            or set(source) != SOURCE_KEYS.get(source["type"])):
        raise Stop("decision source must be an operator tty response or a session ask "
                   "and reply")
    for key in sorted(source.keys() - {"type"}):
        if not isinstance(source[key], str) or not source[key].strip():
            raise Stop(f"decision source {key} is empty; record the actual ask and reply")
    answered = _timestamp(source["answered_at"], "decision answered_at")
    if answered < _timestamp(window["created_at"], "window created_at"):
        raise Stop("decision was answered before this window existed; ask again")


def consume_decision(window: dict, decision: dict, *, kind: str, action: str,
                     attempt_id: str, subject_sha256: str) -> dict:
    """Bind one recorded human decision to one attempt, durably, before it authorizes."""
    directory = _current(window)
    if window["state"] in TERMINAL:
        raise Stop(f"window {window['id']} is {window['state']}; nothing can be authorized")
    if (kind not in KINDS or not isinstance(action, str) or not action
            or not isinstance(attempt_id, str) or not ATTEMPT_ID.fullmatch(attempt_id)
            or not isinstance(subject_sha256, str) or not SHA256.fullmatch(subject_sha256)):
        raise Stop("invalid decision request")
    if decision is None:
        raise Stop("decision absent: ask in the session or at the operator's terminal, "
                   "record the reply and pass --decision-file")
    if (not isinstance(decision, dict) or set(decision) != DECISION_KEYS
            or not _is_one(decision["schema"])):
        raise Stop("decision record does not match schema 1")
    expected = {"kind": kind, "action": action, "window_id": window["id"],
                "attempt_id": attempt_id, "subject_sha256": subject_sha256}
    for key, value in expected.items():
        if decision[key] != value:
            raise Stop(f"decision {key} does not match this invocation; ask again")
    if decision["verdict"] == "declined":
        raise Stop("decision declined; nothing is authorized")
    if decision["verdict"] != "approved":
        raise Stop("decision verdict must be approved or declined")
    _check_source(decision["source"], window)
    record = {"schema": 1, "window_id": window["id"], "attempt_id": attempt_id,
              "kind": kind, "action": action, "subject_sha256": subject_sha256,
              "prepared_sha256": window["prepared_sha256"],
              "decision_sha256": _digest(decision),
              "reply_sha256": _digest(decision["source"]),
              "consumed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "decision": decision}
    decisions = directory / "decisions"
    _make_dirs(decisions)
    _check_dir(decisions)
    with _locked(decisions):
        for name in sorted(os.listdir(decisions)):
            if not name.endswith(".json") or not ATTEMPT_ID.fullmatch(name[:-5]):
                raise Stop(f"{decisions}: unexplained entry {name}; reconcile it")
            consumed = load_record(decisions / name)
            if consumed.get("attempt_id") == attempt_id:
                raise Stop(f"attempt {attempt_id} already consumed a decision; ask again "
                           "for a new attempt")
            if consumed.get("reply_sha256") == record["reply_sha256"]:
                raise Stop(f"this reply was already consumed by attempt "
                           f"{consumed.get('attempt_id')}; ask again")
        _exclusive_write(decisions / f"{attempt_id}.json",
                         (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode())
    return record
