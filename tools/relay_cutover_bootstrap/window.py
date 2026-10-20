"""The cutover window on the controller: preparation, eligibility, quiescence and the
pre-merge abort.

`prepare` reads each host through `inputs-check` and `inventory`, Titan first, and stops at the
first host with blockers. It writes only `prepared.json` at the cutover root and opens no
window. The record holds the manifest's path, generation and digest, its pins and helper
digests, the pick keys of the manifest-verified clean filter, and the controller's checkout,
native session ID and helper digests. Per host it holds the resolved home, root and hq
paths; the toolchain and the install PATH (`/usr/bin:/bin:` and the validated remainder);
the cache prefixes; Claude's identity and versions (and Codex's on Titan); the desktop
inventory; the live Claude and Codex processes, which are future run blockers and never a
reason to refuse preparation; and for each target its resolved path, current digest, pick
values and absent pick keys, and the reviewed member digests. No expected after-image is
built. `check` repeats the reads and compares them with that record; it writes only private
operation records. `recheck` is the same comparison as the run's gate.

A run (Task 4) opens the window with `open_window`, takes the operator's desktop decision in
that invocation, consumes it with `state.consume_decision` and passes the consumed record to
`quiesce_window`. Quiescing runs these steps, each recorded in the window before its request:

1. stop Titan's two Codex daemons with their CLI;
2. strict no-live on both hosts;
3. record and stop each host's timers;
4. wait for their services;
5. strict no-live again;
6. refresh the familiar snapshots.

It returns the quiescent window, still `quiescing`, before any familiar or settings change.

Any failure from `quiescing`, or an INT, TERM or HUP, aborts every host the window touched.
The abort cancels and reconciles the window's pending operations, restores timers from their
records and then returns the snapshots. The window goes `aborting` → `aborted`, or to
`abort-incomplete` when a host cannot finish, including after a second interruption.
`abort_window` is also how the next invocation reconciles after SIGKILL or an incomplete abort,
and how it clears a window that a crash left `prepared`. It refuses a window whose recorded
owner is still running, and any window past the pre-merge boundary. Task 4 must record
`familiar` in the window before its merge begins.

Keys this module adds to the window record:

- `owner` {pid, start_time} and `decision`;
- `attempts` [{host, step, at}];
- `timers` {host: {sha256, recorded_at}}, with copies at `hosts/<host>/timers.json`;
- `quiescent`, `failure`, `abort` and `earlier_aborts` (each incomplete abort's record).

The window directory also keeps the prepared record as `prepared.json`."""
import os
import re
import signal
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import hosts, inputs, inventory, operations, state
from .state import Stop

HOST_ORDER = ("titan", "europa")
PREPARED = "prepared.json"
RUN_ACTION = "run"
BOOTSTRAP = "tools/relay-cutover-bootstrap"
CHECKOUT = Path(__file__).resolve().parents[2]  # the controller's checkout
SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
SESSION_PLACEHOLDER = "<native-session-id>"
ABORTABLE = ("prepared", "quiescing", "applying", "aborting", "abort-incomplete")
MARGIN = 60
NOTHING = "nothing was changed; no window is open"


class Failed(Stop):
    """A stopped step as the operator sees it: no settings, plans, environments or child
    output, only tool-authored text, the private log path and one next command."""

    def __init__(self, step, host, status, error, *, log=None, blockers=(), observed=None,
                 next_command=None):
        super().__init__(f"{step} on {host}: {status}: {error}")
        self.step, self.host, self.status, self.error = step, host, status, error
        self.log, self.blockers = log, list(blockers)
        self.observed, self.next_command = observed, next_command


class _Interrupt(BaseException):
    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _root():
    return hosts._home() / hosts.ROOT


def prepared_sha256(prepared: dict) -> str:
    return state._digest(prepared)


def _me():
    pid = os.getpid()
    return {"pid": pid, "start_time": hosts._start_time(pid)}


def _log(host, path):
    if path is None:
        return None
    return f"{host}:{path}" if hosts.HOSTS[host]["remote"] else path


def _call(host, mode, operation, payload, step):
    """One host operation's result and log, or Failed naming the step."""
    spec = operations.OPERATIONS.get(operation)
    timeout = spec.deadline + MARGIN if spec is not None else hosts.CONTROL_SECONDS
    try:
        response = hosts.request(host, mode, operation, payload, timeout=timeout)
    except hosts.Interrupted as error:
        raise Failed(step, host, "interrupted", str(error)) from None
    except hosts.Unsettled as error:
        raise Failed(step, host, "unsettled", str(error)) from None
    except hosts.Refused as error:
        raise Failed(step, host, "refused", str(error)) from None
    except Stop as error:
        raise Failed(step, host, "failed", str(error)) from None
    log = _log(host, response["log"])
    if response["status"] != "completed":
        raise Failed(step, host, response["status"], response["error"] or "no detail recorded",
                     log=log)
    return response["result"], log


@contextmanager
def _signals():
    """Between requests, INT, TERM and HUP are noted here and raised at the next step; during a
    request, `hosts.request` turns them into an explicit cancel and Interrupted."""
    seen = []
    if threading.current_thread() is not threading.main_thread():
        yield seen
        return
    previous = {signum: signal.signal(signum, lambda signum, frame: seen.append(signum))
                for signum in hosts.INTERRUPTS}
    try:
        yield seen
    finally:
        for signum, handler in previous.items():
            if handler is not None:
                signal.signal(signum, handler)


def _save(window, **changes):
    """Durably update the active window; signals wait until the record is whole."""
    state._current(window)
    updated = {**window, **changes}
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, hosts.INTERRUPTS)
    try:
        state.save_record(Path(window["directory"]) / "window.json", updated)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
    return updated


# --- observation and comparison ------------------------------------------------------------


def _observe(host, *, active, complete):
    """A host's inputs-check and inventory, with every blocker prefixed by the host. Without
    `complete`, inventory is skipped once the inputs already block."""
    payload = {"commits": host == "titan", **({"active": active} if active else {})}
    found, log = _call(host, "live", "inputs-check", payload, "inputs-check")
    manifest = found["manifest"]["content"] if found["manifest"] else None
    seen = {"inputs": found, "manifest": manifest, "inventory": None, "step": None, "log": None,
            "blockers": [f"{host}: {blocker}" for blocker in found["blockers"]]}
    if seen["blockers"]:
        seen.update(step="inputs-check", log=log)
        if not complete:
            return seen
    reason = manifest["hosts"][host]["absence_reason"] if manifest else None
    report, log = _call(host, "live", "inventory",
                        {"absence_reason": reason} if reason else {}, "inventory")
    seen["inventory"] = report
    more = [f"{host}: {blocker}" for blocker in report["blockers"]]
    more += _host_blockers(host, manifest, report)
    if more and seen["step"] is None:
        seen.update(step="inventory", log=log)
    seen["blockers"] += more
    return seen


def _differing(expected, actual):
    expected, actual = expected or {}, actual or {}
    return sorted(key for key in set(expected) | set(actual)
                  if expected.get(key) != actual.get(key))


def _helper_drift(expected, actual):
    drift, members = [], (actual or {}).get("members") or {}
    for name in sorted(set(expected["members"]) | set(members)):
        if members.get(name) != expected["members"].get(name):
            drift.append(f"{name} is missing" if members.get(name) is None
                         else f"{name} is not in the manifest"
                         if name not in expected["members"]
                         else f"{name} differs from the manifest")
    if (actual or {}).get("package_sha256") != expected["package_sha256"]:
        drift.append("the helper package differs from the manifest")
    return drift


def _claude_versions(report):
    claude = ((report or {}).get("harnesses") or {}).get("claude") or {}
    return sorted({(entry or {}).get("version") or "none"
                   for entry in (claude.get("homes") or {}).values()} or {"none"})


def _host_blockers(host, manifest, report):
    """The host's inventory against the reviewed manifest: toolchain, helpers, pins."""
    if manifest is None:
        return []
    found = []
    toolchain = report.get("toolchain") or {}
    for name, expected in sorted(manifest["hosts"][host]["toolchain"].items()):
        fields = _differing(expected, toolchain.get(name))
        if fields:
            found.append(f"{host}: toolchain: {name} differs from the reviewed manifest "
                         f"({', '.join(fields)}); prepare fresh proof, without updating host "
                         "packages")
    found += [f"{host}: helpers: {drift}; deliver matching helpers to main first"
              for drift in _helper_drift(manifest["helpers"], report.get("helpers"))]
    pins = manifest["pins"]
    if (report.get("git_auth") or {}).get("pin") != pins["familiar_theme"]:
        found.append(f"{host}: pins: familiar-theme is not pinned to the manifest's commit")
    versions = _claude_versions(report)
    if versions != [pins["claude_version"]]:
        found.append(f"{host}: version: Claude reports {', '.join(versions)}; the reviewed "
                     f"evidence is {pins['claude_version']}; align the hosts and refresh the "
                     "evidence first")
    if hosts.HOSTS[host]["codex"]:
        codex = ((report.get("harnesses") or {}).get("codex") or {}).get("version")
        if codex != pins["codex_version"]:
            found.append(f"{host}: version: Codex reports {codex or 'none'}; the reviewed "
                         f"evidence is {pins['codex_version']}")
    return found


def _cross_host(seen):
    found = []
    digests = {host: (seen[host]["inputs"]["manifest"] or {}).get("sha256") for host in seen}
    if len(set(digests.values())) != 1:
        found.append("both: sync: the designated manifests differ between titan and europa; "
                     "stage the same generation on both")
    for target_id in inputs.CLAUDE_TARGETS:
        current = {(seen[host]["inputs"]["targets"].get(target_id) or {}).get("sha256")
                   for host in seen}
        if len(current) != 1:
            found.append(f"both: sync: {target_id} differs between titan and europa; wait for "
                         "synchronization and rerun")
    return found


def _controller_helpers():
    return inventory._helpers({"hq": str(CHECKOUT), "home": str(hosts._home())})


def _sessions(report):
    processes = (report or {}).get("processes") or {}
    return sorted(({**entry, "held": entry.get("held")}
                   for entry in processes.get("known", []) + processes.get("unknown", [])),
                  key=lambda entry: entry["pid"])


def _identity(harness):
    """A harness executable's identity: Claude's per-home versions, or Codex's one version."""
    found = {key: harness.get(key) for key in ("path", "real", "sha256")}
    if "version" in harness:  # Codex; its homes are only present or absent
        found["version"] = harness["version"]
    elif isinstance(harness.get("homes"), dict):
        found["versions"] = {name: (entry or {}).get("version")
                             for name, entry in harness["homes"].items()}
    return found


def _host_record(observed):
    report = observed["inventory"]
    home = Path(report["identity"]["home"])
    record = {
        "home": str(home), "root": str(home / hosts.ROOT), "hq": str(home / "d/hq"),
        "observed_at": report["observed_at"], "identity": report["identity"],
        "toolchain": report["toolchain"],
        "install": {"npm": report["toolchain"]["npm"]["path"],
                    "node": report["toolchain"]["node"]["path"], "path": report["path"]["child"]},
        "caches": report["caches"], "user_bus": report["user_bus"],
        "git_auth": report["git_auth"], "claude": _identity(report["harnesses"]["claude"]),
        "desktop": report["desktop"], "sessions": _sessions(report),
        "targets": observed["inputs"]["targets"]}
    if "codex" in report["harnesses"]:
        record["codex"] = _identity(report["harnesses"]["codex"])
    return record


def _drift(host, prepared, observed):
    """What changed on a host since preparation, beyond pick values."""
    recorded, found = prepared["hosts"][host], []
    manifest = observed["inputs"]["manifest"]
    if manifest is None or manifest["sha256"] != prepared["manifest"]["sha256"]:
        found.append(f"{host}: input-manifest: the designated manifest changed since prepare; "
                     "prepare again")
    if observed["inputs"]["filter"] != prepared["filter"]:
        found.append(f"{host}: input-manifest: the clean filter's pick keys changed since "
                     "prepare; prepare again")
    # The run installs with the recorded install PATH, and inventory checks the cache
    # prefixes of whichever shell runs it; the toolchain's own identity must not move.
    report = observed["inventory"]
    changed = _differing(recorded["toolchain"], report.get("toolchain"))
    if changed:
        found.append(f"{host}: toolchain: {', '.join(changed)} changed since prepare; prepare "
                     "again")
    harnesses = report.get("harnesses") or {}
    for name in ("claude", "codex"):
        if name in recorded and _identity(harnesses.get(name) or {}) != recorded[name]:
            found.append(f"{host}: version: the {name} executable or its versions changed "
                         "since prepare; prepare again")
    if (report.get("desktop") or {}).get("state") != recorded["desktop"]["state"]:
        found.append(f"{host}: desktop: the desktop surfaces changed since prepare; prepare "
                     "again")
    for target_id, target in recorded["targets"].items():
        current = observed["inputs"]["targets"].get(target_id)
        if current is not None and current["path"] != target["path"]:
            found.append(f"{host}: target: {target_id} now resolves elsewhere; prepare again")
    return found


# --- preparation and eligibility -----------------------------------------------------------


def _open(root):
    """The current window, refusing unexplained root state or an unfinished window."""
    try:
        current = state.current_window(root)
    except Stop as stop:
        raise Failed("retained-state", "titan", "refused", str(stop),
                     next_command=["status"]) from None
    if current is not None and current["state"] not in state.TERMINAL:
        raise Failed("window", "titan", "blocked", f"window {current['id']} is "
                     f"{current['state']}; it must be finished, aborted or recovered first",
                     observed=f"window {current['id']} is {current['state']}",
                     next_command=["status"])
    return current


def prepare(controller_session: str) -> dict:
    """Record eligibility and the current inputs in prepared.json; open no window."""
    valid = isinstance(controller_session, str) and SESSION.fullmatch(controller_session)
    rerun = ["prepare", "--controller-session",
             controller_session if valid else SESSION_PLACEHOLDER]
    try:
        if not valid:
            raise Failed("arguments", "titan", "refused", "the controller session must be its "
                         "native session ID, a lowercase UUID")
        root = _root()
        _open(root)
        controller, seen = _controller_helpers(), {}
        for host in HOST_ORDER:
            observed = _observe(host, active=None, complete=False)
            if observed["blockers"]:
                raise Failed(observed["step"], host, "blocked",
                             f"{len(observed['blockers'])} blocker(s); none was changed",
                             log=observed["log"], blockers=observed["blockers"])
            seen[host] = observed
        manifest = seen["titan"]["manifest"]
        crossing = _cross_host(seen) + [
            f"controller: helpers: {drift} in the controller checkout {CHECKOUT}"
            for drift in _helper_drift(manifest["helpers"], controller)]
        if crossing:
            raise Failed("eligibility", "titan", "blocked",
                         f"{len(crossing)} blocker(s); none was changed", blockers=crossing)
    except Failed as failed:
        failed.observed = failed.observed or NOTHING
        failed.next_command = failed.next_command or rerun
        raise
    titan = seen["titan"]["inputs"]
    prepared = {
        "schema": 1, "prepared_at": _now(),
        "controller": {"session_id": controller_session, "checkout": str(CHECKOUT),
                       "helpers": controller,
                       "codex": _identity(seen["titan"]["inventory"]["harnesses"]["codex"])},
        "manifest": {key: titan["manifest"][key] for key in ("path", "generation", "sha256")},
        "pins": manifest["pins"], "filter": titan["filter"], "helpers": manifest["helpers"],
        "hosts": {host: _host_record(seen[host]) for host in HOST_ORDER}}
    state.save_record(root / PREPARED, prepared)
    return prepared


def load_prepared() -> dict:
    path = _root() / PREPARED
    rerun = ["prepare", "--controller-session", SESSION_PLACEHOLDER]
    if not os.path.lexists(path):
        raise Failed("prepared-record", "titan", "missing", "nothing is prepared yet",
                     observed=NOTHING, next_command=rerun)
    try:
        return state.load_record(path)
    except Stop as stop:
        raise Failed("prepared-record", "titan", "refused", str(stop), observed=NOTHING,
                     next_command=rerun) from None


def check(prepared: dict) -> dict:
    """Read-only: every host's eligibility and drift since preparation. Live sessions are
    listed as run blockers, not eligibility blockers."""
    root, blockers = _root(), []
    try:
        current = state.current_window(root)
    except Stop:
        current = None  # Titan's inputs-check names the unexplained state
    if current is not None and current["state"] not in state.TERMINAL:
        blockers.append(f"titan: window: window {current['id']} is {current['state']}")
    active = current["id"] if current is not None else None
    seen = {host: _observe(host, active=active, complete=True) for host in HOST_ORDER}
    for host in HOST_ORDER:
        blockers += seen[host]["blockers"] + _drift(host, prepared, seen[host])
    blockers += _cross_host(seen)
    blockers += [f"controller: helpers: {drift} in the controller checkout {CHECKOUT}"
                 for drift in _helper_drift(prepared["helpers"], _controller_helpers())]
    return {"eligible": not blockers, "blockers": blockers,
            "prepared_sha256": prepared_sha256(prepared),
            "logs": {host: seen[host]["log"] for host in HOST_ORDER},
            "sessions": {host: _sessions(seen[host]["inventory"]) for host in HOST_ORDER},
            "targets": {host: seen[host]["inputs"]["targets"] for host in HOST_ORDER}}


def blocking_host(result):
    """The host named by a check's first blocker; Titan for shared or controller blockers."""
    first = result["blockers"][0].split(": ", 1)[0]
    return first if first in hosts.HOSTS else "titan"


def recheck(prepared: dict) -> dict:
    """The run's eligibility gate: `check`, refusing on any blocker; pick drift passes."""
    result = check(prepared)
    if not result["eligible"]:
        host = blocking_host(result)
        raise Failed("eligibility", host, "blocked",
                     f"{len(result['blockers'])} blocker(s) since preparation",
                     log=result["logs"].get(host), blockers=result["blockers"],
                     observed=NOTHING,
                     next_command=["prepare", "--controller-session",
                                   prepared["controller"]["session_id"]])
    return result


def _no_live(host, mode, window_id):
    payload = {"window_id": window_id} if window_id else {}
    result, log = _call(host, mode, "no-live", payload, "no-live")
    blockers = [f"{host}: no-live: {entry['harness']} process {entry['pid']} is running"
                for entry in result["live"]]
    blockers += [f"{host}: no-live: relay-cutover preflight --harness {harness} reports "
                 f"no-live {verdict}" for harness, verdict in result["preflight"].items()
                 if verdict != "ok"]
    if blockers:
        raise Failed("no-live", host, "blocked", "Claude or Codex is still running; close every "
                     "session on both hosts (no process is exempt) and run again", log=log,
                     blockers=blockers)


def require_no_live(mode: str, window_id: str | None = None) -> None:
    """Strict no-live on both hosts, Titan first."""
    for host in HOST_ORDER:
        _no_live(host, mode, window_id)


# --- the window ----------------------------------------------------------------------------


def open_window(prepared: dict, *, mode: str = "live") -> dict:
    """Allocate the run's window for the prepared record on disk; this process owns it."""
    root = _root()
    try:
        recorded = state.load_record(root / PREPARED)
    except Stop as stop:
        raise Stop(f"the prepared record cannot be read ({stop}); prepare again") from None
    if prepared_sha256(recorded) != prepared_sha256(prepared):
        raise Stop("the prepared record on disk differs from this one; check and prepare again")
    window = state.new_window(root, prepared_sha256(prepared), mode=mode)
    state.save_record(Path(window["directory"]) / PREPARED, prepared)
    return _save(window, owner=_me())


def _refuse(message):
    return Failed("quiesce", "titan", "refused", message, observed="nothing was changed",
                  next_command=["status"])


def _check_quiesce(window, prepared, decision):
    if window is None:
        raise _refuse("no window is open; a run opens one before quiescing")
    if not isinstance(decision, dict) or decision.get("window_id") != window["id"]:
        raise _refuse("the decision does not belong to the open window")
    if window["state"] != "prepared":
        raise _refuse(f"window {window['id']} is {window['state']}; only a newly opened "
                      "window quiesces")
    if window["prepared_sha256"] != prepared_sha256(prepared):
        raise _refuse("the window was opened for another preparation")
    if window.get("owner") != _me():
        raise _refuse("another invocation opened this window")
    attempt = decision.get("attempt_id")
    if not isinstance(attempt, str) or not state.ATTEMPT_ID.fullmatch(attempt):
        raise _refuse("the decision names no attempt")
    try:
        consumed = state.load_record(Path(window["directory"]) / "decisions" / f"{attempt}.json")
    except Stop:
        consumed = None
    if (consumed != decision or decision.get("kind") != "desktop"
            or decision.get("action") != RUN_ACTION
            or decision.get("prepared_sha256") != window["prepared_sha256"]):
        raise _refuse("the decision is not this window's consumed desktop decision for this run")


def quiesce_window(prepared: dict, decision: dict) -> dict:
    """Quiesce both hosts for the open window, or abort every host it touched."""
    root = _root()
    window = state.current_window(root)
    _check_quiesce(window, prepared, decision)
    progress = {"step": "quiesce", "host": "titan"}
    with _signals() as seen:  # a signal from here on is noted and aborts at the next step
        window = _save(window, state="quiescing", attempts=[],
                       decision={key: decision[key] for key in (
                           "attempt_id", "subject_sha256", "consumed_at")})
        try:
            return _quiesce(window, prepared, progress, seen)
        except (Exception, _Interrupt) as error:
            failed = _as_failed(error, progress)
        raise _abort_after(failed, seen)


def _as_failed(error, progress):
    if isinstance(error, Failed):
        return error
    if isinstance(error, _Interrupt):
        return Failed(progress["step"], progress["host"], "interrupted",
                      f"interrupted by {signal.Signals(error.signum).name}")
    if isinstance(error, Stop):
        return Failed(progress["step"], progress["host"], "failed", str(error))
    return Failed(progress["step"], progress["host"], "failed",
                  f"unexpected {type(error).__name__}; the window record keeps the step")


def _quiesce(window, prepared, progress, seen):
    mode, identity = window["mode"], window["id"]

    def step(name, host):
        nonlocal window
        if seen:
            raise _Interrupt(seen[-1])
        progress.update(step=name, host=host)
        window = _save(window, attempts=[*window["attempts"],
                                         {"host": host, "step": name, "at": _now()}])

    step("codex-daemon-stop", "titan")
    result, log = _call("titan", mode, "codex-daemon-stop", {
        "window_id": identity, "codex_sha256": prepared["hosts"]["titan"]["codex"]["sha256"]},
        "codex-daemon-stop")
    if result["survivors"]:
        raise Failed("codex-daemon-stop", "titan", "blocked",
                     "Codex processes remain after the supported daemon stop; inspect only "
                     "these PIDs and close their clients; nothing was killed", log=log,
                     blockers=[f"titan: codex-daemon-stop: codex process {entry['pid']} "
                               "survives" for entry in result["survivors"]])
    for host in HOST_ORDER:
        step("no-live", host)
        _no_live(host, mode, identity)
    records = {}
    for host in HOST_ORDER:
        step("timer-record", host)
        result, _ = _call(host, mode, "timer-record", {"window_id": identity}, "timer-record")
        records[host] = result["sha256"]
        state.save_record(Path(window["directory"]) / "hosts" / host / "timers.json",
                          {"schema": 1, "host": host, "sha256": result["sha256"],
                           "timers": result["timers"]})
        window = _save(window, timers={**window.get("timers", {}), host: {
            "sha256": result["sha256"], "recorded_at": _now()}})
        step("timer-stop", host)
        _call(host, mode, "timer-stop", {"window_id": identity, "record_sha256": records[host]},
              "timer-stop")
    for host in HOST_ORDER:
        step("timer-wait", host)
        _call(host, mode, "timer-wait", {"window_id": identity, "record_sha256": records[host]},
              "timer-wait")
    for host in HOST_ORDER:
        step("no-live", host)
        _no_live(host, mode, identity)
    snapshots = {}
    for host in HOST_ORDER:
        step("snapshot-refresh", host)
        result, _ = _call(host, mode, "snapshot-refresh", {
            "window_id": identity, "familiar_pre": prepared["pins"]["familiar_pre"]},
            "snapshot-refresh")
        snapshots[host] = result["moves"]
    window = _save(window, quiescent={"at": _now(), "hosts": {
        host: {"timers": records[host], "snapshots": snapshots[host]} for host in HOST_ORDER}})
    if seen:
        raise _Interrupt(seen[-1])
    return window


def _attempted(window):
    hosts_seen = {attempt["host"] for attempt in window.get("attempts", [])}
    return [host for host in HOST_ORDER if host in hosts_seen]


def _abort_host(window, host, seen, mark):
    """Cancel the window's pending work on host, restore its timers, return its snapshots."""
    mode, identity = window["mode"], window["id"]
    result = {"complete": False, "cancelled": [], "errors": []}

    def interrupted():
        if len(seen) > mark:
            result["interrupted"] = True
            result["errors"].append(f"interrupted by {signal.Signals(seen[-1]).name}")
        return len(seen) > mark

    def attempt(step, operation, payload):
        if interrupted():
            return None
        try:
            return _call(host, mode, operation, payload, step)[0]
        except Failed as failed:
            result["errors"].append(f"{failed.step}: {failed.status}: {failed.error}")
            if failed.status == "interrupted":
                result["interrupted"] = True
            return None

    pending = attempt("abort", "pending-operations", {"window_id": identity})
    if pending is None:
        return result
    for entry in pending["operations"]:
        if entry["window_id"] != identity:
            result["errors"].append(
                f"operation {entry['operation_id']} ({entry['operation']}) is {entry['state']} "
                "and is not this window's; reconcile it with operation-status or "
                "operation-cancel")
            continue
        cancelled = attempt("abort", "operation-cancel", {"operation_id": entry["operation_id"]})
        if cancelled is None:
            return result
        result["cancelled"].append({"operation_id": entry["operation_id"],
                                    "operation": entry["operation"],
                                    "state": cancelled["state"]})
        if cancelled["state"] not in hosts.TERMINAL:
            result["errors"].append(f"operation {entry['operation_id']} ({entry['operation']}) "
                                    f"is still {cancelled['state']} after operation-cancel; "
                                    "inspect it")
    if result["errors"]:
        return result  # this host refuses further mutations until they are reconciled
    expected = (window.get("timers") or {}).get(host, {}).get("sha256")
    result["timers"] = attempt("abort-timers", "timer-restore", {
        "window_id": identity, **({"record_sha256": expected} if expected else {})})
    if result.get("interrupted"):
        return result
    result["snapshots"] = attempt("abort-snapshots", "snapshot-abort", {"window_id": identity})
    result["complete"] = not result["errors"]
    return result


def _abort(window, seen):
    mark = len(seen)
    earlier = window.get("earlier_aborts", []) + ([window["abort"]] if "abort" in window else [])
    window = _save(window, state="aborting", owner=_me(), earlier_aborts=earlier,
                   abort={"started_at": _now(), "hosts": {}})
    results, complete = {}, True
    for host in _attempted(window):
        if len(seen) > mark:
            complete = False
            break
        results[host] = _abort_host(window, host, seen, mark)
        complete = complete and results[host]["complete"]
        window = _save(window, abort={**window["abort"], "hosts": dict(results)})
        if results[host].get("interrupted"):
            break
    final = "aborted" if complete and len(seen) == mark else "abort-incomplete"
    window = _save(window, state=final, abort={**window["abort"], "hosts": results,
                                               "finished_at": _now()})
    return {"state": final, "window": window, "hosts": results}


def _describe(outcome):
    touched = ", ".join(outcome["hosts"]) or "no host"
    if outcome["state"] == "aborted":
        return (f"aborted: timers restored and snapshots returned on {touched}; familiar and "
                "settings were not changed")
    unfinished = [host for host, result in outcome["hosts"].items() if not result["complete"]]
    return (f"abort-incomplete: unfinished on {', '.join(unfinished) or 'an interrupted host'}; "
            "timers may still be paused there; familiar and settings were not changed")


def _abort_after(failed, seen):
    try:
        window = state.current_window(_root())
        window = _save(window, failure={"step": failed.step, "host": failed.host,
                                        "status": failed.status, "error": failed.error,
                                        "log": failed.log, "at": _now()})
        outcome = _abort(window, seen)
    except (Stop, OSError) as error:
        failed.observed = (f"the abort could not run ({hosts._brief(error)}); timers may still "
                           "be paused")
        failed.next_command = ["recover"]
        return failed
    failed.observed = _describe(outcome)
    failed.next_command = ["run"] if outcome["state"] == "aborted" else ["recover"]
    return failed


def abort_window(window: dict) -> dict:
    """The pre-merge abort of the active window: also the reconciliation after SIGKILL or an
    incomplete abort, and the transition for a window a crash left `prepared`."""
    root = _root()
    current = state.current_window(root)
    if current is None or current != window:
        raise Stop("this window record is not the active one on disk; reload it with status")
    name = f"window {window['id']} is {window['state']}"
    if window["state"] in state.TERMINAL:
        raise Stop(f"{name}; there is nothing to abort")
    if window["state"] not in ABORTABLE:
        raise Stop(f"{name}; the pre-merge abort cannot undo it; use recover")
    if window["state"] == "applying" and ("familiar" in window or state.read_ledger(window)):
        raise Stop(f"{name} and familiar or a target changed; use recover")
    owner = window.get("owner")
    if owner is not None and owner != _me() and hosts._alive(owner):
        raise Stop(f"{name} and belongs to a running invocation (pid {owner['pid']}); let it "
                   "finish, or interrupt it so that it aborts")
    with _signals() as seen:
        return _abort(window, seen)


def status() -> dict:
    """Read-only: the prepared record, the active window and the one next command."""
    root = _root()
    report = {"root": str(root), "prepared": None, "window": None, "detail": None,
              "next": None}
    if os.path.lexists(root / PREPARED):
        try:
            recorded = state.load_record(root / PREPARED)
            report["prepared"] = {"sha256": prepared_sha256(recorded),
                                  "prepared_at": recorded.get("prepared_at"),
                                  "generation": (recorded.get("manifest") or {}).get(
                                      "generation")}
        except Stop as stop:
            report["detail"] = f"the prepared record is unreadable ({stop})"
    try:
        current = state.current_window(root)
    except Stop as stop:
        report.update(detail=f"unexplained cutover state: {stop}", next=["status"])
        return report
    if current is not None:
        report["window"] = {key: current[key] for key in ("id", "state", "mode", "created_at")}
    if current is None or current["state"] in state.TERMINAL:
        report["detail"] = report["detail"] or (
            "no window is active" if current is None
            else f"window {current['id']} is {current['state']}; a fresh run may start")
        report["next"] = (["check"] if report["prepared"] else
                          ["prepare", "--controller-session", SESSION_PLACEHOLDER])
        return report
    owner = current.get("owner")
    if owner is not None and owner != _me() and hosts._alive(owner):
        report.update(detail=f"window {current['id']} is {current['state']} and its invocation "
                      f"(pid {owner['pid']}) is still running", next=["status"])
        return report
    attempted = _attempted(current)
    report["detail"] = (f"window {current['id']} is {current['state']} and no invocation is "
                        "running it; " + (f"timers may be paused on {', '.join(attempted)}"
                                          if attempted else "no host was changed"))
    report["next"] = ["recover"]
    return report
