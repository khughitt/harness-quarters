"""familiar's source and dependencies on one cutover host: the base the window merges from, the
single merge of the immutable feature tip on Titan, then each host's own dependency install
once that merge reached it.

familiar's own task tracker commits task records (`tasks/`) into the same repository from any
checkout, so no exact familiar commit is held through a window. Its runtime never reads
`tasks/`. Every proof here is Git plumbing under `GIT_NO_REPLACE_OBJECTS=1`, with
`GIT_ICASE_PATHSPECS` and `GIT_GLOB_PATHSPECS` unset and `core.hooksPath=/dev/null` on every
call, and every path rule is a byte prefix, never a pathspec:

- **Tasks-only descendant** (`tasks_only`): Y is one of X when X is an ancestor of Y and every
  commit in `X..Y` has exactly one parent and, against it, changes only raw entries whose path
  begins with `tasks/` and whose every non-zero mode is 100644 or 100755 (`rev-list`,
  `rev-list --min-parents=2`, `diff-tree -r --no-renames --raw -z`). Y equal to X qualifies. A
  shallow repository or one with `info/grafts` is refused.
- **The working tree equals T** (`worktree_differs`): a temporary `GIT_INDEX_FILE` loaded with
  `read-tree T` gives `diff --quiet T` exit 0, and under it `ls-files -z --others
  --exclude-standard` lists nothing outside `tasks/` and `node_modules/`: untracked means not
  ignored, so a path the repository's `.gitignore`, `info/exclude` or the host's
  `core.excludesFile` ignores is no evidence (ruling R69; HOME and XDG stay the host's, so Git
  finds its own configuration). Judged outside `tasks/`, `diff --name-only -z T` lists
  only `tasks/` paths: tracked changes there (a tracker write deferred because the index held
  other staged changes) are carried, never evidence. The live index is never evidence.
- **The base rule** (`eligible_base`): B, this checkout's HEAD, is a tasks-only descendant of
  PRE with a clean tree (no tracked change, no untracked path outside `tasks/` and the ignored
  `node_modules`), and `merge-tree --write-tree B tip` exits 0 with a tree equal to T0 outside
  `tasks/`. T0 is first recomputed from PRE and the tip and compared with its pin. Read-only
  `merge-tree` writes into a temporary object directory with the real objects as an alternate,
  so a check writes nothing into the synchronized repository; the `diff-tree` against T0 runs
  under the same object environment. Every `merge-tree` and `merge` carries `MERGE_CONFIG`.

These are fixed host operations run by `hosts.execute`; `window.py` orders them:

- `familiar-base` (read-only, Titan): the base rule on this checkout's HEAD; the run derives B
  with it after its final strict no-live check and again at the pre-merge gate.
- `familiar-head` (read-only, Titan): this checkout's HEAD, reread by the controller before a
  Europa HEAD found past an older Titan observation counts as a Europa commit (ruling R68).
- `familiar-sync` (read-only, Europa): waits, one child per poll, for this checkout's HEAD to be
  B; a timeout, or this HEAD ahead of or diverged from B, refuses.
- `familiar-merge` (Titan only): with every harness closed, HEAD = B and the base rule again,
  merges the approved feature tip by its commit with `git -c branch.<current>.mergeOptions=
  merge -s ort --no-ff --no-edit --no-verify --no-autostash` and the fixed options, then proves
  M: parents exactly B and the tip, tree equal to `merge-tree --write-tree B tip` and to T0
  outside `tasks/`, and a clean tree outside `tasks/`.
- `familiar-install` (both hosts): waits a bounded time for the merge to synchronize into this
  host's checkout: HEAD M or a tasks-only descendant of it, with a clean tree outside `tasks/`.
  On Europa HEAD must also equal, or be an ancestor of, the Titan HEAD the controller observed
  in the same step (`titan_head`): a familiar commit made on Europa during the window refuses.
  Every harness must be closed both before that wait and after it, right before the install.
  Only then does it run `/usr/bin/npm ci --allow-git=root` in the checkout, with the prepared
  install PATH (`/usr/bin` first, so npm's env-node shebang finds the system node) and every
  prepared cache prefix pinned explicitly: `npm_config_cache` to npm's prepared cache, each
  inherited cache variable to its prepared value, and none left that preparation did not
  validate. Each prefix is revalidated by the inventory's overlap rule first. It proves the
  relay dependency with `familiar-check --expect relay` and the lock's pinned commit.
- `familiar-verify` (both hosts): the same source proof, and the dependency proof, read-only,
  reporting the HEAD it observed. Titan's is read once; Europa's waits within the sync budget
  for Titan's observed HEAD to arrive, so a tolerated Titan task-record commit never fails it.

Git keeps the host's own configuration, so familiar-theme keeps its SSH pin and credentials.

In a pilot these run on the clone in its owned scratch root (`pilot.resolve`), each host merging
its own clone at its own base (no synchronization joins scratch roots, so no Titan HEAD is
compared), and the existing familiar checks read that clone through their explicit `--root`;
live, they read the fixed main checkout."""
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from . import hosts, inputs, inventory, quiesce, targets
from .state import Stop

CHILD_SECONDS = 120
SYNC_BUDGET_SECONDS = hosts.SYNC_SECONDS  # the longest wait for the merge to reach this host
SYNC_POLL_SECONDS = 2.0
PROOF_CHILDREN = 6  # the bound of one proof, in child timeouts, for operation deadlines
RELAY = "node_modules/relay"
COMMIT = re.compile(r"[0-9a-f]{40}")
TASKS = b"tasks/"
MODULES = b"node_modules/"
FILE_MODES = (b"100644", b"100755")
ABSENT = b"000000"
NO_HOOKS = ("-c", "core.hooksPath=/dev/null")
MERGE_CONFIG = ("-c", "merge.renames=true", "-c", "diff.renames=true",
                "-c", "merge.directoryRenames=conflict")
# Unset for every familiar Git call: pathspec magic, and anything that would point Git at
# another repository, index or object store than the ones a call names itself.
UNSET = ("GIT_ICASE_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_DIR", "GIT_WORK_TREE",
         "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
         "GIT_ALTERNATE_OBJECT_DIRECTORIES")
FREEZE = ("no familiar commit may be made on europa during the window")
# The words of a final Europa refusal: HEAD past the Titan HEAD it was given. The controller
# rereads Titan before it takes one as a Europa commit (ruling R68).
AHEAD = "is ahead of or diverged from titan's HEAD"


def root_args(context):
    """The explicit checkout relay-cutover's familiar checks read: a pilot's scratch clone;
    live, none, so they read the fixed main checkout."""
    return ["--root", context["familiar"]] if context.get("scratch") is not None else []


def _text(result):
    return result.stdout.decode("utf-8", "replace").strip()


def _shown(path):
    return path.decode("utf-8", "replace") if isinstance(path, bytes) else path


def _source(context, head, label):
    """Whether familiar's checkout is at head with a clean tree (relay-cutover's own check)."""
    return targets._helper(context, label, "familiar-source", "--head", head,
                           *root_args(context)).returncode == 0


def _git(context, label, *args, env=None, stdin=None):
    """One Git call on this host's familiar checkout, hooks disabled, replace objects ignored,
    no pathspec magic; `env` adds a call's own index or object environment."""
    environment = hosts._child_env(context)
    for key in UNSET:
        environment.pop(key, None)
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_MERGE_AUTOEDIT": "no",
                        "GIT_NO_REPLACE_OBJECTS": "1", **(env or {})})
    return hosts._run_child(context, label, [hosts.TOOLS["git"], *NO_HOOKS, "-C",
                                             context["familiar"], *args],
                            env=environment, timeout=CHILD_SECONDS, stdin=stdin)


def commit(context, label, name):
    """The commit `name` resolves to here, or None."""
    result = _git(context, label, "rev-parse", "--verify", "-q", f"{name}^{{commit}}")
    text = _text(result)
    return text if result.returncode == 0 and COMMIT.fullmatch(text) else None


def tree(context, name, env=None):
    result = _git(context, "familiar-tree", "rev-parse", "--verify", "-q", f"{name}^{{tree}}",
                  env=env)
    text = _text(result)
    if result.returncode != 0 or not COMMIT.fullmatch(text):
        raise Stop(f"familiar's tree at {name[:12]} cannot be read; inspect it")
    return text


def parents(context, name):
    """The parents of commit `name`, in order."""
    result = _git(context, "familiar-parents", "rev-list", "--parents", "-n", "1", name)
    words = _text(result).split()
    if result.returncode != 0 or not words or words[0] != name:
        raise Stop(f"familiar's history cannot be read at {name[:12]}; inspect it")
    return words[1:]


def ancestor(context, label, older, newer):
    """Whether older is newer or one of its ancestors; None when either is not a commit here."""
    result = _git(context, label, "merge-base", "--is-ancestor", older, newer)
    return {0: True, 1: False}.get(result.returncode)


def _git_path(context, name):
    result = _git(context, "familiar-git-path", "rev-parse", "--git-path", name)
    text = _text(result)
    if result.returncode != 0 or not text:
        raise Stop("familiar's Git directory cannot be read; inspect it")
    path = Path(text)
    return path if path.is_absolute() else Path(context["familiar"]) / path


def index_locked(context):
    return os.path.lexists(_git_path(context, "index.lock"))


# --- raw diffs, the predicate and working-tree equality -------------------------------------


def _raw(data):
    """`diff-tree --raw -z` entries without renames: (old mode, new mode, status, path)."""
    fields, entries, index = data.split(b"\0"), [], 0
    while index < len(fields) and fields[index]:
        meta = fields[index]
        parts = meta[1:].split(b" ") if meta.startswith(b":") else []
        if len(parts) != 5 or index + 1 >= len(fields) or not fields[index + 1]:
            raise Stop("familiar's raw diff cannot be read; inspect it")
        entries.append((parts[0], parts[1], parts[4], fields[index + 1]))
        index += 2
    return entries


def changes(context, label, old, new, env=None):
    """Every raw entry by which tree-ish new differs from old, recursively, renames as their
    delete and add."""
    result = _git(context, label, "diff-tree", "-r", "--no-renames", "--raw", "-z", old, new,
                  env=env)
    if result.returncode != 0:
        raise Stop(f"familiar's diff of {old[:12]} and {new[:12]} cannot be read; inspect it")
    return _raw(result.stdout)


def outside(entries):
    """The paths of entries that lie outside `tasks/`, by byte prefix."""
    return [path for _, _, _, path in entries if not path.startswith(TASKS)]


def unfiled(entries):
    """The paths of entries with a non-zero mode other than a regular file's."""
    return [path for old, new, _, path in entries
            if any(mode != ABSENT and mode not in FILE_MODES for mode in (old, new))]


def _grafted(context):
    """Why this history cannot prove anything: shallow, or rewritten by info/grafts."""
    result = _git(context, "familiar-shallow", "rev-parse", "--is-shallow-repository")
    if result.returncode != 0 or _text(result) not in ("true", "false"):
        raise Stop("familiar's history cannot be read; inspect it")
    if _text(result) == "true":
        return "familiar's checkout is shallow"
    if os.path.lexists(_git_path(context, "info/grafts")):
        return "familiar's checkout has info/grafts"
    return None


def walk(context, older, newer):
    """(None, commits) when newer is a tasks-only descendant of older, with the commits of
    `older..newer` newest first; else (why not, [])."""
    reason = _grafted(context)
    if reason:
        return reason, []
    if older == newer:
        return None, []
    related = ancestor(context, "familiar-ancestor", older, newer)
    if related is None:
        return f"{older[:12]} or {newer[:12]} is not a commit here", []
    if not related:
        return f"{older[:12]} is not an ancestor of {newer[:12]}", []
    merges = _git(context, "familiar-merges", "rev-list", "--min-parents=2", f"{older}..{newer}")
    listed = _git(context, "familiar-commits", "rev-list", "--parents", f"{older}..{newer}")
    if merges.returncode != 0 or listed.returncode != 0:
        raise Stop(f"familiar's history between {older[:12]} and {newer[:12]} cannot be read; "
                   "inspect it")
    if _text(merges):
        return f"a merge commit lies between {older[:12]} and {newer[:12]}", []
    commits = []
    for line in _text(listed).splitlines():
        words = line.split()
        if len(words) != 2:
            return f"commit {words[0][:12]} does not have exactly one parent", []
        entries = changes(context, "familiar-tasks-diff", words[1], words[0])
        stray, special = outside(entries), unfiled(entries)
        if stray:
            return f"commit {words[0][:12]} changes {_shown(stray[0])!r} outside tasks/", []
        if special:
            return (f"commit {words[0][:12]} changes {_shown(special[0])!r}, which is not a "
                    "regular file", [])
        commits.append(words[0])
    return None, commits


def tasks_only(context, older, newer):
    """Whether newer is older or a tasks-only descendant of it (the module's predicate)."""
    return walk(context, older, newer)[0] is None


@contextmanager
def _scratch(context):
    with tempfile.TemporaryDirectory(prefix="relay-cutover-familiar-",
                                     dir=context.get("tmp")) as directory:
        yield Path(directory)


def worktree_differs(context, name, *, outside_tasks):
    """What keeps the working tree from equalling tree-ish `name`, judged through a temporary
    index: tracked differences (outside `tasks/` only, with `outside_tasks`), then untracked
    paths Git does not ignore outside `tasks/` and `node_modules/`. Empty when it is equal."""
    with _scratch(context) as scratch:
        env = {"GIT_INDEX_FILE": str(scratch / "index")}
        if _git(context, "familiar-worktree-index", "read-tree", name, env=env).returncode != 0:
            raise Stop(f"familiar's tree {name[:12]} cannot be read into a temporary index; "
                       "inspect it")
        found = []
        if outside_tasks:
            result = _git(context, "familiar-worktree-diff", "diff", "--name-only", "-z", name,
                          env=env)
            if result.returncode != 0:
                raise Stop("familiar's working tree cannot be compared; inspect it")
            found += [f"{_shown(path)} differs" for path in result.stdout.split(b"\0")
                      if path and not path.startswith(TASKS)]
        else:
            result = _git(context, "familiar-worktree-diff", "diff", "--quiet", name, env=env)
            if result.returncode not in (0, 1):
                raise Stop("familiar's working tree cannot be compared; inspect it")
            if result.returncode == 1:
                found.append("a tracked file differs")
        others = _git(context, "familiar-worktree-others", "ls-files", "-z", "--others",
                      "--exclude-standard", env=env)
        if others.returncode != 0:
            raise Stop("familiar's untracked files cannot be listed; inspect it")
        found += [f"{_shown(path)} is untracked" for path in others.stdout.split(b"\0")
                  if path and not path.startswith(TASKS) and not path.startswith(MODULES)]
    return found


# --- T0, the merge tree and the base rule --------------------------------------------------


@contextmanager
def temporary_objects(context):
    """An object environment whose writes land in a temporary directory, reading the real
    objects as an alternate: read-only `merge-tree` writes nothing into the checkout."""
    real = _git_path(context, "objects")
    with _scratch(context) as scratch:
        objects = scratch / "objects"
        objects.mkdir()
        yield {"GIT_OBJECT_DIRECTORY": str(objects),
               "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(real)}


def merge_tree(context, label, base, tip, env=None):
    """The tree of `merge-tree --write-tree base tip` with the fixed options; any non-zero
    exit, a conflict included, refuses."""
    result = _git(context, label, *MERGE_CONFIG, "merge-tree", "--write-tree", base, tip, env=env)
    first = result.stdout.split(b"\n", 1)[0].decode("utf-8", "replace").strip()
    if result.returncode != 0 or not COMMIT.fullmatch(first):
        raise Stop(f"git merge-tree of {base[:12]} and the feature tip does not merge cleanly "
                   f"(exit {result.returncode}); see the private log")
    return first


def merge_proof(context, base, env):
    """T0 recomputed from PRE and the tip and compared with its pin, then the tree of base
    merged with the tip, which must equal T0 outside `tasks/`."""
    pins = inputs.PINS
    pre, tip, pinned = pins["familiar_pre"], pins["familiar_feature_tip"], pins[
        "familiar_merge_tree"]
    t0 = merge_tree(context, "familiar-merge-tree-pre", pre, tip, env)
    if t0 != pinned:
        raise Stop(f"the merge of the approved PRE and feature tip is tree {t0[:12]}, not the "
                   f"pinned T0 {pinned[:12]}; inspect familiar's history")
    merged = t0 if base == pre else merge_tree(context, "familiar-merge-tree-base", base, tip, env)
    stray = outside(changes(context, "familiar-t0-diff", t0, merged, env))
    if stray:
        raise Stop(f"the merge of {base[:12]} and the feature tip differs from T0 outside "
                   f"tasks/ ({_shown(stray[0])!r})")
    return {"t0": t0, "tree": merged}


def base_problem(context, base):
    """Why commit `base` cannot be a window's base, by its history alone, or None: a tasks-only
    descendant of PRE whose merge with the tip equals T0 outside `tasks/`."""
    reason, _ = walk(context, inputs.PINS["familiar_pre"], base)
    if reason:
        return f"{base[:12]} is not a tasks-only descendant of the approved PRE: {reason}"
    try:
        with temporary_objects(context) as env:
            merge_proof(context, base, env)
    except Stop as stop:
        return str(stop)
    return None


def eligible_base(context):
    """The base rule on this checkout's HEAD, or Stop naming why it fails: the base B and its
    proof (the commits past PRE, T0 and the tree of B merged with the tip)."""
    pre = inputs.PINS["familiar_pre"]
    head = commit(context, "familiar-head", "HEAD")
    if head is None:
        raise Stop("familiar has no HEAD commit")
    reason, commits = walk(context, pre, head)
    if reason:
        raise Stop(f"familiar's HEAD {head[:12]} is not the approved PRE {pre[:12]} or a "
                   f"tasks-only descendant of it: {reason}")
    problems = worktree_differs(context, head, outside_tasks=False)
    if problems:
        raise Stop(f"familiar's working tree at {head[:12]} is not clean: {problems[0]}")
    with temporary_objects(context) as env:
        proof = merge_proof(context, head, env)
    return {"base": head, "commits": commits, **proof}


def familiar_base(context):
    """Read-only: the base rule on this checkout's HEAD (the run's B and its proof)."""
    return eligible_base(context)


def familiar_head(context):
    """Read-only: this checkout's HEAD, which the controller rereads on Titan before it takes
    Europa's HEAD past an older Titan observation for a Europa commit."""
    head = commit(context, "familiar-head", "HEAD")
    if head is None:
        raise Stop("familiar has no HEAD commit")
    return {"head": head}


def familiar_sync(context):
    """Read-only: wait, one child per poll, for this checkout's HEAD to be the window's base B.
    HEAD ahead of or diverged from B refuses at once; B not reached in time refuses."""
    base, started = context["payload"]["base"], time.monotonic()
    while True:
        result = _git(context, "familiar-sync", "rev-list", "--left-right", "--count",
                      f"{base}...HEAD")
        counts = _text(result).split() if result.returncode == 0 else []
        if len(counts) == 2 and all(count.isdigit() for count in counts):
            behind, ahead = int(counts[0]), int(counts[1])
            if ahead:
                head = commit(context, "familiar-head", "HEAD") or "an unreadable commit"
                raise Stop(f"familiar's HEAD {head[:12]} here is ahead of or diverged from "
                           f"titan's base {base[:12]}; {FREEZE}; nothing was changed")
            if not behind:
                return {"base": base, "waited_seconds": round(time.monotonic() - started, 3)}
        if time.monotonic() + SYNC_POLL_SECONDS > started + SYNC_BUDGET_SECONDS:
            raise Stop(f"familiar's source did not reach titan's base {base[:12]} on this host "
                       f"within {SYNC_BUDGET_SECONDS:g} s; it may still be synchronizing; "
                       "nothing was changed")
        time.sleep(SYNC_POLL_SECONDS)


# --- after the mark: source proofs ----------------------------------------------------------


def titan_head(context):
    """The Titan HEAD a live Europa proof compares with; none on Titan or in a pilot."""
    head = context["payload"].get("titan_head")
    if context["host"] == "titan" or context.get("scratch") is not None:
        return None
    if head is None:
        raise Stop("europa's familiar proof needs the titan HEAD the controller observed in "
                   "this step; nothing was checked")
    return head


def source_proof(context, expected, observed_titan):
    """(head, None, False) when this checkout proves `expected`: HEAD it or a tasks-only
    descendant of it, the working tree equal to HEAD outside `tasks/`, and beside Titan's
    observed HEAD, HEAD equal to or an ancestor of it. Else (head, why not, final), where a
    final reason (a familiar commit made here during the window) no wait can change."""
    head = commit(context, "familiar-head", "HEAD")
    if head is None:
        return None, "familiar has no HEAD commit", False
    reason, _ = walk(context, expected, head)
    if reason:
        return head, (f"HEAD {head[:12]} is not {expected[:12]} or a tasks-only descendant of "
                      f"it ({reason})"), False
    problems = worktree_differs(context, head, outside_tasks=True)
    if problems:
        return head, f"the working tree differs from HEAD outside tasks/ ({problems[0]})", False
    if observed_titan is not None and head != observed_titan:
        related = ancestor(context, "familiar-titan-head", head, observed_titan)
        if related is None:
            return head, f"titan's HEAD {observed_titan[:12]} has not reached this host", False
        if not related:
            return head, f"HEAD {head[:12]} here {AHEAD} {observed_titan[:12]}: {FREEZE}", True
    return head, None, False


def synchronized(context, expected, observed_titan, what):
    """Wait, within the sync budget, for this checkout to prove `expected` (`source_proof`);
    (seconds waited, HEAD). `what` names what nothing was done to on a refusal."""
    started = time.monotonic()
    while True:
        head, reason, final = source_proof(context, expected, observed_titan)
        if reason is None:
            return round(time.monotonic() - started, 3), head
        if final:
            raise Stop(f"familiar's source here: {reason}; {what}")
        if time.monotonic() + SYNC_POLL_SECONDS > started + SYNC_BUDGET_SECONDS:
            raise Stop(f"familiar's source did not reach {expected[:12]} on this host within "
                       f"{SYNC_BUDGET_SECONDS:g} s ({reason}); it may still be synchronizing; "
                       f"{what}")
        time.sleep(SYNC_POLL_SECONDS)


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
    pinned = resolved.rsplit("#", 1)[1] if isinstance(resolved, str) and "#" in resolved else None
    if version != inputs.PINS["relay_version"] or pinned != inputs.PINS["relay_commit"]:
        raise Stop(f"familiar's relay dependency is not relay {inputs.PINS['relay_version']} at "
                   "the approved commit")
    return {"version": version, "commit": pinned}


def familiar_merge(context):
    """Merge the approved feature tip once, on Titan, from the window's base B with every
    harness closed."""
    payload = context["payload"]
    pre, tip, base = payload["pre"], payload["tip"], payload["base"]
    if (pre, tip) != (inputs.PINS["familiar_pre"], inputs.PINS["familiar_feature_tip"]):
        raise Stop("the merge must name the approved familiar PRE and feature tip; nothing was "
                   "merged")
    targets.closed(context)
    try:
        found = eligible_base(context)
    except Stop as stop:
        raise Stop(f"{stop}; nothing was merged") from None
    if found["base"] != base:
        raise Stop(f"familiar's HEAD {found['base'][:12]} is not the window's base {base[:12]}; "
                   "nothing was merged")
    kind = _git(context, "familiar-tip", "cat-file", "-t", tip)
    if kind.returncode != 0 or _text(kind) != "commit":
        raise Stop("the approved feature tip is not a commit in familiar's checkout; nothing was "
                   "merged")
    branch = _git(context, "familiar-branch", "symbolic-ref", "--short", "-q", "HEAD")
    current = _text(branch) if branch.returncode == 0 else None
    options = ("-c", f"branch.{current}.mergeOptions=") if current else ()
    if _git(context, "familiar-merge", *MERGE_CONFIG, *options, "merge", "-s", "ort", "--no-ff",
            "--no-edit", "--no-verify", "--no-autostash", tip).returncode != 0:
        raise Stop("git merge of the feature tip failed; inspect familiar's checkout, then "
                   "recover")
    head = commit(context, "familiar-head", "HEAD")
    if head is None or parents(context, head) != [base, tip]:
        raise Stop("the merge commit's parents are not the window's base and the feature tip; "
                   "inspect familiar's checkout, then recover")
    merged = tree(context, head)
    if merged != found["tree"]:
        raise Stop("the merge commit's tree is not git merge-tree's merge of the base and the "
                   "feature tip; inspect familiar's checkout, then recover")
    with temporary_objects(context) as env:
        proof = merge_proof(context, base, env)
        stray = outside(changes(context, "familiar-merge-t0", proof["t0"], merged, env))
    if stray:
        raise Stop("the merge commit differs from T0 outside tasks/; inspect familiar's "
                   "checkout, then recover")
    problems = worktree_differs(context, head, outside_tasks=True)
    if problems:
        raise Stop(f"the merged familiar tree is not clean ({problems[0]}); inspect it, then "
                   "recover")
    return {"merge": head, "parents": [base, tip], "base": base, "tree": merged}


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


def familiar_install(context):
    """This host's familiar dependencies, installed only once the merge has reached it."""
    payload = context["payload"]
    targets.closed(context)
    path = _install_path(payload["path"])
    pinned = _caches(context, payload["caches"])
    waited, head = synchronized(context, payload["merge"], titan_head(context),
                                "nothing was installed here")
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
    return {"merge": payload["merge"], "head": head, "waited_seconds": waited, "path": path,
            "cache": {"npm": pinned["npm_config_cache"], **pinned}, "relay": dependencies(context),
            "tree": quiesce._tree(Path(context["familiar"]) / "node_modules")}


def familiar_verify(context):
    """Read-only: familiar's checkout is the merge or a tasks-only descendant of it, clean
    outside `tasks/`, with the pinned relay; the HEAD observed is reported. Beside Titan's
    observed HEAD (live Europa) the proof waits, within the sync budget, for a tolerated Titan
    task-record commit to synchronize; elsewhere it is read once."""
    merge, observed = context["payload"]["merge"], titan_head(context)
    if observed is not None:
        _, head = synchronized(context, merge, observed, "nothing was changed")
    else:
        head, reason, _ = source_proof(context, merge, None)
        if reason is not None:
            raise Stop(f"familiar's source is not the merge with a clean tree on this host: "
                       f"{reason}")
    return {"merge": merge, "head": head, "relay": dependencies(context)}


_WINDOW = {"window_id": quiesce._window_id}
_MERGE = {**_WINDOW, "merge": quiesce._commit}
_OBSERVED = {"titan_head": quiesce._commit}  # optional: required by a live Europa proof


def _prefixes(value):
    return (isinstance(value, dict) and set(value) <= {"npm", *inventory.CACHE_KEYS}
            and all(hosts._text_field(4096)(prefix) for prefix in value.values()))


_INSTALL = {**_MERGE, "caches": _prefixes, "path": hosts._text_field(4096)}
_SYNC_DEADLINE = hosts.SYNC_SECONDS + PROOF_CHILDREN * CHILD_SECONDS

OPERATIONS = {
    "familiar-base": hosts.Operation(run=familiar_base, deadline=PROOF_CHILDREN * CHILD_SECONDS,
                                     mutation=False, payload=_WINDOW,
                                     required=frozenset(_WINDOW), hosts=("titan",)),
    "familiar-head": hosts.Operation(run=familiar_head, deadline=CHILD_SECONDS + 60,
                                     mutation=False, payload=_WINDOW,
                                     required=frozenset(_WINDOW), hosts=("titan",)),
    "familiar-sync": hosts.Operation(run=familiar_sync,
                                     deadline=hosts.SYNC_SECONDS + CHILD_SECONDS + 60,
                                     mutation=False, payload={**_WINDOW, "base": quiesce._commit},
                                     required=frozenset({"window_id", "base"}),
                                     hosts=("europa",)),
    "familiar-merge": hosts.Operation(
        run=familiar_merge, deadline=2 * PROOF_CHILDREN * CHILD_SECONDS + 60, mutation=True,
        payload={**_WINDOW, "pre": quiesce._commit, "tip": quiesce._commit,
                 "base": quiesce._commit},
        required=frozenset({"window_id", "pre", "tip", "base"}), hosts=("titan",),
        modes=hosts.BOTH, scratch=True, pilot_hosts=tuple(hosts.HOSTS)),
    "familiar-install": hosts.Operation(
        run=familiar_install, deadline=_SYNC_DEADLINE + hosts.INSTALL_SECONDS
        + 3 * CHILD_SECONDS + 60, mutation=True, payload={**_INSTALL, **_OBSERVED},
        required=frozenset(_INSTALL), modes=hosts.BOTH, scratch=True),
    "familiar-verify": hosts.Operation(run=familiar_verify,
                                       deadline=_SYNC_DEADLINE + 3 * CHILD_SECONDS + 60,
                                       mutation=False, payload={**_MERGE, **_OBSERVED},
                                       required=frozenset(_MERGE), modes=hosts.BOTH,
                                       scratch=True),
}
