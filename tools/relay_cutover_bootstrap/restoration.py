"""Restoring one cutover host from a window past the familiar record, and familiar's service.

These are fixed host operations run by `hosts.execute`; `recovery.py` orders them. None runs
npm, a fetch or a reset, the forward preflight or inventory, or any Claude executable: the
installed Claude version and its evidence may have moved since the window began, and nothing
here reads them. What they do require is this window's protected rollback inputs, the pinned
relay and helper that applied its targets, and byte, Git and dependency proofs:

- `recovery-no-live` (both hosts): strict no-live from this user's whole process table, with no
  exemption. It never runs relay-cutover's preflight, whose evidence check launches Claude; that
  check's own process scan is narrower than this one.
- `timer-requiesce` (both hosts): stop this host's timers again from this window's original
  record, which is never rewritten. A restore that an earlier finish completed is kept under
  `quiesce/<window>/requiesced/`, so the window reads as pausing them here again.
- `target-check` (Titan): every settings target against the images this window keeps. A
  registered target is `original`, `relay-applied` (this window's own artifact's after bytes),
  `guard-retired` (its `.after-guard` image) or `unknown`; one never registered is `frozen`
  while it holds its frozen bytes, else `unknown`.
- `target-restore` (Titan): one registered target through `relay-cutover restore`, the existing
  byte gate, with this window's artifact and guard images and the pinned relay for its rollback;
  afterwards it must equal its registered original. Bytes matching no recorded image stop before
  any write: nothing is force-copied.
- `familiar-reconcile` (Titan): familiar's actual Git state against PRE, the approved tip and the
  window's merge and revert records: `merge-in-progress` (HEAD at PRE, MERGE_HEAD the tip),
  `at-pre`, `merged` (HEAD's parents PRE and the tip, recorded or not), `reverted` (one commit
  whose parent is that merge and whose tree is PRE's, recorded or not) or `unexpected`.
- `familiar-restore` (Titan): classifies again and takes that state's one action: `git merge
  --abort`, nothing, `git revert -m 1 --no-edit MERGE` once, or nothing. The result must be a
  clean tree equal to PRE's; a revert's parent must be the merge.
- `dependency-restore` (both hosts): once familiar's source here is the recovered commit (a
  bounded wait for synchronization), replace `node_modules` with this window's verified
  pre-merge snapshot, offline, unless it already equals it; then familiar must check native.
- `service-run` and `service-check` (both hosts): the recorded timer's service, started only
  once this window's timers are restored here (run) or only read (check), waited for within a
  bound and required to end with `Result=success` and `ExecMainStatus=0`.

A pilot restores through the same target, familiar and dependency operations on its owned
scratch root (`pilot.resolve`): its target copies, each host's own clone and its snapshot under
the root's `state/`. Its timers, no-live and services stay live only.

Children run through `hosts._run_child`; their output stays in the private log."""
import hashlib
import os
import shutil
import stat
import time
from pathlib import Path

from . import familiar, hosts, inputs, inventory, quiesce, state, targets
from .state import Stop

CHILD_SECONDS = 120
SYNC_BUDGET_SECONDS = hosts.SYNC_SECONDS  # the longest wait for the recovered source here
SYNC_POLL_SECONDS = 2.0
SERVICE_SECONDS = 600  # the longest wait for a running service to finish
SERVICE_POLL_SECONDS = 2.0
REQUIESCED = "requiesced"
SNAPSHOT = "familiar-node_modules.pre"
RELAY = ("installer", "relay_cutover", "runtime")  # the pinned relay a rollback runs with
EXPECTED = ("merge-in-progress", "at-pre", "merged", "reverted")
SETTLED = ("inactive", "failed")
SERVICE_PROPERTIES = ("ActiveState", "Result", "ExecMainStatus")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


# --- no-live and timers ----------------------------------------------------------------------


def recovery_no_live(context):
    """Every Claude or Codex process of this user, known executable or not."""
    return {"live": quiesce._harness_processes(context)}


def timer_requiesce(context):
    """Stop this host's timers again from this window's original record."""
    path, data = quiesce._recorded(context, context["payload"]["record_sha256"])
    if data is None:
        raise Stop("this window recorded no timers on this host; inspect the window before "
                   "recovery")
    quiesce._parse_timers(data)
    marker, retained = path.parent / quiesce.RESTORED, None
    if os.path.lexists(marker):
        retained = str(quiesce._retain(marker, path.parent / REQUIESCED, quiesce.RESTORED))
    quiesce._timers(context, "timer-requiesce", "stop", path)
    return {"stopped": [quiesce.TIMER], "was_restored": retained is not None,
            "retained": retained}


# --- settings targets ------------------------------------------------------------------------


def _window(context):
    """This window's directory and ledger, kept on Titan with the controller's records."""
    window_id = context["payload"]["window_id"]
    directory = Path(context["root"]) / "windows" / window_id
    try:
        record = state.load_record(directory / "window.json")
        entries = state.read_ledger(record)
    except Stop as stop:
        raise Stop(f"window {window_id}'s ledger cannot be read ({stop}); nothing was written") \
            from None
    return directory, {entry["target_id"]: entry for entry in entries}


def _images(directory, entry):
    """A registered target's original, guard images and this window's own artifact change."""
    live = directory / "live"
    name = entry["target"].replace("/", "_")  # relay-cutover's guard image names
    images = {"original": state._read(Path(entry["original"])),
              "after_guard": targets._read(live / (name + ".after-guard")),
              "artifact": None, "artifact_after": None}
    artifact = Path(entry["artifact"])
    if artifact != live / f"{entry['target_id']}.json":
        raise Stop(f"{entry['target_id']}: the ledger names an artifact outside this window's "
                   "live directory; inspect it")
    data = targets._read(artifact)
    if data is not None:
        recorded = targets._parse(data, f"{entry['target_id']} artifact")
        changes = [change for change in recorded.get("changes") or []
                   if isinstance(change, dict) and change.get("path") == entry["target"]]
        if (not state._is_one(recorded.get("schema")) or len(changes) != 1
                or not isinstance(changes[0].get("after"), str)):
            raise Stop(f"{entry['target_id']}: this window's artifact does not record exactly "
                       "this target's change; inspect it")
        images.update(artifact=str(artifact), artifact_after=changes[0]["after"].encode("utf-8"))
    return images


def _verdict(current, images):
    if current is None:
        return "unknown"
    if current == images["original"]:
        return "original"
    if images["artifact_after"] is not None and current == images["artifact_after"]:
        return "relay-applied"
    if images["after_guard"] is not None and current == images["after_guard"]:
        return "guard-retired"
    return "unknown"


def _resolved(context, target_id):
    return targets.target_path(context, target_id)


def target_check(context):
    """Read-only: each target's bytes against the images this window recorded for it."""
    directory, ledger = _window(context)
    report = {}
    for target_id, frozen in context["payload"]["frozen"].items():
        path = _resolved(context, target_id)
        current = targets._read(Path(path))
        entry = ledger.get(target_id)
        if entry is None:
            native = frozen
            verdict = "frozen" if current is not None and _sha256(current) == frozen else "unknown"
        else:
            images = _images(directory, entry)
            native = _sha256(images["original"])
            verdict = _verdict(current, images) if path == entry["target"] else "unknown"
        report[target_id] = {"path": path, "registered": entry is not None, "verdict": verdict,
                             "sha256": _sha256(current) if current is not None else None,
                             "native_sha256": native}
    return {"targets": report}


def _pinned(context, expected):
    """The relay and helper a rollback runs with must be the bytes this window applied with."""
    home, hq = Path(context["home"]), Path(context["hq"])
    found = {"installer": inventory._file_sha256(hq / targets.INSTALLER),
             "relay_cutover": inventory._file_sha256(hq / targets.RELAY_CUTOVER),
             "runtime": inventory._file_sha256(
                 home / targets.RUNTIME.format(version=inputs.PINS["relay_version"]))}
    changed = [name for name in RELAY if found[name] is None or found[name] != expected[name]]
    if changed:
        raise Stop(f"{', '.join(changed)} differ from the bytes this window applied with; "
                   "deliver the pinned relay and helper first; nothing was written")


def target_restore(context):
    """Return one registered target to its original through the existing byte gate."""
    payload = context["payload"]
    target_id = payload["target_id"]
    directory, ledger = _window(context)
    entry = ledger.get(target_id)
    if entry is None:
        raise Stop(f"{target_id} is not registered in window {payload['window_id']}; nothing "
                   "was written")
    if _resolved(context, target_id) != entry["target"]:
        raise Stop(f"{target_id} no longer resolves to its registered path; inspect it; nothing "
                   "was written")
    targets.closed(context)
    _pinned(context, payload["identities"])
    target = Path(entry["target"])
    images = _images(directory, entry)
    verdict = _verdict(targets._read(target), images)
    result = {"target_id": target_id, "path": entry["target"], "from": verdict,
              "restored": False, "rollback": False,
              "sha256": _sha256(images["original"])}
    if verdict == "original":
        return result
    if verdict == "unknown":
        raise Stop(f"{target_id} holds bytes matching no image this window recorded; nothing "
                   "was force-copied; inspect it")
    args = ["restore", "--target", target, "--backup", directory / "live"]
    if images["artifact"] is not None:  # an artifact is passed only when this window wrote it
        args += ["--artifact", images["artifact"]]
    env = hosts._child_env(context)
    env["RELAY_CUTOVER_RELAY"] = os.path.realpath(Path(context["hq"]) / targets.INSTALLER)
    restored = hosts._run_child(context, f"{target_id}-restore",
                                [hosts.TOOLS["python3"], "-B",
                                 Path(context["hq"]) / targets.RELAY_CUTOVER, *args],
                                env=env, timeout=2 * CHILD_SECONDS)
    if restored.returncode != 0:
        raise Stop(f"relay-cutover restore refused {target_id} (exit {restored.returncode}); "
                   "nothing was force-copied; inspect it (see the private log)")
    if targets._read(target) != images["original"]:
        raise Stop(f"after its restore {target_id} is not its registered original; inspect it")
    result.update(restored=True, rollback=verdict == "relay-applied")
    return result


# --- familiar's source ------------------------------------------------------------------------


def _ref(context, label, name):
    result = familiar._git(context, label, "rev-parse", "--verify", "-q", name)
    text = familiar._text(result)
    return text if result.returncode == 0 and familiar.COMMIT.fullmatch(text) else None


def _parents(context, commit):
    result = familiar._git(context, "familiar-parents", "rev-list", "--parents", "-n", "1",
                           commit)
    words = familiar._text(result).split()
    if result.returncode != 0 or not words or words[0] != commit:
        raise Stop(f"familiar's history cannot be read at {commit[:12]}; inspect it")
    return words[1:]


def _tree(context, commit):
    result = familiar._git(context, "familiar-tree", "rev-parse", "--verify", "-q",
                           f"{commit}^{{tree}}")
    text = familiar._text(result)
    if result.returncode != 0 or not familiar.COMMIT.fullmatch(text):
        raise Stop(f"familiar's tree at {commit[:12]} cannot be read; inspect it")
    return text


def _pins(payload):
    if (payload["pre"], payload["tip"]) != (inputs.PINS["familiar_pre"],
                                           inputs.PINS["familiar_feature_tip"]):
        raise Stop("recovery must name the approved familiar PRE and feature tip; nothing was "
                   "changed")
    return payload["pre"], payload["tip"]


def classify(context):
    """familiar's actual Git state against PRE, the tip and the window's records."""
    payload = context["payload"]
    pre, tip = _pins(payload)
    merge, revert = payload.get("merge"), payload.get("revert")
    found = {"class": "unexpected", "head": None, "merge": merge, "revert": revert,
             "discovered": False, "reason": None}

    def unexpected(reason):
        found["reason"] = reason
        return found

    head = found["head"] = _ref(context, "familiar-head", "HEAD")
    if head is None:
        return unexpected("familiar has no HEAD commit")
    if _ref(context, "familiar-revert-head", "REVERT_HEAD") is not None:
        return unexpected("a revert is in progress in familiar's checkout")
    merging = _ref(context, "familiar-merge-head", "MERGE_HEAD")
    if merging is not None:
        if (head, merging, merge, revert) == (pre, tip, None, None):
            found.update({"class": "merge-in-progress", "revert": None})
            return found
        return unexpected("a merge other than the attempted one is in progress")
    if head == pre:
        if merge is None and revert in (None, pre):
            found.update({"class": "at-pre", "revert": pre})
            return found
        return unexpected("familiar is at PRE although this window recorded its merge or revert")
    parents = _parents(context, head)
    if parents == [pre, tip]:
        if merge in (None, head) and revert is None:
            found.update({"class": "merged", "merge": head, "discovered": merge is None})
            return found
        return unexpected("HEAD is a merge of PRE and the tip other than this window's records")
    if (len(parents) == 1 and parents[0] != pre and _parents(context, parents[0]) == [pre, tip]
            and _tree(context, head) == _tree(context, pre)):
        if merge in (None, parents[0]) and revert in (None, head):
            found.update({"class": "reverted", "merge": parents[0], "revert": head,
                          "discovered": merge is None or revert is None})
            return found
        return unexpected("HEAD reverts a merge other than this window's records")
    return unexpected("HEAD is neither PRE, the attempted merge nor its revert")


def familiar_reconcile(context):
    return classify(context)


def _clean(context, commit, label):
    if not familiar._source(context, commit, label):
        raise Stop(f"familiar's working tree is not clean at {commit[:12]}; inspect it")


def familiar_restore(context):
    """Take the one action familiar's reconciled Git state needs, after classifying it again."""
    payload = context["payload"]
    pre, _ = _pins(payload)
    targets.closed(context)
    found = classify(context)
    if found["class"] != payload["expect"]:
        raise Stop(f"familiar's Git state is {found['class']}, not the {payload['expect']} this "
                   "recovery reconciled; nothing was changed; reconcile again")
    action = "none"
    if found["class"] == "merge-in-progress":
        if familiar._git(context, "familiar-merge-abort", "merge", "--abort").returncode != 0:
            raise Stop("git merge --abort failed; inspect familiar's checkout before any retry")
        if (_ref(context, "familiar-merge-head", "MERGE_HEAD") is not None
                or _ref(context, "familiar-head", "HEAD") != pre):
            raise Stop("familiar did not return to PRE after the merge abort; inspect it")
        action, revert = "merge-aborted", pre
    elif found["class"] == "merged":
        merge = found["merge"]
        _clean(context, merge, "familiar-source-merge")
        if familiar._git(context, "familiar-revert", "revert", "-m", "1", "--no-edit",
                         merge).returncode != 0:
            raise Stop("git revert of the merge failed; inspect familiar's checkout before any "
                       "retry")
        revert = _ref(context, "familiar-head", "HEAD")
        if revert is None or _parents(context, revert) != [merge]:
            raise Stop("the revert commit's parent is not the merge; inspect familiar's checkout")
        action = "reverted"
    else:
        revert = found["revert"]
    if _tree(context, revert) != _tree(context, pre):
        raise Stop("familiar's recovered tree is not PRE's; inspect it")
    _clean(context, revert, "familiar-source-revert")
    return {"class": found["class"], "action": action, "merge": found["merge"],
            "revert": revert, "discovered": found["discovered"]}


# --- familiar's dependencies -------------------------------------------------------------------


def _snapshot(context):
    """This window's verified pre-merge dependency snapshot, unchanged since its refresh."""
    root, window_id = Path(context["state"]), context["payload"]["window_id"]
    record = root / quiesce.QUIESCE / window_id / quiesce.MOVES
    moves = state.load_record(record) if os.path.lexists(record) else {}
    found = [move for move in moves.get("moves") or [] if move.get("name") == SNAPSHOT]
    if not found or found[0].get("state") != "verified" or "aborted" in moves:
        raise Stop(f"this window never verified its {SNAPSHOT} snapshot on this host; inspect "
                   "it; nothing was restored")
    path = root / SNAPSHOT
    info = os.lstat(path) if os.path.lexists(path) else None
    if info is None or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise Stop(f"the retained {SNAPSHOT} snapshot is not this user's directory; nothing was "
                   "restored")
    tree = quiesce._tree(path)
    if tree["sha256"] != found[0]["sha256"]:
        raise Stop(f"the retained {SNAPSHOT} snapshot differs from the copy this window "
                   "verified; inspect it; nothing was restored")
    return path, tree


def _synchronized(context, commit):
    started = time.monotonic()
    while not familiar._source(context, commit, "familiar-source-sync"):
        if time.monotonic() + SYNC_POLL_SECONDS > started + SYNC_BUDGET_SECONDS:
            raise Stop(f"familiar's source did not reach the recovered commit {commit[:12]} on "
                       f"this host within {SYNC_BUDGET_SECONDS:g} s; it may still be "
                       "synchronizing; nothing was restored here")
        time.sleep(SYNC_POLL_SECONDS)
    return round(time.monotonic() - started, 3)


def _modules(path):
    """node_modules' tree, or None when it is absent; a symlink in its place is refused."""
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        raise Stop(f"{path} is a symlink; inspect it; nothing was restored")
    return quiesce._tree(path)


def dependency_restore(context):
    """familiar's dependencies from this window's pre-merge snapshot, offline."""
    payload = context["payload"]
    pre, revert = payload["pre"], payload["revert"]
    if pre != inputs.PINS["familiar_pre"]:
        raise Stop("recovery must name the approved familiar PRE; nothing was restored")
    targets.closed(context)
    snapshot, wanted = _snapshot(context)
    waited = _synchronized(context, revert)
    targets.closed(context)  # the wait can be long: a harness opened meanwhile still refuses
    if _tree(context, revert) != _tree(context, pre):
        raise Stop("familiar's source here is not PRE's tree; inspect it; nothing was restored")
    modules = Path(context["familiar"]) / "node_modules"
    replaced = _modules(modules) != wanted
    if replaced:
        if os.path.lexists(modules):
            shutil.rmtree(modules)
        quiesce._copy(snapshot, modules)
    if quiesce._tree(modules) != wanted:
        raise Stop("familiar's node_modules does not equal the pre-merge snapshot after its "
                   "restore; inspect it")
    if targets._helper(context, "familiar-check", "familiar-check", "--expect", "native",
                       *familiar.root_args(context)).returncode != 0:
        raise Stop("relay-cutover familiar-check --expect native failed; see the private log")
    return {"revert": revert, "waited_seconds": waited, "replaced": replaced, "tree": wanted}


# --- familiar's service --------------------------------------------------------------------------


def _service(context):
    path, data = quiesce._recorded(context, context["payload"]["record_sha256"])
    if data is None:
        raise Stop("this window recorded no timers on this host; its service is unknown")
    return path, quiesce._parse_timers(data)[0]["service"]


def _service_state(context, service):
    result = hosts._run_child(context, "service-show",
                              [hosts.TOOLS["systemctl"], "--user", "show",
                               "--property=" + ",".join(SERVICE_PROPERTIES), service],
                              env=hosts._child_env(context), timeout=CHILD_SECONDS)
    found = dict(line.split("=", 1) for line in familiar._text(result).splitlines()
                 if "=" in line)
    if result.returncode != 0 or not set(SERVICE_PROPERTIES) <= set(found):
        raise Stop(f"systemctl --user show did not report {service}'s state; see the private log")
    return {key: found[key] for key in SERVICE_PROPERTIES}


def _settled(context, service):
    """The service once it is no longer running, which must be a success; nothing is killed."""
    started = time.monotonic()
    while True:
        found = _service_state(context, service)
        if found["ActiveState"] in SETTLED:
            break
        if time.monotonic() + SERVICE_POLL_SECONDS > started + SERVICE_SECONDS:
            raise Stop(f"{service} is still {found['ActiveState']} after {SERVICE_SECONDS:g} s; "
                       "nothing was killed; check it again later")
        time.sleep(SERVICE_POLL_SECONDS)
    report = {"service": service, "active_state": found["ActiveState"],
              "result": found["Result"], "exec_main_status": found["ExecMainStatus"],
              "waited_seconds": round(time.monotonic() - started, 3)}
    if (found["Result"], found["ExecMainStatus"]) != ("success", "0"):
        raise Stop(f"{service} ended with Result={found['Result']} "
                   f"ExecMainStatus={found['ExecMainStatus']}; see its journal")
    return report


def service_run(context):
    """Run the recorded timer's service once its timers are restored, and require success."""
    path, service = _service(context)
    if not os.path.lexists(path.parent / quiesce.RESTORED):
        raise Stop(f"this window keeps {quiesce.TIMER} paused on this host; restore its timers "
                   f"before running {service}")
    result = hosts._run_child(context, "service-start",
                              [hosts.TOOLS["systemctl"], "--user", "start", service],
                              env=hosts._child_env(context), timeout=SERVICE_SECONDS)
    if result.returncode != 0:
        raise Stop(f"systemctl --user start {service} exited {result.returncode}; see the "
                   "private log")
    return {"started": True, **_settled(context, service)}


def service_check(context):
    """Read-only: the recorded timer's service, waited for, must have ended in success."""
    _, service = _service(context)
    return {"started": False, **_settled(context, service)}


def _frozen(value):
    return (isinstance(value, dict) and set(value) == set(inputs.TARGETS)
            and all(quiesce._sha(digest) for digest in value.values()))


def _relay(value):
    return (isinstance(value, dict) and set(value) == set(RELAY)
            and all(quiesce._sha(digest) for digest in value.values()))


def _expected(value):
    return isinstance(value, str) and value in EXPECTED


_WINDOW = {"window_id": quiesce._window_id}
_RECORD = {**_WINDOW, "record_sha256": quiesce._sha}
_FAMILIAR = {**_WINDOW, "pre": quiesce._commit, "tip": quiesce._commit,
             "merge": quiesce._commit, "revert": quiesce._commit}
_FAMILIAR_REQUIRED = frozenset({"window_id", "pre", "tip"})
_DEPENDENCIES = {**_WINDOW, "pre": quiesce._commit, "revert": quiesce._commit}
_SERVICE_DEADLINE = 2 * SERVICE_SECONDS + 4 * CHILD_SECONDS

OPERATIONS = {
    "recovery-no-live": hosts.Operation(run=recovery_no_live, deadline=60, mutation=False,
                                        payload=_WINDOW, required=frozenset(_WINDOW)),
    "timer-requiesce": hosts.Operation(run=timer_requiesce, deadline=CHILD_SECONDS + 60,
                                       mutation=True, payload=_RECORD,
                                       required=frozenset(_RECORD)),
    "target-check": hosts.Operation(run=target_check, deadline=60, mutation=False,
                                    payload={**_WINDOW, "frozen": _frozen},
                                    required=frozenset({"window_id", "frozen"}),
                                    hosts=("titan",), modes=hosts.BOTH, scratch=True),
    "target-restore": hosts.Operation(
        run=target_restore, deadline=2 * CHILD_SECONDS + 60, mutation=True,
        payload={**_WINDOW, "target_id": targets._target_id, "identities": _relay},
        required=frozenset({"window_id", "target_id", "identities"}), hosts=("titan",),
        modes=hosts.BOTH, scratch=True),
    "familiar-reconcile": hosts.Operation(run=familiar_reconcile, deadline=8 * CHILD_SECONDS,
                                          mutation=False, payload=_FAMILIAR,
                                          required=_FAMILIAR_REQUIRED, hosts=("titan",),
                                          modes=hosts.BOTH, scratch=True,
                                          pilot_hosts=tuple(hosts.HOSTS)),
    "familiar-restore": hosts.Operation(
        run=familiar_restore, deadline=14 * CHILD_SECONDS, mutation=True,
        payload={**_FAMILIAR, "expect": _expected},
        required=_FAMILIAR_REQUIRED | {"expect"}, hosts=("titan",), modes=hosts.BOTH,
        scratch=True, pilot_hosts=tuple(hosts.HOSTS)),
    "dependency-restore": hosts.Operation(
        run=dependency_restore, deadline=hosts.SYNC_SECONDS + hosts.INSTALL_SECONDS
        + 4 * CHILD_SECONDS, mutation=True, payload=_DEPENDENCIES,
        required=frozenset(_DEPENDENCIES), modes=hosts.BOTH, scratch=True),
    "service-run": hosts.Operation(run=service_run, deadline=_SERVICE_DEADLINE, mutation=True,
                                   payload=_RECORD, required=frozenset(_RECORD)),
    "service-check": hosts.Operation(run=service_check, deadline=_SERVICE_DEADLINE,
                                     mutation=False, payload=_RECORD,
                                     required=frozenset(_RECORD)),
}
