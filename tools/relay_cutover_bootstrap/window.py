"""The cutover window on the controller: quiescence and the pre-merge abort.

Preparation and eligibility (`prepare`, `check`, `recheck`) are in `prepare.py`. A run
(Task 4) opens the window with `open_window`, takes the operator's desktop decision in that
invocation, consumes it with `state.consume_decision` and passes the consumed record to
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

from . import hosts, operations, state
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


def _stopped(window):
    """Hosts whose timers this window asked to stop: the attempt is recorded before the
    request, so a host absent here never had its timers paused by this window."""
    asked = {attempt["host"] for attempt in window.get("attempts", [])
             if attempt["step"] == "timer-stop"}
    return [host for host in HOST_ORDER if host in asked]


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
        "window_id": identity, "stopped": host in _stopped(window),
        **({"record_sha256": expected} if expected else {})})
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
    attempted, stopped = _attempted(current), _stopped(current)
    report["detail"] = (f"window {current['id']} is {current['state']} and no invocation is "
                        "running it; " + (f"timers may be paused on {', '.join(stopped)}"
                                          if stopped else
                                          f"its hosts ({', '.join(attempted)}) have no paused "
                                          "timer" if attempted else "no host was changed"))
    report["next"] = ["recover"]
    return report
