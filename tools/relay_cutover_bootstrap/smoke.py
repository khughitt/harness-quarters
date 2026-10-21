"""Safe resume after the verified migration, the controller's fresh row, and smoke receipts.

From the verified migration until finish, Claude and Codex run only through the held commands
printed here (`commands`), each a concrete argv quoted for Zsh: the controller's Codex resume
(`resume_argv`: `env DISABLE_UPDATES=1 CODEX_HOME=<resolved home> <validated executable>
--no-daemon resume <captured session>`), the Codex work home's own launch for its hook review,
held Claude launches for both homes on both hosts and the dedicated smoke sessions with the
runbook's flags (Claude `--permission-mode manual`; Codex `--no-daemon --sandbox
workspace-write --ask-for-approval on-request`). `handoff` prints them with the paused timers,
the Claude model and effort freeze, the familiar commit freeze on Europa and the held-launch
rule, naming `cl` and `clw`.

Host side, the fixed read-only operation `smoke-observe` (both hosts, either mode) reads relay's
own registry through `relay list --json` (each row's harness, session, scope, state, cwd,
update time, process and liveness), the session IDs in familiar's intent, this user's Claude
and Codex processes with only their hold key and the home each runs in (`session_home`: the id
resolved from that process's own CLAUDE_CONFIG_DIR or CODEX_HOME alone, never the value), the
installed executables' identity and, for a scratch repo, its two markers, its commit count and
whether Git has an identity there.

Controller side, every observation is kept as private evidence under the window directory
(`smokes/observations/<operation-id>.json`) with its digest and order in the window record
(`observe`). The first observation proves the controller's own row (`check_controller`): its
native session's root Codex row on Titan, alive, held by the prepared executable in the
personal home and updated since the verified migration. An observation that finds Claude or
Codex moved since preparation is a hold breach: new smokes stop, the window needs full recovery
(`recovery-required`) and timers stay paused until it completes.

A receipt (schema 1) names the window, its preparation, host, harness, home, native session,
root row, PID, scratch cwd, the installed and evidence versions, its matrix, each required
case's verdict with its observations and the human's own trust (and, in a full smoke,
permission) verdicts. `check_receipt` binds every case to this window's recorded observations
of that very session: their content, digests, order, the prepared identities and the home
its process was observed in; never a file name. `record_smoke` stores it with the consumed
`smoke-attestation` decision, the actual session ask and human reply or the operator's
terminal answer, that attested its human verdicts; `validate_smokes` is finish's gate on all
six. Keys this module adds to the window record: `smokes` {observations, controller,
receipts}."""
import hashlib
import json
import os
import shlex
from datetime import datetime
from pathlib import Path

from . import hosts, inventory, quiesce, state, targets
from .state import Stop

OBSERVE = "smoke-observe"
KIND, ACTION, PREFIX = "smoke-attestation", "record-smoke", "smoke"
RECEIPT_PLACEHOLDER = "<receipt-file>"
CHILD_SECONDS = 60
INTENT = ".local/state/familiar/intent.json"
MARKERS = {"allowed_marker": "allowed.marker", "denied_marker": "denied.marker"}
REFUSAL = "relay-guard: refusing"
IDLE_MS = 60_000
CODEX_HOMES = {"personal": ".codex", "work": ".codex-work"}
CLAUDE_HOMES = ("personal", "work")
# Each harness's home key, and the home directories it may name under HOME. Claude's personal
# home is the key unset: setting it, even to ~/.claude, moves ~/.claude.json (ruling R59).
HOME_KEYS = {"claude": "CLAUDE_CONFIG_DIR", "codex": "CODEX_HOME"}
HOME_DIRS = {"claude": {"work": ".claude-work"}, "codex": CODEX_HOMES}
CLAUDE_SMOKE = ("--permission-mode", "manual")
CODEX_SMOKE = ("--no-daemon", "--sandbox", "workspace-write", "--ask-for-approval", "on-request")
HARNESS = {"claude-code": "claude", "codex": "codex"}  # relay's harness → the process family
NAMES = {"claude-code": "Claude", "codex": "Codex"}
# Every smoke the cutover requires, (host, harness, home), and its matrix.
REQUIRED = {("titan", "claude-code", "personal"): "full", ("titan", "codex", "personal"): "full",
            ("titan", "claude-code", "work"): "short", ("titan", "codex", "work"): "short",
            ("europa", "claude-code", "personal"): "short",
            ("europa", "claude-code", "work"): "short"}
FULL = ("start-idle", "allow-working", "attribution-denial", "needs-approval", "turn-done",
        "idle-needs-input", "projection-recovery", "normal-exit", "abrupt-death")
SHORT = ("start-idle", "attribution-denial", "normal-exit")
HUMAN = {"full": ("permission", "trust"), "short": ("trust",)}
RECEIPT_KEYS = {"schema", "window_id", "prepared_sha256", "host", "harness", "home",
                "session_id", "row_id", "pid", "cwd", "versions", "matrix", "cases", "human"}
CASE_KEYS = {"verdict", "evidence"}
EXTRA = {"attribution-denial": {"outcome", "refusal"}, "abrupt-death": {"session_id", "pid"}}
EVIDENCE = {"projection-recovery": 2, "abrupt-death": 2}
HOLD = ("until finish, launch Claude and Codex only with the held commands below; avoid cl, "
        "clw, unheld Claude or IDE clients, and update or install commands")
PICKS = ("until finish reports complete, do not change or save Claude model or effort "
         "defaults in either home on either host, including through /model or /effort")
FAMILIAR = ("until finish reports complete, make no familiar commit on europa (concurrent ref "
            "writes are a Dropbox conflict, and europa's source proofs refuse one); task-record "
            "commits on titan are tolerated now that the merge is made")
# A launch that bypasses approval, sandbox, permission or hook-trust review: any of these flags,
# or a flag with this value (`--flag value` or `--flag=value`). Ruling R49.
BYPASS_FLAGS = ("--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust",
                "--dangerously-skip-permissions", "--yolo", "--full-auto", "--approve-for-me")
BYPASS_VALUES = {"--ask-for-approval": "never", "-a": "never",
                 "--permission-mode": "bypassPermissions"}
BYPASSED = ("was launched with a bypass flag (approval, sandbox, permission or hook-trust "
            "review)")


# --- the held commands ----------------------------------------------------------------------


def _executable(identity, what):
    path = (identity or {}).get("real")
    if not isinstance(path, str) or not os.path.isabs(path):
        raise Stop(f"the prepared record has no validated {what} executable; prepare again")
    return path


def resume_argv(prepared: dict, home: str) -> list[str]:
    """The held Codex command for a Titan home: in the personal home, the controller's resume
    of its captured native session; in the work home, which has no captured session, the
    launch whose first start shows that home's own hook review. Each home's defaults apply:
    no sandbox, approval or hook-trust flag."""
    if home not in CODEX_HOMES:
        raise Stop(f"Codex runs in the personal or work home on titan, not {home!r}")
    controller = prepared["controller"]
    session = controller.get("session_id")
    if not isinstance(session, str) or not session:
        raise Stop("the prepared record has no captured controller session; prepare again")
    codex_home = os.path.realpath(os.path.join(prepared["hosts"]["titan"]["home"],
                                               CODEX_HOMES[home]))
    argv = ["env", "DISABLE_UPDATES=1", f"CODEX_HOME={codex_home}",
            _executable(controller.get("codex"), "Codex"), "--no-daemon"]
    return argv + (["resume", session] if home == "personal" else [])


def _claude_argv(prepared, host, home, smoke):
    record = prepared["hosts"][host]
    executable = _executable(record.get("claude"), f"{host} Claude")
    if home == "personal":  # the default home: CLAUDE_CONFIG_DIR would move ~/.claude.json
        argv = ["env", "-u", "CLAUDE_CONFIG_DIR", "DISABLE_UPDATES=1", executable]
    else:
        argv = ["env", "DISABLE_UPDATES=1",
                f"CLAUDE_CONFIG_DIR={os.path.join(record['home'], '.claude-work')}", executable]
    return argv + (list(CLAUDE_SMOKE) if smoke else [])


def commands(prepared: dict) -> list[tuple[str, list[str]]]:
    """Every held launch from the verified migration until finish, labelled: the controller's
    resume, the Codex work home's launch, Claude's homes on both hosts, then the smokes."""
    found = [("titan Codex personal: resume the controller", resume_argv(prepared, "personal")),
             ("titan Codex work: its own hook review", resume_argv(prepared, "work"))]
    for host in hosts.HOSTS:
        found += [(f"{host} Claude {home}", _claude_argv(prepared, host, home, False))
                  for home in CLAUDE_HOMES]
    for host in hosts.HOSTS:
        found += [(f"{host} Claude {home} smoke", _claude_argv(prepared, host, home, True))
                  for home in CLAUDE_HOMES]
    found += [(f"titan Codex {home} smoke", resume_argv(prepared, home)[:4] + list(CODEX_SMOKE))
              for home in CODEX_HOMES]
    return found


def command_lines(prepared: dict) -> list[str]:
    """The held commands as the operator copies them: a label, then one Zsh-quoted line."""
    lines = ["  commands: run each on its own host, as printed; each smoke in a fresh scratch "
             "Git repo with its own user.name and user.email, a full smoke's second session "
             "in the same repo:"]
    for label, argv in commands(prepared):
        lines += [f"    {label}", f"      {shlex.join(argv)}"]
    return lines


def _prepared(window):
    from . import recovery  # recovery imports surfaces, which imports the window lifecycle
    return recovery._prepared(window)


def paused(window: dict) -> list:
    """Hosts this window paused whose timers finish has not restored yet."""
    restored = set((window.get("finish") or {}).get("timers") or {})
    return [host for host in lifecycle._stopped(window) if host not in restored]


def timers_line(window):
    stopped = paused(window)
    restored = [host for host in lifecycle.HOST_ORDER
                if host in ((window.get("finish") or {}).get("timers") or {})]
    parts = []
    if restored:
        parts.append(f"familiar-reap.timer is restored on {' and '.join(restored)}")
    if stopped:
        parts.append(f"{'it' if restored else 'familiar-reap.timer'} stays paused on "
                     f"{' and '.join(stopped)} until finish")
    return "  timers: " + ("; ".join(parts) or "this window paused no familiar-reap.timer")


def _first(window):
    """The controller's proof: the first step after resuming, until it is recorded."""
    from .cli import DECISION_PLACEHOLDER, command_line  # the CLI imports this module
    proof = _smokes(window).get("controller")
    if proof is not None:
        return (f"  controller: {proof['row_id']} pid {proof['pid']} is proven: live on titan "
                "and updated since the verified migration")
    line = ("  first: resume the controller with its held command below, then prove its fresh "
            f"row with {command_line(['record-smoke', '--observe', 'titan'])} before any other "
            "rollout work")
    if window["state"] == "migrated-surfaces-pending":
        line += ("; an agent's session decision for "
                 f"{command_line(['restart-surfaces', '--decision-file', DECISION_PLACEHOLDER])} "
                 "needs that proof, while the operator's own terminal answer to restart-surfaces "
                 "does not")
    return line


def handoff(window: dict) -> tuple[str, ...]:
    """What every report from the verified migration until finish says: the controller's proof
    first, both hosts and homes, the paused timers, the held-launch rule, the pick freeze, the
    familiar commit freeze, and the held commands."""
    try:
        prepared = _prepared(window)
        lines = command_lines(prepared)
    except (Stop, OSError, KeyError, TypeError) as error:
        lines = [f"  commands: the window's prepared record cannot be read "
                 f"({hosts._brief(error)}); run status"]
    return (_first(window), "  hosts: titan (Claude personal and work, Codex personal and work) "
            "and europa (Claude personal and work)", timers_line(window), f"  hold: {HOLD}",
            f"  picks: {PICKS}", f"  familiar: {FAMILIAR}", *lines)


# --- host side --------------------------------------------------------------------------------


def _registry(context):
    """relay's own registry rows through `relay list --json`, reduced to what smokes compare."""
    relay = os.path.realpath(Path(context["hq"]) / targets.INSTALLER)
    result = hosts._run_child(context, "relay-list", [relay, "list", "--json"],
                              env=hosts._child_env(context), timeout=CHILD_SECONDS)
    if result.returncode != 0:
        raise Stop(f"relay list --json exited {result.returncode}; see the private log")
    try:
        value = hosts._decode(result.stdout)
    except (UnicodeDecodeError, ValueError, RecursionError):
        value = None
    if not isinstance(value, dict) or not isinstance(value.get("liveness", {}), dict):
        raise Stop("relay list --json printed no registry; see the private log")
    snapshot, liveness = value.get("snapshot"), value.get("liveness") or {}
    agents = (snapshot or {}).get("agents") if isinstance(snapshot, (dict, type(None))) else None
    if not isinstance(agents if snapshot is not None else {}, dict):
        raise Stop("relay list --json printed no registry; see the private log")
    found = {}
    for key, agent in (agents or {}).items():
        if not isinstance(agent, dict):
            raise Stop("relay list --json printed an unreadable agent row; see the private log")
        process = agent.get("process")
        found[key] = {
            "harness": agent.get("harness"), "session_id": agent.get("sessionId"),
            "scope": agent.get("scope"), "state": agent.get("state"), "cwd": agent.get("cwd"),
            "updated_at": agent.get("updatedAt"),
            "process": ({"pid": process.get("pid"), "start": process.get("start"),
                         "host": process.get("host")} if isinstance(process, dict) else None),
            "liveness": (liveness.get(key) or {}).get("status")
            if isinstance(liveness.get(key), dict) else None}
    return found


def _intent(context):
    """The session IDs familiar's intent projection holds, or absent while it is moved aside."""
    path = Path(context["home"]) / INTENT
    data = targets._read(path)
    if data is None:
        return {"present": False, "sessions": []}
    try:
        value = hosts._decode(data)
    except (UnicodeDecodeError, ValueError, RecursionError):
        value = None
    if not isinstance(value, dict):
        raise Stop(f"~/{INTENT} is not one JSON object; inspect it")
    return {"present": True, "sessions": sorted(value)}


def _identities(context):
    home = Path(context["home"])
    found = {"claude": inventory._resolve(home / ".local/bin/claude",
                                          home / ".local/share/claude/versions",
                                          inventory.CLAUDE_FAMILY)}
    if hosts.HOSTS[context["host"]]["codex"]:
        found["codex"] = inventory._resolve(home / ".local/bin/codex",
                                            home / ".codex/packages/standalone/releases",
                                            inventory.CODEX_FAMILY)
    return found


def _scratch(context, cwd):
    """A scratch repo's markers, commit count and Git identity; Git only reads it."""
    if os.path.realpath(cwd) != cwd or not os.path.isdir(cwd):
        raise Stop("the scratch repo must be an existing directory named by its resolved path")
    env, git = hosts._child_env(context), hosts.TOOLS["git"]
    counted = hosts._run_child(context, "scratch-commits",
                               [git, "-C", cwd, "rev-list", "--all", "--count"], env=env,
                               timeout=CHILD_SECONDS)
    text = counted.stdout.decode("utf-8", "replace").strip()
    identity = True
    for key in ("name", "email"):
        found = hosts._run_child(context, f"scratch-user-{key}",
                                 [git, "-C", cwd, "config", "--get", f"user.{key}"], env=env,
                                 timeout=CHILD_SECONDS)
        identity = identity and found.returncode == 0 and bool(found.stdout.strip())
    return {"cwd": cwd, **{key: os.path.lexists(os.path.join(cwd, name))
                           for key, name in MARKERS.items()},
            "commits": int(text) if counted.returncode == 0 and text.isdigit() else None,
            "identity": identity}


def bypassed(argv: list) -> bool:
    """Whether a process's argv carries a bypass flag. Computed on its host: argv never leaves
    it."""
    args = [str(arg) for arg in argv[1:]]
    for index, arg in enumerate(args):
        flag, joined, value = arg.partition("=")
        if arg in BYPASS_FLAGS or (joined and flag in BYPASS_FLAGS):
            return True
        if joined and BYPASS_VALUES.get(flag) == value:
            return True
        if arg in BYPASS_VALUES and args[index + 1:index + 2] == [BYPASS_VALUES[arg]]:
            return True
    return False


def session_home(context, harness, pid):
    """The home one Claude or Codex process runs in, from its own environment's home key alone
    (`HOME_KEYS`): unset is the personal home; a value naming one of the harness's home
    directories under HOME (resolved) is that home; any other value is "other". None when the
    process's environment cannot be read. Only this id leaves the host, never the value."""
    key = HOME_KEYS[harness]
    found = inventory._environ_key(pid, key)
    if found is None:
        return None
    if key not in found:
        return "personal"
    value = found[key]
    if not os.path.isabs(value):
        return "other"
    real = os.path.realpath(value)
    for home, directory in HOME_DIRS[harness].items():
        if real == os.path.realpath(Path(context["home"]) / directory):
            return home
    return "other"


def smoke_observe(context):
    """Read-only: this host's registry, intent, harness processes and executables, and the
    named scratch repo, for one window's smokes. Each harness process carries `bypass`, whether
    its command line bypasses review (`bypassed`), and `home`, the home it runs in
    (`session_home`); neither its argv nor its environment is sent."""
    payload = context["payload"]
    harnesses = _identities(context)
    observed_at = hosts._now()
    rows = inventory._process_rows()
    processes = inventory._processes(context, rows, harnesses)
    argv = {row["pid"]: row["argv"] for row in rows}
    return {"window_id": payload["window_id"], "host": context["host"],
            "mode": context["mode"], "operation_id": context["operation_id"],
            "nodename": hosts._nodename(), "observed_at": observed_at,
            "harnesses": {name: {key: found[key] for key in ("path", "real", "sha256",
                                                              "familiar")}
                          for name, found in harnesses.items()},
            "processes": sorted([{**entry, "known": known, "bypass": bypassed(argv[entry["pid"]]),
                                  "home": session_home(context, entry["harness"], entry["pid"])}
                                 for known, entries in ((True, processes["known"]),
                                                        (False, processes["unknown"]))
                                 for entry in entries], key=lambda entry: entry["pid"]),
            "agents": _registry(context), "intent": _intent(context),
            "scratch": _scratch(context, payload["cwd"]) if "cwd" in payload else None}


def _path(value):
    return (isinstance(value, str) and os.path.isabs(value) and 0 < len(value) <= 4096
            and value.isprintable())


OPERATIONS = {
    OBSERVE: hosts.Operation(run=smoke_observe, deadline=4 * CHILD_SECONDS + 60,
                             mutation=False, payload={"window_id": quiesce._window_id,
                                                      "cwd": _path},
                             required=frozenset({"window_id"})),
}


# --- observations and the hold --------------------------------------------------------------


def _smokes(window):
    found = json.loads(json.dumps(window.get("smokes") or {}))
    found.setdefault("observations", {})
    found.setdefault("receipts", {})
    return found


def observe(window: dict, host: str, cwd: str | None = None) -> dict:
    """One smoke-observe on host, kept as this window's private evidence before it is used:
    {window, observation, ref}, where ref is the {path, sha256} a receipt cites."""
    payload = {"window_id": window["id"], **({"cwd": cwd} if cwd is not None else {})}
    result, _ = lifecycle._call(host, window["mode"], OBSERVE, payload, OBSERVE)
    record = {"schema": 1, **result}
    path = Path(window["directory"]) / "smokes" / "observations" / f"{result['operation_id']}.json"
    if os.path.lexists(path):
        raise Stop(f"{path}: an observation is already kept under this operation ID; inspect it")
    state.save_record(path, record)
    digest = hashlib.sha256(state._read(path)).hexdigest()
    smokes = _smokes(window)
    smokes["observations"][result["operation_id"]] = {
        "seq": len(smokes["observations"]) + 1, "host": host, "cwd": cwd,
        "observed_at": result["observed_at"], "path": str(path), "sha256": digest}
    window = lifecycle._save(window, smokes=smokes)
    return {"window": window, "observation": record, "ref": {"path": str(path),
                                                              "sha256": digest}}


def drift(prepared: dict, host: str, observation: dict) -> list[str]:
    """How the observed Claude (and on Titan Codex) executable moved since preparation."""
    found, seen = [], observation.get("harnesses") or {}
    for name, label in (("claude", "Claude"), ("codex", "Codex")):
        recorded = prepared["hosts"][host].get(name)
        if recorded is None:
            continue
        now = seen.get(name) or {}
        if (now.get("real"), now.get("sha256")) != (recorded["real"], recorded["sha256"]):
            found.append(f"{label} is now {now.get('real') or 'missing'}, not the prepared "
                         f"{recorded['real']}")
    return found


def hold(window: dict, prepared: dict, host: str, observation: dict) -> None:
    """A hold breach stops new smokes and sends the window to full recovery."""
    moved = drift(prepared, host, observation)
    if not moved:
        return
    error = (f"hold breach: {'; '.join(moved)} on {host} since preparation: stop new smokes; "
             f"familiar-reap.timer stays paused on {' and '.join(paused(window)) or 'no host'}; "
             "close every Claude and Codex "
             "session on both hosts and run recover from an ordinary shell, which needs no "
             "proof for the moved version. A recovered merge ends this window: a later attempt "
             "needs newly reviewed pins and inputs and its own reviewed procedure")
    current = state.current_window(lifecycle._root())
    lifecycle._save(current, state="recovery-required", failure={
        "step": "hold", "host": host, "status": "breach", "error": error, "log": None,
        "at": lifecycle._now(), "next": ["recover"]})
    raise lifecycle.Failed("hold", host, "breach", error, observed=(
        f"window {window['id']} is recovery-required: Claude or Codex moved after the "
        "bootstrap. Do not open Claude or Codex until recover completes"),
        next_command=["recover"])


# --- the controller's own row -------------------------------------------------------------


def _ms(at):
    return int(datetime.fromisoformat(at).timestamp() * 1000)


def _fresh_since(window):
    return _ms(window["verified"]["at"])


def _controller_failed(message):
    return lifecycle.Failed(
        "controller-check", "titan", "blocked", message, observed=(
            "nothing was proven: report this as the controller's trust or startup blocker and "
            "resume it only with the held command below, not configuration edits from that "
            "session; a row proves event delivery, not the smokes"),
        next_command=["record-smoke", "--observe", "titan"])


def check_controller(window: dict, observation: dict) -> None:
    """The controller's own fresh row in a Titan observation, or Failed: its native session's
    root Codex row, alive on Titan, its process the prepared Codex executable at the row's PID
    and start time, launched with no bypass flag in the personal home its captured session
    belongs to, and updated since the verified migration."""
    prepared = _prepared(window)
    session = prepared["controller"]["session_id"]
    row_id = f"codex:{session}"
    if (observation.get("window_id"), observation.get("host"), observation.get("mode")) != (
            window["id"], "titan", window["mode"]):
        raise _controller_failed(f"the observation is not this {window['mode']} window's Titan "
                                 "observation (window, host or mode)")
    row = (observation.get("agents") or {}).get(row_id)
    if row is None:
        raise _controller_failed(f"relay's registry on titan has no row {row_id} for the "
                                 "controller's captured session")
    if row["harness"] != "codex" or row["session_id"] != session or row["scope"] != "session":
        raise _controller_failed(f"{row_id} is not the controller session's root Codex row")
    process = row["process"] or {}
    if row["liveness"] != "alive" or process.get("host") != observation["nodename"]:
        raise _controller_failed(f"{row_id} is not live on titan (liveness "
                                 f"{row['liveness']}, host {process.get('host')})")
    if type(row["updated_at"]) is not int or row["updated_at"] < _fresh_since(window):
        raise _controller_failed(f"{row_id} predates this window's verified migration: a stale "
                                 "row from an earlier attempt")
    expected = prepared["controller"]["codex"]["real"]
    held = [entry for entry in observation.get("processes") or []
            if entry["pid"] == process.get("pid") and str(entry["start_time"]) == str(
                process.get("start")) and entry["harness"] == "codex" and entry["known"]
            and entry["exe"] == expected]
    if not held:
        raise _controller_failed(f"{row_id}'s process (pid {process.get('pid')}) is not the "
                                 f"prepared Codex executable {expected} as relay recorded it")
    if any(entry.get("bypass") is not False for entry in held):
        raise _controller_failed(f"{row_id}'s process (pid {process.get('pid')}) {BYPASSED}: "
                                 "its row proves nothing about the trust review; exit it and "
                                 "resume the controller only with its printed held command")
    homes = sorted({entry.get("home") or "unknown" for entry in held})
    if homes != ["personal"]:
        raise _controller_failed(f"{row_id}'s process (pid {process.get('pid')}) runs in the "
                                 f"{' and '.join(homes)} Codex home, not the personal home its "
                                 "captured session belongs to; exit it and resume the "
                                 "controller only with its printed held command")


def _proof(window, observation, ref):
    session = _prepared(window)["controller"]["session_id"]
    row = observation["agents"][f"codex:{session}"]
    return {"row_id": f"codex:{session}", "session_id": session,
            "pid": row["process"]["pid"], "start": row["process"]["start"],
            "updated_at": row["updated_at"], "observation": ref["path"],
            "checked_at": lifecycle._now()}


def _waiting(window, proof=False):
    """Failed unless the window takes smoke steps: ready for smokes, surfaces restarted. With
    `proof` (the controller's own Titan observation) surfaces-pending is enough."""
    if window is None or window["state"] != "ready-for-smokes" and not (
            proof and window["state"] == "migrated-surfaces-pending"):
        report = lifecycle.status()
        reason = ("familiar's surfaces must restart first; until then only the controller's "
                  "proof (record-smoke --observe titan) runs" if window is not None
                  and window["state"] == "migrated-surfaces-pending"
                  else "smokes run only once the migration verified and familiar's surfaces "
                  "restarted, until finish starts")
        raise lifecycle.Failed(ACTION, "titan", "refused", (
            f"window {window['id']} is {window['state']}; {reason}" if window is not None
            else "no window is open for smokes"), observed=report["detail"],
            next_command=report["next"])


def _pending(failed, host, cwd):
    """A declined or failed observation records nothing and never passes: it stays pending."""
    if failed.step == OBSERVE:
        failed.observed = (f"nothing was recorded from {failed.host}: this observer check stays "
                           "pending until it runs, and no verdict passes without it")
        failed.next_command = ["record-smoke", "--observe", host,
                               *(["--cwd", cwd] if cwd is not None else [])]
    return failed


def observe_step(window: dict, host: str, cwd: str | None = None) -> dict:
    """record-smoke --observe: the controller's row proven first, once, then one observation of
    host, each checked against the hold. Returns {window, controller, observation, ref,
    unheld}, where `controller` is the proof this call made, if any."""
    state._current(window)
    _waiting(window, proof=host == "titan" and cwd is None)
    try:
        return _observe_step(window, host, cwd)
    except lifecycle.Failed as failed:
        raise _pending(failed, host, cwd) from None


def _observe_step(window, host, cwd):
    prepared, proof = _prepared(window), None
    if "controller" not in _smokes(window):
        seen = observe(window, "titan")
        hold(seen["window"], prepared, "titan", seen["observation"])
        check_controller(seen["window"], seen["observation"])
        proof = _proof(seen["window"], seen["observation"], seen["ref"])
        smokes = _smokes(seen["window"])
        smokes["controller"] = proof
        window = lifecycle._save(seen["window"], smokes=smokes)
    seen = observe(window, host, cwd)
    hold(seen["window"], prepared, host, seen["observation"])
    unheld = sorted(entry["pid"] for entry in seen["observation"]["processes"]
                    if entry["harness"] == "claude" and entry.get("held") is not True)
    return {**seen, "controller": proof, "unheld": unheld}


# --- receipts ---------------------------------------------------------------------------------


def slot(host, harness, home):
    return f"{host}/{harness}/{home}"


def label(host, harness, home, matrix=None):
    name = f"{host} {NAMES.get(harness, harness)} {home}"
    return f"{name} ({matrix})" if matrix else name


def _versions(prepared, host, harness, home):
    if harness == "codex":
        return prepared["hosts"]["titan"]["codex"]["version"], prepared["pins"]["codex_version"]
    return (prepared["hosts"][host]["claude"]["versions"][home],
            prepared["pins"]["claude_version"])


class _Receipt:
    """One receipt's validation against this window's records; `refuse` raises Failed."""

    def __init__(self, window, prepared, receipt):
        self.window, self.prepared, self.receipt = window, prepared, receipt
        self.smokes = _smokes(window)
        self.host = (receipt.get("host") if isinstance(receipt, dict)
                     and receipt.get("host") in hosts.HOSTS else "titan")

    def refuse(self, message):
        raise lifecycle.Failed("receipt", self.host, "refused", message,
                               observed="nothing was recorded",
                               next_command=["record-smoke", "--preview", "--receipt",
                                             RECEIPT_PLACEHOLDER])

    # -- the receipt's own fields --

    def binding(self, own):
        receipt, window = self.receipt, self.window
        if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS
                or not state._is_one(receipt.get("schema"))):
            self.refuse("the receipt is not schema 1 with exactly "
                        + ", ".join(sorted(RECEIPT_KEYS)))
        if receipt["window_id"] != window["id"]:
            self.refuse(f"the receipt names window {receipt['window_id']!r}, not this live "
                        f"window {window['id']}: receipts from another window or a pilot never "
                        "count here")
        if receipt["prepared_sha256"] != window["prepared_sha256"]:
            self.refuse("the receipt names another preparation than this window's")
        if not all(isinstance(receipt[name], str) for name in ("host", "harness", "home")):
            self.refuse("the receipt's host, harness and home must be names")
        key = (receipt["host"], receipt["harness"], receipt["home"])
        if key not in REQUIRED:
            self.refuse(f"{receipt['host']} {receipt['harness']} {receipt['home']} is not a "
                        "smoke this cutover requires")
        matrix = REQUIRED[key]
        if receipt["matrix"] != matrix:
            self.refuse(f"{label(*key)} is a {matrix} smoke; the receipt says "
                        f"{receipt['matrix']!r}")
        expected = _versions(self.prepared, *key)
        if len(set(expected)) != 1:
            self.refuse(f"the prepared installed version {expected[0]} is not the evidence "
                        f"version {expected[1]}; prepare again")
        if receipt["versions"] != {"installed": expected[0], "evidence": expected[1]}:
            self.refuse(f"the receipt's versions are not the prepared installed and evidence "
                        f"version {expected[0]}")
        self.sessions(own)
        human = receipt["human"]
        wanted = HUMAN[matrix]
        if not isinstance(human, dict) or sorted(human) != list(wanted):
            self.refuse(f"a {matrix} smoke needs exactly the human's "
                        f"{' and '.join(sorted(wanted, reverse=True))} verdict"
                        f"{'s' if len(wanted) > 1 else ''}, which the operator answers")
        for name in wanted:
            if human[name] != "approved":
                self.refuse(f"the human {name} verdict is {human[name]!r}: only the operator's "
                            "own approval passes; a declined, unanswered or automatic approval "
                            "cannot")
        names = SHORT if matrix == "short" else tuple(
            name for name in FULL if name != "idle-needs-input"
            or receipt["harness"] == "claude-code")
        cases = receipt["cases"]
        if not isinstance(cases, dict) or set(cases) != set(names):
            found = set(cases) if isinstance(cases, dict) else set()
            parts = [f"missing: {', '.join(name for name in names if name not in found)}"
                     if set(names) - found else "",
                     f"unexpected: {', '.join(sorted(found - set(names)))}"
                     if found - set(names) else ""]
            self.refuse(f"a {matrix} {NAMES[receipt['harness']]} smoke needs exactly its "
                        f"cases; {'; '.join(part for part in parts if part)}")
        for name in names:
            entry = cases[name]
            if not isinstance(entry, dict) or set(entry) != CASE_KEYS | EXTRA.get(name, set()):
                self.refuse(f"{name} must hold exactly "
                            + ", ".join(sorted(CASE_KEYS | EXTRA.get(name, set()))))
            if entry["verdict"] != "passed":
                self.refuse(f"{name} is {entry['verdict']!r}: a failed smoke blocks finish")
        return names

    def sessions(self, own):
        receipt = self.receipt
        controller = self.prepared["controller"]["session_id"]
        proof = self.smokes.get("controller") or {}
        session, pid = receipt["session_id"], receipt["pid"]
        if not isinstance(session, str) or not session.strip():
            self.refuse("the receipt names no native session")
        if receipt["row_id"] != f"{receipt['harness']}:{session}":
            self.refuse("the row ID must be this harness and session's root row")
        if type(pid) is not int or pid <= 0:
            self.refuse("the receipt's pid must be the tested session's process ID")
        if not isinstance(receipt["cwd"], str) or not os.path.isabs(receipt["cwd"]):
            self.refuse("the receipt's cwd must be its scratch repo's absolute path")
        used = {session}
        if session == controller or pid == proof.get("pid"):
            self.refuse("this is the live controller's session: smokes run in their own "
                        "dedicated sessions")
        abrupt = receipt["cases"].get("abrupt-death") if isinstance(receipt["cases"],
                                                                     dict) else None
        if isinstance(abrupt, dict):
            if abrupt.get("session_id") in (controller, session) or abrupt.get("pid") in (
                    proof.get("pid"), pid):
                self.refuse("abrupt-death names the live controller's or the tested session's "
                            "own session or PID: it kills only its own second session")
            if isinstance(abrupt.get("session_id"), str):
                used.add(abrupt["session_id"])
        for key, entry in self.smokes["receipts"].items():
            if key == own:
                continue
            other = entry["receipt"]
            taken = {other["session_id"],
                     ((other.get("cases") or {}).get("abrupt-death") or {}).get("session_id")}
            if used & taken:
                self.refuse(f"its session is already used by the {key.replace('/', ' ')} "
                            "receipt: each home needs its own")

    # -- the evidence --

    def evidence(self, name, count=1):
        refs = self.receipt["cases"][name]["evidence"]
        if not isinstance(refs, list) or len(refs) != count:
            self.refuse(f"{name} needs exactly {count} recorded evidence observation(s)")
        return [self.observation(name, ref) for ref in refs]

    def observation(self, name, ref):
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            self.refuse(f"{name}: each evidence entry is exactly its path and sha256")
        recorded = next((entry for entry in self.smokes["observations"].values()
                         if entry["path"] == ref["path"]), None)
        if recorded is None:
            self.refuse(f"{name}: evidence {ref['path']} is not an observation this window "
                        "recorded: evidence counts only by its recorded content, never by its "
                        "name or place")
        if ref["sha256"] != recorded["sha256"]:
            self.refuse(f"{name}: evidence {ref['path']} names another digest than the one "
                        "recorded")
        path = Path(ref["path"])
        try:
            state._check_dir(path.parent)
            data = state._read(path)
        except Stop:
            self.refuse(f"{name}: evidence {ref['path']} is missing or unreadable")
        if hashlib.sha256(data).hexdigest() != recorded["sha256"]:
            self.refuse(f"{name}: evidence {ref['path']} changed since it was recorded")
        value = hosts._decode(data)
        if (value.get("window_id"), value.get("mode")) != (self.window["id"],
                                                           self.window["mode"]):
            self.refuse(f"{name}: evidence {ref['path']} belongs to another window or mode")
        if value.get("host") != self.receipt["host"]:
            self.refuse(f"{name}: evidence {ref['path']} was observed on {value.get('host')}, "
                        f"not {self.receipt['host']}")
        if drift(self.prepared, self.receipt["host"], value):
            self.refuse(f"{name}: evidence {ref['path']} was observed after Claude or Codex "
                        "moved")
        return {**value, "seq": recorded["seq"]}

    def row(self, name, seen, state_name=None, session=None, pid=None):
        """The live root row of the tested (or named) session in one observation."""
        receipt = self.receipt
        session, pid = session or receipt["session_id"], pid or receipt["pid"]
        row_id = f"{receipt['harness']}:{session}"
        row = seen["agents"].get(row_id)
        if row is None:
            self.refuse(f"{name}: observation {seen['operation_id']} has no row {row_id}")
        if (row["harness"], row["session_id"], row["scope"]) != (receipt["harness"], session,
                                                                 "session"):
            self.refuse(f"{name}: {row_id} is not that session's root row")
        if state_name is not None and row["state"] != state_name:
            self.refuse(f"{name}: {row_id} is {row['state']}, not {state_name}")
        if row["cwd"] != receipt["cwd"]:
            self.refuse(f"{name}: {row_id}'s cwd is not the receipt's scratch repo: a stale row "
                        "or another session")
        process = row["process"] or {}
        if process.get("pid") != pid or process.get("host") != seen["nodename"]:
            self.refuse(f"{name}: {row_id}'s process is not pid {pid} on {receipt['host']}")
        if type(row["updated_at"]) is not int or row["updated_at"] < _fresh_since(self.window):
            self.refuse(f"{name}: {row_id} predates this window's verified migration: a stale "
                        "row")
        return row

    def live(self, name, seen, state_name=None):
        row = self.row(name, seen, state_name)
        if row["liveness"] != "alive":
            self.refuse(f"{name}: {row['session_id']}'s row is {row['liveness']}, not alive")
        if row["process"]["start"] != self.start:
            self.refuse(f"{name}: the row's process is not the one the start observed")
        return row

    def scratch(self, name, seen):
        scratch = seen.get("scratch") or {}
        if scratch.get("cwd") != self.receipt["cwd"]:
            self.refuse(f"{name}: observation {seen['operation_id']} did not read the "
                        "receipt's scratch repo (its cwd)")
        return scratch

    def gone(self, name, seen, session):
        row_id = f"{self.receipt['harness']}:{session}"
        if row_id in seen["agents"]:
            self.refuse(f"{name}: observation {seen['operation_id']} still has its row {row_id}")
        if not seen["intent"]["present"] or session in seen["intent"]["sessions"]:
            self.refuse(f"{name}: familiar's intent still names {session} or is moved aside")

    # -- the cases --

    def cases(self, names):
        receipt, cases = self.receipt, self.receipt["cases"]
        [start] = self.evidence("start-idle")
        row = self.row("start-idle", start, "idle")
        if row["liveness"] != "alive":
            self.refuse(f"start-idle: {row['session_id']}'s row is {row['liveness']}, not alive")
        self.start = row["process"]["start"]
        family = HARNESS[receipt["harness"]]
        if receipt["harness"] == "codex":
            expected = self.prepared["hosts"]["titan"]["codex"]["real"]
        else:
            expected = self.prepared["hosts"][receipt["host"]]["claude"]["real"]
        held = [entry for entry in start["processes"] if entry["pid"] == receipt["pid"]
                and str(entry["start_time"]) == str(self.start) and entry["harness"] == family
                and entry["known"] and entry["exe"] == expected
                and (family != "claude" or entry.get("held") is True)]
        if not held:
            self.refuse(f"start-idle: pid {receipt['pid']} is not a held "
                        f"{NAMES[receipt['harness']]} process of the prepared executable "
                        f"{expected}")
        if any(entry.get("bypass") is not False for entry in held):
            self.refuse(f"start-idle: pid {receipt['pid']} {BYPASSED}: a smoke runs only "
                        "through its printed held smoke command")
        homes = sorted({entry.get("home") or "unknown" for entry in held})
        if homes != [receipt["home"]]:
            self.refuse(f"start-idle: pid {receipt['pid']} runs in the {' and '.join(homes)} "
                        f"{NAMES[receipt['harness']]} home, not the receipt's {receipt['home']} "
                        "home: each home's receipt needs a session launched in that home "
                        "through its printed held smoke command")
        seqs = [start["seq"]]
        if "allow-working" in names:
            [seen] = self.evidence("allow-working")
            self.live("allow-working", seen, "working")
            if not self.scratch("allow-working", seen).get("allowed_marker"):
                self.refuse("allow-working: allowed.marker is absent from the scratch repo")
            seqs.append(seen["seq"])
        entry = cases["attribution-denial"]
        if entry["outcome"] != "refused":
            self.refuse(f"attribution-denial: the denial's outcome is {entry['outcome']!r}: a "
                        "denial that succeeded, met a Git identity error or was never attempted "
                        "is a failed smoke")
        if not isinstance(entry["refusal"], str) or REFUSAL not in entry["refusal"]:
            self.refuse(f"attribution-denial: the quoted native result does not show "
                        f"{REFUSAL}")
        [seen] = self.evidence("attribution-denial")
        scratch = self.scratch("attribution-denial", seen)
        if scratch.get("commits") != 0:
            self.refuse(f"attribution-denial: the scratch repo has {scratch.get('commits')} "
                        "commit(s): the denied commit must leave none")
        if scratch.get("denied_marker") is not False:
            self.refuse("attribution-denial: denied.marker exists: the command ran")
        if scratch.get("identity") is not True:
            self.refuse("attribution-denial: Git has no identity in the scratch repo, so a "
                        "refusal there may be a Git identity error rather than the guard")
        self.live("attribution-denial", seen)
        seqs.append(seen["seq"])
        for name, state_name in (("needs-approval", "needs-approval"), ("turn-done", "done")):
            if name in names:
                [seen] = self.evidence(name)
                self.live(name, seen, state_name)
                seqs.append(seen["seq"])
                if name == "turn-done":
                    done = seen["agents"][receipt["row_id"]]["updated_at"]
        if "idle-needs-input" in names:
            [seen] = self.evidence("idle-needs-input")
            row = self.live("idle-needs-input", seen, "needs-input")
            if row["updated_at"] < done + IDLE_MS:
                self.refuse("idle-needs-input: needs-input came less than 60 s after the turn "
                            "ended: no idle prompt was proven")
            seqs.append(seen["seq"])
        if "projection-recovery" in names:
            moved, recovered = self.evidence("projection-recovery", 2)
            message = ("projection-recovery needs an observation with the session missing from "
                       "familiar's intent, then one after familiar reap with it back")
            self.live("projection-recovery", moved)
            self.live("projection-recovery", recovered)
            if (receipt["session_id"] in moved["intent"]["sessions"]
                    or receipt["session_id"] not in recovered["intent"]["sessions"]
                    or moved["seq"] > recovered["seq"]):
                self.refuse(message)
            seqs += [moved["seq"], recovered["seq"]]
        [exited] = self.evidence("normal-exit")
        self.gone("normal-exit", exited, receipt["session_id"])
        if exited["seq"] < max(seqs):
            self.refuse("normal-exit must be observed after every other case of the session")
        if "abrupt-death" in names:
            self.abrupt(cases["abrupt-death"])

    def abrupt(self, entry):
        if not isinstance(entry["session_id"], str) or type(entry["pid"]) is not int:
            self.refuse("abrupt-death names its second session's ID and recorded PID")
        dead, gone = self.evidence("abrupt-death", 2)
        message = ("abrupt-death needs the killed session's dead row first, then an "
                   "observation after relay and familiar reap with it gone")
        row = self.receipt["harness"] + ":" + entry["session_id"]
        if row not in dead["agents"] or dead["seq"] > gone["seq"]:
            self.refuse(message)
        self.row("abrupt-death", dead, session=entry["session_id"], pid=entry["pid"])
        if dead["agents"][row]["liveness"] != "dead":
            self.refuse(f"abrupt-death: {row} is {dead['agents'][row]['liveness']}, not dead "
                        "before reaping")
        self.gone("abrupt-death", gone, entry["session_id"])

    def proven(self):
        if "controller" not in self.smokes:
            self.refuse("no smoke evidence counts until the controller's fresh row is proven: "
                        "run record-smoke --observe titan first")


def _check(window, prepared, receipt, own=None):
    checked = _Receipt(window, prepared, receipt)
    names = checked.binding(own)
    checked.proven()
    checked.cases(names)
    return state._digest(receipt)


def _recorded(window, receipt):
    if isinstance(receipt, dict) and all(isinstance(receipt.get(key), str)
                                         for key in ("host", "harness", "home")):
        key = slot(receipt["host"], receipt["harness"], receipt["home"])
        if key in _smokes(window)["receipts"]:
            raise lifecycle.Failed(
                "receipt", receipt["host"] if receipt["host"] in hosts.HOSTS else "titan",
                "refused", f"the {key.replace('/', ' ')} receipt is already recorded",
                observed="nothing was recorded", next_command=lifecycle.status()["next"])


def check_receipt(window: dict, receipt: dict) -> str:
    """Read-only: the receipt's digest, which its attestation decision must name, or Failed
    naming the first binding it breaks."""
    state._current(window)
    _waiting(window)
    _recorded(window, receipt)
    return _check(window, _prepared(window), receipt)


def next_attempt(window: dict) -> str:
    """The attempt ID of this window's next smoke attestation."""
    return state.next_attempt(window, PREFIX)


def record_smoke(window: dict, receipt: dict, decision: dict) -> None:
    """Store one validated receipt with the consumed decision that attested its human
    verdicts: this window's `smoke-attestation` for exactly this receipt, used once."""
    digest = check_receipt(window, receipt)
    attempt = decision.get("attempt_id") if isinstance(decision, dict) else None
    consumed = None
    if isinstance(attempt, str) and state.ATTEMPT_ID.fullmatch(attempt):
        try:
            consumed = state.load_record(Path(window["directory"]) / "decisions"
                                         / f"{attempt}.json")
        except Stop:
            consumed = None
    if (consumed is None or consumed != decision or decision.get("kind") != KIND
            or decision.get("action") != ACTION or decision.get("window_id") != window["id"]
            or decision.get("prepared_sha256") != window["prepared_sha256"]
            or decision.get("subject_sha256") != digest):
        raise lifecycle.Failed("decision", receipt["host"], "refused", "the decision is not this "
                               "window's consumed attestation of exactly this receipt; ask again",
                               observed="nothing was recorded",
                               next_command=["record-smoke", "--preview", "--receipt",
                                             RECEIPT_PLACEHOLDER])
    smokes = _smokes(window)
    if any(entry["attempt_id"] == attempt for entry in smokes["receipts"].values()):
        raise lifecycle.Failed("decision", receipt["host"], "refused", f"attempt {attempt} "
                               "already attested a receipt; ask again",
                               observed="nothing was recorded", next_command=["status"])
    smokes["receipts"][slot(receipt["host"], receipt["harness"], receipt["home"])] = {
        "receipt": receipt, "sha256": digest, "attempt_id": attempt,
        "decision_sha256": decision["decision_sha256"],
        "consumed_sha256": state._digest(decision),
        "source": decision["decision"]["source"]["type"], "recorded_at": lifecycle._now()}
    lifecycle._save(window, smokes=smokes)


def missing(window):
    recorded = _smokes(window)["receipts"]
    return [key for key in REQUIRED if slot(*key) not in recorded]


def validate_smokes(window: dict) -> None:
    """finish's gate: every required receipt recorded in this live window, each still valid
    against its recorded observations and attested by its own consumed decision."""
    if window["mode"] != "live":
        raise lifecycle.Failed("receipts", "titan", "refused", f"window {window['id']} is a "
                               f"{window['mode']} window: pilot receipts never satisfy a live "
                               "finish", observed="nothing was changed", next_command=["status"])
    absent = missing(window)
    if absent:
        raise lifecycle.Failed(
            "receipts", "titan", "blocked", f"{len(absent)} required smoke receipt(s) are "
            f"missing: {', '.join(label(*key, REQUIRED[key]) for key in absent)}",
            observed="nothing was changed", next_command=status(window)["next"])
    prepared = _prepared(window)
    for key, entry in _smokes(window)["receipts"].items():
        _check(window, prepared, entry["receipt"], own=key)
        try:
            consumed = state.load_record(Path(window["directory"]) / "decisions"
                                         / f"{entry['attempt_id']}.json")
        except Stop:
            consumed = None
        if (consumed is None or state._digest(consumed) != entry["consumed_sha256"]
                or consumed.get("decision_sha256") != entry["decision_sha256"]
                or consumed.get("subject_sha256") != entry["sha256"]
                or consumed.get("kind") != KIND):
            raise lifecycle.Failed("receipts", "titan", "blocked", f"the {key} receipt's "
                                   "attestation decision is missing or changed; inspect it",
                                   observed="nothing was changed", next_command=["status"])


def status(window: dict) -> dict:
    """The read-only status detail and next command of a window past its verified migration."""
    from . import finish, surfaces  # both import this module
    if window["state"] == "migrated-surfaces-pending":
        return surfaces.status(window)
    if window["state"] == "finishing":
        return finish.status(window)
    smokes = _smokes(window)
    absent = missing(window)
    lead = (f"window {window['id']} verified the migration and restarted familiar's surfaces "
            f"({surfaces._summary(window, surfaces.FORWARD)}); {timers_line(window).strip()}")
    if "controller" not in smokes:
        return {"detail": f"{lead}; the controller's fresh row is not proven yet: resume it "
                          "with its printed held command, then observe titan first",
                "next": ["record-smoke", "--observe", "titan"]}
    done = [label(*key, REQUIRED[key]) for key in REQUIRED if key not in absent]
    if absent:
        return {"detail": (f"{lead}; the controller's row is proven; receipts recorded: "
                           f"{', '.join(done) or 'none'}; missing: "
                           f"{', '.join(label(*key, REQUIRED[key]) for key in absent)}"),
                "next": ["record-smoke", "--preview", "--receipt", RECEIPT_PLACEHOLDER]}
    stopped = (window.get("finish") or {}).get("failure")
    last = (f"; finish stopped at {stopped['step']} on {stopped['host']} ({stopped['status']}) "
            "before any timer changed" if stopped else "")
    return {"detail": f"{lead}; every smoke receipt is recorded{last}", "next": ["finish"]}


# The controller side uses the window lifecycle, which imports operations and so this module:
# it is bound here, once this module's operations are defined.
from . import window as lifecycle  # noqa: E402
