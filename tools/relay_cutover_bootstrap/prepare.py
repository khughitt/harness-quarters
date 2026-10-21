"""Preparation and eligibility for the cutover, on the controller.

`prepare` reads each host through `inputs-check` and `inventory`, Titan first, and stops at the
first host with blockers. It writes only `prepared.json` at the cutover root and opens no
window. The record holds the manifest's path, generation and digest, its pins and helper
digests, the pick keys of the manifest-verified clean filter, and the controller's checkout,
native session ID and helper digests. Per host it holds the resolved home, root and hq
paths; the toolchain and the install PATH (`/usr/bin:/bin:` and the validated remainder);
the cache prefixes; Claude's identity and versions (and Codex's on Titan); the desktop
inventory; the live Claude and Codex processes, which are future run blockers and never a
reason to refuse preparation; and for each target its resolved path, current digest, pick
values and absent pick keys, and the reviewed member digests. No expected after-image is
built. Per host it also holds familiar's base: its HEAD under the base rule, a tasks-only
descendant of PRE whose merge with the tip equals T0 outside `tasks/`, with its proof;
Europa's HEAD must equal or precede Titan's. `check` repeats the reads and compares them with
that record, but a base that moved while it stays eligible is not drift; it writes only
private operation records. `recheck` is the same comparison as the run's gate.

The window lifecycle that consumes the prepared record is in `window.py`."""
import os
from pathlib import Path

from . import hosts, inputs, inventory, state, window
from .state import Stop
from .window import (HOST_ORDER, NOTHING, PREPARED, SESSION, SESSION_PLACEHOLDER, Failed,
                     _call, _now, _root, prepared_sha256)


# --- observation and comparison ------------------------------------------------------------


def _observe(host, *, active, complete, titan_head=None):
    """A host's inputs-check and inventory, with every blocker prefixed by the host. Without
    `complete`, inventory is skipped once the inputs already block. `titan_head` is Titan's
    observed familiar base, which Europa's own HEAD must equal or precede."""
    payload = {"commits": host == "titan", **({"active": active} if active else {}),
               **({"titan_head": titan_head} if titan_head else {})}
    found, log = _call(host, "live", "inputs-check", payload, "inputs-check")
    manifest = found["manifest"]["content"] if found["manifest"] else None
    seen = {"inputs": found, "manifest": manifest, "inventory": None, "step": None, "log": None,
            "blockers": [f"{host}: {blocker}" for blocker in found["blockers"]]}
    if seen["blockers"]:
        seen.update(step="inputs-check", log=log)
        if not complete:
            return seen
    reason = manifest["hosts"][host]["absence_reason"] if manifest else None
    report, log = _call(host, "live", "inventory",
                        {"absence_reason": reason} if reason else {}, "inventory")
    seen["inventory"] = report
    more = [f"{host}: {blocker}" for blocker in report["blockers"]]
    more += _host_blockers(host, manifest, report)
    if more and seen["step"] is None:
        seen.update(step="inventory", log=log)
    seen["blockers"] += more
    return seen


def _differing(expected, actual):
    expected, actual = expected or {}, actual or {}
    return sorted(key for key in set(expected) | set(actual)
                  if expected.get(key) != actual.get(key))


def _helper_drift(expected, actual):
    drift, members = [], (actual or {}).get("members") or {}
    for name in sorted(set(expected["members"]) | set(members)):
        if members.get(name) != expected["members"].get(name):
            drift.append(f"{name} is missing" if members.get(name) is None
                         else f"{name} is not in the manifest"
                         if name not in expected["members"]
                         else f"{name} differs from the manifest")
    if (actual or {}).get("package_sha256") != expected["package_sha256"]:
        drift.append("the helper package differs from the manifest")
    return drift


def _claude_versions(report):
    claude = ((report or {}).get("harnesses") or {}).get("claude") or {}
    return sorted({(entry or {}).get("version") or "none"
                   for entry in (claude.get("homes") or {}).values()} or {"none"})


def _host_blockers(host, manifest, report):
    """The host's inventory against the reviewed manifest: toolchain, helpers, pins."""
    if manifest is None:
        return []
    found = []
    toolchain = report.get("toolchain") or {}
    for name, expected in sorted(manifest["hosts"][host]["toolchain"].items()):
        fields = _differing(expected, toolchain.get(name))
        if fields:
            found.append(f"{host}: toolchain: {name} differs from the reviewed manifest "
                         f"({', '.join(fields)}); prepare fresh proof, without updating host "
                         "packages")
    found += [f"{host}: helpers: {drift}; deliver matching helpers to main first"
              for drift in _helper_drift(manifest["helpers"], report.get("helpers"))]
    pins = manifest["pins"]
    if (report.get("git_auth") or {}).get("pin") != pins["familiar_theme"]:
        found.append(f"{host}: pins: familiar-theme is not pinned to the manifest's commit")
    versions = _claude_versions(report)
    if versions != [pins["claude_version"]]:
        found.append(f"{host}: version: Claude reports {', '.join(versions)}; the reviewed "
                     f"evidence is {pins['claude_version']}; align the hosts and refresh the "
                     "evidence first")
    if hosts.HOSTS[host]["codex"]:
        codex = ((report.get("harnesses") or {}).get("codex") or {}).get("version")
        if codex != pins["codex_version"]:
            found.append(f"{host}: version: Codex reports {codex or 'none'}; the reviewed "
                         f"evidence is {pins['codex_version']}")
    return found


def _titan_base(seen):
    """Titan's observed familiar base, which Europa's HEAD must equal or precede; None before
    Titan is observed or while its familiar fails the base rule (a Titan blocker already)."""
    return ((seen.get("titan") or {}).get("inputs", {}).get("familiar") or {}).get("base")


def _cross_host(seen):
    found = []
    digests = {host: (seen[host]["inputs"]["manifest"] or {}).get("sha256") for host in seen}
    if len(set(digests.values())) != 1:
        found.append("both: sync: the designated manifests differ between titan and europa; "
                     "stage the same generation on both")
    for target_id in inputs.CLAUDE_TARGETS:
        current = {(seen[host]["inputs"]["targets"].get(target_id) or {}).get("sha256")
                   for host in seen}
        if len(current) != 1:
            found.append(f"both: sync: {target_id} differs between titan and europa; wait for "
                         "synchronization and rerun")
    return found


def _controller_helpers():
    return inventory._helpers({"hq": str(window.CHECKOUT), "home": str(hosts._home())})


def _sessions(report):
    processes = (report or {}).get("processes") or {}
    return sorted(({**entry, "held": entry.get("held")}
                   for entry in processes.get("known", []) + processes.get("unknown", [])),
                  key=lambda entry: entry["pid"])


def _identity(harness):
    """A harness executable's identity: Claude's per-home versions, or Codex's one version."""
    found = {key: harness.get(key) for key in ("path", "real", "sha256")}
    if "version" in harness:  # Codex; its homes are only present or absent
        found["version"] = harness["version"]
    elif isinstance(harness.get("homes"), dict):
        found["versions"] = {name: (entry or {}).get("version")
                             for name, entry in harness["homes"].items()}
    return found


def _host_record(observed):
    report = observed["inventory"]
    home = Path(report["identity"]["home"])
    record = {
        "home": str(home), "root": str(home / hosts.ROOT), "hq": str(home / "d/hq"),
        "observed_at": report["observed_at"], "identity": report["identity"],
        "toolchain": report["toolchain"],
        "install": {"npm": report["toolchain"]["npm"]["path"],
                    "node": report["toolchain"]["node"]["path"], "path": report["path"]["child"]},
        "caches": report["caches"], "user_bus": report["user_bus"],
        "git_auth": report["git_auth"], "claude": _identity(report["harnesses"]["claude"]),
        "desktop": report["desktop"], "sessions": _sessions(report),
        "familiar": observed["inputs"]["familiar"], "targets": observed["inputs"]["targets"]}
    if "codex" in report["harnesses"]:
        record["codex"] = _identity(report["harnesses"]["codex"])
    return record


def _drift(host, prepared, observed):
    """What changed on a host since preparation, beyond pick values."""
    recorded, found = prepared["hosts"][host], []
    manifest = observed["inputs"]["manifest"]
    if manifest is None or manifest["sha256"] != prepared["manifest"]["sha256"]:
        found.append(f"{host}: input-manifest: the designated manifest changed since prepare; "
                     "prepare again")
    if observed["inputs"]["filter"] != prepared["filter"]:
        found.append(f"{host}: input-manifest: the clean filter's pick keys changed since "
                     "prepare; prepare again")
    # The run installs with the recorded install PATH, and inventory checks the cache
    # prefixes of whichever shell runs it; the toolchain's own identity must not move.
    report = observed["inventory"]
    changed = _differing(recorded["toolchain"], report.get("toolchain"))
    if changed:
        found.append(f"{host}: toolchain: {', '.join(changed)} changed since prepare; prepare "
                     "again")
    harnesses = report.get("harnesses") or {}
    for name in ("claude", "codex"):
        if name in recorded and _identity(harnesses.get(name) or {}) != recorded[name]:
            found.append(f"{host}: version: the {name} executable or its versions changed "
                         "since prepare; prepare again")
    if window.desktop_subject(report.get("desktop")) != window.desktop_subject(
            recorded["desktop"]):
        found.append(f"{host}: desktop: the familiar surfaces, their startup commands or "
                     "processes, or the niri socket changed since prepare; prepare again")
    for target_id, target in recorded["targets"].items():
        current = observed["inputs"]["targets"].get(target_id)
        if current is not None and current["path"] != target["path"]:
            found.append(f"{host}: target: {target_id} now resolves elsewhere; prepare again")
    return found


# --- preparation and eligibility -----------------------------------------------------------


def _open(root):
    """The current window, refusing unexplained root state or an unfinished window."""
    try:
        current = state.current_window(root)
    except Stop as stop:
        raise Failed("retained-state", "titan", "refused", str(stop),
                     next_command=["status"]) from None
    if current is not None and current["state"] not in state.TERMINAL:
        raise Failed("window", "titan", "blocked", f"window {current['id']} is "
                     f"{current['state']}; it must be finished, aborted or recovered first",
                     observed=f"window {current['id']} is {current['state']}",
                     next_command=["status"])
    return current


def prepare(controller_session: str) -> dict:
    """Record eligibility and the current inputs in prepared.json; open no window."""
    valid = isinstance(controller_session, str) and SESSION.fullmatch(controller_session)
    rerun = ["prepare", "--controller-session",
             controller_session if valid else SESSION_PLACEHOLDER]
    try:
        if not valid:
            raise Failed("arguments", "titan", "refused", "the controller session must be its "
                         "native session ID, a lowercase UUID")
        root = _root()
        _open(root)
        controller, seen = _controller_helpers(), {}
        for host in HOST_ORDER:
            observed = _observe(host, active=None, complete=False,
                                titan_head=_titan_base(seen))
            if observed["blockers"]:
                raise Failed(observed["step"], host, "blocked",
                             f"{len(observed['blockers'])} blocker(s); none was changed",
                             log=observed["log"], blockers=observed["blockers"])
            seen[host] = observed
        manifest = seen["titan"]["manifest"]
        crossing = _cross_host(seen) + [
            f"controller: helpers: {drift} in the controller checkout {window.CHECKOUT}"
            for drift in _helper_drift(manifest["helpers"], controller)]
        if crossing:
            raise Failed("eligibility", "titan", "blocked",
                         f"{len(crossing)} blocker(s); none was changed", blockers=crossing)
    except Failed as failed:
        failed.observed = failed.observed or NOTHING
        failed.next_command = failed.next_command or rerun
        raise
    titan = seen["titan"]["inputs"]
    prepared = {
        "schema": 1, "prepared_at": _now(),
        "controller": {"session_id": controller_session, "checkout": str(window.CHECKOUT),
                       "helpers": controller,
                       "codex": _identity(seen["titan"]["inventory"]["harnesses"]["codex"])},
        "manifest": {key: titan["manifest"][key] for key in ("path", "generation", "sha256")},
        "pins": manifest["pins"], "filter": titan["filter"], "helpers": manifest["helpers"],
        "hosts": {host: _host_record(seen[host]) for host in HOST_ORDER}}
    state.save_record(root / PREPARED, prepared)
    return prepared


def load_prepared() -> dict:
    path = _root() / PREPARED
    rerun = ["prepare", "--controller-session", SESSION_PLACEHOLDER]
    if not os.path.lexists(path):
        raise Failed("prepared-record", "titan", "missing", "nothing is prepared yet",
                     observed=NOTHING, next_command=rerun)
    try:
        return state.load_record(path)
    except Stop as stop:
        raise Failed("prepared-record", "titan", "refused", str(stop), observed=NOTHING,
                     next_command=rerun) from None


def check(prepared: dict, *, opened: dict | None = None) -> dict:
    """Read-only: every host's eligibility and drift since preparation. Live sessions are
    listed as run blockers, not eligibility blockers. `opened` is the run's own window, still
    `prepared`, which is not a blocker for its own gate."""
    root, blockers = _root(), []
    try:
        current = state.current_window(root)
    except Stop:
        current = None  # Titan's inputs-check names the unexplained state
    own = (opened is not None and current is not None and current["id"] == opened["id"]
           and current["state"] == "prepared")
    open_window = current is not None and current["state"] not in state.TERMINAL
    if open_window and not own:
        blockers.append(f"titan: window: window {current['id']} is {current['state']}")
    # Only an open window is named: beside a closed one (a recovered revert, a completed
    # cutover) the hosts read familiar, which no later window merges from unless its HEAD
    # passes the base rule.
    active = current["id"] if open_window else None
    seen = {}
    for host in HOST_ORDER:
        seen[host] = _observe(host, active=active, complete=True, titan_head=_titan_base(seen))
    for host in HOST_ORDER:
        blockers += seen[host]["blockers"] + _drift(host, prepared, seen[host])
    blockers += _cross_host(seen)
    blockers += [f"controller: helpers: {drift} in the controller checkout {window.CHECKOUT}"
                 for drift in _helper_drift(prepared["helpers"], _controller_helpers())]
    return {"eligible": not blockers, "blockers": blockers,
            "prepared_sha256": prepared_sha256(prepared),
            "logs": {host: seen[host]["log"] for host in HOST_ORDER},
            "sessions": {host: _sessions(seen[host]["inventory"]) for host in HOST_ORDER},
            "familiar": {host: seen[host]["inputs"]["familiar"] for host in HOST_ORDER},
            "targets": {host: seen[host]["inputs"]["targets"] for host in HOST_ORDER}}


def blocking_host(result):
    """The host named by a check's first blocker; Titan for shared or controller blockers."""
    first = result["blockers"][0].split(": ", 1)[0]
    return first if first in hosts.HOSTS else "titan"


def recheck(prepared: dict, *, opened: dict | None = None) -> dict:
    """The run's eligibility gate: `check`, refusing on any blocker; pick drift passes. Its
    inventory completes and collects the held Claude version and doctor probes on both hosts
    and in both homes before it reads their process tables."""
    result = check(prepared, opened=opened)
    if not result["eligible"]:
        host = blocking_host(result)
        raise Failed("eligibility", host, "blocked",
                     f"{len(result['blockers'])} blocker(s) since preparation",
                     log=result["logs"].get(host), blockers=result["blockers"],
                     observed=NOTHING,
                     next_command=["prepare", "--controller-session",
                                   prepared["controller"]["session_id"]])
    return result
