"""Settings targets on one cutover host: the six dry runs before familiar's merge, Titan's single
apply, and the check of applied and synchronized bytes.

These are fixed host operations run by `hosts.execute`; `window.py` orders them. Each dry run
keeps its records on its host under `dry/<window-id>/<target-id>/` in the cutover root (0700
directories, 0600 files):

- `frozen.json`: the live target's exact bytes when the dry run froze it;
- `settings.json` for Claude, or `hooks.json` for Codex, whose installer takes only that
  basename: the copy the installer plans for and applies to. A Claude copy first has its native
  guard retired by the existing helper, which leaves its `.before-guard` and `.after-guard`
  images beside it;
- `plan.json` and `artifact.json`: the installer's plan and its dry apply's schema 1 artifact;
- `result.json`: the verdict with every digest and identity the window seals.

`target-dry` (both hosts) accepts only when the copy's bytes after the dry apply equal the
planned `changes[].after` for exactly that copy, encoded as UTF-8 and never reserialized, and
the output parsed equals the reviewed after-image apart from the clean filter's pick keys,
whose values and absence equal the frozen input. A Codex output equals its reviewed image
whole. The applied bytes become the window's expected bytes, so the installer, never this tool,
chooses pick position, indentation, escaping and the final newline. A non-pick difference is
`input-review-required` and names the original image review; nothing here updates a reviewed
baseline. Installer artifacts retained from the original preparation never drive an apply or a
rollback: only those written in this window do.

`target-apply` (Titan only) writes one shared target once. It requires the window's ledger to
hold the target's durable original and artifact path, every harness closed, the frozen bytes
still in place and the installer, evidence, helper, runtime and subscribers unchanged since the
dry run. It then retires a Claude target's guard into the window's `live/`, requires the live
plan's own after bytes to equal the sealed dry output, applies, and checks the applied bytes,
the artifact and hooks and statusLine. `target-verify` (both hosts) compares targets with
expected digests, waiting a bounded time for synchronization, and with `verify` also runs the
existing hooks and statusLine check and the exact evidence and installer identity. With `picks`
(finish's fresh check, after sessions resumed) a Claude target whose parsed content differs from
this window's sealed dry output only in the clean filter's pick keys passes too; a Codex target
still needs its exact bytes, and nothing here rewrites a target or a rollback original.

Parsed JSON compares canonically, by `json.dumps(value, sort_keys=True, ensure_ascii=False)`,
so `true`, `1` and `1.0` differ, unlike Python's `==`. Messages name keys and paths, never
values; children run through `hosts._run_child` and their output stays in the private log."""
import hashlib
import json
import os
import stat
import time
from pathlib import Path

from . import hosts, inputs, inventory, quiesce, state
from .state import Stop

HARNESS = {"claude": "claude-code", "claude-work": "claude-code", "codex": "codex",
           "codex-work": "codex"}
COPY = {"claude-code": "settings.json", "codex": "hooks.json"}
NODE = "/usr/bin/node"  # written into every installed hook command: always the system node
INSTALLER = "relay/bin/relay"
RELAY_CUTOVER = "tools/relay-cutover"
RUNTIME = ".local/share/relay/v{version}/node_modules/relay/bin/relay.js"
SUBSCRIBERS = ".config/relay/subscribers.json"
EVIDENCE = "docs/runbooks/relay-guard-evidence-{harness}.json"
DRY = "dry"
IDENTITIES = ("installer", "relay_cutover", "runtime", "subscribers", "evidence")
SEALED = ("path", "copy", "frozen", "guarded", "plan", "artifact", "expected", "reviewed",
          "identities")
CHILD_SECONDS = 120
SYNC_BUDGET_SECONDS = hosts.SYNC_SECONDS  # the longest wait for another host's synced bytes
SYNC_POLL_SECONDS = 2.0


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    """A parsed JSON value's type-exact identity: `true`, `1` and `1.0` differ."""
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False)
    return _sha256(text.encode("utf-8", "surrogatepass"))


def differing(first, second):
    """Top-level keys whose presence or canonical value differs between two objects."""
    return sorted(key for key in set(first) | set(second)
                  if key not in first or key not in second
                  or canonical(first[key]) != canonical(second[key]))


def _parse(data, label):
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=state._unique,
                           parse_constant=state._constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Stop(f"{label} is not valid JSON") from None
    if not isinstance(value, dict):
        raise Stop(f"{label} is not a JSON object")
    return value


def _live_only(context):
    if context["mode"] != "live":
        raise Stop(f"{context['mode']} mode cannot dry-run, apply or verify this host's settings "
                   "targets; these operations are live only")


def _relevant(context, target_id):
    if target_id not in inputs.relevant(context["host"]):
        raise Stop(f"{target_id} is not read by {context['host']}'s harnesses")


def closed(context):
    """Refuse while any Claude or Codex process of this user runs here; none is exempt."""
    live = quiesce._harness_processes(context)
    if live:
        raise Stop("Claude or Codex is running on this host (pids "
                   f"{', '.join(str(entry['pid']) for entry in live)}); close every session, "
                   "with no process exempt; nothing was written")


def _read(path):
    """A file's bytes at a path that is not a symlink, or None when it is absent."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Stop(f"{path} is not a regular file")
        return stream.read()


def _write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    state._sync(path.parent)


def _env(context):
    return hosts.claude_hold_env(hosts._child_env(context))


def _helper(context, label, *args):
    """One existing relay-cutover command, run from this host's main checkout."""
    return hosts._run_child(context, label, [hosts.TOOLS["python3"], "-B",
                                             Path(context["hq"]) / RELAY_CUTOVER, *args],
                            env=_env(context), timeout=CHILD_SECONDS)


def _install(context, label, harness, target, *extra):
    """The pinned installer with the cutover's flags: retire familiar in the same install."""
    home = Path(context["home"])
    argv = [os.path.realpath(Path(context["hq"]) / INSTALLER), "install", "--harness", harness,
            "--subscribers", home / SUBSCRIBERS, "--target", target, "--retire", "familiar",
            "--evidence", home / "d/ops" / EVIDENCE.format(harness=harness), "--node", NODE,
            *extra]
    return hosts._run_child(context, label, argv, env=_env(context), timeout=CHILD_SECONDS)


# --- reviewed inputs and identities ------------------------------------------------------------


def _reviewed(context, target_id):
    """The designated manifest prepare recorded, with the target's reviewed images and keys."""
    root = Path(context["root"])
    manifest, _, digest = inputs.load_manifest(root)
    if digest != context["payload"]["manifest_sha256"]:
        raise Stop("input-manifest: the designated manifest changed since prepare; nothing was "
                   "written; prepare again")
    members = manifest["targets"][target_id]
    images = {role: inputs._member(root, target_id, role, members[role])
              for role in ("before", "after")}
    keys = ()
    if target_id in inputs.CLAUDE_TARGETS:
        keys = inputs.claude_keys(context["hq"],
                                  manifest["helpers"]["members"][inputs.FILTER_MEMBER])
    return {"manifest": manifest, "keys": keys, **images,
            "after_path": root / members["after"]["path"],
            "digests": {role: members[role]["sha256"] for role in ("before", "after")}}


def identities(context, manifest, harness):
    """This host's installer, helper and evidence, which must be the reviewed bytes, and its
    relay runtime and subscribers, which a later apply must find unchanged."""
    home, hq = Path(context["home"]), Path(context["hq"])
    evidence = EVIDENCE.format(harness=harness)
    found = {"installer": inventory._file_sha256(hq / INSTALLER),
             "relay_cutover": inventory._file_sha256(hq / RELAY_CUTOVER),
             "runtime": inventory._file_sha256(
                 home / RUNTIME.format(version=inputs.PINS["relay_version"])),
             "subscribers": inventory._file_sha256(home / SUBSCRIBERS),
             "evidence": inventory._file_sha256(home / "d/ops" / evidence)}
    members = manifest["helpers"]["members"]
    for name, member, what in (
            ("installer", f"hq:{INSTALLER}", f"~/d/hq/{INSTALLER}"),
            ("relay_cutover", f"hq:{RELAY_CUTOVER}", f"~/d/hq/{RELAY_CUTOVER}"),
            ("evidence", f"ops:{evidence}", f"the {harness} evidence ~/d/ops/{evidence}")):
        if found[name] is None or found[name] != members.get(member):
            raise Stop(f"{what} is not the reviewed manifest's bytes; nothing was written"
                       + ("; refresh and review the evidence first" if name == "evidence"
                          else "; deliver matching helpers first"))
    for name in ("runtime", "subscribers"):
        if found[name] is None:
            raise Stop(f"the relay {name} is missing on this host; nothing was written")
    return found


def _live(context, target_id):
    resolved = os.path.realpath(Path(context["home"]) / inputs.TARGETS[target_id])
    return resolved, inputs._read_target(resolved, target_id)


def _eligible(target_id, data, reviewed):
    """The frozen bytes parsed: non-pick content must equal the reviewed native before-image."""
    current = _parse(data, f"{target_id} live target")
    keys = reviewed["keys"]
    changed = differing(inputs.nonpick(current, keys),
                        inputs.nonpick(_parse(reviewed["before"], f"{target_id} before-image"),
                                       keys))
    if changed:
        what = "settings other than the clean filter's pick keys" if keys else "the hooks file"
        raise Stop(f"{inputs.REVIEW}: {target_id}: {what} differ from the reviewed native "
                   f"before-image ({', '.join(changed)}); {inputs.PROCEDURE}")
    return current


# --- the installer's plan, apply and output --------------------------------------------------


def _planned(result, target, source, label):
    """The plan's after-image for exactly this target, as UTF-8 bytes, never reserialized."""
    if result.returncode != 0:
        raise Stop(f"{label}: the installer refused the plan (exit {result.returncode}); see "
                   "the private log; nothing was written")
    plan = _parse(result.stdout, f"{label} plan")
    changes = plan.get("changes")
    if not state._is_one(plan.get("schema")) or not isinstance(changes, list):
        raise Stop(f"{label}: the installer's plan is not a schema 1 plan")
    mine = [change for change in changes if isinstance(change, dict)
            and change.get("path") == str(target)]
    if len(changes) != 1 or len(mine) != 1:
        raise Stop(f"{label}: the installer's plan must change exactly {target}, once")
    before, after = mine[0].get("before"), mine[0].get("after")
    if not isinstance(before, str) or not isinstance(after, str):
        raise Stop(f"{label}: the installer's plan gives no before and after text")
    try:
        if before.encode("utf-8") != source:
            raise Stop(f"{label}: the installer's plan does not start from the frozen bytes")
        return after, after.encode("utf-8")
    except UnicodeEncodeError:
        raise Stop(f"{label}: the installer's plan is not UTF-8 text") from None


def _applied(context, label, harness, target, artifact, source, text, planned):
    """Apply with this window's own artifact; the target must then hold the planned bytes."""
    result = _install(context, f"{label}-apply", harness, target, "--apply", "--artifact",
                      artifact)
    if result.returncode != 0:
        raise Stop(f"{label}: the installer's apply failed (exit {result.returncode}); see the "
                   "private log")
    applied = _read(target)
    if applied != planned:
        raise Stop(f"{label}: the applied bytes are not the installer's planned after-image")
    recorded = _parse(_read(artifact) or b"", f"{label} artifact")
    changes = recorded.get("changes")
    if (not state._is_one(recorded.get("schema")) or not isinstance(changes, list)
            or len(changes) != 1 or not isinstance(changes[0], dict)
            or (changes[0].get("path"), changes[0].get("before"), changes[0].get("after"))
            != (str(target), source.decode("utf-8"), text)):
        raise Stop(f"{label}: the installer's artifact does not record exactly this change")
    return applied


def _accept(target_id, applied, frozen, reviewed):
    """The output against the reviewed after-image, and its picks against the frozen input."""
    value = _parse(applied, f"{target_id} installer output")
    keys = reviewed["keys"]
    changed = differing(inputs.nonpick(value, keys),
                        inputs.nonpick(_parse(reviewed["after"], f"{target_id} after-image"),
                                       keys))
    if changed:
        raise Stop(f"{inputs.REVIEW}: {target_id}: the installer's output differs from the "
                   f"reviewed after-image ({', '.join(changed)}); {inputs.PROCEDURE}")
    found, absent = inputs.picks(value, keys)
    kept, missing = inputs.picks(frozen, keys)
    if absent != missing or canonical(found) != canonical(kept):
        changed = sorted(set(differing(found, kept)) | (set(absent) ^ set(missing)))
        raise Stop(f"{target_id}: the installer's output changed the clean filter's pick keys "
                   f"({', '.join(changed)}); picks must stay as frozen")


def _verify(context, target_id, target, expected):
    result = _helper(context, f"{target_id}-verify", "verify", "--target", target, "--expect",
                     expected)
    if result.returncode != 0:
        raise Stop(f"{target_id}: relay-cutover verify finds hooks or statusLine differ from "
                   "the reviewed after-image; see the private log")


# --- the operations ----------------------------------------------------------------------------


def _dry_directory(context, target_id):
    base = Path(context["root"]) / DRY / context["payload"]["window_id"]
    state._make_dirs(base)
    state._check_dir(base)
    directory = base / target_id
    try:
        os.mkdir(directory, 0o700)
    except FileExistsError:
        raise Stop(f"{target_id} was already dry-run in window "
                   f"{context['payload']['window_id']}; a window dry-runs each target once") \
            from None
    state._sync(base)
    return directory


def target_dry(context):
    """Freeze one target, dry-run the pinned installer on a private copy, return its verdict."""
    _live_only(context)
    target_id = context["payload"]["target_id"]
    _relevant(context, target_id)
    harness = HARNESS[target_id]
    reviewed = _reviewed(context, target_id)
    found = identities(context, reviewed["manifest"], harness)
    resolved, frozen = _live(context, target_id)
    frozen_value = _eligible(target_id, frozen, reviewed)
    directory = _dry_directory(context, target_id)
    _write_new(directory / "frozen.json", frozen)
    copy = directory / COPY[harness]
    _write_new(copy, frozen)
    copy = Path(os.path.realpath(copy))
    guarded = None
    if harness == "claude-code":
        if _helper(context, f"{target_id}-dry-guard", "retire-native-guard", "--target", copy,
                   "--backup", directory).returncode != 0:
            raise Stop(f"{target_id}: retire-native-guard refused the dry copy; see the private "
                       "log")
        guarded = _read(copy)
    source = guarded if guarded is not None else frozen
    plan = _install(context, f"{target_id}-dry-plan", harness, copy)
    if plan.returncode == 0:
        _write_new(directory / "plan.json", plan.stdout)
    text, planned = _planned(plan, copy, source, f"{target_id} dry run")
    artifact = directory / "artifact.json"
    applied = _applied(context, f"{target_id}-dry", harness, copy, artifact, source, text,
                       planned)
    _accept(target_id, applied, frozen_value, reviewed)
    result = {"target_id": target_id, "path": resolved, "directory": str(directory),
              "copy": str(copy),
              "frozen": {"path": str(directory / "frozen.json"), "sha256": _sha256(frozen)},
              "guarded": _sha256(guarded) if guarded is not None else None,
              "plan": {"path": str(directory / "plan.json"), "sha256": _sha256(plan.stdout)},
              "artifact": {"path": str(artifact), "sha256": _sha256(_read(artifact))},
              "expected": {"path": str(copy), "sha256": _sha256(applied)},
              "reviewed": reviewed["digests"], "identities": found}
    state.save_record(directory / "result.json", {"schema": 1, **result})
    return result


def _registered(context, target_id, resolved, artifact):
    window_id = context["payload"]["window_id"]
    directory = Path(context["root"]) / "windows" / window_id
    try:
        entries = state.read_ledger(state.load_record(directory / "window.json"))
    except Stop as stop:
        raise Stop(f"{target_id}: window {window_id}'s ledger cannot be read ({stop}); nothing "
                   "was written") from None
    found = [entry for entry in entries if entry["target_id"] == target_id]
    if not found or (found[0]["target"], found[0]["artifact"]) != (resolved, str(artifact)):
        raise Stop(f"{target_id} is not registered in window {window_id} with its resolved path, "
                   "durable original and artifact; nothing was written")
    return found[0]


def target_apply(context):
    """Write one shared target once on Titan, after its registration, to the sealed bytes."""
    _live_only(context)
    payload = context["payload"]
    target_id = payload["target_id"]
    harness = HARNESS[target_id]
    resolved = os.path.realpath(Path(context["home"]) / inputs.TARGETS[target_id])
    live = Path(context["root"]) / "windows" / payload["window_id"] / "live"
    artifact = live / f"{target_id}.json"
    entry = _registered(context, target_id, resolved, artifact)
    closed(context)
    frozen = payload["frozen_sha256"]
    _, data = _live(context, target_id)
    if _sha256(_read(Path(entry["original"])) or b"") != frozen or _sha256(data) != frozen:
        raise Stop(f"{target_id} changed after the freeze: its registered original or current "
                   "bytes are not the frozen bytes; nothing was written")
    reviewed = _reviewed(context, target_id)
    found = identities(context, reviewed["manifest"], harness)
    if found != payload["identities"]:
        changed = sorted(name for name in IDENTITIES if found[name] != payload["identities"][name])
        raise Stop(f"{target_id}: {', '.join(changed)} changed since the dry run; nothing was "
                   "written")
    guarded = None
    if harness == "claude-code":
        if _helper(context, f"{target_id}-guard", "retire-native-guard", "--target", resolved,
                   "--backup", live).returncode != 0:
            raise Stop(f"{target_id}: retire-native-guard refused the live target; see the "
                       "private log")
        guarded = _read(resolved)
    source = guarded if guarded is not None else data
    plan = _install(context, f"{target_id}-plan", harness, resolved)
    if plan.returncode == 0:
        _write_new(live / f"{target_id}.plan.json", plan.stdout)
    text, planned = _planned(plan, resolved, source, f"{target_id} live plan")
    if _sha256(planned) != payload["expected_sha256"]:
        raise Stop(f"{target_id}: the live plan's after bytes differ from the sealed dry output; "
                   "nothing more was written"
                   + ("; the guard images let recover undo the guard" if guarded else ""))
    applied = _applied(context, target_id, harness, resolved, artifact, source, text, planned)
    _verify(context, target_id, resolved, reviewed["after_path"])
    return {"target_id": target_id, "path": resolved, "sha256": _sha256(applied),
            "guard": guarded is not None,
            "plan": {"path": str(live / f"{target_id}.plan.json"),
                     "sha256": _sha256(plan.stdout)},
            "artifact": {"path": str(artifact), "sha256": _sha256(_read(artifact))}}


def _pick_only(context, target_id, path, expected):
    """Whether a Claude target differs from this window's sealed dry output, kept on this host,
    only in the clean filter's pick keys."""
    if HARNESS[target_id] != "claude-code":
        return False
    sealed = (Path(context["root"]) / DRY / context["payload"]["window_id"] / target_id
              / COPY["claude-code"])
    data = _read(sealed)
    if data is None or _sha256(data) != expected:
        raise Stop(f"{target_id}: this window's sealed dry output on this host is missing or "
                   "changed; inspect it")
    current = _read(path)
    if current is None:
        return False
    keys = _reviewed(context, target_id)["keys"]
    return canonical(inputs.nonpick(_parse(current, f"{target_id} live target"), keys)) == \
        canonical(inputs.nonpick(_parse(data, f"{target_id} sealed output"), keys))


def target_verify(context):
    """Each named target's digest against its expectation, waiting a bounded time for
    synchronization; with `verify`, also hooks, statusLine and the exact evidence; with
    `picks`, a Claude target's pick-only difference from its sealed output passes."""
    _live_only(context)
    payload = context["payload"]
    wanted = payload["targets"]
    for target_id in wanted:
        _relevant(context, target_id)
    home = Path(context["home"])
    paths = {target_id: os.path.realpath(home / inputs.TARGETS[target_id]) for target_id in wanted}
    started = time.monotonic()
    while True:
        current = {}
        for target_id, path in paths.items():
            data = _read(path)
            current[target_id] = _sha256(data) if data is not None else None
        matched = all(current[target_id] == wanted[target_id] for target_id in wanted)
        if (matched or not payload["wait"]
                or time.monotonic() + SYNC_POLL_SECONDS > started + SYNC_BUDGET_SECONDS):
            break
        time.sleep(SYNC_POLL_SECONDS)
    report = {target_id: {"path": paths[target_id], "sha256": current[target_id],
                          "matches": current[target_id] == wanted[target_id]}
              for target_id in wanted}
    picked = sorted(target_id for target_id in wanted if payload.get("picks")
                    and not report[target_id]["matches"]
                    and _pick_only(context, target_id, paths[target_id], wanted[target_id]))
    accepted = all(entry["matches"] or target_id in picked for target_id, entry in report.items())
    if payload["verify"] and accepted:
        for target_id, path in paths.items():
            reviewed = _reviewed(context, target_id)
            identities(context, reviewed["manifest"], HARNESS[target_id])
            _verify(context, target_id, path, reviewed["after_path"])
    return {"targets": report, "verified": payload["verify"] and accepted, "picks": picked,
            "waited_seconds": round(time.monotonic() - started, 3)}


# --- the window's seal -------------------------------------------------------------------------


def seal(prepared, results):
    """The window's sealed expectations from the six dry verdicts, `{host: {target_id: result}}`:
    both hosts must have frozen the same bytes and dry-applied the same output for each shared
    Claude target. `effective_inputs_sha256` digests prepared, manifest, filter and every
    frozen, planned, applied and identity digest."""
    for target_id in inputs.CLAUDE_TARGETS:
        found = [results[host][target_id] for host in results if target_id in results[host]]
        if len({result["frozen"]["sha256"] for result in found}) != 1:
            raise Stop(f"sync: {target_id} was frozen with different bytes on titan and europa; "
                       "wait for synchronization and run again")
        if len({result["expected"]["sha256"] for result in found}) != 1:
            raise Stop(f"{target_id}: the installers' dry outputs differ between titan and "
                       "europa; inspect both hosts' installers, runtimes and evidence")
    sealed = {"prepared_sha256": state._digest(prepared),
              "manifest_sha256": prepared["manifest"]["sha256"], "filter": prepared["filter"],
              "hosts": {host: {target_id: {key: result[key] for key in SEALED}
                               for target_id, result in found.items()}
                        for host, found in results.items()}}
    return {"at": hosts._now(), "effective_inputs_sha256": state._digest(sealed),
            "inputs": sealed}


def _sha(value):
    return isinstance(value, str) and state.SHA256.fullmatch(value) is not None


def _target_id(value):
    return isinstance(value, str) and value in inputs.TARGETS


def _expectations(value):
    return (isinstance(value, dict) and bool(value)
            and all(_target_id(key) and _sha(digest) for key, digest in value.items()))


def _identity_map(value):
    return (isinstance(value, dict) and set(value) == set(IDENTITIES)
            and all(_sha(digest) for digest in value.values()))


def _flag(value):
    return type(value) is bool


_DRY = {"window_id": quiesce._window_id, "target_id": _target_id, "manifest_sha256": _sha}
_APPLY = {**_DRY, "frozen_sha256": _sha, "expected_sha256": _sha, "identities": _identity_map}
_VERIFY = {"window_id": quiesce._window_id, "targets": _expectations, "wait": _flag,
           "verify": _flag, "manifest_sha256": _sha}
_VERIFY_REQUIRED = frozenset(_VERIFY)

OPERATIONS = {
    "target-dry": hosts.Operation(run=target_dry, deadline=5 * CHILD_SECONDS + 60,
                                  mutation=True, payload=_DRY, required=frozenset(_DRY)),
    "target-apply": hosts.Operation(run=target_apply, deadline=5 * CHILD_SECONDS + 60,
                                    mutation=True, payload=_APPLY, required=frozenset(_APPLY),
                                    hosts=("titan",)),
    "target-verify": hosts.Operation(
        run=target_verify, deadline=hosts.SYNC_SECONDS + len(inputs.TARGETS) * CHILD_SECONDS + 60,
        mutation=False, payload={**_VERIFY, "picks": _flag}, required=_VERIFY_REQUIRED),
}
