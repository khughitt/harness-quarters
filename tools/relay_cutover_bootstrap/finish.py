"""finish: the cutover window's normal completion, on the controller.

`finish_window` runs from `ready-for-smokes`, or again from `finishing`, once every required
smoke receipt is recorded (`smoke.validate_smokes`, before any host is contacted). Each attempt
repeats, from actual state:

1. this window's unfinished operations on both hosts are settled: a dead owner's read, timer
   restore or service run is cancelled and recorded, anything else unfinished stops finish;
2. the fresh checks, before any timer changes: each host's Claude (and Titan's Codex)
   executable is still the prepared one, or the hold is breached and the window needs full
   recovery; each target holds the window's sealed bytes apart from Claude's pick keys, which a
   resumed session may have saved, with hooks, statusLine, installer and evidence verified;
   familiar is the merge or a tasks-only descendant of it, clean outside `tasks/`, with its
   pinned relay dependency, Europa's HEAD equal to or an ancestor of the HEAD observed on Titan
   (reread before an "ahead" counts, ruling R68), and each host's observed HEAD recorded;
   familiar's recorded surfaces still run as restarted. Drift beyond picks stops for inspection
   and recover; a surface that exited, was replaced or sits behind a desktop blocker stops
   finish with nothing changed, for a consented `restart-surfaces` retry;
3. the window becomes `finishing`; each host's timers return to the window's original record
   (quiesce's `timer-restore`, `stopped` true), which is never rewritten;
4. each host runs `familiar-reap.service` once its timers are restored and waits for it,
   requiring `Result=success` and `ExecMainStatus=0` (restoration's `service-run`);
5. closure: each recorded abruptly killed session's row and intent entry are gone from its
   host, and the controller, while its recorded process lives, keeps its row and intent entry.

Then the window is `complete`: the held-launch rule and the Claude pick freeze end, and
ordinary launches use their prior update policy while held sessions stay held until they exit.
A stop leaves the timers named in the report and `finish` repeats from step 1; it never edits
hooks or source, never restores a target and never replaces an original timer record. Keys this
module adds to the window record: `finish` {started_at, attempted_at, attempts, checks, timers,
services, closure, failure, failures, completed}."""
import copy

from . import hosts, smoke, state
from . import window as lifecycle
from .state import Stop

FINISHABLE = ("ready-for-smokes", "finishing")
# A finish retry cancels this window's own dead-owner reads and finish operations only.
OWN = ("timer-restore", "service-run", "service-check")
INSPECT = ("target-verify", "familiar-verify")
RELEASE = ("finish released the cutover's hold: ordinary launches use their prior update "
           "policy again, and cl, clw and Claude model or effort changes are allowed again; "
           "held sessions keep DISABLE_UPDATES=1 until they exit, so exit them for ordinary "
           "updates")


def _record(window):
    return copy.deepcopy(window.get("finish") or {})


def _recorded(window, **changes):
    return lifecycle._save(window, finish={**_record(window), **changes})


def _refuse(window, reason, following=None):
    report = lifecycle.status()
    return lifecycle.Failed("finish", "titan", "refused",
                            f"window {window['id']} is {window['state']}; {reason}",
                            observed=report["detail"], next_command=following or report["next"])


def _gate(window):
    if window["mode"] != "live":
        raise lifecycle.Failed("finish", "titan", "refused", f"window {window['id']} is a "
                               f"{window['mode']} window: pilot receipts never satisfy a live "
                               "finish, and finish runs only for a live window",
                               observed="nothing was changed", next_command=["status"])
    if window["state"] == "migrated-surfaces-pending":
        raise _refuse(window, "familiar's surfaces must restart before the smokes and finish")
    if window["state"] not in FINISHABLE:
        raise _refuse(window, "finish runs only once every smoke is recorded")
    owner = window.get("owner")
    if owner is not None and owner != lifecycle._me() and hosts._alive(owner):
        raise _refuse(window, f"its invocation (pid {owner['pid']}) is still running",
                      ["status"])
    desktop = window.get("desktop") or {}
    if "forward" not in (desktop.get("completed") or {}):
        raise _refuse(window, "familiar's surfaces have no completed restart recorded")


def _cancellable(entry):
    spec = hosts._operations().get(entry["operation"])
    return spec is not None and (entry["operation"] in OWN or not spec.mutation)


def _settle(window):
    from . import recovery  # recovery imports surfaces, which imports the window lifecycle
    blockers, cancelled, dead = recovery._settle(window, cancel=_cancellable)
    blockers += dead
    if blockers:
        raise lifecycle.Failed("reconcile", blockers[0].split(":", 1)[0], "unsettled",
                               "a host's operations are unfinished or cannot be read, so finish "
                               "changed nothing; once that host answers (its SSH or user "
                               "systemd permission allowed) and they settle, run finish again",
                               blockers=blockers)
    return cancelled


def _fresh(window, prepared, step):
    """The checks before any timer changes: hold, targets, familiar, then the surfaces."""
    mode, identity = window["mode"], window["id"]
    for host in lifecycle.HOST_ORDER:
        step("smoke-observe", host)
        seen = smoke.observe(state.current_window(lifecycle._root()), host)
        smoke.hold(seen["window"], prepared, host, seen["observation"])
    window = state.current_window(lifecycle._root())
    sealed, checks, observed = window["sealed"]["inputs"], {}, None
    for host in lifecycle.HOST_ORDER:
        step("target-verify", host)
        expected = {target_id: result["expected"]["sha256"]
                    for target_id, result in sealed["hosts"][host].items()}
        found, log = lifecycle._call(host, mode, "target-verify", {
            "window_id": identity, "targets": expected, "wait": False, "verify": True,
            "picks": True, "manifest_sha256": sealed["manifest_sha256"]}, "target-verify")
        if not found["verified"]:
            differing = sorted(target_id for target_id, entry in found["targets"].items()
                               if not entry["matches"] and target_id not in found["picks"])
            raise lifecycle.Failed("target-verify", host, "blocked", f"{', '.join(differing)} "
                                   "differ from the window's sealed output beyond Claude's pick "
                                   "keys; nothing was restored", log=log)
        step("familiar-verify", host)
        def verify(head, host=host):
            return lifecycle._call(host, mode, "familiar-verify", {
                "window_id": identity, "merge": window["familiar"]["merge"],
                **({"titan_head": head} if head else {})}, "familiar-verify")

        source, _ = lifecycle.prove_source(host, mode, identity, observed, verify,
                                           "familiar-verify", step)
        observed = observed or source["head"]
        checks[host] = {"picks": found["picks"], "familiar": source, "surfaces": None}
    from . import surfaces  # surfaces imports the window lifecycle
    recorded = window["desktop"]["hosts"]
    for host in lifecycle.HOST_ORDER:
        if recorded[host]["state"] != "present":
            continue
        step("surface-preview", host)
        found, _ = lifecycle._call(host, mode, "surface-preview", {
            "window_id": identity, "phase": surfaces.FORWARD, "recorded": recorded[host]},
            "surface-preview")
        checks[host]["surfaces"] = {
            "blockers": found["blockers"], "changes": found["changes"],
            "verdicts": {name: entry["verdict"] for name, entry in found["surfaces"].items()}}
        retry = surfaces.unwell(found, recorded[host])
        if found["blockers"] or retry:
            problems = [*found["blockers"], *found["changes"]] + [
                f"{name} is {found['surfaces'][name]['verdict']}, not running as restarted"
                for name in retry if found["surfaces"][name]["verdict"] not in surfaces.HEALTHY]
            raise lifecycle.Failed(
                "surface-check", host, "blocked", "familiar's surfaces need a consented retry "
                "before finish: " + "; ".join(problems) + "; nothing was changed",
                blockers=[f"{host}: surface: {problem}" for problem in problems],
                next_command=["restart-surfaces"])
    return _recorded(state.current_window(lifecycle._root()), checks={
        "at": lifecycle._now(), "hosts": checks})


def _timers(window, step):
    for host in lifecycle.HOST_ORDER:
        step("timer-restore", host)
        result, _ = lifecycle._call(host, window["mode"], "timer-restore", {
            "window_id": window["id"], "record_sha256": window["timers"][host]["sha256"],
            "stopped": True}, "timer-restore")
        if not result.get("restored"):
            raise lifecycle.Failed("timer-restore", host, "blocked", "this window recorded no "
                                   "timers to restore on this host; inspect it")
        window = state.current_window(lifecycle._root())
        window = _recorded(window, timers={**_record(window).get("timers", {}), host: result})
    return window


def _services(window, step):
    for host in lifecycle.HOST_ORDER:
        step("service-run", host)
        result, _ = lifecycle._call(host, window["mode"], "service-run", {
            "window_id": window["id"], "record_sha256": window["timers"][host]["sha256"]},
            "service-run")
        window = state.current_window(lifecycle._root())
        window = _recorded(window, services={**_record(window).get("services", {}),
                                             host: result})
    return window


def _closure(window, step):
    """Each recorded abruptly killed session gone from its host; the live controller kept."""
    receipts = smoke._smokes(window)["receipts"]
    proof = smoke._smokes(window).get("controller")
    closure = {"hosts": {}, "controller": "exited"}
    for host in lifecycle.HOST_ORDER:
        step("closure", host)
        seen = smoke.observe(state.current_window(lifecycle._root()), host)
        observation = seen["observation"]
        killed = sorted(f"{entry['receipt']['harness']}:"
                        f"{entry['receipt']['cases']['abrupt-death']['session_id']}"
                        for entry in receipts.values() if entry["receipt"]["host"] == host
                        and "abrupt-death" in entry["receipt"]["cases"])
        for row_id in killed:
            session = row_id.split(":", 1)[1]
            if row_id in observation["agents"] or session in observation["intent"]["sessions"]:
                raise lifecycle.Failed("closure", host, "blocked", f"the recorded dead row "
                                       f"{row_id} or its intent entry is still present; reap "
                                       "it on this host (relay reap, then familiar reap)")
        closure["hosts"][host] = {"dead_rows_absent": killed, "observation": seen["ref"]["path"]}
        if host == "titan" and proof is not None:
            alive = any(entry["pid"] == proof["pid"]
                        and str(entry["start_time"]) == str(proof["start"])
                        for entry in observation["processes"])
            if alive:
                row = observation["agents"].get(proof["row_id"])
                if (row is None or row["liveness"] != "alive"
                        or proof["session_id"] not in observation["intent"]["sessions"]):
                    raise lifecycle.Failed("closure", host, "blocked", "the live controller's "
                                           f"row {proof['row_id']} or its intent entry was not "
                                           "preserved; inspect familiar's reap")
                closure["controller"] = "kept"
        window = seen["window"]
    return _recorded(state.current_window(lifecycle._root()), closure=closure)


def _summary(window):
    record = _record(window)
    restored = [host for host in lifecycle.HOST_ORDER if host in record.get("timers", {})]
    ran = [host for host in lifecycle.HOST_ORDER if host in record.get("services", {})]
    paused = [host for host in lifecycle.HOST_ORDER
              if host in lifecycle._stopped(window) and host not in restored]
    parts = []
    if restored:
        parts.append(f"familiar-reap.timer restored on {' and '.join(restored)}")
    if ran:
        parts.append(f"familiar-reap.service succeeded on {' and '.join(ran)}")
    if paused:
        parts.append(f"familiar-reap.timer still paused on {' and '.join(paused)}")
    return "; ".join(parts) or "no timer was restored"


def _stopped(failed, window):
    """Record a stopped finish. Drift beyond picks, by the stop's cause, needs inspection and
    recover; a hold breach already sent the window to recovery; anything else, a refusal, a
    transport failure or an unsettled request included, leaves the window to finish again."""
    if failed.step == "hold":
        return failed
    inspect = failed.step in INSPECT and failed.drift
    try:
        current = state.current_window(lifecycle._root())
        entry = {"step": failed.step, "host": failed.host, "status": failed.status,
                 "error": failed.error, "log": failed.log, "at": lifecycle._now()}
        record = _record(current)
        changes = {"finish": {**record, "failure": entry,
                              "failures": [*record.get("failures", []), entry]}}
        if inspect:
            changes.update(state="inspection-required", failure=entry)
        current = lifecycle._save(current, **changes)
    except (Stop, OSError) as error:
        failed.observed = (f"the window record could not be updated ({hosts._brief(error)}); "
                           "run status")
        failed.next_command = ["status"]
        return failed
    if inspect:
        failed.observed = (f"window {current['id']} is inspection-required: its settings, "
                           "familiar source or dependencies changed beyond Claude's pick keys "
                           f"since the verified migration; {_summary(current)}. Do not open "
                           "Claude or Codex until recover completes")
        failed.next_command = ["recover"]
    elif failed.step == "surface-check":
        failed.observed = (f"window {current['id']} is {current['state']}: {_summary(current)}; "
                           "no timer changed. restart-surfaces retries only the surfaces not "
                           "running as restarted, with fresh consent, and keeps the smoke "
                           "receipts; then run finish again")
        failed.next_command = ["restart-surfaces"]
    else:
        failed.observed = (f"window {current['id']} is {current['state']}: {_summary(current)}; "
                           "finish repeats from actual state, and the hold stays until it "
                           "completes")
        failed.next_command = ["finish"]
    return failed


def status(window: dict) -> dict:
    """The read-only status detail and next command of a finishing window."""
    failure = _record(window).get("failure")
    last = (f"; finish stopped at {failure['step']} on {failure['host']} ({failure['status']})"
            if failure else "")
    return {"detail": (f"window {window['id']} is finishing: {_summary(window)}{last}; finish "
                       "repeats from actual state"), "next": ["finish"]}


def finish_window(window: dict) -> dict:
    """The window's normal completion, or Failed naming the step and the timers' state; see the
    module docstring for its order. Returns {window, state, observed, next}."""
    state._current(window)
    _gate(window)
    smoke.validate_smokes(window)
    prepared = smoke._prepared(window)
    progress = {"step": "reconcile", "host": "titan"}
    with lifecycle._signals() as seen:
        try:
            record = _record(window)
            window = lifecycle._save(window, owner=lifecycle._me(), finish={
                **record, "started_at": record.get("started_at", lifecycle._now()),
                "attempted_at": lifecycle._now(), "attempts": record.get("attempts", 0) + 1})

            def step(name, host):
                lifecycle._step(state.current_window(lifecycle._root()), seen, progress, name,
                                host)

            _settle(window)
            window = _fresh(window, prepared, step)
            window = lifecycle._save(window, state="finishing")
            window = _timers(window, step)
            window = _services(window, step)
            window = _closure(window, step)
            if seen:
                raise lifecycle._Interrupt(seen[-1])
            window = lifecycle._save(window, state="complete", finish={
                **_record(window), "failure": None, "completed": {"at": lifecycle._now()}})
        except (Exception, lifecycle._Interrupt) as error:
            failed = lifecycle._as_failed(error, progress)
        else:
            return {"window": window, "state": window["state"],
                    "observed": f"window {window['id']} is complete: {_summary(window)}",
                    "next": lifecycle.status()["next"]}
    raise _stopped(failed, window)
