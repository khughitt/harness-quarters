"""Reviewed cutover inputs on one host: the designated manifest, its members and eligibility.

`inputs-check` is a read-only host operation. The reviewed inputs are a protected generation
staged under the cutover root (0700 directories, 0600 records):

    inputs/designated.json       {"schema": 1, "generation": "<name>"}
    inputs/<name>/manifest.json  the generation's manifest (below)

The manifest is schema 1 with exactly these keys:

- `generation`: its own name.
- `pins`: `relay_version`, `relay_commit`, `familiar_pre` and `familiar_feature_tip`, which
  must equal this tool's approved pins, plus `familiar_theme` (familiar-theme's SSH pin),
  `claude_version` and `codex_version` (the reviewed evidence versions), compared with each
  host's inventory by the controller.
- `helpers`: `members` and `package_sha256` exactly as the inventory records them, including
  `hq:.githooks/harness-state-clean`, the clean filter whose `CLAUDE_JSON_KEYS` own the picks.
- `hosts`: per host, `toolchain` (the inventory's npm, node, git and python3 records) and
  `absence_reason` (an explained absence of familiar desktop surfaces, or null).
- `targets`: for each of `claude`, `claude-work`, `codex` and `codex-work`, the members
  `before` (the reviewed native before-image), `after` (the reviewed after-image) and
  `artifact` (the reviewed installer artifact). A member is `{"path", "sha256"}` plus, for
  `before` and `after`, a `provenance`:
  - `{"type": "commit", "commit": "<40 hex>", "path": "<repository path>"}`: the bytes are
    that path's blob at that immutable hq commit (checked on Titan through git);
  - `{"type": "digest-record", "record": "expected-images.sha256" | "live-before.sha256"}`:
    the digest is listed in that retained preparation record.

Member paths are plain paths below the cutover root's `inputs/`, `prep/` or `images/`, or
`claude-work.after.json`; they are read without following symlinks and must match their
digests. The tool checks paths, digests, pins and provenance; it never creates approval,
reads task notes or reports, or adopts current bytes by recomputing a digest.

Eligibility compares each current target with its reviewed before-image as parsed JSON. For
the Claude targets the filter's pick keys are excluded and their current values, or absence,
are recorded; any other difference, hooks and statusLine included, is `input-review-required`
and names the original cutover plan's Task 6 image review. Codex targets compare whole.
Blockers are `<code>: <message>` strings; messages name keys and paths, never values."""
import hashlib
import json
import os
import re
import runpy
import stat
from pathlib import Path

from . import hosts, inventory, quiesce, state
from .state import Stop

TARGETS = {"claude": "d/hq/claude/settings.json",
           "claude-work": "d/hq/local/claude/settings.work.json",
           "codex": "d/hq/codex/hooks.json", "codex-work": "d/hq/codex/work/hooks.json"}
CLAUDE_TARGETS = ("claude", "claude-work")
FILTER = ".githooks/harness-state-clean"
FILTER_MEMBER = "hq:" + FILTER
DESIGNATED = "inputs/designated.json"
GENERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
RECORDS = ("expected-images.sha256", "live-before.sha256")
RECORD_LINE = re.compile(r"([0-9a-f]{64}) [ *].+")
COMMIT = re.compile(r"[0-9a-f]{40}")
REPOSITORY_PATH = re.compile(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*")
ROLES = ("before", "after", "artifact")
PROVEN = ("before", "after")
MEMBER_ROOTS = ("inputs", "prep", "images", "claude-work.after.json")
PINS = {"relay_version": "0.1.1", "relay_commit": "4ceec5d2ad22b136b37ee360e7a4ed00949f28d9",
        "familiar_pre": "00f4899ae523d613d21f44bfc2c456aac67f8e5f",
        "familiar_feature_tip": "a16f4daa59b04e32f1010764d6f94401ca4eed8b"}
OBSERVED_PINS = ("familiar_theme", "claude_version", "codex_version")
MANIFEST_KEYS = {"schema", "generation", "pins", "helpers", "hosts", "targets"}
REVIEW = "input-review-required"
PROCEDURE = ("regenerate the before/after images, guard snapshots and installer plans and "
             "artifacts on copies by the original cutover plan's Task 6 procedure "
             "(docs/plans/2026-10-19-relay-cutover.md, \"Task 6: Prepare the reviewed "
             "settings images\"), obtain their review, stage a new reviewed input generation "
             "and manifest on both hosts and rerun prepare")
RESTAGE = "restage the reviewed bytes; never recompute a digest to fit current bytes"


class Blocked(Stop):
    """One named blocker: `code: message`."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _is_sha(value):
    return isinstance(value, str) and state.SHA256.fullmatch(value) is not None


def relevant(host):
    """The targets a host's harnesses read: all four on Titan, the Claude two on Europa."""
    return tuple(TARGETS) if hosts.HOSTS[host]["codex"] else CLAUDE_TARGETS


def _decode(data, label, code):
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=state._unique,
                           parse_constant=state._constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Blocked(code, f"{label} is not valid JSON") from None
    if not isinstance(value, dict):
        raise Blocked(code, f"{label} is not a JSON object")
    return value


# --- the manifest ------------------------------------------------------------------------


def _check_pins(pins):
    if not isinstance(pins, dict) or set(pins) != set(PINS) | set(OBSERVED_PINS):
        raise Blocked("input-manifest", "pins must name exactly " + ", ".join(
            sorted(set(PINS) | set(OBSERVED_PINS))))
    for name, value in PINS.items():
        if pins[name] != value:
            raise Blocked("input-manifest", f"pin {name} is not the approved {value}")
    if not isinstance(pins["familiar_theme"], str) or not COMMIT.fullmatch(pins["familiar_theme"]):
        raise Blocked("input-manifest", "pin familiar_theme is not a full commit")
    for name in ("claude_version", "codex_version"):
        if not isinstance(pins[name], str) or not pins[name].strip():
            raise Blocked("input-manifest", f"pin {name} is empty")


def _check_shape(manifest, generation):
    if set(manifest) != MANIFEST_KEYS:
        raise Blocked("input-manifest", "the manifest must hold exactly " + ", ".join(
            sorted(MANIFEST_KEYS)))
    if manifest["generation"] != generation:
        raise Blocked("input-manifest", "the manifest names another generation")
    _check_pins(manifest["pins"])
    helpers = manifest["helpers"]
    if (not isinstance(helpers, dict) or set(helpers) != {"members", "package_sha256"}
            or not isinstance(helpers["members"], dict) or not _is_sha(helpers["package_sha256"])
            or not all(isinstance(name, str) and _is_sha(digest)
                       for name, digest in helpers["members"].items())
            or not _is_sha(helpers["members"].get(FILTER_MEMBER))):
        raise Blocked("input-manifest", "helpers must give a digest for every member, "
                      f"{FILTER_MEMBER} included, and the package digest")
    if not isinstance(manifest["hosts"], dict) or set(manifest["hosts"]) != set(hosts.HOSTS):
        raise Blocked("input-manifest", "hosts must name exactly titan and europa")
    for host, spec in manifest["hosts"].items():
        reason = spec.get("absence_reason") if isinstance(spec, dict) else None
        if (not isinstance(spec, dict) or set(spec) != {"toolchain", "absence_reason"}
                or not isinstance(spec["toolchain"], dict)
                or set(spec["toolchain"]) != set(inventory.VERSIONS)
                or not (reason is None or hosts._text_field(500)(reason))):
            raise Blocked("input-manifest", f"hosts.{host} must give the npm, node, git and "
                          "python3 records and an absence reason or null")
    targets = manifest["targets"]
    if not isinstance(targets, dict) or set(targets) != set(TARGETS):
        raise Blocked("input-manifest", "targets must name exactly " + ", ".join(TARGETS))
    for target_id, members in targets.items():
        if not isinstance(members, dict) or set(members) != set(ROLES):
            raise Blocked("input-manifest", f"{target_id} must give its before, after and "
                          "artifact members")
        for role, member in members.items():
            allowed = {"path", "sha256", "provenance"} if role in PROVEN else {"path", "sha256"}
            if (not isinstance(member, dict) or not {"path", "sha256"} <= set(member)
                    or set(member) - allowed or not _is_sha(member["sha256"])):
                raise Blocked("input-manifest", f"{target_id} {role} must give a path and a "
                              "SHA-256 digest")


def load_manifest(root):
    """The designated manifest, its root-relative path and its digest."""
    root = Path(root)
    try:
        pointer = state.load_record(root / DESIGNATED)
    except Stop as stop:
        raise Blocked("input-manifest", f"no designated reviewed input generation ({stop})")
    generation = pointer.get("generation")
    if set(pointer) != {"schema", "generation"} or not isinstance(generation, str) \
            or not GENERATION.fullmatch(generation):
        raise Blocked("input-manifest", f"{DESIGNATED} must name one generation")
    relative = f"inputs/{generation}/manifest.json"
    try:
        state._check_dir(root / "inputs" / generation)
        data = state._read(root / relative)  # the digest is of exactly the bytes parsed
    except Stop as stop:
        raise Blocked("input-manifest", f"generation {generation}: {stop}")
    manifest = _decode(data, relative, "input-manifest")
    if not state._is_one(manifest.get("schema")):
        raise Blocked("input-manifest", f"{relative} is not a schema 1 manifest")
    _check_shape(manifest, generation)
    return manifest, relative, _sha256(data)


# --- members and their provenance --------------------------------------------------------


def _parts(value):
    if not isinstance(value, str) or not value or value.startswith("/"):
        return None
    parts = value.split("/")
    if (any(part in ("", ".", "..") for part in parts) or parts[0] not in MEMBER_ROOTS
            or (parts[0] == "claude-work.after.json") != (len(parts) == 1)):
        return None
    return parts


def _read_plain(root, parts, label, code):
    """A member's bytes, reached from root without following any symlink."""
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            for part in parts[:-1]:
                inner = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=fd)
                os.close(fd)
                fd = inner
            member = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        finally:
            os.close(fd)
    except FileNotFoundError:
        raise Blocked(code, f"{label} is missing") from None
    except OSError:
        raise Blocked(code, f"{label} is not a plain path (a symlink or not a directory)") \
            from None
    with os.fdopen(member, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise Blocked(code, f"{label} is not this user's regular file, closed to writes "
                          "by others")
        return stream.read()


def _member(root, target_id, role, member):
    label = f"{target_id} {role} ({member['path']})"
    parts = _parts(member["path"])
    if parts is None:
        raise Blocked("input-member", f"{target_id} {role}: its path is not a plain path under "
                      "the cutover root's inputs, prep or images")
    data = _read_plain(root, parts, label, "input-member")
    if _sha256(data) != member["sha256"]:
        raise Blocked("input-member", f"{label} does not match its recorded digest; {RESTAGE}")
    value = _decode(data, label, "input-member")
    if role == "artifact" and (not state._is_one(value.get("schema"))
                               or not isinstance(value.get("changes"), list)):
        raise Blocked("input-member", f"{label} is not a relay installer artifact")
    return data


def _review(target_id, role, reason):
    return Blocked(REVIEW, f"{target_id} {role}: {reason}; its review provenance cannot be "
                   f"verified, so {PROCEDURE}")


def _provenance(context, target_id, role, member, data, commits):
    proof = member.get("provenance")
    kind = proof.get("type") if isinstance(proof, dict) else None
    if kind == "commit":
        if (set(proof) != {"type", "commit", "path"} or not isinstance(proof["commit"], str)
                or not COMMIT.fullmatch(proof["commit"]) or not isinstance(proof["path"], str)
                or not REPOSITORY_PATH.fullmatch(proof["path"])
                or ".." in proof["path"].split("/")):
            raise _review(target_id, role, "its commit provenance names no immutable commit "
                          "and repository path")
        if not commits:
            return
        env = {**hosts._child_env(context), "GIT_TERMINAL_PROMPT": "0"}
        result = hosts._run_child(
            context, f"provenance-{target_id}-{role}",
            [hosts.TOOLS["git"], "--no-optional-locks", "-C", context["hq"], "cat-file", "blob",
             f"{proof['commit']}:{proof['path']}"], env=env, timeout=60)
        if result.returncode != 0 or _sha256(result.stdout) != _sha256(data):
            raise _review(target_id, role, f"its bytes are not {proof['path']} at commit "
                          f"{proof['commit']}")
    elif kind == "digest-record":
        if set(proof) != {"type", "record"} or proof["record"] not in RECORDS:
            raise _review(target_id, role, "its digest record is not a retained preparation "
                          "record")
        text = _read_plain(Path(context["root"]), [proof["record"]], proof["record"],
                           REVIEW).decode("utf-8", "replace")
        listed = {line[:64] for line in text.splitlines() if RECORD_LINE.fullmatch(line)}
        if _sha256(data) not in listed:
            raise _review(target_id, role, f"its digest is not listed in {proof['record']}")
    else:
        raise _review(target_id, role, "it has no commit or digest-record provenance")


# --- the pick keys and eligibility -------------------------------------------------------


def claude_keys(hq, expected):
    """CLAUDE_JSON_KEYS from the manifest-verified clean filter, loaded as live-picks does."""
    path = Path(hq) / FILTER
    label = f"the clean filter {FILTER}"
    data = _read_plain(Path(hq), FILTER.split("/"), label, "input-manifest")
    if _sha256(data) != expected:
        raise Blocked("input-manifest", f"{label} differs from the manifest's helper digest; "
                      "deliver and stage the reviewed filter")
    namespace = runpy.run_path(str(path))
    if _sha256(_read_plain(Path(hq), FILTER.split("/"), label, "input-manifest")) != expected:
        raise Blocked("input-manifest", f"{label} changed while it was loaded; retry")
    keys = namespace.get("CLAUDE_JSON_KEYS")
    if (not isinstance(keys, tuple) or not keys or len(set(keys)) != len(keys)
            or not all(isinstance(key, str) and key for key in keys)):
        raise Blocked("input-manifest", f"{label} gives no CLAUDE_JSON_KEYS tuple")
    return keys


def nonpick(value, keys):
    """A parsed settings object without the clean filter's pick keys."""
    return {key: item for key, item in value.items() if key not in keys}


def picks(value, keys):
    """The pick keys present with their values, and those absent, in the filter's order."""
    return ({key: value[key] for key in keys if key in value},
            [key for key in keys if key not in value])


def _read_target(path, target_id):
    """The live target's bytes at its resolved path, which must be a regular file."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise Blocked("target", f"{target_id}: the live target {path} cannot be read "
                      f"({hosts._brief(error)})") from None
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Blocked("target", f"{target_id}: the live target {path} is not a regular file")
        return stream.read()


def _eligible(context, target_id, keys, before, members):
    resolved = os.path.realpath(Path(context["home"]) / TARGETS[target_id])
    data = _read_target(resolved, target_id)
    current = _decode(data, f"{target_id} ({resolved})", "target")
    reviewed = _decode(before, f"{target_id} reviewed before-image", "input-member")
    owned = keys if target_id in CLAUDE_TARGETS else ()
    if nonpick(current, owned) != nonpick(reviewed, owned):
        missing = object()
        changed = sorted(key for key in set(current) | set(reviewed) if key not in owned
                         and current.get(key, missing) != reviewed.get(key, missing))
        what = ("settings other than the clean filter's pick keys differ" if owned
                else "the hooks file differs")
        raise Blocked(REVIEW, f"{target_id}: {what} from the reviewed native before-image "
                      f"({', '.join(changed)}); {PROCEDURE}")
    found, absent = picks(current, owned)
    return {"path": resolved, "sha256": _sha256(data), "picks": found, "absent": absent,
            "nonpick_sha256": state._digest(nonpick(current, owned)),
            "reviewed": {role: members[role]["sha256"] for role in ROLES}}


def inputs_check(context):
    """Read-only: this host's retained state, the designated manifest, its members and
    provenance, the manifest-verified pick keys and each relevant target's eligibility."""
    root = Path(context["root"])
    blockers = quiesce.readiness(context)
    report = {"manifest": None, "filter": None, "targets": {}, "blockers": blockers}
    try:
        manifest, relative, digest = load_manifest(root)
        keys = claude_keys(context["hq"], manifest["helpers"]["members"][FILTER_MEMBER])
    except Blocked as blocked:
        blockers.append(str(blocked))
        return report
    report["manifest"] = {"path": relative, "generation": manifest["generation"],
                          "sha256": digest, "content": manifest}
    report["filter"] = {"sha256": manifest["helpers"]["members"][FILTER_MEMBER],
                        "keys": list(keys)}
    commits = context["payload"].get("commits", False)
    for target_id in relevant(context["host"]):
        members = manifest["targets"][target_id]
        try:
            data = {role: _member(root, target_id, role, members[role]) for role in ROLES}
            for role in PROVEN:
                _provenance(context, target_id, role, members[role], data[role], commits)
            report["targets"][target_id] = _eligible(context, target_id, keys, data["before"],
                                                     members)
        except Blocked as blocked:
            blockers.append(str(blocked))
    return report


OPERATIONS = {
    "inputs-check": hosts.Operation(
        run=inputs_check, deadline=300, mutation=False,
        payload={"commits": lambda value: type(value) is bool,
                 "active": lambda value: isinstance(value, str)
                 and state.WINDOW_ID.fullmatch(value) is not None}),
}
