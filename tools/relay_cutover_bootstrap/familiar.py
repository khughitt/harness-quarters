"""familiar's source and dependencies on one cutover host: the single merge of the immutable
feature tip on Titan, then each host's own dependency install once that merge reached it.

These are fixed host operations run by `hosts.execute`; `window.py` orders them after the six
dry runs and the familiar mark:

- `familiar-merge` (Titan only): with every harness closed and familiar at PRE with a clean
  tree (`relay-cutover familiar-source`), merges the approved feature tip by its commit, never a
  branch name, with `git merge --no-ff --no-edit`. The result must be a clean tree whose commit
  has exactly PRE and the tip as parents.
- `familiar-install` (both hosts): waits a bounded time for the merge to synchronize into this
  host's checkout, proved by `familiar-source --head MERGE`. Every harness must be closed both
  before that wait and after it, right before the install. Only then does it run
  `/usr/bin/npm ci --allow-git=root` in the checkout, with the prepared install PATH (`/usr/bin`
  first, so npm's env-node shebang finds the system node) and every prepared cache prefix pinned
  explicitly: `npm_config_cache` to npm's prepared cache, each inherited cache variable to its
  prepared value, and none left that preparation did not validate. Each prefix is revalidated by
  the inventory's overlap rule first. It proves the relay dependency with `familiar-check
  --expect relay` and the lock's pinned commit.
- `familiar-verify` (both hosts): the same source and dependency proof, read-only, for the
  run's final verification.

Git keeps the host's own configuration, so familiar-theme keeps its SSH pin and credentials.

In a pilot all three run on the clone in its owned scratch root (`pilot.resolve`), each host
merging its own clone (no synchronization joins scratch roots), and the existing familiar checks
read that clone through their explicit `--root`; live, they read the fixed main checkout."""
import json
import re
import time
from pathlib import Path

from . import hosts, inputs, inventory, quiesce, targets
from .state import Stop

CHILD_SECONDS = 120
SYNC_BUDGET_SECONDS = hosts.SYNC_SECONDS  # the longest wait for the merge to reach this host
SYNC_POLL_SECONDS = 2.0
RELAY = "node_modules/relay"
COMMIT = re.compile(r"[0-9a-f]{40}")


def root_args(context):
    """The explicit checkout relay-cutover's familiar checks read: a pilot's scratch clone;
    live, none, so they read the fixed main checkout."""
    return ["--root", context["familiar"]] if context.get("scratch") is not None else []


def _text(result):
    return result.stdout.decode("utf-8", "replace").strip()


def _source(context, head, label):
    """Whether familiar's checkout is at head with a clean tree (relay-cutover's own check)."""
    return targets._helper(context, label, "familiar-source", "--head", head,
                           *root_args(context)).returncode == 0


def _git(context, label, *args):
    env = {**hosts._child_env(context), "GIT_TERMINAL_PROMPT": "0", "GIT_MERGE_AUTOEDIT": "no"}
    return hosts._run_child(context, label, [hosts.TOOLS["git"], "-C", context["familiar"], *args],
                            env=env, timeout=CHILD_SECONDS)


def dependencies(context):
    """familiar's relay dependency: relay-cutover's relay check, then the pinned version and the
    lock's resolved commit."""
    if targets._helper(context, "familiar-check", "familiar-check", "--expect", "relay",
                       *root_args(context)).returncode != 0:
        raise Stop("relay-cutover familiar-check --expect relay failed; see the private log")
    root = Path(context["familiar"])
    try:
        version = json.loads((root / RELAY / "package.json").read_bytes()).get("version")
        resolved = json.loads((root / "package-lock.json").read_bytes())["packages"][RELAY][
            "resolved"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise Stop("familiar's relay dependency or its lock entry cannot be read") from None
    commit = resolved.rsplit("#", 1)[1] if isinstance(resolved, str) and "#" in resolved else None
    if version != inputs.PINS["relay_version"] or commit != inputs.PINS["relay_commit"]:
        raise Stop(f"familiar's relay dependency is not relay {inputs.PINS['relay_version']} at "
                   "the approved commit")
    return {"version": version, "commit": commit}


def familiar_merge(context):
    """Merge the approved feature tip once, on Titan, from PRE with every harness closed."""
    pre, tip = context["payload"]["pre"], context["payload"]["tip"]
    if (pre, tip) != (inputs.PINS["familiar_pre"], inputs.PINS["familiar_feature_tip"]):
        raise Stop("the merge must name the approved familiar PRE and feature tip; nothing was "
                   "merged")
    targets.closed(context)
    if not _source(context, pre, "familiar-source-pre"):
        raise Stop("familiar is not at PRE with a clean tree; nothing was merged")
    kind = _git(context, "familiar-tip", "cat-file", "-t", tip)
    if kind.returncode != 0 or _text(kind) != "commit":
        raise Stop("the approved feature tip is not a commit in familiar's checkout; nothing was "
                   "merged")
    if _git(context, "familiar-merge", "merge", "--no-ff", "--no-edit", tip).returncode != 0:
        raise Stop("git merge of the feature tip failed; inspect familiar's checkout, then "
                   "recover")
    head = _text(_git(context, "familiar-head", "rev-parse", "HEAD"))
    parents = _text(_git(context, "familiar-parents", "rev-list", "--parents", "-n", "1",
                         head)).split() if COMMIT.fullmatch(head) else []
    if parents != [head, pre, tip]:
        raise Stop("the merge commit's parents are not PRE and the feature tip; inspect "
                   "familiar's checkout, then recover")
    if not _source(context, head, "familiar-source-merge"):
        raise Stop("the merged familiar tree is not clean; inspect it, then recover")
    return {"merge": head, "parents": [pre, tip]}


def _install_path(value):
    _, rejected = hosts._child_path(value)
    if rejected or value.split(":")[:len(hosts.SYSTEM_PATH)] != list(hosts.SYSTEM_PATH):
        raise Stop("the prepared install PATH must start with /usr/bin:/bin and hold only "
                   "absolute entries; nothing was installed")
    return value


def _caches(context, caches):
    """The prepared cache prefixes, each revalidated, as the install's pinned environment."""
    if "npm" not in caches:
        raise Stop("the prepared caches name no npm cache; prepare again")
    for key, value in caches.items():
        problem = inventory.cache_problem(context["home"], key, value)
        if problem:
            raise Stop(f"{problem}; nothing was installed")
    pinned = {key: caches[key] for key in inventory.CACHE_KEYS if key in caches}
    return {**pinned, "npm_config_cache": caches["npm"]}


def _synchronized(context, merge):
    """Wait, within the sync budget, for familiar's checkout here to be the merge, clean."""
    started = time.monotonic()
    while not _source(context, merge, "familiar-source-sync"):
        if time.monotonic() + SYNC_POLL_SECONDS > started + SYNC_BUDGET_SECONDS:
            raise Stop(f"familiar's source did not reach the merge {merge[:12]} on this host "
                       f"within {SYNC_BUDGET_SECONDS:g} s; it may still be synchronizing; "
                       "nothing was installed here")
        time.sleep(SYNC_POLL_SECONDS)
    return round(time.monotonic() - started, 3)


def familiar_install(context):
    """This host's familiar dependencies, installed only once the merge has reached it."""
    payload = context["payload"]
    targets.closed(context)
    path = _install_path(payload["path"])
    pinned = _caches(context, payload["caches"])
    waited = _synchronized(context, payload["merge"])
    targets.closed(context)  # the wait can be long: a harness opened meanwhile still refuses
    env = hosts.claude_hold_env(hosts._child_env(context))
    for key in inventory.CACHE_KEYS:
        env.pop(key, None)
    env.update(PATH=path, **pinned)
    result = hosts._run_child(context, "npm-ci", [hosts.TOOLS["npm"], "ci", "--allow-git=root"],
                              env=env, timeout=hosts.INSTALL_SECONDS, cwd=context["familiar"])
    if result.returncode != 0:
        raise Stop(f"npm ci exited {result.returncode} after familiar reached the merge; see the "
                   "private log, then recover")
    return {"merge": payload["merge"], "waited_seconds": waited, "path": path,
            "cache": {"npm": pinned["npm_config_cache"], **pinned}, "relay": dependencies(context),
            "tree": quiesce._tree(Path(context["familiar"]) / "node_modules")}


def familiar_verify(context):
    """Read-only: familiar's checkout is the merge with a clean tree and the pinned relay."""
    merge = context["payload"]["merge"]
    if not _source(context, merge, "familiar-source-verify"):
        raise Stop("familiar's source is not the merge with a clean tree on this host")
    return {"merge": merge, "relay": dependencies(context)}


_WINDOW = {"window_id": quiesce._window_id}
_MERGE = {**_WINDOW, "merge": quiesce._commit}
def _prefixes(value):
    return (isinstance(value, dict) and set(value) <= {"npm", *inventory.CACHE_KEYS}
            and all(hosts._text_field(4096)(prefix) for prefix in value.values()))


_INSTALL = {**_MERGE, "caches": _prefixes, "path": hosts._text_field(4096)}

OPERATIONS = {
    "familiar-merge": hosts.Operation(
        run=familiar_merge, deadline=7 * CHILD_SECONDS + 60, mutation=True,
        payload={**_WINDOW, "pre": quiesce._commit, "tip": quiesce._commit},
        required=frozenset({"window_id", "pre", "tip"}), hosts=("titan",), modes=hosts.BOTH,
        scratch=True, pilot_hosts=tuple(hosts.HOSTS)),
    "familiar-install": hosts.Operation(
        run=familiar_install, deadline=hosts.SYNC_SECONDS + hosts.INSTALL_SECONDS
        + 3 * CHILD_SECONDS + 60, mutation=True, payload=_INSTALL, required=frozenset(_INSTALL),
        modes=hosts.BOTH, scratch=True),
    "familiar-verify": hosts.Operation(run=familiar_verify, deadline=3 * CHILD_SECONDS + 60,
                                       mutation=False, payload=_MERGE,
                                       required=frozenset(_MERGE), modes=hosts.BOTH,
                                       scratch=True),
}
