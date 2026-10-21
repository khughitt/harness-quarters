"""Familiar's two desktop surfaces: their consent-bound restart, its retry and the pilot probe.

A window records each host's desktop as its consent subject binds it (`window.desktop_subject`):
its state and explained absence, the trusted niri socket, and each surface's one startup command
with its recorded process (PID, start time and argv). An explained absence stays absent: nothing
is started there. Each phase of the window (`forward`: run and restart-surfaces; `recovery`:
recover) restarts every present surface once:

- a recorded process still running as recorded gets TERM and is waited for; nothing else is ever
  signalled;
- a recorded process that exited is expected: its surface's command simply starts;
- the command starts through niri's own spawn on the recorded socket (`niri msg action spawn-sh
  -- COMMAND`), exactly as `spawn-sh-at-startup` runs it, and the one new process that stays up
  is the validated replacement;
- a changed socket or startup command, a recorded PID now held by another process, or a surface
  process nobody recorded stops that restart before any signal or spawn: it needs inspection,
  then a new inventory and a new decision.

Each replacement is journaled on its host before the operation replies (`surfaces/<window-id>.json`
in the cutover root) and persisted in the window before the next surface. A retry asks again,
adopts a replacement a partial attempt already started and starts only the surfaces still missing.

Host side, the fixed operations in `OPERATIONS`:

- `surface-preview` (both hosts, read-only): the desktop now against the recorded inventory, and
  that host's new inventory when its context changed;
- `surface-restart` (both, live only): one recorded surface, as above;
- `surface-probe` (both, pilot only): the fixed command `true` through the same niri spawn; it
  proves the spawn route, not a surface's health.

Controller side: `preview` builds an action's consent subject, `bind` keeps a consumed decision's
subject in the window, `restart_surfaces` takes one consumed decision through the restart, and
`probe_subject` and `probe` drive the pilot's spawn. Keys this module adds to the window record:
`desktop` {hosts, phases {phase: {host: {surface: replacement record}}}, attempts, completed,
failure, failures} and, for a pilot, `probes`."""
import copy
import json
import os
import signal
import time
from pathlib import Path

from . import hosts, inventory, quiesce, state
from .state import Stop

SURFACES = tuple(inventory.SURFACES)
FORWARD, RECOVERY = "forward", "recovery"
RESTART_ACTION, RECOVER_ACTION, PROBE_ACTION = "restart-surfaces", "recover", "pilot-spawn"
RUN_ACTION = "run"  # window.RUN_ACTION, the run's own decision
ACTIONS = {RUN_ACTION: FORWARD, RESTART_ACTION: FORWARD, RECOVER_ACTION: RECOVERY}
PREFIXES = {RESTART_ACTION: "restart", RECOVER_ACTION: "recover", PROBE_ACTION: "probe"}
JOURNAL = "surfaces"
PROBE_COMMAND = "true"
RECOVERY_IMPACT = ("familiar's niri watcher and desktop panel stop and start again from the "
                   "restored native source; the panel is briefly absent")
PROBE_IMPACT = ("niri runs the fixed command true through its spawn on each named host; no "
                "window opens and no surface stops")
IPC_SECONDS = 10
SPAWN_SECONDS = 10
STOP_SECONDS = 10.0  # the wait for a recorded process to exit after TERM
APPEAR_SECONDS = 15.0  # the wait for one replacement to appear and stay up
SETTLE_SECONDS = 2.0  # how long that one new process must stay the only one
POLL_SECONDS = 0.1
RESTART_DEADLINE = IPC_SECONDS + STOP_SECONDS + SPAWN_SECONDS + APPEAR_SECONDS + 60


# --- host side -------------------------------------------------------------------------------


def _terminate(identity):
    """TERM one recorded surface process while it is still that process (a pidfd pins it)."""
    return hosts._send(identity, signal.SIGTERM)


def _identity(row):
    return {"pid": row["pid"], "start_time": row["start_time"], "argv": row["argv"]}


def _running(name, home):
    return [_identity(row) for row in inventory._process_rows()
            if inventory._is_surface(name, row, home)]


def _journal_path(context):
    return Path(context["root"]) / JOURNAL / f"{context['payload']['window_id']}.json"


def _journal(context):
    """This window's journal on this host: what each phase's restart of each surface did."""
    path = _journal_path(context)
    if not os.path.lexists(path):
        return {}
    record = state.load_record(path)
    if (record.get("window_id") != context["payload"]["window_id"]
            or not isinstance(record.get("entries"), dict)):
        raise Stop(f"{path}: not this window's surface journal; inspect it")
    return record["entries"]


def _journaled(context, key, entry):
    entries = {**_journal(context), key: {**entry, "at": hosts._now()}}
    state.save_record(_journal_path(context), {
        "schema": 1, "window_id": context["payload"]["window_id"], "entries": entries})


def _niri(context, label, argv, socket, timeout):
    """One niri client child on the explicitly named socket; an inherited one is never used."""
    return hosts._run_child(context, label, [hosts.TOOLS["niri"], "msg", *argv],
                            env={**hosts._child_env(context), "NIRI_SOCKET": socket},
                            timeout=timeout)


def _ipc(context, socket):
    """Whether read-only niri IPC answers on the socket."""
    try:
        result = _niri(context, "niri-ipc", ["--json", "version"], socket, IPC_SECONDS)
        return result.returncode == 0 and isinstance(json.loads(result.stdout or b"null"), dict)
    except (Stop, OSError, ValueError):
        return False


def _spawn(context, socket, command, label):
    """Start one command through niri's own spawn, as `spawn-sh-at-startup` does: niri, not
    this operation, is its parent. Niri's exit status is the acknowledgement."""
    result = _niri(context, label, ["action", "spawn-sh", "--", command], socket, SPAWN_SECONDS)
    if result.returncode != 0:
        raise Stop(f"niri msg action spawn-sh exited {result.returncode} on the trusted socket; "
                   "see the private log")


def _classify(surface, rows, home, configured, entry, report):
    """One recorded surface now: `running` as recorded, `exited`, `missing` (none recorded),
    `restarted` by this phase already, or `reused` (its PID is another process). Unrecorded
    processes and the reused PID are changes; a changed command or two processes are blockers."""
    name = surface["name"]
    running = [_identity(row) for row in rows if inventory._is_surface(name, row, home)]
    recorded = surface["processes"][0] if surface["processes"] else None
    restarted = entry.get("replacement") if entry.get("state") == "started" else None
    if configured != surface["configured"]:
        report["blockers"].append(f"{name}: its niri startup command is not the recorded one")
    held = next((row for row in rows if recorded is not None
                 and row["pid"] == recorded["pid"]), None)
    if recorded is None:
        verdict = "missing"
    elif held is None:
        verdict = "exited"
    elif _identity(held) == recorded and recorded in running:
        verdict = "running"
    else:
        verdict = "reused"
        report["changes"].append(f"{name}: its recorded pid {recorded['pid']} now belongs to "
                                 "another process")
    if (restarted is not None and restarted in running
            and (verdict in ("missing", "exited") or recorded == restarted)):
        verdict = "restarted"
    known = {"restarted": restarted, "running": recorded}.get(verdict)
    others = [process for process in running if process != known]
    if len(others) > 1 or (others and known is not None):
        report["blockers"].append(f"{name}: {len(running)} processes run it; inspect them")
    elif others:
        report["changes"].append(f"{name}: pid {others[0]['pid']} runs it and was never "
                                 "recorded")
    return {"verdict": verdict, "process": recorded,
            "restarted": restarted if verdict == "restarted" else None,
            "running": running, "configured": configured}


def _observe(context, recorded, phase, names):
    """The desktop now against one host's recorded inventory, for the named surfaces."""
    home = Path(context["home"])
    rows = inventory._process_rows()
    trusted = inventory._niri_sockets(rows)
    configured = inventory._niri_config(home)
    journal = _journal(context)
    report = {"socket": trusted[0] if len(trusted) == 1 else None, "ipc": False,
              "surfaces": {}, "changes": [], "blockers": []}
    if not trusted:
        report["blockers"].append("no trusted niri socket for this user's session")
    elif len(trusted) > 1:
        report["blockers"].append(f"{len(trusted)} trusted niri sockets make the desktop "
                                  "context ambiguous")
    else:
        if trusted[0] != recorded["socket"]:
            report["changes"].append("the trusted niri socket is not the recorded one")
        report["ipc"] = _ipc(context, trusted[0])
        if not report["ipc"]:
            report["blockers"].append("read-only niri IPC on the trusted socket failed")
    for surface in recorded["surfaces"]:
        if surface["name"] in names:
            report["surfaces"][surface["name"]] = _classify(
                surface, rows, home, configured[surface["name"]],
                journal.get(f"{phase}:{surface['name']}") or {}, report)
    return report


def surface_preview(context):
    """Read-only: one host's desktop against its recorded inventory. Where it changed without a
    blocker, `inventory` is this host's new inventory for a new decision to approve."""
    payload = context["payload"]
    recorded = payload["recorded"]
    report = _observe(context, recorded, payload["phase"],
                      tuple(surface["name"] for surface in recorded["surfaces"]))
    report["inventory"] = None if report["blockers"] else {
        "state": "present", "absence_reason": recorded["absence_reason"],
        "socket": report["socket"],
        "surfaces": [{"name": surface["name"],
                      "configured": report["surfaces"][surface["name"]]["configured"],
                      "processes": report["surfaces"][surface["name"]]["running"]}
                     for surface in recorded["surfaces"]]}
    return report


def _exited(identity):
    """Wait, bounded, for one recorded process to leave the process table."""
    end = time.monotonic() + STOP_SECONDS
    while True:
        if not any(row["pid"] == identity["pid"] and row["start_time"] == identity["start_time"]
                   for row in inventory._process_rows()):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(POLL_SECONDS)


def _appeared(name, home, before):
    """The one new process for the surface once it has stayed the only one for SETTLE_SECONDS.
    A launcher that forks (`qs -d`) briefly shows two; only a stable single one is accepted."""
    end = time.monotonic() + APPEAR_SECONDS
    candidate, since, seen = None, None, 0
    while True:
        new = [process for process in _running(name, home) if process not in before]
        now, seen = time.monotonic(), len(new)
        if len(new) == 1 and new[0] == candidate:
            if now - since >= SETTLE_SECONDS:
                return candidate
        else:
            candidate, since = (new[0], now) if len(new) == 1 else (None, None)
        if now >= end:
            detail = ("no replacement appeared" if seen == 0 else
                      f"{seen} new processes run it; inspect them" if seen > 1 else
                      "its replacement did not stay up")
            raise Stop(f"{name}: niri accepted the spawn, but {detail} within "
                       f"{APPEAR_SECONDS:g} s")
        time.sleep(POLL_SECONDS)


def surface_restart(context):
    """Restart one recorded surface of this host in one phase, or adopt the replacement this
    phase already started. Refuses any changed context before a signal or spawn."""
    _live_only(context)
    payload = context["payload"]
    recorded, name, phase = payload["recorded"], payload["name"], payload["phase"]
    surface = next((entry for entry in recorded["surfaces"] if entry["name"] == name), None)
    if surface is None:
        raise Stop(f"{name} is not a recorded surface of this host")
    home = Path(context["home"])
    report = _observe(context, recorded, phase, (name,))
    problems = report["blockers"] + report["changes"]
    if problems:
        raise Stop("changed context: " + "; ".join(problems) + "; nothing was signalled or "
                   "started: inspect it, then ask again with a new inventory")
    found = report["surfaces"][name]
    if found["verdict"] == "restarted":
        return {"name": name, "adopted": True, "replacement": found["restarted"],
                "stopped": None, "exited": False, "socket": recorded["socket"]}
    # From here until this operation records its reply, INT, TERM, HUP and the deadline alarm
    # stay blocked: a cancel waits for the replacement to be journaled, so no surface this
    # operation started goes unrecorded. Every wait below is bounded on its own; `execute`
    # restores the signal mask once the reply is recorded.
    signal.pthread_sigmask(signal.SIG_BLOCK, hosts.WATCHED)
    key, stopped = f"{phase}:{name}", None
    if found["verdict"] == "running":
        _journaled(context, key, {"state": "stopping", "from": found["process"]})
        _terminate(found["process"])
        if not _exited(found["process"]):
            raise Stop(f"{name}: recorded pid {found['process']['pid']} did not exit within "
                       f"{STOP_SECONDS:g} s of TERM; nothing else was signalled; inspect it")
        stopped = found["process"]
    before = _running(name, home)
    _journaled(context, key, {"state": "spawning", "from": found["process"], "stopped": stopped})
    _spawn(context, recorded["socket"], surface["configured"][0], f"niri-spawn-{name}")
    replacement = _appeared(name, home, before)
    _journaled(context, key, {"state": "started", "from": found["process"], "stopped": stopped,
                              "replacement": replacement})
    return {"name": name, "adopted": False, "replacement": replacement, "stopped": stopped,
            "exited": found["verdict"] in ("exited", "missing"), "socket": recorded["socket"]}


def surface_probe(context):
    """Pilot only: the fixed command `true` through niri's spawn on the consented socket."""
    if context["mode"] != "pilot":
        raise Stop(f"{context['mode']} mode cannot run the fixed true spawn; it is pilot only")
    socket = context["payload"]["socket"]
    if inventory._niri_sockets(inventory._process_rows()) != [socket]:
        raise Stop("the consented niri socket is not this session's one trusted socket; nothing "
                   "was spawned")
    if not _ipc(context, socket):
        raise Stop("read-only niri IPC on the trusted socket failed; nothing was spawned")
    _spawn(context, socket, PROBE_COMMAND, "niri-spawn-probe")
    return {"command": PROBE_COMMAND, "socket": socket, "acknowledged": True}


def _live_only(context):
    if context["mode"] != "live":
        raise Stop(f"{context['mode']} mode cannot restart familiar's surfaces; this operation "
                   "is live only")


def _path(value):
    return (isinstance(value, str) and os.path.isabs(value) and 0 < len(value) <= 4096
            and value.isprintable())


def _process(value):
    return (isinstance(value, dict) and set(value) == {"pid", "start_time", "argv"}
            and type(value["pid"]) is int and value["pid"] > 0
            and type(value["start_time"]) is int and value["start_time"] >= 0
            and isinstance(value["argv"], list) and 0 < len(value["argv"]) <= 64
            and all(isinstance(arg, str) and len(arg) <= 4096 for arg in value["argv"]))


def _surface(value):
    return (isinstance(value, dict) and set(value) == {"name", "configured", "processes"}
            and value["name"] in SURFACES and isinstance(value["configured"], list)
            and len(value["configured"]) == 1 and hosts._text_field(1000)(value["configured"][0])
            and isinstance(value["processes"], list) and len(value["processes"]) <= 1
            and all(_process(process) for process in value["processes"]))


def _recorded(value):
    """One host's recorded present desktop, as the window keeps it."""
    return (isinstance(value, dict)
            and set(value) == {"state", "absence_reason", "socket", "surfaces"}
            and value["state"] == "present" and value["absence_reason"] is None
            and _path(value["socket"]) and isinstance(value["surfaces"], list)
            and [surface.get("name") if isinstance(surface, dict) else None
                 for surface in value["surfaces"]] == list(SURFACES)
            and all(_surface(surface) for surface in value["surfaces"]))


_WINDOW = {"window_id": quiesce._window_id}
_PHASE = {"phase": lambda value: value in (FORWARD, RECOVERY)}

OPERATIONS = {
    "surface-preview": hosts.Operation(
        run=surface_preview, deadline=IPC_SECONDS + 60, mutation=False,
        payload={**_WINDOW, **_PHASE, "recorded": _recorded},
        required=frozenset({"window_id", "phase", "recorded"})),
    "surface-restart": hosts.Operation(
        run=surface_restart, deadline=RESTART_DEADLINE, mutation=True,
        payload={**_WINDOW, **_PHASE, "name": lambda value: value in SURFACES,
                 "recorded": _recorded},
        required=frozenset({"window_id", "phase", "name", "recorded"})),
    "surface-probe": hosts.Operation(
        run=surface_probe, deadline=IPC_SECONDS + SPAWN_SECONDS + 60, mutation=True,
        payload={**_WINDOW, "socket": _path}, required=frozenset({"window_id", "socket"})),
}


# --- controller side -------------------------------------------------------------------------


def _record(window):
    """The window's desktop record; before any restart, the run's consent subject."""
    if "desktop" in window:
        return window["desktop"]
    return {"hosts": copy.deepcopy(window["surfaces"]["hosts"]), "phases": {}, "attempts": []}


def pending(window: dict, phase: str) -> dict:
    """Each host's recorded present surfaces not yet restarted in phase; none where an
    explained absence holds."""
    record = _record(window)
    done = record["phases"].get(phase, {})
    return {host: [surface["name"] for surface in record["hosts"][host]["surfaces"]
                   if surface["name"] not in done.get(host, {})]
            if record["hosts"][host]["state"] == "present" else []
            for host in lifecycle.HOST_ORDER}


def _summary(window, phase):
    record, todo = _record(window), pending(window, phase)
    done = record["phases"].get(phase, {})
    restarted = [f"{host} {name}" for host in lifecycle.HOST_ORDER
                 for name in done.get(host, {})]
    missing = [f"{host} {name}" for host in lifecycle.HOST_ORDER for name in todo[host]]
    return "; ".join(part for part in (
        "restarted: " + ", ".join(restarted) if restarted else "",
        "pending: " + ", ".join(missing) if missing else "") if part) or "nothing to restart"


def status(window: dict) -> dict:
    """The read-only status detail and next command of a window past its verified migration."""
    stopped = ", ".join(lifecycle._stopped(window)) or "no host"
    if window["state"] == "ready-for-smokes":
        return {"detail": (f"window {window['id']} verified the migration and restarted "
                           f"familiar's surfaces ({_summary(window, FORWARD)}); timers stay "
                           f"paused on {stopped} until finish; the trust and smoke handoff is "
                           "next"), "next": ["record-smoke"]}
    failure = _record(window).get("failure")
    last = (f"; the last attempt stopped at {failure['step']} on {failure['host']} "
            f"({failure['status']})" if failure else "")
    return {"detail": (f"window {window['id']} verified the migration on both hosts; familiar's "
                       f"surfaces are pending ({_summary(window, FORWARD)}){last}; migrated, "
                       f"surfaces pending: timers stay paused on {stopped}; Claude and Codex "
                       "may resume through the held trust and resume path"),
            "next": ["restart-surfaces"]}


def next_attempt(window: dict, action: str) -> str:
    """The attempt ID this window's next decision for action names."""
    prefix = PREFIXES[action] + "-"
    directory = Path(window["directory"]) / "decisions"
    numbers = [int(name[len(prefix):-5]) for name in (
        os.listdir(directory) if os.path.isdir(directory) else ())
        if name.startswith(prefix) and name.endswith(".json") and name[len(prefix):-5].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1}"


def _subject(window, action, inventory_hosts, restart):
    impact = lifecycle.IMPACT if ACTIONS[action] == FORWARD else RECOVERY_IMPACT
    return {"action": action, "window_id": window["id"], "hosts": inventory_hosts,
            "restart": restart, "impact": impact,
            "duration_seconds": lifecycle.DURATION_SECONDS}


def preview(window: dict, action: str) -> dict:
    """Read-only: the consent subject for action (restart-surfaces or recover), its digest, the
    next attempt ID and each observed host's desktop-only reading.

    Each host with surfaces left in the action's phase is read with surface-preview, never the
    forward inventory or any Claude probe. Where the desktop matches its recording, that host's
    subject is the recorded inventory, so an expected exit leaves the subject, and an approval
    of it, unchanged. Where the socket changed, a recorded PID belongs to another process or an
    unrecorded process runs a surface, the subject offers that host's new inventory instead,
    which only a new decision can approve. A changed startup command, a missing or ambiguous
    socket, failed IPC or two processes for one surface stop for inspection."""
    phase = ACTIONS[action]
    record, todo = _record(window), pending(window, phase)
    inventory_hosts, observed = {}, {}
    for host in lifecycle.HOST_ORDER:
        inventory_hosts[host] = record["hosts"][host]
        if not todo[host]:
            continue
        found, log = lifecycle._call(host, window["mode"], "surface-preview", {
            "window_id": window["id"], "phase": phase, "recorded": record["hosts"][host]},
            "surface-preview")
        observed[host] = found
        if found["blockers"]:
            raise lifecycle.Failed(
                "surface-preview", host, "blocked", "the desktop needs inspection before any "
                "restart: " + "; ".join(found["blockers"]), log=log,
                blockers=[f"{host}: desktop: {blocker}" for blocker in found["blockers"]],
                observed="nothing was changed", next_command=[action])
        if found["changes"]:
            inventory_hosts[host] = found["inventory"]
    subject = _subject(window, action, inventory_hosts,
                       {host: todo[host] for host in lifecycle.HOST_ORDER})
    return {"subject": subject, "sha256": state._digest(subject),
            "attempt_id": next_attempt(window, action), "observed": observed}


def bind(window: dict, consumed: dict, subject: dict) -> dict:
    """Keep the subject a consumed decision approved in the window before anything acts on it:
    the consumed record keeps only its digest."""
    if (state._digest(subject) != consumed.get("subject_sha256")
            or consumed.get("action") != subject.get("action")
            or consumed.get("window_id") != window["id"]):
        raise Stop("the consumed decision does not approve this subject; ask again")
    record = _record(window)
    if any(entry["attempt_id"] == consumed["attempt_id"] for entry in record["attempts"]):
        raise Stop(f"attempt {consumed['attempt_id']} is already bound; ask again")
    attempts = [*record["attempts"], {"attempt_id": consumed["attempt_id"],
                                      "action": consumed["action"], "subject": subject,
                                      "bound_at": lifecycle._now()}]
    return lifecycle._save(window, desktop={**record, "attempts": attempts})


def _refused(message, action):
    retry = {RESTART_ACTION: [RESTART_ACTION], RECOVER_ACTION: [RECOVER_ACTION]}
    return lifecycle.Failed("decision", "titan", "refused", message,
                            observed="nothing was changed",
                            next_command=retry.get(action, ["status"]))


def authorized(window: dict, decision: dict) -> dict:
    """The subject one consumed desktop decision approved for this window, or Failed before any
    action: it must be the durable consumed record, of this window and preparation, bound to
    its subject (the run's is its `surfaces`) and not yet used by any restart."""
    action = decision.get("action") if isinstance(decision, dict) else None
    if action not in ACTIONS:
        raise _refused("restarts take one consumed desktop decision for run, restart-surfaces "
                       "or recover", "status")
    attempt = decision.get("attempt_id")
    consumed = None
    if isinstance(attempt, str) and state.ATTEMPT_ID.fullmatch(attempt):
        try:
            consumed = state.load_record(Path(window["directory"]) / "decisions"
                                         / f"{attempt}.json")
        except Stop:
            consumed = None
    if (consumed != decision or decision.get("kind") != "desktop"
            or decision.get("window_id") != window["id"]
            or decision.get("prepared_sha256") != window["prepared_sha256"]):
        raise _refused(f"the decision is not this window's consumed desktop decision for "
                       f"{action}; ask again", action)
    entry = next((item for item in _record(window)["attempts"]
                  if item["attempt_id"] == attempt), None)
    if action == RUN_ACTION:
        if attempt != lifecycle.RUN_ATTEMPT or entry is not None:
            raise _refused("the run's decision authorizes the run's one restart only", action)
        subject = window["surfaces"]
    else:
        if entry is None or entry["action"] != action:
            raise _refused(f"no subject is bound for attempt {attempt}; ask again", action)
        if "started_at" in entry:
            raise _refused(f"attempt {attempt} already authorized a restart; ask again", action)
        subject = entry["subject"]
    if state._digest(subject) != decision["subject_sha256"]:
        raise _refused("the decision's subject is not the inventory bound for it; ask again",
                       action)
    return subject


def _gate(window, action):
    """The window state each restart starts from, and its one owning invocation."""
    name = f"window {window['id']} is {window['state']}"

    def refuse(reason, following):
        return lifecycle.Failed("surface-restart", "titan", "refused", f"{name}{reason}",
                                observed="no surface was restarted", next_command=following)

    if action == RECOVER_ACTION:
        if window["state"] != "recovering" or "restored" not in (window.get("recovery") or {}):
            raise refuse("; recovery restarts surfaces only once it restored native settings, "
                         "source and dependencies", ["recover"])
    elif window["state"] != "migrated-surfaces-pending":
        raise refuse("; familiar's surfaces restart only from the verified migration",
                     lifecycle.status()["next"])
    owner = window.get("owner")
    mine = owner == lifecycle._me()
    if action in (RUN_ACTION, RECOVER_ACTION) and not mine:
        raise refuse(" and this invocation did not take it there", ["status"])
    if not mine and owner is not None and hosts._alive(owner):
        raise refuse(f" and belongs to a running invocation (pid {owner['pid']})", ["status"])


def _cancellable(entry):
    """A surface retry cancels only this window's own dead-owner reads and surface operations;
    any other unfinished mutation needs recover."""
    spec = hosts._operations().get(entry["operation"])
    return spec is not None and (entry["operation"] in OPERATIONS or not spec.mutation)


def _settle(window):
    from . import recovery  # recovery imports this module
    blockers, cancelled, dead = recovery._settle(window, cancel=_cancellable)
    blockers += dead
    if blockers:
        raise lifecycle.Failed("reconcile", blockers[0].split(":", 1)[0], "unsettled",
                               "unfinished host operations block the surface retry; nothing was "
                               "signalled or started", blockers=blockers)
    return cancelled


def _start(window, decision, subject, phase):
    """Record the attempt as started, with the inventory its decision approved, before any
    host is touched."""
    record = copy.deepcopy(_record(window))
    record["hosts"] = copy.deepcopy(subject["hosts"])
    now = lifecycle._now()
    if decision["action"] == RUN_ACTION:
        record["attempts"].append({"attempt_id": decision["attempt_id"], "action": RUN_ACTION,
                                   "subject": subject, "bound_at": now})
    for entry in record["attempts"]:
        if entry["attempt_id"] == decision["attempt_id"]:
            entry.update(phase=phase, started_at=now)
    return lifecycle._save(window, owner=lifecycle._me(), desktop=record)


def _attempt(record, attempt, **changes):
    for entry in record["attempts"]:
        if entry["attempt_id"] == attempt:
            entry.update(changes)


def _recheck(window, attempt, seen, progress):
    """The verified migration again, before a retry touches any desktop."""
    def step(name, host):
        nonlocal window
        window = lifecycle._step(window, seen, progress, name, host)

    lifecycle.verified_migration(window, window["familiar"]["merge"], step)
    record = copy.deepcopy(window["desktop"])
    _attempt(record, attempt, rechecked_at=lifecycle._now())
    return lifecycle._save(window, desktop=record)


def _persist(window, phase, host, name, result, attempt):
    """Each replacement becomes the surface's recorded process before the next one starts."""
    record = copy.deepcopy(window["desktop"])
    for surface in record["hosts"][host]["surfaces"]:
        if surface["name"] == name:
            surface["processes"] = [result["replacement"]]
    record["phases"].setdefault(phase, {}).setdefault(host, {})[name] = {
        "replacement": result["replacement"], "stopped": result["stopped"],
        "exited": result["exited"], "adopted": result["adopted"], "attempt": attempt,
        "at": lifecycle._now()}
    return lifecycle._save(window, desktop=record)


def _restart(window, phase, attempt, seen, progress):
    for host in lifecycle.HOST_ORDER:
        for name in pending(window, phase)[host]:
            window = lifecycle._step(window, seen, progress, "surface-restart", host)
            result, _ = lifecycle._call(host, window["mode"], "surface-restart", {
                "window_id": window["id"], "phase": phase, "name": name,
                "recorded": window["desktop"]["hosts"][host]}, "surface-restart")
            window = _persist(window, phase, host, name, result, attempt)
    return window


def _complete(window, phase, attempt):
    record = copy.deepcopy(window["desktop"])
    now = lifecycle._now()
    _attempt(record, attempt, outcome="complete", finished_at=now)
    record["completed"] = {**record.get("completed", {}), phase: now}
    record.pop("failure", None)
    changes = {"desktop": record}
    if phase == FORWARD:
        changes["state"] = "ready-for-smokes"
    return lifecycle._save(window, **changes)


def restarted(window: dict, phase: str) -> dict:
    done = _record(window)["phases"].get(phase, {})
    return {host: {name: entry["replacement"] for name, entry in done.get(host, {}).items()}
            for host in lifecycle.HOST_ORDER}


def pending_failure(failed, phase: str, attempt: str):
    """Record a stopped restart and say what it leaves. In the forward phase only the surfaces
    stay pending, unless the migration recheck itself found the migration changed, which needs
    inspection and recover; in recovery the caller records the recovery stop."""
    inspect = (phase == FORWARD and failed.step in ("target-verify", "familiar-verify")
               and failed.status not in ("interrupted", "unsettled"))
    try:
        window = state.current_window(lifecycle._root())
        record = copy.deepcopy(_record(window))
        entry = {"step": failed.step, "host": failed.host, "status": failed.status,
                 "error": failed.error, "log": failed.log, "at": lifecycle._now()}
        record["failure"] = entry
        record["failures"] = [*record.get("failures", []), entry]
        _attempt(record, attempt, outcome="stopped", finished_at=entry["at"])
        changes = {"desktop": record}
        if inspect:
            changes.update(state="inspection-required", failure=entry)
        window = lifecycle._save(window, **changes)
    except (Stop, OSError) as error:
        failed.observed = (f"the window record could not be updated ({hosts._brief(error)}); "
                           "run status")
        failed.next_command = ["status"]
        return failed
    stopped = ", ".join(lifecycle._stopped(window)) or "no host"
    if inspect:
        failed.observed = (f"window {window['id']} is inspection-required: the verified "
                           "migration no longer holds and no surface was restarted. Do not open "
                           "Claude or Codex until recover completes: run is blocked and timers "
                           f"stay paused on {stopped}")
        failed.next_command = ["recover"]
    elif phase == FORWARD:
        failed.observed = (f"window {window['id']} is {window['state']}: migrated, surfaces "
                           f"pending ({_summary(window, FORWARD)}); timers stay paused on "
                           f"{stopped} until finish; Claude and Codex may resume through the "
                           "held trust and resume path")
        failed.next_command = (["status"] if failed.status == "unsettled"
                               else ["restart-surfaces"])
    else:
        failed.next_command = ["recover"]
    return failed


def restart_surfaces(window: dict, decision: dict) -> dict:
    """Restart every recorded surface left in the decision's phase, authorized by that one
    consumed decision, and return {window, state, restarted, observed, next}.

    The decision is the run's own (`run`, right after its verified checkpoint), a later
    `restart-surfaces` retry's, or `recover`'s once recovery restored native state; its bound
    subject is the inventory it approved, which becomes the window's recorded one. A retry
    first settles this window's own dead-owner reads and surface operations and rechecks the
    verified migration. Every surface is restarted by `surface-restart` and persisted before the
    next; an explained absence is never started. The forward phase ends `ready-for-smokes`; a
    forward failure leaves `migrated-surfaces-pending` with only the surfaces pending (a
    recheck that finds the migration changed needs inspection). A recovery restart stays
    `recovering` for the original timers."""
    state._current(window)
    action = decision.get("action") if isinstance(decision, dict) else None
    if action in ACTIONS:
        _gate(window, action)
    subject = authorized(window, decision)
    attempt, phase = decision["attempt_id"], ACTIONS[action]
    progress = {"step": "surface-restart", "host": "titan"}
    with lifecycle._signals() as seen:
        try:
            window = _start(window, decision, subject, phase)
            if action == RESTART_ACTION:
                progress.update(step="reconcile")
                _settle(window)
                window = _recheck(window, attempt, seen, progress)
            window = _restart(window, phase, attempt, seen, progress)
            if seen:
                raise lifecycle._Interrupt(seen[-1])
            window = _complete(window, phase, attempt)
        except (Exception, lifecycle._Interrupt) as error:
            failed = lifecycle._as_failed(error, progress)
        else:
            stopped = ", ".join(lifecycle._stopped(window)) or "no host"
            if phase == FORWARD:
                observed = (f"window {window['id']} is {window['state']}: familiar's surfaces "
                            f"were restarted ({_summary(window, FORWARD)}); timers stay paused "
                            f"on {stopped} until finish")
                following = lifecycle.status()["next"]
            else:
                observed = (f"familiar's surfaces were restarted from the native source "
                            f"({_summary(window, RECOVERY)}); the original timers are still "
                            "pending")
                following = ["recover"]
            return {"window": window, "state": window["state"],
                    "restarted": restarted(window, phase), "observed": observed,
                    "next": following}
    raise pending_failure(failed, phase, attempt)


# --- the pilot's fixed spawn -----------------------------------------------------------------


def probe_subject(window: dict, sockets: dict) -> dict:
    """The consent subject of a pilot's fixed `true` spawn: each named host's niri socket."""
    return {"action": PROBE_ACTION, "window_id": window["id"], "command": [PROBE_COMMAND],
            "hosts": {host: {"socket": sockets[host]} for host in lifecycle.HOST_ORDER
                      if host in sockets},
            "impact": PROBE_IMPACT, "duration_seconds": 1}


def probe(window: dict, decision: dict, sockets: dict) -> dict:
    """Pilot only: spawn the fixed `true` through niri on each named host's socket, with this
    invocation's one consumed decision for exactly that subject. Returns each host's
    acknowledgement; it proves the spawn route, not persistent surface health."""
    state._current(window)
    if window["mode"] != "pilot" or window["state"] in state.TERMINAL:
        raise _refused(f"window {window['id']} is a {window['mode']} window that is "
                       f"{window['state']}; the fixed true spawn runs only in an open pilot",
                       "status")
    subject = probe_subject(window, sockets)
    attempt = decision.get("attempt_id") if isinstance(decision, dict) else None
    consumed = None
    if isinstance(attempt, str) and state.ATTEMPT_ID.fullmatch(attempt):
        try:
            consumed = state.load_record(Path(window["directory"]) / "decisions"
                                         / f"{attempt}.json")
        except Stop:
            consumed = None
    if (consumed is None or consumed != decision or decision.get("kind") != "desktop"
            or decision.get("action") != PROBE_ACTION
            or decision.get("subject_sha256") != state._digest(subject)):
        raise _refused("the decision is not this pilot's consumed decision for this spawn; ask "
                       "again", PROBE_ACTION)
    if any(entry["attempt_id"] == attempt for entry in window.get("probes", [])):
        raise _refused(f"attempt {attempt} already ran the fixed spawn; ask again", PROBE_ACTION)
    window = lifecycle._save(window, probes=[*window.get("probes", []), {
        "attempt_id": attempt, "subject": subject, "started_at": lifecycle._now()}])
    results = {}
    for host in subject["hosts"]:
        results[host], _ = lifecycle._call(host, "pilot", "surface-probe", {
            "window_id": window["id"], "socket": sockets[host]}, "surface-probe")
        probes = copy.deepcopy(window["probes"])
        probes[-1]["results"] = dict(results)
        window = lifecycle._save(window, probes=probes)
    return {"window": window, "hosts": results}


# The controller side uses the window lifecycle, which imports operations and so this module:
# it is bound here, once this module's operations are defined.
from . import window as lifecycle  # noqa: E402
