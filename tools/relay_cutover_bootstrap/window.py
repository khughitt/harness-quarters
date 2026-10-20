"""The cutover window on the controller: the run's lifecycle and the pre-merge abort.

Preparation and eligibility (`prepare`, `check`, `recheck`) are in `prepare.py`; the host side of
targets and familiar is in `targets.py` and `familiar.py`. A run opens the window with
`open_window`, takes the operator's desktop decision in that invocation (cli.py), consumes it with
`state.consume_decision` and passes the consumed record to `run_window`, which runs:

1. the eligibility gate, whose inventory completes and collects the held Claude version and doctor
   probes on both hosts and in both homes; a Claude process left afterwards blocks;
2. `quiesce_window`: stop Titan's two Codex daemons with their CLI; strict no-live on both hosts,
   with no exemption; record and stop each host's timers; wait for their services; strict no-live
   again; refresh the familiar snapshots;
3. `dry_targets`: the six dry runs on frozen copies, cross-host agreement and the seal;
4. the frozen targets unchanged and both hosts closed, then the `familiar` record;
5. the merge of the immutable tip on Titan; each host's install once the merge reached it; each
   target registered, then applied once on Titan; every host verified. Both hosts are checked
   closed before each install and each target write. The window becomes
   `migrated-surfaces-pending`.

Full recovery of a window past the `familiar` record, and the reconciliation of a run that
stopped without recording its outcome, are in `recovery.py`; `status` names their states.

Each step is recorded in the window before its request. Any failure before the `familiar` record,
or an INT, TERM or HUP, aborts every host the window touched: the abort cancels and reconciles
the window's pending operations, restores timers from their records and then returns the
snapshots. The window goes `aborting` → `aborted`, or to `abort-incomplete` when a host cannot
finish, including after a second interruption. `abort_window` is also how the next invocation
reconciles after SIGKILL or an incomplete abort, and how it clears a window that a crash left
`prepared`. It refuses a window whose recorded owner is still running, and any window past the
pre-merge boundary. After the `familiar` record a failure leaves `recovery-required`, with
timers paused and nothing undone here.

Keys this module adds to the window record:

- `owner` {pid, start_time} and `decision`;
- `attempts` [{host, step, at}];
- `timers` {host: {sha256, recorded_at}}, with copies at `hosts/<host>/timers.json`;
- `quiescent`, `failure`, `abort` and `earlier_aborts` (each incomplete abort's record);
- `surfaces`: the consent subject, every host's recorded familiar surfaces;
- `dry` {host: {target: verdict}} and `sealed` {at, effective_inputs_sha256, inputs};
- `familiar` {started_at, pre, tip}, recorded before the merge, then merge, parents, merged_at;
- `dependencies` {host: install proof}, `applied` {target: apply result}, `verified`.

The window directory also keeps the prepared record as `prepared.json`, the ledger
(`touched.tsv`, `<target>.original`) and each target's live guard images, plan and artifact
under `live/`."""
import os
import re
import signal
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import hosts, inputs, operations, state, targets
from .state import Stop

HOST_ORDER = ("titan", "europa")
PREPARED = "prepared.json"
RUN_ACTION = "run"
RUN_ATTEMPT = "run"  # the run's one desktop decision in its window
IMPACT = ("familiar's niri watcher and desktop panel stop and start again from the merged "
          "source; the panel is briefly absent")
DURATION_SECONDS = 30
BOOTSTRAP = "tools/relay-cutover-bootstrap"
CHECKOUT = Path(__file__).resolve().parents[2]  # the controller's checkout
SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
SESSION_PLACEHOLDER = "<native-session-id>"
ABORTABLE = ("prepared", "quiescing", "applying", "aborting", "abort-incomplete")
MARGIN = 60
NOTHING = "nothing was changed; no window is open"


class Failed(Stop):
    """A stopped step as the operator sees it: no settings, plans, environments or child
    output, only tool-authored text, the private log path and one next command. `aborted` is
    true once the pre-merge abort ran for it, so no caller runs that abort again."""

    def __init__(self, step, host, status, error, *, log=None, blockers=(), observed=None,
                 next_command=None):
        super().__init__(f"{step} on {host}: {status}: {error}")
        self.step, self.host, self.status, self.error = step, host, status, error
        self.log, self.blockers = log, list(blockers)
        self.observed, self.next_command = observed, next_command
        self.aborted = False


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


def _refuse(message, step="quiesce"):
    return Failed(step, "titan", "refused", message, observed="nothing was changed",
                  next_command=["status"])


def _check_quiesce(window, prepared, decision, step="quiesce"):
    if window is None:
        raise _refuse("no window is open; a run opens one before quiescing", step)
    if not isinstance(decision, dict) or decision.get("window_id") != window["id"]:
        raise _refuse("the decision does not belong to the open window", step)
    if window["state"] != "prepared":
        raise _refuse(f"window {window['id']} is {window['state']}; only a newly opened "
                      "window quiesces", step)
    if window["prepared_sha256"] != prepared_sha256(prepared):
        raise _refuse("the window was opened for another preparation", step)
    if window.get("owner") != _me():
        raise _refuse("another invocation opened this window", step)
    attempt = decision.get("attempt_id")
    if not isinstance(attempt, str) or not state.ATTEMPT_ID.fullmatch(attempt):
        raise _refuse("the decision names no attempt", step)
    try:
        consumed = state.load_record(Path(window["directory"]) / "decisions" / f"{attempt}.json")
    except Stop:
        consumed = None
    if (consumed != decision or decision.get("kind") != "desktop"
            or decision.get("action") != RUN_ACTION
            or decision.get("prepared_sha256") != window["prepared_sha256"]):
        raise _refuse("the decision is not this window's consumed desktop decision for this run",
                      step)


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


def _step(window, seen, progress, name, host):
    """Record one attempt in the window before its request; a signal noted since stops here."""
    if seen:
        raise _Interrupt(seen[-1])
    progress.update(step=name, host=host)
    return _save(window, attempts=[*window.get("attempts", []),
                                   {"host": host, "step": name, "at": _now()}])


def _quiesce(window, prepared, progress, seen):
    mode, identity = window["mode"], window["id"]

    def step(name, host):
        nonlocal window
        window = _step(window, seen, progress, name, host)

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
    failed.aborted = True
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


# --- the run: eligibility, quiescence, six dry runs, familiar and the four targets ----------


def desktop_subject(desktop: dict | None) -> dict:
    """What desktop consent binds on one host: its state and explained absence, the trusted
    niri socket and each familiar surface's startup commands and recorded processes."""
    desktop = desktop or {}
    return {"state": desktop.get("state"), "absence_reason": desktop.get("absence_reason"),
            "socket": desktop.get("socket"),
            "surfaces": [{"name": surface.get("name"), "configured": surface.get("configured"),
                          "processes": surface.get("processes")}
                         for surface in desktop.get("surfaces") or []]}


def run_subject(prepared: dict) -> dict:
    """The run's desktop decision subject: every host's recorded surfaces, impact, duration."""
    return {"action": RUN_ACTION,
            "hosts": {host: desktop_subject(prepared["hosts"][host]["desktop"])
                      for host in HOST_ORDER},
            "impact": IMPACT, "duration_seconds": DURATION_SECONDS}


def _probes_collected(result):
    """After the held probes were collected, a Claude process left on either host blocks; the
    tool's own probes are not exempt."""
    blockers = [f"{host}: no-live: claude process {entry['pid']} is still running after the "
                "held version and doctor probes" for host in HOST_ORDER
                for entry in result["sessions"][host] if entry["harness"] == "claude"]
    if blockers:
        host = blockers[0].split(": ", 1)[0]
        raise Failed("no-live", host, "blocked", "Claude is still running after the held probes "
                     "were collected; close every session on both hosts (no process is exempt, "
                     "this tool's own probes included) and run again",
                     log=result["logs"].get(host), blockers=blockers)


def run_window(prepared: dict, decision: dict) -> dict:
    """The run from its eligibility gate to the verified migration (`migrated-surfaces-pending`),
    for the window this invocation opened and the desktop decision it consumed.

    1. The decision's subject must be this preparation's desktop inventory; the window keeps it
       as `surfaces`. The eligibility gate repeats preparation's checks; its inventory completes
       and collects the held Claude probes for every host and home, and any Claude process
       left afterwards blocks.
    2. `quiesce_window`: daemon stop, the final strict no-live, timers and snapshots.
    3. `dry_targets`: the six dry runs and the seal.
    4. The frozen targets are unchanged and both hosts are closed; then `familiar` is recorded
       and the immutable tip is merged.
    5. With both hosts checked closed before each install and each target write, each host
       waits for the merge and installs; each target is registered and applied once on Titan;
       every host's targets, source, dependencies and evidence are verified.

    Failures before step 4's record abort every touched host; after it the window becomes
    `recovery-required` and nothing is undone here."""
    from . import prepare as preparation  # prepare imports this module for its step helpers
    window = state.current_window(_root())
    _check_quiesce(window, prepared, decision, step="run")
    progress = {"step": "eligibility", "host": "titan"}
    failed = None
    with _signals() as seen:
        try:
            subject = run_subject(prepared)
            if decision.get("subject_sha256") != state._digest(subject):
                raise Failed("decision", "titan", "refused", "the decision's subject is not this "
                             "preparation's desktop inventory; ask again")
            window = _save(window, surfaces=subject)
            _probes_collected(preparation.recheck(prepared, opened=window))
            if seen:
                raise _Interrupt(seen[-1])
        except (Exception, _Interrupt) as error:
            failed = _as_failed(error, progress)
        if failed is not None:
            raise _abort_after(failed, seen)
        try:
            # Both abort their own failures; any refusal of theirs that did not (a precondition
            # after quiescence) still takes the pre-merge abort here.
            window = quiesce_window(prepared, decision)
            progress.update(step="target-dry", host="titan")
            window = dry_targets(window)
            window = _before_merge(window, seen, progress)
            window = _save(window, familiar={"started_at": _now(),
                                             "pre": prepared["pins"]["familiar_pre"],
                                             "tip": prepared["pins"]["familiar_feature_tip"]})
        except (Exception, _Interrupt) as error:
            if isinstance(error, Failed) and error.aborted:
                raise
            failed = _as_failed(error, progress)
        if failed is not None:
            raise _abort_after(failed, seen)
        try:
            return _migrate(window, prepared, seen, progress)
        except (Exception, _Interrupt) as error:
            failed = _as_failed(error, progress)
        raise _recovery_after(failed)


def dry_targets(window: dict) -> dict:
    """The six dry runs before familiar's merge: Titan's four targets, then Europa's two Claude
    copies, each with its own host's installer, runtime and evidence (targets.py). Then both
    hosts' shared outputs must agree and the window seals its effective inputs (`sealed`). The
    quiescent window becomes `applying`; any failure aborts every host it touched."""
    if state.current_window(_root()) != window:
        raise Stop("this window record is not the active one on disk; reload it with status")
    if (window["state"] != "quiescing" or "quiescent" not in window or "familiar" in window
            or window.get("owner") != _me()):
        raise _refuse(f"window {window['id']} is not this invocation's quiescent window",
                      "target-dry")
    prepared = state.load_record(Path(window["directory"]) / PREPARED)
    if prepared_sha256(prepared) != window["prepared_sha256"]:
        raise _refuse("the window's prepared record changed", "target-dry")
    progress, failed = {"step": "target-dry", "host": "titan"}, None
    with _signals() as seen:
        try:
            window = _save(window, state="applying")
            results = {}
            for host in HOST_ORDER:
                for target_id in inputs.relevant(host):
                    window = _step(window, seen, progress, "target-dry", host)
                    result, _ = _call(host, window["mode"], "target-dry", {
                        "window_id": window["id"], "target_id": target_id,
                        "manifest_sha256": prepared["manifest"]["sha256"]}, "target-dry")
                    results.setdefault(host, {})[target_id] = result
                    window = _save(window, dry={name: dict(verdicts)
                                                for name, verdicts in results.items()})
            window = _save(window, sealed=targets.seal(prepared, results))
            if seen:
                raise _Interrupt(seen[-1])
            return window
        except (Exception, _Interrupt) as error:
            failed = _as_failed(error, progress)
        raise _abort_after(failed, seen)


def _before_merge(window, seen, progress):
    """The last pre-merge gate: every frozen target still holds its frozen bytes on both hosts,
    and both hosts are closed."""
    mode, identity, sealed = window["mode"], window["id"], window["sealed"]["inputs"]
    for host in HOST_ORDER:
        window = _step(window, seen, progress, "target-frozen", host)
        frozen = {target_id: result["frozen"]["sha256"]
                  for target_id, result in sealed["hosts"][host].items()}
        found, log = _call(host, mode, "target-verify", {
            "window_id": identity, "targets": frozen, "wait": False, "verify": False,
            "manifest_sha256": sealed["manifest_sha256"]}, "target-frozen")
        drifted = sorted(target_id for target_id, entry in found["targets"].items()
                         if not entry["matches"])
        if drifted:
            raise Failed("target-frozen", host, "blocked", f"{', '.join(drifted)} changed after "
                         "the freeze; nothing was written", log=log)
    for host in HOST_ORDER:
        window = _step(window, seen, progress, "no-live", host)
        _no_live(host, mode, identity)
    return window


def _migrate(window, prepared, seen, progress):
    """Past the familiar record: merge, install, register and apply, then verify both hosts."""
    mode, identity, sealed = window["mode"], window["id"], window["sealed"]["inputs"]
    pins = prepared["pins"]
    window = _step(window, seen, progress, "familiar-merge", "titan")
    merged, _ = _call("titan", mode, "familiar-merge", {
        "window_id": identity, "pre": pins["familiar_pre"],
        "tip": pins["familiar_feature_tip"]}, "familiar-merge")
    window = _save(window, familiar={**window["familiar"], "merge": merged["merge"],
                                     "parents": merged["parents"], "merged_at": _now()})
    for host in HOST_ORDER:
        for checked in HOST_ORDER:
            window = _step(window, seen, progress, "no-live", checked)
            _no_live(checked, mode, identity)
        window = _step(window, seen, progress, "familiar-install", host)
        record = prepared["hosts"][host]
        result, _ = _call(host, mode, "familiar-install", {
            "window_id": identity, "merge": merged["merge"],
            "caches": record["caches"]["prefixes"], "path": record["install"]["path"]},
            "familiar-install")
        window = _save(window, dependencies={**window.get("dependencies", {}), host: result})
    titan = sealed["hosts"]["titan"]
    for target_id in inputs.TARGETS:
        for host in HOST_ORDER:
            window = _step(window, seen, progress, "no-live", host)
            _no_live(host, mode, identity)
        entry = titan[target_id]
        window = _step(window, seen, progress, "target-register", "titan")
        state.register_target(window, target_id, Path(entry["path"]),
                              Path(window["directory"]) / "live" / f"{target_id}.json")
        window = _step(window, seen, progress, "target-apply", "titan")
        result, _ = _call("titan", mode, "target-apply", {
            "window_id": identity, "target_id": target_id,
            "manifest_sha256": sealed["manifest_sha256"],
            "frozen_sha256": entry["frozen"]["sha256"],
            "expected_sha256": entry["expected"]["sha256"], "identities": entry["identities"]},
            "target-apply")
        window = _save(window, applied={**window.get("applied", {}), target_id: result})
    verified = {}
    for host in HOST_ORDER:
        window = _step(window, seen, progress, "target-verify", host)
        expected = {target_id: result["expected"]["sha256"]
                    for target_id, result in sealed["hosts"][host].items()}
        found, log = _call(host, mode, "target-verify", {
            "window_id": identity, "targets": expected, "wait": host != "titan", "verify": True,
            "manifest_sha256": sealed["manifest_sha256"]}, "target-verify")
        missing = sorted(target_id for target_id, entry in found["targets"].items()
                         if not entry["matches"])
        if missing or not found["verified"]:
            raise Failed("target-verify", host, "blocked", f"{', '.join(missing)} do not hold the "
                         "sealed bytes" + (" after waiting for synchronization"
                                           if host != "titan" else ""), log=log)
        window = _step(window, seen, progress, "familiar-verify", host)
        source, _ = _call(host, mode, "familiar-verify",
                          {"window_id": identity, "merge": merged["merge"]}, "familiar-verify")
        verified[host] = {"targets": expected, "familiar": source}
    if seen:
        raise _Interrupt(seen[-1])
    return _save(window, state="migrated-surfaces-pending",
                 verified={"at": _now(), "hosts": verified})


def _recovery_after(failed):
    """Past the familiar record nothing is undone here: the window needs full recovery."""
    stop = ("familiar or settings may have changed and timers stay paused. Do not open Claude "
            "or Codex until recover completes")
    try:
        window = state.current_window(_root())
        window = _save(window, state="recovery-required", failure={
            "step": failed.step, "host": failed.host, "status": failed.status,
            "error": failed.error, "log": failed.log, "at": _now()})
    except (Stop, OSError) as error:
        failed.observed = f"the window record could not be updated ({hosts._brief(error)}); {stop}"
    else:
        failed.observed = f"window {window['id']} is recovery-required: {stop}"
    failed.next_command = ["recover"]
    return failed


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
    if current["state"] == "migrated-surfaces-pending":
        report.update(detail=f"window {current['id']} verified the migration on both hosts; "
                      "familiar's surfaces are pending and timers stay paused on "
                      f"{', '.join(stopped) or 'no host'}", next=["restart-surfaces"])
        return report
    paused = (f"timers may be paused on {', '.join(stopped)}" if stopped else
              f"its hosts ({', '.join(attempted)}) have no paused timer" if attempted
              else "no host was changed")
    report["next"] = ["recover"]
    if "familiar" not in current:
        report["detail"] = (f"window {current['id']} is {current['state']} and no invocation is "
                            f"running it; {paused}")
        return report
    recovery = current.get("recovery") or {}
    failure = recovery.get("failure") or current.get("failure") or {}
    stopped_at = (f"{failure.get('step')} on {failure.get('host')} ({failure.get('status')})"
                  if failure else "an unrecorded point")
    if current["state"] == "inspection-required":
        lead = (f"stopped pending inspection at {stopped_at}: {failure.get('error')}; inspect it, "
                "then run recover; nothing was force-copied, reset or reverted blindly")
    elif current["state"] == "recovering" and "restored" in recovery:
        lead = ("recovery restored native settings, source and dependencies on both hosts; "
                "familiar's surfaces and the original timers are still pending")
    elif current["state"] == "recovering":
        lead = f"recovery stopped at {stopped_at}; recover repeats it from actual state"
    else:
        lead = (f"familiar or settings may have changed; the run stopped at {stopped_at}"
                if failure else "the run stopped past familiar's mark without recording its "
                "outcome; recover reconciles actual state first")
    report["detail"] = (f"window {current['id']} is {current['state']}: {lead}. Do not open "
                        "Claude or Codex until recover completes: run is blocked and timers "
                        f"stay paused on {', '.join(stopped) or 'no host'}")
    return report
