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
5. familiar's actual Git state is reconciled against the window's recorded base B (a merge
   committed before its record is recorded from HEAD's history before anything else; a window
   without a recorded base is refused for inspection) and takes its one action: abort the
   attempted merge, nothing, or the plumbing restore R (B's tree with HEAD's task records);
6. each host waits for the restoration point (or a tasks-only descendant of it; on Europa, not
   past Titan's), restores its dependencies offline from this window's verified pre-merge
   snapshot, and checks familiar native.

It returns with native targets, source and dependencies verified, timers still paused and the
window `recovering`. `recover_window` is the full recover: this restoration core, then familiar's
surfaces restarted with this invocation's fresh consent (`surfaces.py`), then each host's original
timers restored and its service run to success before the window is `recovered`. Bytes matching
no recorded image and unexpected Git history stop as `inspection-required`, with nothing
force-copied, reset or reverted blindly; any other stop or signal leaves `recovering`, and the
next call repeats from reconciliation, skipping what actual state shows done. Recovery never
runs the forward check, preflight or inventory, nor any Claude executable, so stale Claude
evidence never blocks it.

`reconcile_window` reads actual state for the next command and cancels nothing. A run that
stopped past familiar's mark without recording its outcome becomes `migrated-surfaces-pending`
only when no operation on either host is unsettled (this window's dead-owner ones included, whose
children may still be writing) and actual state passes the run's own verified-checkpoint gate
(`window.verified_migration`) with Titan's four targets holding this window's applied artifacts;
otherwise it becomes `recovery-required`, which blocks fresh sessions. When only running or
unreadable operations stopped it, that window stays reconcilable: once they settle,
restart-surfaces (or run) reconciles it again; otherwise it names recover. `recover` itself is
always the full rollback.

Keys this module adds to the window record: `recovery` {started_at, attempted_at, cancelled,
codex, timers, check, targets, originals, familiar, clones, dependencies, actions, restored,
surfaces, original_timers, services, completed, failure, failures}, where `actions` lists each
destructive action once, as it is taken, `codex` is the executable the daemon stop ran and
`clones` holds a pilot's other scratch clones (`restore_native`, which the pilot shares). Recovery also
sets `state` and `owner`; reconciliation sets `failure`, or `familiar` and `verified` when it
promotes, keeping a superseded reconciliation failure in `reconciled`."""
import signal
from pathlib import Path

from . import hosts, inputs, state, surfaces
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


def _settle(window, *, cancel, reads=True):
    """Each host's unfinished operations, as (blockers, cancelled, dead): any operation still
    running, unknown or another window's, and a host that cannot be read, is a blocker for every
    mutation. This window's operations whose owner died are cancelled and recorded where
    `cancel(entry)` holds (recovery cancels them all; a surface retry only its own reads and
    surface operations; reconciliation none); the rest are returned in `dead`, untouched. With
    `reads`, any operation whose owner died and that changes nothing is cancelled too, whichever
    window or none ran it: only its bounded children could still run (ruling R48).
    Reconciliation, which cancels nothing, passes reads=False."""
    mode, identity = window["mode"], window["id"]
    blockers, cancelled, dead = [], [], []
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
            own = entry["window_id"] == identity
            read = reads and not own and lifecycle.owner_lost_read(entry)
            if (own and entry["state"] == "owner-lost") or read:
                if not read and not cancel(entry):
                    dead.append(f"{host}: {name} is owner-lost; its recorded children may still "
                                "run until recover cancels them")
                    continue
                outcome, _ = _call(host, entry.get("mode") or mode, "operation-cancel",
                                   {"operation_id": entry["operation_id"]}, "reconcile")
                cancelled.append({"host": host, "operation_id": entry["operation_id"],
                                  "operation": entry["operation"], "state": outcome["state"]})
                if outcome["state"] in hosts.TERMINAL:
                    continue
                blockers.append(f"{host}: {name} is {outcome['state']} after operation-cancel; "
                                "inspect its recorded children")
                continue
            owner = "this window's" if own else "not this window's"
            blockers.append(f"{host}: {name} is {entry['state']} and {owner}; "
                            f"{lifecycle.remedy(host, entry)}")
    return blockers, cancelled, dead


def reconcile_operations(host: str) -> dict:
    """Every unfinished operation on host, reported (ruling R48): one whose owner died gets
    operation-cancel, which stops its recorded children and records it interrupted, whichever
    window or none ran it; a running one's owner is alive, so it is reported and never
    cancelled; an operation directory without its start record is left for inspection. Returns
    {operations: [entry with its outcome], settled, observed, next}."""
    found, _ = _call(host, "live", "pending-operations", {}, "reconcile-operations")
    reported, settled = [], True
    for entry in found["operations"]:
        if entry["state"] == "owner-lost":
            outcome, _ = _call(host, entry.get("mode") or "live", "operation-cancel",
                               {"operation_id": entry["operation_id"]}, "reconcile-operations")
            if outcome["state"] in hosts.TERMINAL:
                text = f"owner-lost: cancelled; now {outcome['state']}"
            else:
                settled = False
                text = (f"owner-lost: still {outcome['state']} after operation-cancel; "
                        f"{len(outcome.get('survivors') or [])} recorded child process(es) "
                        "survive; inspect them")
        elif entry["state"] == "running":
            text = ("running: its owner is alive, so it is reported and never cancelled; let "
                    "it finish")
        else:
            settled = False
            text = (f"{entry['state']}: no start record; inspect it "
                    "(docs/runbooks/relay-cutover.md §11)")
        reported.append({**entry, "outcome": text})
    observed = (f"{host}: no unfinished operation" if not reported else
                f"{host}: every owner-lost operation is settled" if settled else
                f"{host}: an operation still needs inspection")
    return {"operations": reported, "settled": settled, "observed": observed, "next": ["status"]}


def _closed(host, mode, identity):
    found, log = _call(host, mode, "recovery-no-live", {"window_id": identity}, "no-live")
    if found["live"]:
        raise Failed("no-live", host, "blocked", "Claude or Codex is running; close every session "
                     "on both hosts (no process is exempt) and run recover again", log=log,
                     blockers=[f"{host}: no-live: {entry['harness']} process {entry['pid']} is "
                               "running" for entry in found["live"]])


def base_of(window, clone=None, host="titan"):
    """The base B this window recorded for one checkout: Titan's under `familiar.base`, or a
    pilot's other scratch clone's under `familiar.bases`; before a pilot's familiar record,
    the base each of its main clones recorded at creation. A window without one is refused for
    inspection: B is never assumed to be PRE."""
    run = window.get("familiar") or {}
    base = run.get("base") if clone is None else (run.get("bases") or {}).get(clone)
    if base is None and window.get("mode") == "pilot":
        created = (window.get("pilot") or {}).get("created") or {}
        base = (created.get(clone or "titan") or {}).get("base")
    if not isinstance(base, str):
        raise Failed("familiar-reconcile", host, "blocked", "this window recorded no familiar "
                     "base, which is never assumed to be PRE; inspect familiar's checkout; "
                     "nothing was reset or restored")
    return base


def _familiar_payload(window, recovered, clone=None, host="titan"):
    """PRE, the tip, the recorded base and whatever merge and restore this window has recorded
    for one checkout: Titan's, or with `clone` a pilot's other scratch clone, whose merge and
    base the window keeps under `familiar.clones` and `familiar.bases` (never Titan's)."""
    run = window.get("familiar") or {}
    merged = run.get("merge") if clone is None else (run.get("clones") or {}).get(clone)
    payload = {"window_id": window["id"], "pre": inputs.PINS["familiar_pre"],
               "tip": inputs.PINS["familiar_feature_tip"],
               "base": base_of(window, clone, host)}
    for key in ("merge", "revert"):
        value = recovered.get(key) or (merged if key == "merge" else None)
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
    blockers, cancelled, _ = _settle(window, cancel=lambda entry: True)
    if blockers:
        raise Failed("reconcile", blockers[0].split(":", 1)[0], "unsettled",
                     "unfinished host operations block every recovery mutation; nothing was "
                     "changed", blockers=blockers, next_command=["status"])
    # Each attempt starts from actual state; an earlier outcome stays only in `failures`, and
    # the timers re-quiesced below undo an earlier attempt's restore of them.
    earlier = {key: value for key, value in (window.get("recovery") or {}).items()
               if key not in ("restored", "failure", "surfaces", "original_timers", "services")}
    window = _save(window, state="recovering", owner=_me(), recovery={
        **earlier, "started_at": earlier.get("started_at", _now()), "attempted_at": _now(),
        "actions": earlier.get("actions", []),
        "cancelled": [*earlier.get("cancelled", []), *cancelled]})

    # Drift blocks forward progress, never restoration: the supported stop runs the Codex
    # installed at the recorded path even if it changed since preparation, recording what ran.
    step("codex-daemon-stop", "titan")
    result, log = _call("titan", mode, "codex-daemon-stop", {
        "window_id": identity, "codex_sha256": prepared["hosts"]["titan"]["codex"]["sha256"],
        "recovery": True}, "codex-daemon-stop")
    window = _recorded(window, codex=result["executable"])
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

    return restore_native(window, seen, progress)


def restore_native(window: dict, seen: list, progress: dict, *, clones=("titan",),
                   scopes: dict | None = None, pending=PENDING) -> dict:
    """The core's offline restoration, stages 4-6, after the window's operations settled and
    its hosts are closed: every target checked against this window's images, the registered
    ones restored in reverse ledger order and all verified native; familiar's actual Git state
    reconciled and restored in each checkout this window merged (`clones`: Titan's, whose revert
    reaches Europa by synchronization; a pilot's two scratch clones); then each host's
    dependencies from its verified pre-merge snapshot. `scopes` adds each host's request scope,
    a pilot's scratch root. The window records `restored` with what stays `pending`."""
    scopes = scopes or {host: {} for host in HOST_ORDER}
    window = _restore_targets(window, seen, progress, scopes)
    reverts = {}
    for host in clones:
        window, recovered = restore_clone(window, host, seen, progress, scope=scopes[host],
                                          key=None if host == "titan" else host)
        reverts[host] = recovered["revert"]
    observed = None  # Titan's HEAD as its own restore observed it (live: one shared checkout)
    for host in HOST_ORDER:
        clone = None if host == "titan" or host not in clones else host
        window, result = restore_dependencies(
            window, host, reverts.get(host, reverts["titan"]), seen, progress,
            scope=scopes[host], base=base_of(window, clone, host),
            titan_head=observed if window["mode"] == "live" else None)
        observed = observed or result["head"]
    if seen:
        raise _Interrupt(seen[-1])
    return _recorded(window, restored={"at": _now(), "revert": reverts["titan"],
                                       "pending": list(pending)})


def _restore_targets(window, seen, progress, scopes):
    """Stage 4: every target against this window's images; the registered ones restored in
    reverse ledger order; all four native on Titan and, once synchronized, Europa's two."""
    mode, identity = window["mode"], window["id"]

    def step(name, host):
        nonlocal window
        window = _step(window, seen, progress, name, host)

    sealed = window["sealed"]["inputs"]
    titan = sealed["hosts"]["titan"]
    step("target-check", "titan")
    checked, log = _call("titan", mode, "target-check", {
        "window_id": identity,
        "frozen": {target_id: entry["frozen"]["sha256"] for target_id, entry in titan.items()},
        **scopes["titan"]}, "target-check")
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
            "identities": {name: titan[target_id]["identities"][name] for name in RELAY},
            **scopes["titan"]}, "target-restore")
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
            "verify": False, "manifest_sha256": sealed["manifest_sha256"], **scopes[host]},
            "target-originals")
        differing = sorted(target_id for target_id, entry in found["targets"].items()
                           if not entry["matches"])
        if differing:
            raise Failed("target-originals", host, "blocked", f"{', '.join(differing)} do not "
                         "hold their native bytes" + (" after waiting for synchronization; "
                                                      "it may still be synchronizing"
                                                      if host != "titan" else ""), log=log)
    return _recorded(window, originals={"at": _now(), "targets": native})


def restore_clone(window: dict, host: str, seen: list, progress: dict, *, scope: dict,
                  key: str | None = None) -> tuple[dict, dict]:
    """Stage 5 for one familiar checkout on host: its actual Git state reconciled (a merge
    committed before its record is recorded from its parents before anything acts on it), then
    its one action: abort the attempted merge, nothing, or one revert. `key` names the
    checkout: none for Titan's, recorded under `familiar`; else a pilot's other scratch clone,
    whose merge is `familiar.clones[key]` and whose record is `clones[key]`. Returns the window
    and that record."""
    mode = window["mode"]

    def step(name, on):
        nonlocal window
        window = _step(window, seen, progress, name, on)

    def keep(recovered):
        if key is None:
            return _recorded(window, familiar=recovered)
        return _recorded(window, clones={**window["recovery"].get("clones", {}), key: recovered})

    recovered = (window["recovery"].get("familiar") if key is None
                 else window["recovery"].get("clones", {}).get(key)) or {}
    step("familiar-reconcile", host)
    found, log = _call(host, mode, "familiar-reconcile",
                       {**_familiar_payload(window, recovered, key, host), **scope},
                       "familiar-reconcile")
    if found["class"] == "unexpected":
        raise Failed("familiar-reconcile", host, "blocked", f"{found['reason']}; inspect "
                     "familiar's checkout; nothing was reset or reverted", log=log)
    if (found["merge"] and not recovered.get("merge")) or found.get("abandoned"):
        # A merge or restore found only in Git, or a recorded restore that can no longer apply,
        # is recorded before anything acts on it.
        abandoned = recovered.get("abandoned", [])
        if found.get("abandoned") and found["abandoned"] not in abandoned:
            abandoned = [*abandoned, found["abandoned"]]
        recovered = {**recovered, "merge": found["merge"] or recovered.get("merge"),
                     "discovered": found["discovered"], "class": found["class"],
                     "abandoned": abandoned}
        if found.get("abandoned"):
            recovered.pop("revert", None)
        window = keep(recovered)
    step("familiar-restore", host)
    result, _ = _call(host, mode, "familiar-restore",
                      {**_familiar_payload(window, recovered, key, host),
                       "expect": found["class"], **scope}, "familiar-restore")
    recovered = {**recovered, "class": result["class"], "action": result["action"],
                 "revert": result["revert"], "head": result["head"], "at": _now()}
    window = keep(recovered)
    if result["action"] != "none":
        window = _act(window, host, result["action"], revert=result["revert"])
    return window, recovered


def restore_dependencies(window: dict, host: str, revert: str, seen: list, progress: dict, *,
                         scope: dict, base: str, titan_head: str | None = None,
                         key: str | None = None) -> tuple[dict, dict]:
    """Stage 6 on host: once its source is the restoration point or a tasks-only descendant of
    it (and, with `titan_head`, not past the HEAD Titan's own restore observed), its
    dependencies from this window's verified pre-merge snapshot, offline. `key` names the
    record, the host's own by default. Returns the window and the result."""
    window = _step(window, seen, progress, "dependency-restore", host)
    result, _ = _call(host, window["mode"], "dependency-restore", {
        "window_id": window["id"], "pre": inputs.PINS["familiar_pre"], "base": base,
        "revert": revert, **({"titan_head": titan_head} if titan_head else {}), **scope},
        "dependency-restore")
    window = _recorded(window, dependencies={**window["recovery"].get("dependencies", {}),
                                             key or host: result})
    if result["replaced"]:
        window = _act(window, host, "dependency-restore")
    return window, result


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
    if "surfaces" in recovery:
        done.append("familiar's surfaces were restarted from it")
    if recovery.get("original_timers"):
        done.append("original timers are restored on " + ", ".join(recovery["original_timers"]))
    return "; ".join(done) or "nothing has been restored yet"


def _stopped(failed, lead=None):
    """Record a stopped recovery: inspection when it observed unknown bytes or history (drift,
    by the stop's cause), else recovering. `lead` replaces the report's account of the stop."""
    inspect = ((failed.step in INSPECT and failed.drift)
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
        lead = lead or ("stopped pending inspection: nothing was force-copied, reset or reverted "
                        "blindly" if inspect else
                        f"recovery stopped at {failed.step} on {failed.host}")
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


def _original_timers(window, seen, progress):
    """Stage 6: each host's timers back to this window's original record, then its service run
    once and required to succeed. Only then is the window `recovered`."""
    mode, identity = window["mode"], window["id"]

    def step(name, host):
        nonlocal window
        window = _step(window, seen, progress, name, host)

    stopped = lifecycle._stopped(window)
    for host in HOST_ORDER:
        step("timer-restore", host)
        result, _ = _call(host, mode, "timer-restore", {
            "window_id": identity, "record_sha256": window["timers"][host]["sha256"],
            "stopped": host in stopped}, "timer-restore")
        window = _recorded(window, original_timers={
            **window["recovery"].get("original_timers", {}), host: result})
    for host in HOST_ORDER:
        step("service-run", host)
        result, _ = _call(host, mode, "service-run", {
            "window_id": identity, "record_sha256": window["timers"][host]["sha256"]},
            "service-run")
        window = _recorded(window, services={**window["recovery"].get("services", {}),
                                             host: result})
    if seen:
        raise _Interrupt(seen[-1])
    return _save(window, state="recovered", recovery={**window["recovery"],
                                                      "completed": {"at": _now()}})


def recover_window(window: dict, decision: dict | None, *, held=None) -> dict:
    """The full recover. A window that never reached familiar's mark takes the pre-merge abort
    only, with no decision. Any other runs the six stages in order, every attempt from the first:

    1-4. `restore_window`: strict no-live, both hosts' timers stopped again from their original
       records, every touched target restored and verified, familiar's source reverted and its
       dependencies restored offline;
    5. familiar's recorded surfaces restarted from the native source with this invocation's
       consumed `recover` decision (the run's or any earlier consent never covers it); an
       explained absence stays absent, and surfaces this recovery already restarted are not
       restarted again;
    6. each host's original timer state restored and its service run to success.

    Until stage 6 passes the window stays `recovering` and every report says not to open Claude
    or Codex; a stop at any stage records it and names `recover` again.

    `held` is why stage 5 cannot run in this invocation: its entry-time desktop preview was
    blocked, or the operator declined its restarts (rulings R36 and R46). Stages 1-4 still run,
    since they touch no desktop and are what recover was invoked for; recover then stops in
    `recovering` before stage 5, naming `held`, and a rerun previews the desktop and asks again."""
    _active(window)
    if pre_merge(window):
        return restore_window(window)
    if held is not None:
        window = restore_window(window)["window"]
        when = ("once the desktop blocker is inspected and cleared"
                if held.step == "surface-preview" else
                "when the operator approves recovery's surface restarts")
        held.next_command = ["recover"]
        raise _stopped(held, lead=(
            "native settings, source and dependencies are restored, and familiar's surfaces and "
            f"the original timers wait for recover again, {when}: it previews the desktop and "
            "asks before any restart"))
    todo = surfaces.pending(window, surfaces.RECOVERY)
    if decision is None:
        if any(todo.values()):
            raise Failed("decision", "titan", "refused", "recover restarts familiar's surfaces "
                         "only with this invocation's own desktop decision; ask the operator at "
                         "their terminal", observed="nothing was changed",
                         next_command=["recover"])
    else:
        if decision.get("action") != surfaces.RECOVER_ACTION:
            raise Failed("decision", "titan", "refused", "only a decision for this recovery "
                         "authorizes its restarts; an earlier run's or retry's consent does not",
                         observed="nothing was changed", next_command=["recover"])
        surfaces.authorized(window, decision)
    window = restore_window(window)["window"]
    if decision is not None:
        try:
            window = surfaces.restart_surfaces(window, decision)["window"]
        except Failed as failed:
            raise _stopped(failed) from None
    window = _recorded(window, surfaces={"at": _now(),
                                         "attempt": (decision or {}).get("attempt_id")})
    progress = {"step": "timer-restore", "host": "titan"}
    with _signals() as seen:
        try:
            window = _original_timers(window, seen, progress)
        except (Exception, _Interrupt) as error:
            failed = _as_failed(error, progress)
        else:
            return {"class": "recovered", "state": window["state"], "window": window,
                    "stages": {stage: "passed" for stage in (
                        "no-live", "timers-requiesced", "targets", "source", "dependencies",
                        "native-surfaces", "original-timers")},
                    "observed": (f"window {window['id']} is recovered: {_summary(window)} on "
                                 "both hosts; familiar-reap.service succeeded; fresh native "
                                 "sessions may start"),
                    "next": lifecycle.status()["next"]}
    raise _stopped(failed)


# --- reconciliation -------------------------------------------------------------------------


def _verify_migration(window, found):
    """(verified, None) when actual state is the sealed migration, else (None, what differs):
    familiar is the attempted merge, Titan's four targets hold this window's own applied
    artifacts, and the run's own verified-checkpoint gate passes on both hosts."""
    if found["class"] != "merged":
        return None, f"familiar is {found['class']}, not the attempted merge"
    titan = window["sealed"]["inputs"]["hosts"]["titan"]
    try:
        checked, _ = _call("titan", window["mode"], "target-check", {
            "window_id": window["id"], "frozen": {target_id: entry["frozen"]["sha256"]
                                                  for target_id, entry in titan.items()}},
            "target-check")
        applied = sorted(target_id for target_id, entry in checked["targets"].items()
                         if entry["verdict"] != "relay-applied"
                         or entry["sha256"] != titan[target_id]["expected"]["sha256"])
        if applied:
            return None, f"{', '.join(applied)} do not hold this window's applied artifact bytes"
        hosts_verified = lifecycle.verified_migration(window, found["merge"])
    except Failed as failed:
        if failed.status == "interrupted":
            raise
        return None, f"{failed.step} on {failed.host}: {failed.error}"
    return {"at": _now(), "hosts": hosts_verified, "reconciled": True}, None


def reconcilable(window: dict) -> bool:
    """Whether reconciliation may still promote the window to its verified migration: it is past
    familiar's mark with nothing recovered, and either the run never recorded its outcome or
    reconciliation itself stopped beside unsettled operations, which took no mutation. A window
    stopped by any other failure needs recover."""
    if "recovery" in window or pre_merge(window):
        return False
    failure = window.get("failure")
    if window["state"] == "applying":
        return failure is None
    return (window["state"] == "recovery-required" and isinstance(failure, dict)
            and failure.get("step") == "reconcile" and failure.get("status") == "unsettled")


def _promote(window, **changes):
    """Save the promoted window; a reconciliation failure it supersedes moves to `reconciled`."""
    state._current(window)
    updated = {key: value for key, value in window.items() if key != "failure"}
    if "failure" in window:
        updated["reconciled"] = [*window.get("reconciled", []), window["failure"]]
    updated.update(changes)
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, hosts.INTERRUPTS)
    try:
        state.save_record(Path(window["directory"]) / "window.json", updated)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
    return updated


def reconcile_window(window: dict) -> dict:
    """Classify the active window against actual host state and name its one next command. Only a
    run that stopped past familiar's mark without recording its outcome, or one reconciliation
    already stopped beside unsettled operations (`reconcilable`), changes state here."""
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
    blockers, _, dead = _settle(window, cancel=lambda entry: False, reads=False)
    if reconcilable(window) and (blockers or dead):
        # Unsettled work may still be writing: never promote beside it. Reconciliation cancels
        # nothing; recover cancels this window's dead-owner operations before it acts. Work
        # that is only running or unreadable may settle, and then restart-surfaces reconciles
        # this window again; a dead owner's never settles by itself.
        from .cli import command_line  # the operator's complete command, as cli prints it
        unsettled = [*blockers, *dead]
        following = ["recover"] if dead else ["restart-surfaces"]
        window = _save(window, state="recovery-required", failure={
            "step": "reconcile", "host": unsettled[0].split(":", 1)[0], "status": "unsettled",
            "error": "the run stopped past familiar's mark beside unsettled operations: "
                     + "; ".join(unsettled), "log": None, "at": _now(), "next": following})
        then = (f"run {command_line(['recover'])}: it cancels this window's dead-owner "
                "operations and rolls the window back" if dead else
                f"once they settle, {command_line(['restart-surfaces'])} reconciles it again, "
                f"or {command_line(['recover'])} rolls it back")
        return {**report, "state": window["state"], "class": "recovery-required",
                "blockers": unsettled, "next": following,
                "observed": (f"window {window['id']} is recovery-required: its migration is not "
                             "verified beside unsettled operations (" + "; ".join(unsettled)
                             + f"); {then}. {STOP}")}
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
    if window["state"] == "applying" or reconcilable(window):
        if reconcilable(window):
            verified, reason = _verify_migration(window, found)
        else:
            verified, reason = None, "recovery was already requested for it"
        if verified is not None:
            merged = {**window["familiar"], "merge": found["merge"],
                      "parents": [window["familiar"]["base"],
                                  inputs.PINS["familiar_feature_tip"]]}
            window = _promote(window, state="migrated-surfaces-pending", familiar=merged,
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
