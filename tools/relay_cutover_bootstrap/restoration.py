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
- `familiar-reconcile` (Titan): familiar's actual Git state against the window's recorded base
  B, the approved tip, and the window's merge and restore records (`classify`):
  `merge-in-progress`, `at-base`, `merged`, `reverted` or `unexpected`. Without a merge record
  the merge M is found on HEAD's first-parent history since B, and above it the restore R.
- `familiar-restore` (Titan): classifies again and takes that state's one action, never `git
  revert`: `merge-in-progress` rebuilds the live index from the working tree's proven state, then
  `git merge --abort`; `at-base` and `reverted` take none; `merged` builds R by plumbing (B's tree
  with HEAD's `tasks` entry, `ls-tree -z` and `mktree -z`, `commit-tree -p P`), records it in
  `quiesce/<window>/familiar-restore.json` before any index or working-tree change, then moves
  HEAD to it (`read-tree -m -u P R` from a rebuilt index, `update-ref HEAD R P`). A recorded R
  that can no longer apply is recorded as abandoned. The live index is never evidence, a present
  `.git/index.lock` refuses, and the result must be HEAD at the restoration point or a
  tasks-only descendant of it, with the working tree equal to HEAD outside `tasks/`.
- `dependency-restore` (both hosts): once familiar's source here is the restoration point or a
  tasks-only descendant of it, clean outside `tasks/` (on Europa, not past the Titan HEAD the
  controller observed), a bounded wait for synchronization, replace `node_modules` with this
  window's verified pre-merge snapshot, offline, unless it already equals it; then familiar
  must check native.
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
import tempfile
import time
from pathlib import Path

from . import familiar, hosts, inputs, inventory, quiesce, state, targets
from .state import Stop

CHILD_SECONDS = 120
SERVICE_SECONDS = 600  # the longest wait for a running service to finish
SERVICE_START_SECONDS = 600  # the bound on `systemctl --user start` itself, apart from that wait
SERVICE_POLL_SECONDS = 2.0
REQUIESCED = "requiesced"
SNAPSHOT = "familiar-node_modules.pre"
RELAY = ("installer", "relay_cutover", "runtime")  # the pinned relay a rollback runs with
EXPECTED = ("merge-in-progress", "at-base", "merged", "reverted")
RESTORE_RECORD = "familiar-restore.json"  # under quiesce/<window>/: the R built here
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
    return familiar.commit(context, label, name)


def _pins(payload):
    """The approved PRE and tip, and the window's recorded base B."""
    if (payload["pre"], payload["tip"]) != (inputs.PINS["familiar_pre"],
                                           inputs.PINS["familiar_feature_tip"]):
        raise Stop("recovery must name the approved familiar PRE and feature tip; nothing was "
                   "changed")
    return payload["pre"], payload["tip"], payload["base"]


def _record_path(context):
    return (Path(context["state"]) / quiesce.QUIESCE / context["payload"]["window_id"]
            / RESTORE_RECORD)


def _host_record(context):
    """This window's durable restore record on this host: the R it built and every R it
    abandoned, or an empty record."""
    path = _record_path(context)
    if not os.path.lexists(path):
        return {"schema": 1, "window_id": context["payload"]["window_id"], "revert": None,
                "parent": None, "abandoned": []}
    record = state.load_record(path)
    if record.get("window_id") != context["payload"]["window_id"]:
        raise Stop(f"{path} names another window; inspect it; nothing was changed")
    return record


def _save_host_record(context, record):
    state._make_dirs(_record_path(context).parent)
    state.save_record(_record_path(context), record)


def _first_parents(context, base, head):
    """`rev-list --first-parent --parents base..head`, newest first: (commit, parents)."""
    result = familiar._git(context, "familiar-first-parents", "rev-list", "--first-parent",
                           "--parents", f"{base}..{head}")
    if result.returncode != 0:
        raise Stop(f"familiar's history between {base[:12]} and {head[:12]} cannot be read; "
                   "inspect it")
    return [(words[0], words[1:]) for words in
            (line.split() for line in familiar._text(result).splitlines()) if words]


def _outside(context, label, old, new):
    return familiar.outside(familiar.changes(context, label, old, new))


def classify(context):
    """familiar's actual Git state against the window's base B, the tip and the window's
    records (the payload's, else this host's own durable restore record):

    - `merge-in-progress`: HEAD = B and MERGE_HEAD = the tip;
    - `at-base`: no merge or revert in progress and HEAD a tasks-only descendant of B;
    - `merged`: HEAD a tasks-only descendant of the one merge M on HEAD's first-parent history
      since B, whose parents are exactly B and the tip and whose tree equals T0 outside
      `tasks/`;
    - `reverted`: HEAD a tasks-only descendant of the one commit R above M that changes a path
      outside `tasks/`, whose one parent is a tasks-only descendant of M, whose tree equals B's
      outside `tasks/` and whose `tasks/` changes are regular files; the walk's R governs, and
      a recorded R that differs is abandoned;
    - otherwise `unexpected`, for inspection. B itself must still pass the base rule."""
    payload = context["payload"]
    pre, tip, base = _pins(payload)
    recorded = _host_record(context)
    merge, revert = payload.get("merge"), payload.get("revert") or recorded.get("revert")
    found = {"class": "unexpected", "head": None, "base": base, "merge": merge,
             "revert": revert, "discovered": False, "reason": None, "abandoned": None}

    def unexpected(reason):
        found["reason"] = reason
        return found

    problem = familiar.base_problem(context, base)
    if problem:
        return unexpected(f"the window's base fails the base rule: {problem}")
    head = found["head"] = _ref(context, "familiar-head", "HEAD")
    if head is None:
        return unexpected("familiar has no HEAD commit")
    if _ref(context, "familiar-revert-head", "REVERT_HEAD") is not None:
        return unexpected("a revert is in progress in familiar's checkout")
    merging = _ref(context, "familiar-merge-head", "MERGE_HEAD")
    if merging is not None:
        if (head, merging, merge, revert) == (base, tip, None, None):
            found.update({"class": "merge-in-progress", "revert": None})
            return found
        return unexpected("a merge other than the attempted one is in progress")
    if familiar.tasks_only(context, base, head):
        if merge is None and revert in (None, base):
            found.update({"class": "at-base", "revert": base})
            return found
        return unexpected("familiar is at the window's base although this window recorded its "
                          "merge or restore")
    if not familiar.ancestor(context, "familiar-base-ancestor", base, head):
        return unexpected(f"HEAD {head[:12]} does not descend from the window's base "
                          f"{base[:12]}")
    walked = _first_parents(context, base, head)
    merges = [index for index, (_, parents) in enumerate(walked) if len(parents) > 1]
    if len(merges) != 1:
        return unexpected(f"HEAD's first-parent history since the window's base holds "
                          f"{len(merges)} merges, not the attempted one")
    m, parents = walked[merges[0]]
    if parents != [base, tip]:
        return unexpected("the merge above the window's base is not of that base and the "
                          "feature tip")
    if merge not in (None, m):
        return unexpected("HEAD's merge is not the one this window recorded")
    above = walked[:merges[0]]
    touching = [(commit, parents) for commit, parents in above
                if _outside(context, "familiar-walk-diff", parents[0], commit)]
    if len(touching) > 1:
        return unexpected(f"{len(touching)} commits above the merge change paths outside "
                          "tasks/; inspect them")
    try:
        with familiar.temporary_objects(context) as env:
            proof = familiar.merge_proof(context, base, env)
            stray = familiar.outside(familiar.changes(context, "familiar-merge-t0", proof["t0"],
                                                      m, env))
    except Stop as stop:
        return unexpected(str(stop))
    if stray:
        return unexpected("the merge differs from T0 outside tasks/")
    found.update({"merge": m, "discovered": merge is None})
    if not touching:
        if not familiar.tasks_only(context, m, head):
            return unexpected("HEAD is not the merge or a tasks-only descendant of it")
        found["class"] = "merged"
        if revert is not None:
            if _ref(context, "familiar-revert", revert) is None:
                return unexpected("the restore commit this window recorded is not here")
            if familiar.parents(context, revert) != [head]:
                found.update({"abandoned": revert, "revert": None})
        return found
    r, parents = touching[0]
    candidate = "the commit above the merge that changes paths outside tasks/"
    if len(parents) != 1:
        return unexpected(f"{candidate} does not have exactly one parent")
    if not familiar.tasks_only(context, m, parents[0]):
        return unexpected(f"{candidate} does not follow the merge or a tasks-only descendant "
                          "of it")
    if _outside(context, "familiar-restore-diff", base, r):
        return unexpected(f"{candidate} is not the window's base outside tasks/")
    if familiar.unfiled([entry for entry in familiar.changes(
            context, "familiar-restore-tasks", parents[0], r)
            if entry[3].startswith(familiar.TASKS)]):
        return unexpected(f"{candidate} changes a tasks/ entry that is not a regular file")
    if not familiar.tasks_only(context, r, head):
        return unexpected(f"HEAD is not {candidate} or a tasks-only descendant of it")
    found.update({"class": "reverted", "revert": r,
                  "discovered": merge is None or payload.get("revert") != r,
                  "abandoned": revert if revert not in (None, r) else None})
    return found


def familiar_reconcile(context):
    return classify(context)


def _unlocked(context):
    if familiar.index_locked(context):
        raise Stop("familiar's .git/index.lock exists: another Git command may be running; "
                   "inspect it (it is never deleted here); nothing was changed")


def _rebuild_index(context, name):
    """The live index rebuilt from tree-ish `name`, never trusted as evidence (Dropbox
    synchronizes it): `read-tree`, then `update-index -q --refresh`."""
    if familiar._git(context, "familiar-index", "read-tree", name).returncode != 0:
        raise Stop(f"familiar's index cannot be rebuilt from {name[:12]}; inspect it")
    if familiar._git(context, "familiar-refresh", "update-index", "-q",
                     "--refresh").returncode not in (0, 1):
        raise Stop("familiar's index cannot be refreshed; inspect it")


def _abort_merge(context, base, tip):
    """The attempted merge aborted after the live index is rebuilt from the working tree's
    proven state (judged outside `tasks/`): the merge's tree, or B. Returns which."""
    _unlocked(context)
    # The live index may need this tree, so it is written to the real objects: recovery is
    # not read-only.
    merged = familiar.merge_tree(context, "familiar-restore-merge-tree", base, tip)
    if not familiar.worktree_differs(context, merged, outside_tasks=True):
        _rebuild_index(context, merged)
        rebuilt = "merge"
    elif not familiar.worktree_differs(context, base, outside_tasks=True):
        _rebuild_index(context, base)
        rebuilt = "base"
    else:
        raise Stop("familiar's working tree is neither the attempted merge nor the window's base "
                   "outside tasks/; inspect it; nothing was changed")
    if familiar._git(context, "familiar-merge-abort", *familiar.MERGE_CONFIG, "merge",
                     "--abort").returncode != 0:
        raise Stop("git merge --abort failed; inspect familiar's checkout before any retry")
    if (_ref(context, "familiar-merge-head", "MERGE_HEAD") is not None
            or _ref(context, "familiar-head", "HEAD") != base):
        raise Stop("familiar did not return to the window's base after the merge abort; "
                   "inspect it")
    return rebuilt


def _restore_tree(context, base, head):
    """B's tree with its `tasks` entry replaced by HEAD's (`ls-tree -z` and `mktree -z`)."""
    def entries(label, *args):
        result = familiar._git(context, label, "ls-tree", "-z", *args)
        if result.returncode != 0:
            raise Stop("familiar's tree cannot be listed; inspect it")
        return [entry for entry in result.stdout.split(b"\0") if entry]

    kept = [entry for entry in entries("familiar-base-tree", base)
            if entry.split(b"\t", 1)[1] != b"tasks"]
    tasks = [entry for entry in entries("familiar-tasks-entry", head, "--", "tasks")
             if entry.split(b"\t", 1)[1] == b"tasks"]
    with tempfile.TemporaryFile(dir=context.get("tmp")) as stream:
        stream.write(b"".join(entry + b"\0" for entry in kept + tasks))
        stream.flush()
        stream.seek(0)
        result = familiar._git(context, "familiar-mktree", "mktree", "-z", stdin=stream)
    tree = familiar._text(result)
    if result.returncode != 0 or not familiar.COMMIT.fullmatch(tree):
        raise Stop("familiar's restore tree cannot be written; inspect it")
    return tree


def _restore_merge(context, found, base):
    """R on HEAD = P: the recorded R when HEAD is its parent, else a fresh one (B's tree with
    HEAD's `tasks` entry, `commit-tree -p HEAD`) recorded durably here before any index or
    working-tree change; then HEAD moved to it by compare-and-swap from the proven working
    tree. Returns R and the tree the live index was rebuilt from: `head` or `restore`."""
    head, payload = found["head"], context["payload"]
    record = _host_record(context)
    if found["abandoned"]:
        record["abandoned"] = sorted({*record.get("abandoned", []), found["abandoned"]})
        record.update(revert=None, parent=None)
        _save_host_record(context, record)
    wanted = _restore_tree(context, base, head)
    if found["revert"] is not None:
        r = found["revert"]
        if familiar.tree(context, r) != wanted:
            raise Stop("the restore commit this window recorded is not the base's tree with "
                       "HEAD's task records; inspect it; nothing was changed")
    else:
        message = (f"Restore familiar to {base[:12]} outside tasks/\n\nrelay cutover recovery "
                   f"of window {payload['window_id']}: undoes the merge {found['merge'][:12]} of "
                   "the feature tip and keeps familiar's task records as they stand.\n")
        result = familiar._git(context, "familiar-commit-tree", "commit-tree", wanted, "-p", head,
                               "-m", message)
        r = familiar._text(result)
        if result.returncode != 0 or not familiar.COMMIT.fullmatch(r):
            raise Stop("familiar's restore commit cannot be written; inspect it; nothing else was "
                       "changed")
        record.update(revert=r, parent=head, built_at=hosts._now())
        _save_host_record(context, record)  # durable before any index or working-tree change
    _unlocked(context)
    if not familiar.worktree_differs(context, head, outside_tasks=True):
        _rebuild_index(context, head)
        rebuilt = "head"
        if familiar._git(context, "familiar-read-tree", "read-tree", "-m", "-u", head,
                         r).returncode != 0:
            raise Stop("git read-tree -m -u of the restore failed; inspect familiar's checkout "
                       "before any retry")
    elif not familiar.worktree_differs(context, r, outside_tasks=True):
        _rebuild_index(context, r)
        rebuilt = "restore"
    else:
        raise Stop("familiar's working tree is neither HEAD nor its restore outside tasks/; "
                   "inspect it; HEAD was not moved")
    if familiar._git(context, "familiar-update-ref", "update-ref", "-m",
                     "relay cutover recovery", "HEAD", r, head).returncode != 0:
        raise Stop("git update-ref of HEAD to the restore failed; inspect familiar's checkout "
                   "before any retry")
    return r, rebuilt


def familiar_restore(context):
    """Take the one action familiar's reconciled Git state needs, after classifying it again:
    abort the attempted merge, nothing, the plumbing restore R, or nothing. On every path HEAD
    must end as the restoration point or a tasks-only descendant of it, with the working tree
    equal to HEAD outside `tasks/`, and the restoration point's tree equal to B's outside
    `tasks/`."""
    payload = context["payload"]
    _, tip, base = _pins(payload)
    targets.closed(context)
    found = classify(context)
    if found["class"] != payload["expect"]:
        raise Stop(f"familiar's Git state is {found['class']}, not the {payload['expect']} this "
                   "recovery reconciled; nothing was changed; reconcile again")
    action, rebuilt = "none", None
    if found["class"] == "merge-in-progress":
        point, action, rebuilt = base, "merge-aborted", _abort_merge(context, base, tip)
    elif found["class"] == "merged":
        (point, rebuilt), action = _restore_merge(context, found, base), "reverted"
    elif found["class"] == "at-base":
        point = base
    else:
        point = found["revert"]
        if found["abandoned"]:
            record = _host_record(context)
            record["abandoned"] = sorted({*record.get("abandoned", []), found["abandoned"]})
            _save_host_record(context, record)
    if _outside(context, "familiar-restored-diff", base, point):
        raise Stop("familiar's restoration point differs from the window's base outside tasks/; "
                   "inspect it")
    head = _ref(context, "familiar-head", "HEAD")
    if head is None or not familiar.tasks_only(context, point, head):
        raise Stop("familiar's HEAD is not its restoration point or a tasks-only descendant of "
                   "it; inspect it")
    problems = familiar.worktree_differs(context, head, outside_tasks=True)
    if problems:
        raise Stop(f"familiar's recovered working tree differs from HEAD ({problems[0]}); "
                   "inspect it")
    return {"class": found["class"], "action": action, "merge": found["merge"], "revert": point,
            "head": head, "discovered": found["discovered"], "abandoned": found["abandoned"],
            "rebuilt": rebuilt}


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


def _modules(path):
    """node_modules' tree, or None when it is absent; a symlink in its place is refused."""
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        raise Stop(f"{path} is a symlink; inspect it; nothing was restored")
    return quiesce._tree(path)


def dependency_restore(context):
    """familiar's dependencies from this window's pre-merge snapshot, offline, once this
    checkout is the restoration point or a tasks-only descendant of it, clean outside `tasks/`
    (and on Europa, not past Titan's observed HEAD)."""
    payload = context["payload"]
    pre, base, revert = payload["pre"], payload["base"], payload["revert"]
    if pre != inputs.PINS["familiar_pre"]:
        raise Stop("recovery must name the approved familiar PRE; nothing was restored")
    targets.closed(context)
    snapshot, wanted = _snapshot(context)
    waited, head = familiar.synchronized(context, revert, familiar.titan_head(context),
                                         "nothing was restored here")
    targets.closed(context)  # the wait can be long: a harness opened meanwhile still refuses
    problem = familiar.base_problem(context, base)
    if problem or _outside(context, "familiar-restored-diff", base, revert):
        raise Stop("familiar's restoration point here is not the window's base outside tasks/; "
                   "inspect it; nothing was restored")
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
    return {"revert": revert, "head": head, "waited_seconds": waited, "replaced": replaced,
            "tree": wanted}


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
                              env=hosts._child_env(context), timeout=SERVICE_START_SECONDS)
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
_FAMILIAR = {**_WINDOW, "pre": quiesce._commit, "tip": quiesce._commit, "base": quiesce._commit,
             "merge": quiesce._commit, "revert": quiesce._commit}
_FAMILIAR_REQUIRED = frozenset({"window_id", "pre", "tip", "base"})
_DEPENDENCIES = {**_WINDOW, "pre": quiesce._commit, "base": quiesce._commit,
                 "revert": quiesce._commit}
_SOURCE_DEADLINE = familiar.PROOF_CHILDREN * CHILD_SECONDS
_SERVICE_DEADLINE = SERVICE_START_SECONDS + SERVICE_SECONDS + 4 * CHILD_SECONDS

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
    "familiar-reconcile": hosts.Operation(run=familiar_reconcile,
                                          deadline=3 * _SOURCE_DEADLINE + 8 * CHILD_SECONDS,
                                          mutation=False, payload=_FAMILIAR,
                                          required=_FAMILIAR_REQUIRED, hosts=("titan",),
                                          modes=hosts.BOTH, scratch=True,
                                          pilot_hosts=tuple(hosts.HOSTS)),
    "familiar-restore": hosts.Operation(
        run=familiar_restore, deadline=6 * _SOURCE_DEADLINE + 14 * CHILD_SECONDS, mutation=True,
        payload={**_FAMILIAR, "expect": _expected},
        required=_FAMILIAR_REQUIRED | {"expect"}, hosts=("titan",), modes=hosts.BOTH,
        scratch=True, pilot_hosts=tuple(hosts.HOSTS)),
    "dependency-restore": hosts.Operation(
        run=dependency_restore, deadline=hosts.SYNC_SECONDS + 3 * _SOURCE_DEADLINE
        + hosts.INSTALL_SECONDS + 4 * CHILD_SECONDS, mutation=True,
        payload={**_DEPENDENCIES, "titan_head": quiesce._commit},
        required=frozenset(_DEPENDENCIES), modes=hosts.BOTH, scratch=True),
    "service-run": hosts.Operation(run=service_run, deadline=_SERVICE_DEADLINE, mutation=True,
                                   payload=_RECORD, required=frozenset(_RECORD)),
    "service-check": hosts.Operation(run=service_check, deadline=_SERVICE_DEADLINE,
                                     mutation=False, payload=_RECORD,
                                     required=frozenset(_RECORD)),
}
