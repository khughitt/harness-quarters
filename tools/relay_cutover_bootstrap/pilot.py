"""The rehearsal: the smallest end-to-end pilot of the cutover, run once through the real SSH
transport and remote helper, with every application change inside owned scratch roots.

Host side, the fixed operations in `OPERATIONS` (pilot mode only):

- `pilot-create` (both hosts): an owned scratch root `pilot/<root-id>/` in this host's cutover
  root, 0700, named afterwards only by its opaque 16-hex ID. `scratch.json` records its window,
  purpose and host before anything else is written. A `main` root holds copies of the current
  targets this host's harnesses read (`home/<target path>`); every root holds a clone of familiar
  at PRE (`familiar/`, made with Git's own transport from the live checkout, with the approved tip
  pinned by a local ref and no remote left), the native dependencies copied from the live
  checkout, their verified pre-merge snapshot (`state/familiar-node_modules.pre`, recorded under
  `state/quiesce/<window>/` as restoration reads it), `state/` for dry runs and `tmp/`, the
  children's TMPDIR.
- `pilot-observe` (both, read-only): a scratch root's clone (HEAD, tree, clean tree, dependency
  tree), its target copies' digests and this window's sealed dry outputs there.
- `pilot-install` (Europa): the disconnect case's scratch install: `familiar-install` itself, then,
  with the pilot-only `latch`, a bounded hold until this operation's reply connection is gone, so
  that a dropped client always lands while it runs, after npm actually started.
- `pilot-cleanup` (both): removes every scratch root of one window, never following a link, and
  refuses an entry it cannot explain.

`resolve` turns a pilot request's root ID into that root's paths, for every operation that takes
one (`hosts.Operation.scratch`): targets resolve under `home/`, familiar is the clone, application
state is `state/` and TMPDIR is `tmp/`; HOME, authentication, the user bus and the prepared caches
stay the host's own. Every target path must resolve inside the root (`targets.target_path`).

Controller side: `preview` allocates the pilot window and its consent subject before any ask;
`answer` takes this invocation's decision; `rehearse` runs the one case, or reconciles and closes
an interrupted one: held inventory on both hosts (Git access, bus queries, desktop IPC), the
consented `true` spawn (`spawn_gate`), scratch roots, the six dry runs and the seal, a merge and
install in each host's clone, Titan's four copies registered and applied under one touched record,
verification including Europa's expectations of the shared images, the disconnect case
(`disconnect_case`, `dropped_install`), restoration through recovery's offline core, and cleanup.
It writes a private machine-readable verdict, `pilot-verdict.json`, in the window directory. Real
timers are only queried, no surface restarts, no live target, registry or harness is touched, and
pilot receipts never satisfy a live finish."""
import hashlib
import os
import secrets
import select
import shutil
import signal
import stat
import time
from pathlib import Path

from . import familiar, hosts, inputs, quiesce, restoration, state, targets
from .state import Stop

PILOT = "pilot"
OWNER = "scratch.json"
PARTS = ("home", "familiar", "state", "tmp")
PURPOSES = ("main", "disconnect")
TIP_REF = "refs/heads/relay-pilot-tip"
CHILD_SECONDS = 120
CREATE_SECONDS = 900
HOLD_SECONDS = 120  # the latch's bound: the longest the scratch install waits for its drop
VERDICT = "pilot-verdict.json"
VERDICT_KIND = "relay-cutover-pilot"
WATCH_SECONDS = 0.2  # the disconnect case's status reads while it waits to drop
SETTLE_SECONDS = 1.0  # its status reads after the drop
GATES = ("inventory", "git-access", "bus", "desktop-ipc", "toolchain", "spawn", "scratch",
         "dry-runs", "source", "dependencies", "apply", "remote-expectations", "restore",
         "disconnect", "cleanup")
STEP_GATES = {"inventory": "inventory", "pilot-create": "scratch", "target-dry": "dry-runs",
              "target-frozen": "dry-runs", "familiar-merge": "source",
              "familiar-install": "dependencies", "target-register": "apply",
              "target-apply": "apply", "target-verify": "apply", "familiar-verify": "source",
              "pilot-observe": "remote-expectations", "pilot-install": "disconnect",
              "pilot-cleanup": "cleanup"}
# What the pilot leaves to fixtures and the live window, recorded in every verdict.
UNEXERCISED = ("timer-mutation", "surface-restart", "registry-import", "harness-launch",
               "smoke-receipts")
RUNTIME = "existing authentication and SSH runtime bookkeeping"
SPAWN = "the consented no-window niri spawn of the fixed command true"


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


# --- host side: scratch roots -------------------------------------------------------------


def _base(context):
    return Path(context["root"]) / PILOT


def _parts(directory):
    return {name: str(directory / name) for name in PARTS}


def _scoped(context, directory, root_id, purpose):
    parts = _parts(directory)
    return {**context, "targets": parts["home"], "familiar": parts["familiar"],
            "state": parts["state"], "tmp": parts["tmp"],
            "scratch": {"id": root_id, "path": str(directory),
                        "real": os.path.realpath(directory), "purpose": purpose}}


def resolve(context: dict, payload: dict) -> dict:
    """A pilot request's context with its scratch root's paths in place of the fixed ones, or
    Refused before any write: the ID names this user's plain 0700 directory under this host's
    pilot/, recorded by pilot-create for the request's window on this host, and each of its
    parts is a plain directory of its own inside it."""
    root_id = payload[hosts.SCRATCH]
    base, refused = _base(context), f"scratch root {root_id}"
    directory = base / root_id
    try:
        state._check_dir(base)
        state._check_dir(directory)
        owner = state.load_record(directory / OWNER)
    except Stop as stop:
        raise hosts.Refused(f"{refused} is not an owned pilot root on this host ({stop})") \
            from None
    if (owner.get("root"), owner.get("host"), owner.get("window_id")) != (
            root_id, context["host"], payload.get("window_id")):
        raise hosts.Refused(f"{refused} belongs to another window or host")
    if os.path.realpath(directory) != os.path.join(os.path.realpath(base), root_id):
        raise hosts.Refused(f"{refused} does not resolve inside this host's pilot roots")
    for name in PARTS:
        path = directory / name
        info = os.lstat(path) if os.path.lexists(path) else None
        if info is None or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise hosts.Refused(f"{refused}: {name} is not a plain directory inside the "
                                "scratch root")
    return _scoped(context, directory, root_id, owner["purpose"])


def _git(context, label, *args):
    env = {**hosts._child_env(context), "GIT_TERMINAL_PROMPT": "0"}
    return hosts._run_child(context, label, [hosts.TOOLS["git"], *args], env=env,
                            timeout=CHILD_SECONDS)


def _must(result, message):
    if result.returncode != 0:
        raise Stop(f"{message}; see the private log; inspect the scratch root")
    return familiar._text(result)


def _clone(context, live, pre, tip):
    """familiar at PRE in the scratch root: cloned by Git's transport (never hard links into the
    live checkout), the tip kept reachable by a local ref, and no remote left."""
    clone = context["familiar"]
    _must(_git(context, "pilot-clone", "clone", "--no-local", "--no-checkout", "--quiet", "--",
               live, clone), "git clone of familiar's checkout failed")
    os.chmod(clone, 0o700)
    _must(familiar._git(context, "pilot-checkout", "checkout", "--quiet", "--detach", pre),
          "familiar's clone cannot check out PRE")
    if familiar._text(familiar._git(context, "pilot-tip", "cat-file", "-t", tip)) != "commit":
        raise Stop("the approved feature tip is not a commit in familiar's checkout; nothing "
                   "else was cloned")
    _must(familiar._git(context, "pilot-tip-ref", "update-ref", TIP_REF, tip),
          "the approved tip cannot be pinned in familiar's clone")
    _must(familiar._git(context, "pilot-remote", "remote", "remove", "origin"),
          "familiar's clone keeps its remote")
    head = familiar._text(familiar._git(context, "pilot-head", "rev-parse", "HEAD"))
    if head != pre:
        raise Stop("familiar's clone is not at PRE")


def _modules(context, live):
    """The live checkout's native dependencies, copied into the clone and its snapshot, which
    is recorded verified as the pre-merge snapshot restoration takes them back from."""
    clone, root = Path(context["familiar"]), Path(context["state"])
    source = quiesce._source(Path(live) / "node_modules")
    quiesce._copy(source, clone / "node_modules")
    quiesce._copy(clone / "node_modules", root / restoration.SNAPSHOT)
    os.chmod(root / restoration.SNAPSHOT, 0o700)
    live_tree, copied = quiesce._tree(source), quiesce._tree(clone / "node_modules")
    snapshot = quiesce._tree(root / restoration.SNAPSHOT)
    if not live_tree == copied == snapshot:
        raise Stop("familiar's dependencies changed while they were copied; run again")
    window_id = context["payload"]["window_id"]
    state.save_record(root / quiesce.QUIESCE / window_id / quiesce.MOVES, {
        "schema": 1, "window_id": window_id, "pilot": True, "moves": [{
            "name": restoration.SNAPSHOT, "live": str(clone / "node_modules"),
            "state": "verified", "entries": snapshot["entries"],
            "sha256": snapshot["sha256"]}]})
    return snapshot


def pilot_create(context):
    """One owned scratch root on this host, recorded first; its ID is the reply."""
    payload, home = context["payload"], Path(context["home"])
    pre, tip = payload["pre"], inputs.PINS["familiar_feature_tip"]
    if pre != inputs.PINS["familiar_pre"]:
        raise Stop("a pilot clones familiar only at the approved PRE; nothing was created")
    base = _base(context)
    state._make_dirs(base)
    state._check_dir(base)
    root_id = secrets.token_hex(8)
    directory = base / root_id
    os.mkdir(directory, 0o700)
    state._sync(base)
    state.save_record(directory / OWNER, {
        "schema": 1, "root": root_id, "window_id": payload["window_id"],
        "purpose": payload["purpose"], "host": context["host"], "created_at": hosts._now(),
        "operation_id": context["operation_id"]})
    for name in PARTS:
        if name != "familiar":
            os.mkdir(directory / name, 0o700)
    state._sync(directory)
    scratch = _scoped(context, directory, root_id, payload["purpose"])
    copied = {}
    if payload["purpose"] == "main":
        for target_id in inputs.relevant(context["host"]):
            live = os.path.realpath(home / inputs.TARGETS[target_id])
            data = inputs._read_target(live, target_id)
            copy = Path(scratch["targets"]) / inputs.TARGETS[target_id]
            state._make_dirs(copy.parent)
            targets._write_new(copy, data)
            copied[target_id] = _sha256(data)
    _clone(scratch, context["familiar"], pre, tip)
    modules = _modules(scratch, context["familiar"])
    if not familiar._source(scratch, pre, "pilot-source-pre"):
        raise Stop("familiar's clone is not PRE with a clean tree")
    if targets._helper(scratch, "pilot-check", "familiar-check", "--expect", "native",
                       *familiar.root_args(scratch)).returncode != 0:
        raise Stop("familiar's clone does not check native; see the private log")
    return {"root": root_id, "purpose": payload["purpose"], "pre": pre, "targets": copied,
            "modules": modules}


def pilot_observe(context):
    """Read-only: the scratch clone and its dependencies, the target copies and this window's
    sealed dry outputs on this host, each by digest."""
    head = restoration._ref(context, "pilot-head", "HEAD")
    window_id = context["payload"]["window_id"]
    copies, dry = {}, {}
    for target_id in inputs.relevant(context["host"]):
        data = targets._read(Path(targets.target_path(context, target_id)))
        copies[target_id] = _sha256(data) if data is not None else None
        sealed = (Path(context["state"]) / targets.DRY / window_id / target_id
                  / targets.COPY[targets.HARNESS[target_id]])
        data = targets._read(sealed)
        dry[target_id] = _sha256(data) if data is not None else None
    return {"head": head, "tree": restoration._tree(context, head) if head else None,
            "clean": bool(head) and familiar._source(context, head, "pilot-source"),
            "modules": restoration._modules(Path(context["familiar"]) / "node_modules"),
            "targets": copies, "dry": dry}


def _hold(context):
    """After the install, wait until this operation's reply connection is gone, or the hold's
    bound: the disconnect case's pilot-only latch. Only an error or hang-up on the reply
    descriptor releases it as a disconnect."""
    started = time.monotonic()
    poller = select.poll()
    poller.register(1, 0)  # no requested events: only POLLERR, POLLHUP and POLLNVAL report
    while True:
        waited = time.monotonic() - started
        remaining = min(HOLD_SECONDS - waited, context["deadline"] - time.monotonic())
        if remaining <= 0:
            return {"released": "timeout", "seconds": round(waited, 3)}
        for _, mask in poller.poll(min(remaining, 0.2) * 1000):
            if mask & select.POLLNVAL:
                raise Stop("this operation has no reply connection to hold on")
            if mask & (select.POLLERR | select.POLLHUP):
                return {"released": "disconnect",
                        "seconds": round(time.monotonic() - started, 3)}


def pilot_install(context):
    """The disconnect case's scratch install: familiar-install itself, then, with the latch, the
    hold until its client is gone."""
    result = familiar.familiar_install(context)
    return {**result, "held": _hold(context) if context["payload"]["latch"] else None}


def pilot_cleanup(context):
    """Remove every scratch root of one window on this host; refuse any entry not explained."""
    window_id, base = context["payload"]["window_id"], _base(context)
    if not os.path.lexists(base):
        return {"removed": [], "kept": 0}
    state._check_dir(base)
    owners, unexplained = {}, []
    for name in sorted(os.listdir(base)):
        path = base / name
        info = os.lstat(path)
        if (not hosts.ROOT_ID.fullmatch(name) or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()):
            unexplained.append(name)
            continue
        try:
            owners[name] = state.load_record(path / OWNER)
        except Stop:
            unexplained.append(name)
    if unexplained:
        raise Stop(f"{base}: unexplained entries {', '.join(unexplained)}; inspect them; nothing "
                   "was removed")
    removed = []
    for name, owner in owners.items():
        if owner.get("window_id") == window_id:
            shutil.rmtree(base / name)  # it removes links in the tree, never what they name
            removed.append(name)
    state._sync(base)
    return {"removed": removed, "kept": len(owners) - len(removed)}


def _purpose(value):
    return isinstance(value, str) and value in PURPOSES


def _flag(value):
    return type(value) is bool


_WINDOW = {"window_id": quiesce._window_id}
_CREATE = {**_WINDOW, "purpose": _purpose, "pre": quiesce._commit}
_INSTALL = {**familiar._INSTALL, "latch": _flag}

OPERATIONS = {
    "pilot-create": hosts.Operation(run=pilot_create, deadline=CREATE_SECONDS, mutation=True,
                                    payload=_CREATE, required=frozenset(_CREATE),
                                    modes=("pilot",)),
    "pilot-observe": hosts.Operation(run=pilot_observe, deadline=4 * CHILD_SECONDS + 60,
                                     mutation=False, payload=_WINDOW,
                                     required=frozenset(_WINDOW), modes=("pilot",),
                                     scratch=True),
    "pilot-install": hosts.Operation(
        run=pilot_install, deadline=familiar.OPERATIONS["familiar-install"].deadline
        + HOLD_SECONDS, mutation=True, payload=_INSTALL, required=frozenset(_INSTALL),
        hosts=("europa",), modes=("pilot",), scratch=True),
    "pilot-cleanup": hosts.Operation(run=pilot_cleanup, deadline=CREATE_SECONDS, mutation=True,
                                     payload=_WINDOW, required=frozenset(_WINDOW),
                                     modes=("pilot",)),
}


# --- controller side: the preview, the answer and the spawn -------------------------------


def _session(controller_session):
    if not (isinstance(controller_session, str)
            and lifecycle.SESSION.fullmatch(controller_session)):
        raise lifecycle.Failed("arguments", "titan", "refused", "the controller session must be "
                               "its native session ID, a lowercase UUID",
                               observed="nothing was changed",
                               next_command=[lifecycle.REHEARSE, "--controller-session",
                                             lifecycle.SESSION_PLACEHOLDER, "--preview"])


def _next(session, *argv):
    return [lifecycle.REHEARSE, "--controller-session", session, *argv]


def _refused(message, session, *argv, step="rehearse", observed="nothing was changed"):
    return lifecycle.Failed(step, "titan", "refused", message, observed=observed,
                            next_command=_next(session, *argv))


def _offer(window):
    return {key: window["pilot"][key] for key in ("subject", "sha256", "attempt_id", "exempt")}


def preview(controller_session: str) -> dict:
    """Allocate the pilot window, or keep the one an earlier preview left unrun for this same
    preparation, and return its spawn's consent subject from the prepared desktops: each present
    host's trusted niri socket, each explained absence an exemption. It contacts no host."""
    _session(controller_session)
    from .prepare import load_prepared  # prepare imports the window lifecycle
    prepared = load_prepared()
    digest, root = lifecycle.prepared_sha256(prepared), lifecycle._root()
    current = state.current_window(root)
    if current is not None and current["state"] not in state.TERMINAL:
        if current["mode"] != "pilot":
            raise _refused(f"window {current['id']} is {current['state']}; a pilot opens only "
                           "while no live window is open", controller_session, "--preview")
        if current["state"] != "prepared":
            raise _refused(f"pilot window {current['id']} is {current['state']}; rehearse "
                           "reconciles and closes it first", controller_session)
        if current["prepared_sha256"] == digest and "pilot" in current:
            attempt = state.next_attempt(current, surfaces.PREFIXES[surfaces.PROBE_ACTION])
            if attempt != current["pilot"]["attempt_id"]:  # an earlier answer was consumed
                current = _pilot(current, attempt_id=attempt)
            return {"window": current, **_offer(current)}
        lifecycle._save(current, state="aborted", aborted={
            "at": lifecycle._now(), "reason": "previewed for another preparation; it contacted "
                                              "no host"})
    sockets, exempt = {}, {}
    for host in lifecycle.HOST_ORDER:
        desktop = prepared["hosts"][host].get("desktop") or {}
        if desktop.get("state") == "present" and desktop.get("socket"):
            sockets[host] = desktop["socket"]
        elif desktop.get("state") == "explained-absent" and desktop.get("absence_reason"):
            exempt[host] = desktop["absence_reason"]
        else:
            raise _refused(f"{host}'s prepared desktop is neither present with its niri socket "
                           "nor an explained absence; prepare again", controller_session,
                           "--preview")
    window = state.new_window(root, digest, mode="pilot")
    state.save_record(Path(window["directory"]) / lifecycle.PREPARED, prepared)
    subject = surfaces.probe_subject(window, sockets)
    window = lifecycle._save(window, pilot={
        "controller_session": controller_session, "previewed_at": lifecycle._now(),
        "subject": subject, "sha256": state._digest(subject),
        "attempt_id": state.next_attempt(window, surfaces.PREFIXES[surfaces.PROBE_ACTION]),
        "exempt": exempt})
    return {"window": window, **_offer(window)}


def answer(window: dict, record: dict | None):
    """This invocation's answer to the previewed spawn: None when there is none, a declined
    record once it names this preview's own subject, or the approved record consumed."""
    if record is None:
        return None
    offer = window["pilot"]
    expected = {"kind": "desktop", "action": surfaces.PROBE_ACTION, "window_id": window["id"],
                "attempt_id": offer["attempt_id"], "subject_sha256": offer["sha256"]}
    if isinstance(record, dict) and record.get("verdict") == "declined":
        if set(record) != state.DECISION_KEYS or not state._is_one(record.get("schema")):
            raise Stop("decision record does not match schema 1")
        for key, value in expected.items():
            if record[key] != value:
                raise Stop(f"decision {key} does not match this invocation; ask again")
        state._check_source(record["source"], window)
        return record
    return state.consume_decision(window, record, kind="desktop", action=surfaces.PROBE_ACTION,
                                  attempt_id=offer["attempt_id"], subject_sha256=offer["sha256"])


def _declined(decision):
    return decision is None or decision.get("verdict") == "declined"


def spawn_gate(window: dict, decision) -> tuple[dict, dict]:
    """The spawn gate: the fixed `true` through niri on each previewed host, with this
    invocation's consumed decision for exactly that subject; pending, never passed, when the
    answer is absent or declined; an explained absent desktop is an exemption."""
    offer = window["pilot"]
    subject, attempt = offer["subject"], offer["attempt_id"]
    sockets = {host: entry["socket"] for host, entry in subject["hosts"].items()}
    exempt = {host: {"verdict": "exempt", "reason": reason}
              for host, reason in offer["exempt"].items()}
    if not sockets:
        gate = {"verdict": "exempt", "reason": "no host has a desktop", "attempt_id": attempt,
                "hosts": exempt}
    elif _declined(decision):
        gate = {"verdict": "pending", "reason": "absent" if decision is None else "declined",
                "attempt_id": attempt,
                "hosts": {**{host: {"verdict": "pending", "socket": socket}
                             for host, socket in sockets.items()}, **exempt}}
    else:
        try:
            result = surfaces.probe(window, decision, sockets)
        except lifecycle.Failed as failed:
            window = state.current_window(lifecycle._root())
            done = (window.get("probes") or [{}])[-1].get("results") or {}
            gate = {"verdict": "failed", "reason": f"{failed.step} on {failed.host}: "
                                                   f"{failed.error}", "attempt_id": attempt,
                    "hosts": {**{host: {"verdict": "acknowledged" if host in done else "failed",
                                        "socket": socket} for host, socket in sockets.items()},
                              **exempt}}
        else:
            window = result["window"]
            gate = {"verdict": "passed", "reason": None, "attempt_id": attempt,
                    "hosts": {**{host: {"verdict": "acknowledged", "socket": sockets[host]}
                                 for host, entry in result["hosts"].items()
                                 if entry.get("acknowledged")}, **exempt}}
    window = lifecycle._save(window, pilot={**window["pilot"], "spawn": gate})
    return window, gate


# --- controller side: the run ---------------------------------------------------------------


def _gate(window, name, verdict, **detail):
    gates = {**window["pilot"].get("gates", {}), name: {"verdict": verdict, **detail}}
    return lifecycle._save(window, pilot={**window["pilot"], "gates": gates})


def _pilot(window, **changes):
    return lifecycle._save(window, pilot={**window["pilot"], **changes})


def _scopes(window):
    return {host: {hosts.SCRATCH: root_id} for host, root_id in window["pilot"]["roots"].items()}


def _inventory(window, prepared, seen, progress):
    """Each host's held inventory over the real transport: Git access to the pinned theme, the
    user bus and its unit query, the trusted desktop's read-only IPC and the toolchain."""
    from .prepare import _differing  # prepare imports the window lifecycle
    found = {name: {} for name in ("inventory", "git-access", "bus", "desktop-ipc", "toolchain")}
    for host in lifecycle.HOST_ORDER:
        window = lifecycle._step(window, seen, progress, "inventory", host)
        recorded = prepared["hosts"][host]
        reason = (recorded.get("desktop") or {}).get("absence_reason")
        report, _ = lifecycle._call(host, "pilot", "inventory",
                                    {"absence_reason": reason} if reason else {}, "inventory")
        found["inventory"][host] = "passed"
        found["git-access"][host] = ("passed" if (report.get("git_auth") or {}).get("access")
                                     else "failed")
        bus = report.get("user_bus") or {}
        found["bus"][host] = ("passed" if bus.get("bus") and bus.get("system")
                              and (bus.get("units") or {}).get(quiesce.TIMER) == "loaded"
                              else "failed")
        desktop = report.get("desktop") or {}
        socket = window["pilot"]["subject"]["hosts"].get(host, {}).get("socket")
        if host in window["pilot"]["exempt"]:
            found["desktop-ipc"][host] = ("exempt" if desktop.get("state") == "explained-absent"
                                          else "failed")
        else:
            found["desktop-ipc"][host] = ("passed" if desktop.get("state") == "present"
                                          and desktop.get("ipc") and desktop.get("socket") == socket
                                          else "failed")
        changed = _differing(recorded["toolchain"], report.get("toolchain"))
        found["toolchain"][host] = "passed" if not changed else "failed"
    for name, verdicts in found.items():
        verdict = ("failed" if "failed" in verdicts.values() else "passed")
        window = _gate(window, name, verdict, hosts=verdicts)
    return window


def _create(window, seen, progress, purpose):
    pins = inputs.PINS
    created = {}
    for host in (lifecycle.HOST_ORDER if purpose == "main" else ("europa",)):
        window = lifecycle._step(window, seen, progress, "pilot-create", host)
        created[host], _ = lifecycle._call(host, "pilot", "pilot-create", {
            "window_id": window["id"], "purpose": purpose, "pre": pins["familiar_pre"]},
            "pilot-create")
        if purpose == "main":
            window = _pilot(window, roots={**window["pilot"]["roots"],
                                           host: created[host]["root"]},
                            created={**window["pilot"].get("created", {}), host: created[host]})
    return window, created


def _frozen(window, seen, progress, scopes):
    """Before the merge, every frozen copy still holds its frozen bytes on both hosts."""
    sealed = window["sealed"]["inputs"]
    for host in lifecycle.HOST_ORDER:
        window = lifecycle._step(window, seen, progress, "target-frozen", host)
        frozen = {target_id: result["frozen"]["sha256"]
                  for target_id, result in sealed["hosts"][host].items()}
        found, log = lifecycle._call(host, "pilot", "target-verify", {
            "window_id": window["id"], "targets": frozen, "wait": False, "verify": False,
            "manifest_sha256": sealed["manifest_sha256"], **scopes[host]}, "target-frozen")
        drifted = sorted(target_id for target_id, entry in found["targets"].items()
                         if not entry["matches"])
        if drifted:
            raise lifecycle.Failed("target-frozen", host, "blocked", f"{', '.join(drifted)} "
                                   "changed after the freeze; nothing was merged", log=log)
    return window


def _merge_and_install(window, prepared, seen, progress, scopes):
    """Each host's own scratch clone merges the immutable tip, then installs: a pilot's clones
    are not joined by synchronization, so each host merges and installs its own."""
    pins, merges = inputs.PINS, {}
    for host in lifecycle.HOST_ORDER:
        window = lifecycle._step(window, seen, progress, "familiar-merge", host)
        merged, _ = lifecycle._call(host, "pilot", "familiar-merge", {
            "window_id": window["id"], "pre": pins["familiar_pre"],
            "tip": pins["familiar_feature_tip"], **scopes[host]}, "familiar-merge")
        merges[host] = merged["merge"]
        if host == "titan":
            window = lifecycle._save(window, familiar={
                **window["familiar"], "merge": merged["merge"], "parents": merged["parents"],
                "merged_at": lifecycle._now()})
        else:
            window = _clone_merge(window, host, merged["merge"])
    for host in lifecycle.HOST_ORDER:
        window = lifecycle._step(window, seen, progress, "familiar-install", host)
        recorded = prepared["hosts"][host]
        result, _ = lifecycle._call(host, "pilot", "familiar-install", {
            "window_id": window["id"], "merge": merges[host],
            "caches": recorded["caches"]["prefixes"], "path": recorded["install"]["path"],
            **scopes[host]}, "familiar-install")
        window = lifecycle._save(window, dependencies={**window.get("dependencies", {}),
                                                       host: result})
    return window, merges


def _clone_merge(window, key, merge):
    """Record the merge of a scratch clone other than Titan's, where restoration reads it."""
    record = window.get("familiar") or {}
    return lifecycle._save(window, familiar={**record, "clones": {**record.get("clones", {}),
                                                                  key: merge}})


def _apply(window, seen, progress, scopes):
    """Titan's four live-simulation copies, each registered under the one touched record before
    its first write, then applied to the sealed bytes."""
    sealed = window["sealed"]["inputs"]
    for target_id in inputs.TARGETS:
        entry = sealed["hosts"]["titan"][target_id]
        window = lifecycle._step(window, seen, progress, "target-register", "titan")
        state.register_target(window, target_id, Path(entry["path"]),
                              Path(window["directory"]) / "live" / f"{target_id}.json")
        window = lifecycle._step(window, seen, progress, "target-apply", "titan")
        result, _ = lifecycle._call("titan", "pilot", "target-apply", {
            "window_id": window["id"], "target_id": target_id,
            "manifest_sha256": sealed["manifest_sha256"],
            "frozen_sha256": entry["frozen"]["sha256"],
            "expected_sha256": entry["expected"]["sha256"],
            "identities": entry["identities"], **scopes["titan"]}, "target-apply")
        window = lifecycle._save(window, applied={**window.get("applied", {}), target_id: result})
    return window


def _verify(window, seen, progress, scopes, merges):
    """Titan's copies hold the sealed bytes with hooks, statusLine, installer and evidence
    verified; each clone is its merge with the pinned relay; both merged trees are equal; and
    Europa's own sealed outputs of the shared images are exactly Titan's applied bytes."""
    sealed, identity = window["sealed"]["inputs"], window["id"]
    expected = {target_id: result["expected"]["sha256"]
                for target_id, result in sealed["hosts"]["titan"].items()}
    window = lifecycle._step(window, seen, progress, "target-verify", "titan")
    found, log = lifecycle._call("titan", "pilot", "target-verify", {
        "window_id": identity, "targets": expected, "wait": False, "verify": True,
        "manifest_sha256": sealed["manifest_sha256"], **scopes["titan"]}, "target-verify")
    missing = sorted(target_id for target_id, entry in found["targets"].items()
                     if not entry["matches"])
    if missing or not found["verified"]:
        raise lifecycle.Failed("target-verify", "titan", "blocked", f"{', '.join(missing)} do "
                               "not hold the sealed bytes", log=log)
    window = _gate(window, "apply", "passed", targets={
        target_id: result["sha256"] for target_id, result in window["applied"].items()})
    sources, observed = {}, {}
    for host in lifecycle.HOST_ORDER:
        window = lifecycle._step(window, seen, progress, "familiar-verify", host)
        sources[host], _ = lifecycle._call(host, "pilot", "familiar-verify", {
            "window_id": identity, "merge": merges[host], **scopes[host]}, "familiar-verify")
        window = lifecycle._step(window, seen, progress, "pilot-observe", host)
        observed[host], _ = lifecycle._call(host, "pilot", "pilot-observe", {
            "window_id": identity, **scopes[host]}, "pilot-observe")
    trees = {host: observed[host]["tree"] for host in lifecycle.HOST_ORDER}
    equal = len(set(trees.values())) == 1 and all(observed[host]["clean"]
                                                   for host in lifecycle.HOST_ORDER)
    window = _gate(window, "source", "passed" if equal else "failed", equal=equal,
                   merges=merges, trees=trees)
    pins = {"version": inputs.PINS["relay_version"], "commit": inputs.PINS["relay_commit"]}
    relays = {host: sources[host]["relay"] for host in lifecycle.HOST_ORDER}
    window = _gate(window, "dependencies", "passed" if all(
        relay == pins for relay in relays.values()) else "failed", hosts=relays,
        trees={host: window["dependencies"][host]["tree"] for host in lifecycle.HOST_ORDER})
    applied = {target_id: window["applied"][target_id]["sha256"]
               for target_id in inputs.CLAUDE_TARGETS}
    remote = {target_id: observed["europa"]["dry"][target_id]
              for target_id in inputs.CLAUDE_TARGETS}
    europa = {target_id: sealed["hosts"]["europa"][target_id]["expected"]["sha256"]
              for target_id in inputs.CLAUDE_TARGETS}
    window = _gate(window, "remote-expectations",
                   "passed" if applied == remote == europa else "failed", targets=applied,
                   europa=remote)
    if not equal or window["pilot"]["gates"]["remote-expectations"]["verdict"] != "passed":
        raise lifecycle.Failed("pilot-observe", "europa", "blocked", "the merged sources or "
                               "Europa's sealed shared images differ from Titan's")
    return lifecycle._save(window, verified={"at": lifecycle._now(), "sources": sources,
                                             "observed": observed})


# --- the disconnect case --------------------------------------------------------------------


def _status(operation_id: str) -> dict:
    """One operation-status read over a new connection to Europa."""
    return hosts.reconcile_operation({"host": "europa", "mode": "pilot"}, operation_id)


def _seen(status):
    return {"state": status["state"], "children": status.get("children") or []}


def _install_child(observed):
    found = [child for child in (observed or {}).get("children", ())
             if child["label"] == "npm-ci" and child["started"]]
    return found[-1] if found else None


def exercised(latch: bool, before: dict | None, after: dict | None,
              response: dict | None) -> tuple[bool, str]:
    """Whether one drop exercised the disconnect case, and how. It needs the install-start
    observation (npm's recorded start) while the operation ran. Unlatched, npm must still have
    been running then and the operation still running after the drop; latched, the operation
    must report that its hold ended because its client was gone. Anything else is unexercised."""
    if before is None:
        return False, "no install-start observation was made"
    if before["state"] in hosts.TERMINAL:
        return False, "the install finished before the disconnect point"
    child = _install_child(before)
    if child is None or before["state"] != "running":
        return False, "no observation of npm started while the install ran"
    if latch:
        held = ((response or {}).get("result") or {}).get("held") or {}
        if held.get("released") == "disconnect":
            return True, "latched"
        return False, "the latched install did not see its client leave"
    if child["exit"] is not None:
        return False, "the install finished npm before the disconnect point"
    if (after or {}).get("state") != "running":
        return False, "the install finished before the disconnect point could be confirmed"
    return True, "npm-running"


def _final(operation_id, deadline):
    """The dropped operation's durable reply, read by its ID until it is final; an unreachable
    host is retried until the deadline. Nothing reruns it."""
    while True:
        try:
            status = _status(operation_id)
        except Stop:
            status = None
        if status is not None and status["state"] in hosts.TERMINAL:
            return status["response"]
        if status is not None and status["state"] == "owner-lost":
            raise hosts.Unsettled(f"europa: operation {operation_id} lost its owner before it "
                                  "recorded completion", host="europa",
                                  operation_id=operation_id, remote=status)
        if time.monotonic() >= deadline:
            raise hosts.Unsettled(f"europa: operation {operation_id} is still not final; it may "
                                  "still be running until its own deadline", host="europa",
                                  operation_id=operation_id, remote=status)
        time.sleep(SETTLE_SECONDS)


def dropped_install(payload: dict) -> dict:
    """One attempt of the disconnect case: Europa's scratch install through start_request; its
    durable start and npm's start watched over a second connection; then only the returned
    owned local SSH client dropped (stopped and reaped; nothing is sent to Europa) and the
    operation reconciled by ID through completion or its deadline. A local signal sends an
    explicit operation-cancel and is reconciled the same way."""
    spec = OPERATIONS["pilot-install"]
    deadline = time.monotonic() + spec.deadline + lifecycle.MARGIN
    attempt = {"latch": payload["latch"], "observed": [None, None], "client": None,
               "dropped": False, "interrupted": None}
    with hosts._raising_signals():
        try:
            operation_id, client = hosts.start_request("europa", "pilot", "pilot-install",
                                                       payload, timeout=spec.deadline)
        except hosts._Signal:
            raise hosts.Interrupted("europa: the scratch install was interrupted while it was "
                                    "sent; reconcile Europa's operations before any retry",
                                    host="europa", operation_id=None, remote=None) from None
        attempt["operation_id"] = operation_id
        started = time.monotonic()
        try:
            while time.monotonic() < deadline:
                try:
                    status = _status(operation_id)
                except Stop:
                    time.sleep(WATCH_SECONDS)
                    continue
                if status["state"] == "unknown" and (
                        time.monotonic() < started + hosts.READ_SECONDS + hosts.GRACE_SECONDS):
                    time.sleep(WATCH_SECONDS)  # its durable start is not visible yet
                    continue
                attempt["observed"][0] = _seen(status)
                child = _install_child(status)
                if status["state"] != "running" or (
                        child is not None and (payload["latch"] or child["exit"] is None)):
                    break  # final already, or the install-start observation to drop on
                time.sleep(WATCH_SECONDS)
            hosts._abandon(client)  # only the owned local client: its pipes close
            attempt.update(client=client.returncode, dropped=True)
            try:
                attempt["observed"][1] = _seen(_status(operation_id))
            except Stop:
                attempt["observed"][1] = None
            response = _final(operation_id, deadline)
        except hosts._Signal as caught:
            hosts._abandon(client)
            attempt.update(client=client.returncode, interrupted=caught.signum)
            try:
                try:
                    hosts._control("europa", "pilot", "operation-cancel", operation_id)
                except Stop:
                    pass  # unreachable: reconciliation below still reads it to the deadline
                response = _final(operation_id, deadline)
            except hosts._Signal:
                raise hosts.Interrupted(f"europa: operation {operation_id} was interrupted again "
                                        "while it was cancelled; reconcile it with "
                                        "operation-status before any retry", host="europa",
                                        operation_id=operation_id, remote=None) from None
    attempt["response"] = response
    attempt["exercised"], how = exercised(payload["latch"], attempt["observed"][0],
                                          attempt["observed"][1], response)
    attempt["drop"] = how if attempt["exercised"] else None
    attempt["reason"] = None if attempt["exercised"] else how
    return attempt


def _summary(attempt):
    response = attempt["response"]
    return {key: attempt[key] for key in ("operation_id", "latch", "exercised", "drop", "reason",
                                          "client", "observed", "interrupted")} | {
        "response": {"status": response["status"], "error": response["error"]}}


def _recover_clone(window, host, seen, progress, *, scope, key):
    """One scratch clone restored offline through recovery's core: its merge reverted, then its
    dependencies returned from its own pre-merge snapshot."""
    from . import recovery  # recovery imports the window lifecycle
    if "recovery" not in window:
        window = lifecycle._save(window, recovery={"started_at": lifecycle._now(),
                                                   "attempted_at": lifecycle._now(),
                                                   "actions": [], "cancelled": []})
    window, recovered = recovery.restore_clone(window, host, seen, progress, scope=scope,
                                               key=key)
    window, dependencies = recovery.restore_dependencies(window, host, recovered["revert"],
                                                         seen, progress, scope=scope, key=key)
    return window, {"familiar": recovered, "dependencies": dependencies}


def disconnect_case(window: dict, prepared: dict, reference: dict, seen: list,
                    progress: dict) -> dict:
    """The real disconnect: a second scratch clone on Europa, merged, then installed with its
    client dropped while it runs (`dropped_install`). An install that finished first is
    unexercised and retried once with the pilot-only latch; an exercised one needs its known
    completion, the pinned relay and the dependency tree of Europa's main install. A failed or
    timed-out install has its scratch dependencies recovered offline. Cleanup follows later."""
    def step(name, host):
        nonlocal window
        window = lifecycle._step(window, seen, progress, name, host)

    def keep(**changes):
        nonlocal window
        window = _pilot(window, disconnect={**window["pilot"].get("disconnect", {}), **changes})

    pins = inputs.PINS
    window, created = _create(window, seen, progress, "disconnect")
    scope = {hosts.SCRATCH: created["europa"]["root"]}
    keep(root=created["europa"]["root"], attempts=[], verdict=None)
    step("familiar-merge", "europa")
    merged, _ = lifecycle._call("europa", "pilot", "familiar-merge", {
        "window_id": window["id"], "pre": pins["familiar_pre"],
        "tip": pins["familiar_feature_tip"], **scope}, "familiar-merge")
    window = _clone_merge(window, "disconnect", merged["merge"])
    keep(merge=merged["merge"])
    recorded = prepared["hosts"]["europa"]
    payload = {"window_id": window["id"], "merge": merged["merge"],
               "caches": recorded["caches"]["prefixes"], "path": recorded["install"]["path"],
               **scope}
    attempts = []
    for latch in (False, True):
        step("pilot-install", "europa")
        try:
            attempt = dropped_install({**payload, "latch": latch})
        except hosts.Unsettled as error:
            raise lifecycle.Failed("pilot-install", "europa", "unsettled", str(error)) from None
        attempts.append(_summary(attempt))
        keep(attempts=list(attempts))
        response = attempt["response"]
        if response["status"] != "completed" or attempt["interrupted"]:
            keep(verdict="failed", reason=f"the scratch install ended {response['status']}: "
                                          f"{response['error']}")
            window, recovered = _recover_clone(window, "europa", seen, progress, scope=scope,
                                               key="disconnect")
            keep(recovered=recovered)
            if attempt["interrupted"]:  # the operator's signal stops the rehearsal here
                raise lifecycle.Failed("pilot-install", "europa", "interrupted", "interrupted "
                                       f"by {signal.Signals(attempt['interrupted']).name}; the "
                                       "scratch install was cancelled, reconciled and its "
                                       "dependencies recovered offline")
            return window
        if attempt["exercised"]:
            result = response["result"]
            relay = {"version": pins["relay_version"], "commit": pins["relay_commit"]}
            equal = result["tree"] == reference.get("tree")
            keep(relay=result["relay"], tree=result["tree"], equal=equal,
                 verdict="passed" if equal and result["relay"] == relay else "failed")
            return window
    keep(verdict="unexercised", reason="every attempt finished before its disconnect point")
    return window


# --- restoration, cleanup and the verdict ---------------------------------------------------


def _restore(window, seen, progress):
    """Titan's copies, both clones and both dependency trees restored offline through recovery's
    own core, after this window's unfinished operations are reconciled."""
    from . import recovery  # recovery imports the window lifecycle
    progress.update(step="reconcile", host="titan")
    blockers, cancelled, _ = recovery._settle(window, cancel=lambda entry: True)
    if blockers:
        raise lifecycle.Failed("reconcile", blockers[0].split(":", 1)[0], "unsettled",
                               "unfinished host operations block the pilot's restoration",
                               blockers=blockers)
    earlier = window.get("recovery") or {}
    window = lifecycle._save(window, state="recovering", recovery={
        **earlier, "started_at": earlier.get("started_at", lifecycle._now()),
        "attempted_at": lifecycle._now(), "actions": earlier.get("actions", []),
        "cancelled": [*earlier.get("cancelled", []), *cancelled]})
    window = recovery.restore_native(window, seen, progress, clones=lifecycle.HOST_ORDER,
                                     scopes=_scopes(window), pending=())
    recovered = window["recovery"]
    clones = {"titan": recovered["familiar"]["revert"],
              **{host: entry["revert"] for host, entry in recovered.get("clones", {}).items()
                 if host in lifecycle.HOST_ORDER}}
    return _gate(window, "restore", "passed",
                 targets={target_id: "native" for target_id in recovered["originals"]["targets"]},
                 familiar=clones, dependencies={host: recovered["dependencies"][host]["tree"]
                                                for host in lifecycle.HOST_ORDER})


def _forward(window, prepared, decision, seen, progress):
    window = _inventory(window, prepared, seen, progress)
    window, gate = spawn_gate(window, decision)
    window = _gate(window, "spawn", gate["verdict"], **{key: gate[key] for key in (
        "reason", "attempt_id", "hosts")})
    window, _ = _create(window, seen, progress, "main")
    window = _gate(window, "scratch", "passed", roots=window["pilot"]["roots"])
    scopes = _scopes(window)
    window = lifecycle.dry_runs(window, prepared, seen, progress, scopes)
    window = _frozen(window, seen, progress, scopes)
    window = _gate(window, "dry-runs", "passed",
                   order=[[host, target_id] for host, found in window["dry"].items()
                          for target_id in found],
                   effective_inputs_sha256=window["sealed"]["effective_inputs_sha256"])
    window = lifecycle._save(window, familiar={"started_at": lifecycle._now(),
                                               "pre": inputs.PINS["familiar_pre"],
                                               "tip": inputs.PINS["familiar_feature_tip"]})
    window, merges = _merge_and_install(window, prepared, seen, progress, scopes)
    window = _apply(window, seen, progress, scopes)
    window = _verify(window, seen, progress, scopes, merges)
    window = disconnect_case(window, prepared, window["dependencies"]["europa"], seen,
                             progress)
    case = window["pilot"]["disconnect"]
    window = _gate(window, "disconnect", case["verdict"], **{
        key: case.get(key) for key in ("root", "attempts", "relay", "equal", "reason",
                                       "recovered")})
    if seen:
        raise lifecycle._Interrupt(seen[-1])
    return _restore(window, seen, progress)


def _restorable(window):
    roots = window["pilot"].get("roots") or {}
    return ("sealed" in window and set(roots) == set(lifecycle.HOST_ORDER)
            and window["state"] == "applying")


def _cleanup(window, seen, progress):
    """Every scratch root of this window removed on both hosts, once its operations settled."""
    from . import recovery  # recovery imports the window lifecycle
    progress.update(step="reconcile", host="titan")
    blockers, cancelled, _ = recovery._settle(window, cancel=lambda entry: True)
    if blockers:
        raise lifecycle.Failed("reconcile", blockers[0].split(":", 1)[0], "unsettled",
                               "unfinished host operations block the scratch cleanup; their "
                               "roots stay until they settle", blockers=blockers)
    removed = {}
    for host in lifecycle.HOST_ORDER:
        window = lifecycle._step(window, seen, progress, "pilot-cleanup", host)
        result, _ = lifecycle._call(host, "pilot", "pilot-cleanup", {"window_id": window["id"]},
                                    "pilot-cleanup")
        removed[host] = sorted(result["removed"])
    return _gate(window, "cleanup", "passed", hosts=removed, cancelled=cancelled)


def _failure(failed):
    return {"step": failed.step, "host": failed.host, "status": failed.status,
            "error": failed.error, "log": failed.log}


def _verdict(window, prepared, failures):
    gates = {name: (window["pilot"].get("gates") or {}).get(name, {"verdict": "not-run"})
             for name in GATES}
    for failed in failures:
        name = STEP_GATES.get(failed.step, "restore")
        if gates[name]["verdict"] in ("passed", "not-run"):
            gates[name] = {"verdict": "failed", "error": failed.error, "step": failed.step,
                           "host": failed.host}
    verdicts = {gate["verdict"] for gate in gates.values()}
    overall = ("failed" if failures or verdicts & {"failed", "not-run"} else
               "pending" if verdicts & {"pending", "unexercised"} else "passed")
    spawned = gates["spawn"]["verdict"] in ("passed", "failed")
    return {
        "schema": 1, "kind": VERDICT_KIND, "window_id": window["id"],
        "prepared_sha256": window["prepared_sha256"],
        "controller_session": window["pilot"].get("controller_session"),
        "helper_sha256": hosts.helper_digest(), "started_at": window["pilot"].get("started_at"),
        "finished_at": lifecycle._now(), "verdict": overall,
        "failure": _failure(failures[0]) if failures else None, "gates": gates,
        "hosts": {host: {"toolchain": prepared["hosts"][host]["toolchain"],
                         "install_path": prepared["hosts"][host]["install"]["path"]}
                  for host in lifecycle.HOST_ORDER},
        "permitted_writes": {"caches": {host: prepared["hosts"][host]["caches"]["prefixes"]
                                        for host in lifecycle.HOST_ORDER},
                             "runtime": RUNTIME, "spawn": SPAWN if spawned else None},
        "host_byte_equal": False, "unexercised": list(UNEXERCISED)}


def _conclude(window, prepared, failures):
    """The private verdict, written in the window; the window closes once cleanup passed."""
    verdict = _verdict(window, prepared, failures)
    path = Path(window["directory"]) / VERDICT
    state.save_record(path, verdict)
    closed = (window["pilot"].get("gates") or {}).get("cleanup", {}).get("verdict") == "passed"
    window = lifecycle._save(window, state="recovered" if closed else window["state"],
                             pilot={**window["pilot"], "verdict": {
                                 "path": str(path), "verdict": verdict["verdict"],
                                 "sha256": _sha256(path.read_bytes())}})
    return {**verdict, "window": window, "path": str(path), "closed": closed}


def _earlier(window):
    """Why an open pilot stopped: its recorded verdict's failure (a cleanup that could not run),
    or an interruption that recorded no outcome."""
    recorded = window["pilot"].get("verdict")
    if recorded is not None:
        failure = state.load_record(Path(recorded["path"])).get("failure")
        if failure:
            return lifecycle.Failed(failure["step"], failure["host"], failure["status"],
                                    failure["error"], log=failure["log"])
    last = (window.get("attempts") or [{}])[-1]
    return lifecycle.Failed(last.get("step", "rehearse"), last.get("host", "titan"),
                            "interrupted", "the rehearsal stopped without recording its "
                            "outcome; it was reconciled")


def _prepared(window, session):
    from .prepare import load_prepared  # prepare imports the window lifecycle
    prepared = state.load_record(Path(window["directory"]) / lifecycle.PREPARED)
    if (lifecycle.prepared_sha256(prepared) != window["prepared_sha256"]
            or lifecycle.prepared_sha256(load_prepared()) != window["prepared_sha256"]):
        raise _refused(f"pilot window {window['id']} was previewed for another preparation; "
                       "preview again", session, "--preview")
    return prepared


def rehearse(controller_session: str, decision: dict | None) -> dict:
    """Run the previewed pilot with this invocation's answer to its spawn (`answer`), or
    reconcile and close an interrupted one, and return its verdict. Any stop restores what it
    can offline, removes every scratch root and records a failed verdict naming the step."""
    _session(controller_session)
    root = lifecycle._root()
    window = state.current_window(root)
    if window is None or window["mode"] != "pilot" or window["state"] in state.TERMINAL:
        raise _refused("no pilot preview is open; preview one first", controller_session,
                       "--preview")
    owner = window.get("owner")
    if owner is not None and owner != lifecycle._me() and hosts._alive(owner):
        raise _refused(f"pilot window {window['id']} belongs to a running invocation (pid "
                       f"{owner['pid']})", controller_session)
    prepared = _prepared(window, controller_session)
    failures, progress = [], {"step": "inventory", "host": "titan"}
    if window["state"] == "prepared":
        window = lifecycle._save(window, state="applying", owner=lifecycle._me(), attempts=[],
                                 pilot={**window["pilot"], "roots": {},
                                        "controller_session": controller_session,
                                        "started_at": lifecycle._now()})
        with lifecycle._signals() as seen:
            try:
                _forward(window, prepared, decision, seen, progress)
            except (Exception, lifecycle._Interrupt) as error:
                failures.append(lifecycle._as_failed(error, progress))
    else:
        failures.append(_earlier(window))
        window = lifecycle._save(window, owner=lifecycle._me())
    window = state.current_window(root)
    if failures and _restorable(window):
        with lifecycle._signals() as seen:
            try:
                _restore(window, seen, progress)
            except (Exception, lifecycle._Interrupt) as error:
                failures.append(lifecycle._as_failed(error, progress))
        window = state.current_window(root)
    with lifecycle._signals() as seen:
        try:
            _cleanup(window, seen, progress)
        except (Exception, lifecycle._Interrupt) as error:
            failures.append(lifecycle._as_failed(error, progress))
    return _conclude(state.current_window(root), prepared, failures)


# The controller side uses the window lifecycle and the surfaces, which import operations (the
# lifecycle directly, the surfaces through it) and so this module: they are bound here, once this
# module's operations are defined.
from . import surfaces  # noqa: E402
from . import window as lifecycle  # noqa: E402
