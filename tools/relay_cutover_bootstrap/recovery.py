"""Restoring a window past familiar's mark, and reconciling an interrupted run, on the controller.

`restore_window` is the restoration core of full recovery. A window that never reached familiar's
mark and registered no target follows the pre-merge abort only (`window.abort_window`). Any other
unfinished window is restored in the runbook's order:

1. this window's unfinished operations on both hosts are reconciled: a dead owner's recorded
   children are cancelled and recorded; one still running, unknown, or an unreachable host stops
   recovery before any mutation;
2. both Titan Codex daemons stop through their CLI, then strict no-live passes on both hosts from
   the whole process table, with no exemption;
3. both hosts' timers stop again from this window's original records, even where an earlier finish
   restored them, and both services are waited for; strict no-live passes again;
4. every target is checked against the images this window recorded, and only then are the
   registered ones restored in reverse ledger order through the existing byte gate; all four
   targets must hold their native bytes on Titan and, once synchronized, Europa's two;
5. familiar's actual Git state is reconciled (a merge committed before its record is recorded
   from its parents before anything else) and takes its one action: abort the attempted merge,
   nothing, or one revert;
6. each host waits for the recovered source, restores its dependencies offline from this window's
   verified pre-merge snapshot, and checks familiar native.

It returns with native targets, source and dependencies verified, timers still paused and the
window `recovering`: familiar's surfaces (with fresh consent) and the original timers are the
remaining stages of the full recover. Bytes matching no recorded image and unexpected Git history
stop as `inspection-required`, with nothing force-copied, reset or reverted blindly; any other
stop or signal leaves `recovering`, and the next call repeats from reconciliation, skipping what
actual state shows done. Recovery never runs the forward check, preflight or inventory, nor any
Claude executable, so stale Claude evidence never blocks it.

`reconcile_window` reads actual state for the next command. A run that stopped past familiar's
mark without recording its outcome becomes `migrated-surfaces-pending` only when every target on
both hosts holds its sealed bytes from this window's own artifacts, familiar is the attempted
merge on both hosts with its pinned relay dependency and the evidence still matches; otherwise
it becomes `recovery-required`, which blocks fresh sessions and names recover.

Keys this module adds to the window record: `recovery` {started_at, attempted_at, cancelled,
timers, check, targets, originals, familiar, dependencies, actions, restored, failure, failures},
where `actions` lists each destructive action once, as it is taken. Recovery also sets `state`
and `owner`; reconciliation sets `failure`, or `familiar` and `verified` when it promotes."""
from pathlib import Path

from . import hosts, inputs, state
from . import window as lifecycle
from .state import Stop
from .window import (HOST_ORDER, Failed, _Interrupt, _as_failed, _call, _me, _now, _root, _save,
                     _signals, _step)

RECOVERABLE = ("applying", "recovery-required", "recovering", "inspection-required",
               "migrated-surfaces-pending", "ready-for-smokes", "finishing")
MIGRATED = ("migrated-surfaces-pending", "ready-for-smokes", "finishing")
# Steps whose refusal means actual bytes or history matched no record: stop for inspection.
INSPECT = ("target-check", "target-restore", "familiar-reconcile", "familiar-restore")
RELAY = ("installer", "relay_cutover", "runtime")
STOP = ("Do not open Claude or Codex until recover completes: run is blocked and timers stay "
        "paused on titan and europa")
PENDING = ("native-surfaces", "original-timers")


def _active(window):
    current = state.current_window(_root())
    if current is None or current != window:
        raise Stop("this window record is not the active one on disk; reload it with status")


def _running_elsewhere(window):
    owner = window.get("owner")
    return owner is not None and owner != _me() and hosts._alive(owner)


def pre_merge(window: dict) -> bool:
    """Whether the window never reached familiar's mark nor registered a target."""
    return "familiar" not in window and not state.read_ledger(window)


def _prepared(window):
    prepared = state.load_record(Path(window["directory"]) / lifecycle.PREPARED)
    if lifecycle.prepared_sha256(prepared) != window["prepared_sha256"]:
        raise Stop("the window's prepared record changed; inspect it")
    return prepared


def _settle(window, *, cancel):
    """Each host's unfinished operations. With `cancel`, this window's operations whose owner
    died are cancelled and recorded; any operation still running, unknown or another window's,
    and a host that cannot be read, is a blocker for every mutation."""
    mode, identity = window["mode"], window["id"]
    blockers, cancelled = [], []
    for host in HOST_ORDER:
        try:
            found, _ = _call(host, mode, "pending-operations", {"window_id": identity},
                             "reconcile")
        except Failed as failed:
            if failed.status == "interrupted":
                raise
            blockers.append(f"{host}: its operations cannot be read ({failed.status}); they may "
                            "still be running until their own deadlines")
            continue
        for entry in found["operations"]:
            name = f"operation {entry['operation_id']} ({entry['operation']})"
            if entry["window_id"] == identity and entry["state"] == "owner-lost":
                if not cancel:
                    continue  # recovery cancels it first
                outcome, _ = _call(host, mode, "operation-cancel",
                                   {"operation_id": entry["operation_id"]}, "reconcile")
                cancelled.append({"host": host, "operation_id": entry["operation_id"],
                                  "operation": entry["operation"], "state": outcome["state"]})
                if outcome["state"] in hosts.TERMINAL:
                    continue
                blockers.append(f"{host}: {name} is {outcome['state']} after operation-cancel; "
                                "inspect its recorded children")
                continue
            owner = "this window's" if entry["window_id"] == identity else "not this window's"
            blockers.append(f"{host}: {name} is {entry['state']} and {owner}; let it finish or "
                            "reconcile it with operation-status or operation-cancel")
    return blockers, cancelled


def _closed(host, mode, identity):
    found, log = _call(host, mode, "recovery-no-live", {"window_id": identity}, "no-live")
    if found["live"]:
        raise Failed("no-live", host, "blocked", "Claude or Codex is running; close every session "
                     "on both hosts (no process is exempt) and run recover again", log=log,
                     blockers=[f"{host}: no-live: {entry['harness']} process {entry['pid']} is "
                               "running" for entry in found["live"]])


def _familiar_payload(window, recovered):
    """PRE, the tip and whatever merge and revert this window has recorded."""
    run = window.get("familiar") or {}
    payload = {"window_id": window["id"], "pre": inputs.PINS["familiar_pre"],
               "tip": inputs.PINS["familiar_feature_tip"]}
    for key in ("merge", "revert"):
        value = recovered.get(key) or (run.get(key) if key == "merge" else None)
        if value:
            payload[key] = value
    return payload


def _recorded(window, **changes):
    return _save(window, recovery={**window["recovery"], **changes})


def _act(window, host, action, **detail):
    actions = [*window["recovery"].get("actions", []),
               {"host": host, "action": action, "at": _now(), **detail}]
    return _recorded(window, actions=actions)


def _restore(window, prepared, seen, progress):
    mode, identity = window["mode"], window["id"]

    def step(name, host):
        nonlocal window
        window = _step(window, seen, progress, name, host)

    progress.update(step="reconcile", host="titan")
    blockers, cancelled = _settle(window, cancel=True)
    if blockers:
        raise Failed("reconcile", blockers[0].split(":", 1)[0], "unsettled",
                     "unfinished host operations block every recovery mutation; nothing was "
                     "changed", blockers=blockers, next_command=["status"])
    # Each attempt starts from actual state; an earlier outcome stays only in `failures`.
    earlier = {key: value for key, value in (window.get("recovery") or {}).items()
               if key not in ("restored", "failure")}
    window = _save(window, state="recovering", owner=_me(), recovery={
        **earlier, "started_at": earlier.get("started_at", _now()), "attempted_at": _now(),
        "actions": earlier.get("actions", []),
        "cancelled": [*earlier.get("cancelled", []), *cancelled]})

    step("codex-daemon-stop", "titan")
    result, log = _call("titan", mode, "codex-daemon-stop", {
        "window_id": identity, "codex_sha256": prepared["hosts"]["titan"]["codex"]["sha256"]},
        "codex-daemon-stop")
    if result["survivors"]:
        raise Failed("codex-daemon-stop", "titan", "blocked", "Codex processes remain after the "
                     "supported daemon stop; close their clients; nothing was killed", log=log,
                     blockers=[f"titan: codex-daemon-stop: codex process {entry['pid']} survives"
                               for entry in result["survivors"]])
    for host in HOST_ORDER:
        step("no-live", host)
        _closed(host, mode, identity)

    timers = {}
    for host in HOST_ORDER:
        step("timer-requiesce", host)
        timers[host], _ = _call(host, mode, "timer-requiesce", {
            "window_id": identity, "record_sha256": window["timers"][host]["sha256"]},
            "timer-requiesce")
        window = _recorded(window, timers=dict(timers))
    for host in HOST_ORDER:
        step("timer-wait", host)
        _call(host, mode, "timer-wait", {"window_id": identity,
                                         "record_sha256": window["timers"][host]["sha256"]},
              "timer-wait")
    for host in HOST_ORDER:
        step("no-live", host)
        _closed(host, mode, identity)

    sealed = window["sealed"]["inputs"]
    titan = sealed["hosts"]["titan"]
    step("target-check", "titan")
    checked, log = _call("titan", mode, "target-check", {
        "window_id": identity,
        "frozen": {target_id: entry["frozen"]["sha256"] for target_id, entry in titan.items()}},
        "target-check")
    window = _recorded(window, check=checked["targets"])
    unknown = sorted(target_id for target_id, entry in checked["targets"].items()
                     if entry["verdict"] == "unknown")
    if unknown:
        raise Failed("target-check", "titan", "blocked", f"{', '.join(unknown)} hold bytes "
                     "matching no image this window recorded (a pick changed after apply is "
                     "one); nothing was written or force-copied", log=log)
    for entry in reversed(state.read_ledger(window)):
        target_id = entry["target_id"]
        if checked["targets"][target_id]["verdict"] == "original":
            continue  # nothing was written to it, or an earlier attempt restored it
        step("target-restore", "titan")
        result, _ = _call("titan", mode, "target-restore", {
            "window_id": identity, "target_id": target_id,
            "identities": {name: titan[target_id]["identities"][name] for name in RELAY}},
            "target-restore")
        window = _recorded(window, targets={**window["recovery"].get("targets", {}),
                                            target_id: result})
        if result["restored"]:
            window = _act(window, "titan", "target-restore", target_id=target_id,
                          rollback=result["rollback"])
    native = {target_id: entry["native_sha256"] for target_id, entry in checked["targets"].items()}
    for host in HOST_ORDER:
        step("target-originals", host)
        expected = {target_id: native[target_id] for target_id in inputs.relevant(host)}
        found, log = _call(host, mode, "target-verify", {
            "window_id": identity, "targets": expected, "wait": host != "titan",
            "verify": False, "manifest_sha256": sealed["manifest_sha256"]}, "target-originals")
        differing = sorted(target_id for target_id, entry in found["targets"].items()
                           if not entry["matches"])
        if differing:
            raise Failed("target-originals", host, "blocked", f"{', '.join(differing)} do not "
                         "hold their native bytes" + (" after waiting for synchronization; "
                                                      "it may still be synchronizing"
                                                      if host != "titan" else ""), log=log)
    window = _recorded(window, originals={"at": _now(), "targets": native})

    recovered = window["recovery"].get("familiar") or {}
    step("familiar-reconcile", "titan")
    found, log = _call("titan", mode, "familiar-reconcile", _familiar_payload(window, recovered),
                       "familiar-reconcile")
    if found["class"] == "unexpected":
        raise Failed("familiar-reconcile", "titan", "blocked", f"{found['reason']}; inspect "
                     "familiar's checkout; nothing was reset or reverted", log=log)
    if found["merge"] and not recovered.get("merge"):
        # A merge or revert found only in Git is recorded before anything acts on it.
        recovered = {**recovered, "merge": found["merge"], "discovered": found["discovered"],
                     "class": found["class"]}
        window = _recorded(window, familiar=recovered)
    step("familiar-restore", "titan")
    result, _ = _call("titan", mode, "familiar-restore",
                      {**_familiar_payload(window, recovered), "expect": found["class"]},
                      "familiar-restore")
    recovered = {**recovered, "class": result["class"], "action": result["action"],
                 "revert": result["revert"], "at": _now()}
    window = _recorded(window, familiar=recovered)
    if result["action"] != "none":
        window = _act(window, "titan", result["action"], revert=result["revert"])

    dependencies = {}
    for host in HOST_ORDER:
        step("dependency-restore", host)
        dependencies[host], _ = _call(host, mode, "dependency-restore", {
            "window_id": identity, "pre": inputs.PINS["familiar_pre"],
            "revert": recovered["revert"]}, "dependency-restore")
        window = _recorded(window, dependencies={**window["recovery"].get("dependencies", {}),
                                                 host: dependencies[host]})
        if dependencies[host]["replaced"]:
            window = _act(window, host, "dependency-restore")
    if seen:
        raise _Interrupt(seen[-1])
    return _recorded(window, restored={"at": _now(), "revert": recovered["revert"],
                                       "pending": list(PENDING)})


def _summary(window):
    """What this window's recovery has verified so far, for the operator."""
    recovery = window.get("recovery") or {}
    done = []
    if "originals" in recovery:
        done.append("every target holds its native bytes")
    familiar = recovery.get("familiar") or {}
    if familiar.get("revert"):
        done.append(f"familiar is at {familiar['revert'][:12]} on titan")
    if recovery.get("dependencies"):
        done.append("dependencies are native on " + ", ".join(recovery["dependencies"]))
    return "; ".join(done) or "nothing has been restored yet"


def _stopped(failed):
    """Record a stopped recovery: inspection for unknown bytes or history, else recovering."""
    inspect = ((failed.step in INSPECT and failed.status in ("blocked", "failed"))
               or (failed.step == "target-originals" and failed.host == "titan"
                   and failed.status == "blocked"))
    try:
        window = state.current_window(_root())
        recovery = window.get("recovery") or {}
        record = {"step": failed.step, "host": failed.host, "status": failed.status,
                  "error": failed.error, "log": failed.log, "at": _now()}
        window = _save(window, state="inspection-required" if inspect else window["state"],
                       recovery={**recovery, "failure": record,
                                 "failures": [*recovery.get("failures", []), record]})
    except (Stop, OSError) as error:
        failed.observed = f"the window record could not be updated ({hosts._brief(error)}); {STOP}"
    else:
        lead = ("stopped pending inspection: nothing was force-copied, reset or reverted blindly"
                if inspect else f"recovery stopped at {failed.step} on {failed.host}")
        failed.observed = (f"window {window['id']} is {window['state']}: {lead}; "
                           f"{_summary(window)}. {STOP}")
    failed.next_command = failed.next_command or ["recover"]
    return failed


def restore_window(window: dict) -> dict:
    """Restore native targets, source and dependencies for a window past familiar's mark, or
    follow the pre-merge abort for one that never reached it. Timers stay paused and the window
    stays `recovering`: surfaces and the original timers are the full recover's later stages."""
    _active(window)
    name = f"window {window['id']} is {window['state']}"
    if window["state"] in state.TERMINAL:
        raise Stop(f"{name}; there is nothing to recover")
    if _running_elsewhere(window):
        raise Stop(f"{name} and belongs to a running invocation (pid {window['owner']['pid']}); "
                   "let it finish, or interrupt it")
    if pre_merge(window):
        outcome = lifecycle.abort_window(window)
        return {"class": "abort", "state": outcome["state"], "window": outcome["window"],
                "hosts": outcome["hosts"], "observed": lifecycle._describe(outcome),
                "next": ["run"] if outcome["state"] == "aborted" else ["recover"]}
    if window["state"] not in RECOVERABLE:
        raise Stop(f"{name}; recovery cannot classify it; inspect it")
    if set(window.get("timers") or {}) != set(HOST_ORDER) or "sealed" not in window:
        raise Stop(f"{name} without both hosts' timer records and its sealed inputs; inspect it")
    prepared = _prepared(window)
    progress = {"step": "reconcile", "host": "titan"}
    with _signals() as seen:
        try:
            window = _restore(window, prepared, seen, progress)
        except (Exception, _Interrupt) as error:
            failed = _as_failed(error, progress)
        else:
            return {"class": "restored", "state": window["state"], "window": window,
                    "revert": window["recovery"]["restored"]["revert"],
                    "stages": {"no-live": "passed", "timers": "paused", "targets": "native",
                               "source": "native", "dependencies": "native",
                               **{stage: "pending" for stage in PENDING}},
                    "observed": (f"window {window['id']} is recovering: {_summary(window)} on "
                                 "both hosts; familiar's surfaces and the original timers are "
                                 f"still pending. {STOP}"),
                    "next": ["recover"]}
    raise _stopped(failed)


# --- reconciliation -------------------------------------------------------------------------


def _verify_migration(window, found):
    """None when actual state on both hosts is the sealed migration, else what differs."""
    mode, identity = window["mode"], window["id"]
    sealed = window["sealed"]["inputs"]
    if found["class"] != "merged":
        return None, f"familiar is {found['class']}, not the attempted merge"
    merge = found["merge"]
    titan = sealed["hosts"]["titan"]
    checked, _ = _call("titan", mode, "target-check", {
        "window_id": identity,
        "frozen": {target_id: entry["frozen"]["sha256"] for target_id, entry in titan.items()}},
        "reconcile")
    applied = sorted(target_id for target_id, entry in checked["targets"].items()
                     if entry["verdict"] != "relay-applied"
                     or entry["sha256"] != titan[target_id]["expected"]["sha256"])
    if applied:
        return None, f"{', '.join(applied)} do not hold this window's applied artifact bytes"
    verified = {}
    for host in HOST_ORDER:
        expected = {target_id: entry["expected"]["sha256"]
                    for target_id, entry in sealed["hosts"][host].items()}
        report, _ = _call(host, mode, "target-verify", {
            "window_id": identity, "targets": expected, "wait": host != "titan", "verify": True,
            "manifest_sha256": sealed["manifest_sha256"]}, "reconcile")
        if not report["verified"]:
            return None, f"{host}'s targets, hooks or evidence do not verify"
        source, _ = _call(host, mode, "familiar-verify", {"window_id": identity, "merge": merge},
                          "reconcile")
        verified[host] = {"targets": expected, "familiar": source}
    return {"at": _now(), "hosts": verified, "reconciled": True}, None


def reconcile_window(window: dict) -> dict:
    """Classify the active window against actual host state and name its one next command. Only a
    run that stopped past familiar's mark without recording its outcome changes state here."""
    _active(window)
    report = {"window_id": window["id"], "state": window["state"], "class": None,
              "blockers": [], "familiar": None, "observed": None, "next": None}
    if window["state"] in state.TERMINAL:
        return {**report, "class": "closed", "next": lifecycle.status()["next"],
                "observed": f"window {window['id']} is {window['state']}"}
    if _running_elsewhere(window):
        return {**report, "class": "running", "next": ["status"],
                "observed": f"its invocation (pid {window['owner']['pid']}) is still running"}
    if pre_merge(window):  # the abort reconciles this window's own operations itself
        return {**report, "class": "abort", "next": ["recover"],
                "observed": ("familiar and settings were never changed: recover completes the "
                             "pre-merge timer and snapshot abort only")}
    blockers, _ = _settle(window, cancel=False)
    if blockers:
        return {**report, "class": "unsettled", "blockers": blockers, "next": ["status"],
                "observed": ("unfinished host operations block every retry and recovery "
                             f"mutation until they finish or are reconciled. {STOP}")}
    if window["state"] in MIGRATED:
        return {**report, "class": "migrated", "next": lifecycle.status()["next"],
                "observed": f"window {window['id']} verified its migration"}
    found, _ = _call("titan", window["mode"], "familiar-reconcile",
                     _familiar_payload(window, (window.get("recovery") or {}).get("familiar")
                                       or {}), "reconcile")
    report["familiar"] = {key: found[key] for key in ("class", "merge", "revert", "discovered",
                                                      "reason")}
    if window["state"] == "applying":
        if "failure" in window or "recovery" in window:
            verified, reason = None, "recovery was already requested for it"
        else:
            try:
                verified, reason = _verify_migration(window, found)
            except Failed as failed:
                if failed.status == "interrupted":
                    raise
                verified, reason = None, f"{failed.step} on {failed.host}: {failed.error}"
        if verified is not None:
            merged = {**window["familiar"], "merge": found["merge"],
                      "parents": [inputs.PINS["familiar_pre"], inputs.PINS["familiar_feature_tip"]]}
            window = _save(window, state="migrated-surfaces-pending", familiar=merged,
                           verified=verified)
            return {**report, "state": window["state"], "class": "verified",
                    "next": ["restart-surfaces"],
                    "observed": (f"window {window['id']} verified its migration from actual "
                                 "state on both hosts; familiar's surfaces are pending and "
                                 "timers stay paused")}
        window = _save(window, state="recovery-required", failure={
            "step": "reconcile", "host": "titan", "status": "unverified",
            "error": f"the run stopped past familiar's mark before its verified checkpoint: "
                     f"{reason}", "log": None, "at": _now()})
    return {**report, "state": window["state"], "class": window["state"], "next": ["recover"],
            "observed": f"window {window['id']} is {window['state']}: {_summary(window)}. {STOP}"}
