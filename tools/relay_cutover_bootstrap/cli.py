"""Argument parsing, the human decision and phase messages for tools/relay-cutover-bootstrap.

`prepare --controller-session ID` records eligibility and the current inputs; `check`
compares both hosts with that record without changing them; `run` opens a window, takes this
invocation's desktop decision, runs through the verified migration and restarts familiar's
surfaces with that same decision; `restart-surfaces` retries surfaces still pending after a
verified migration; `record-smoke` observes the smokes (`--observe HOST`) and records each home's
receipt with the human's attestation; `finish` restores the original timers, runs the scheduled
reconciliation and verifies closure; `recover` rolls a window back to native; `status` reads the
local records and names the one next command. From the verified migration until finish every
report prints the held commands and the hold (`smoke.handoff`); before that, check and status
print the bounded refresh a closure request needs, with ordinary use allowed. A stopped command
prints its step, host, status, private log, observed state and one next command, then returns 1
to the calling shell. It never prints settings, plans, environments, credentials or child
output.

`run` and `recover` are operator-run: their desktop decision comes only from the operator's
terminal (`/dev/tty`: a bounded preview of its subject, then an explicit answer recorded as a
`tty` source), and they take no decision file. Without a terminal they stop with instructions
before any change. `restart-surfaces` takes the operator's terminal answer too, or a decision
file: the private record of an actual session ask and the human's reply, about the subject that
`restart-surfaces --preview` shows read-only. Without either it stops with those instructions
before any change. `record-smoke --receipt FILE` takes the same two sources for its smoke
attestation, about the receipt `record-smoke --preview` shows read-only. Each invocation consumes
its one decision before the first authorized action; no flag or default answers for the
operator. A terminal reached from a Claude or Codex process is that agent's own, even when the
agent holds a pseudo-terminal there, so an invocation running under one (`_agent_ancestor`)
takes no terminal answer at all: run refuses before it opens a window.

`recover`'s entry-time desktop preview can be blocked, or the operator can decline its surface
restarts; recover then still restores native settings, source and dependencies and stops before
the surfaces (rulings R36 and R46). `reconcile-operations --host HOST` reports every unfinished
operation on a host and cancels only the owner-lost ones (ruling R48).

`rehearse_main` is tools/relay-cutover-rehearse, the separate pilot entry (`pilot.py`): with
`--preview` it allocates the pilot window and shows its spawn's bounded consent subject; then an
agent's `--decision-file` (the recorded session ask and reply) or the operator's terminal answer
runs the rehearsal, whose private verdict it summarizes. Without an approval it still runs every
part but the spawn, whose gate stays pending. While a pilot window is open, run, recover,
restart-surfaces, record-smoke and finish refuse and name the rehearse entry; nothing in the
caller's environment selects a pilot for them."""
import argparse
import json
import os
import shlex
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import finish as finishing
from . import prepare as preparation
from . import hosts, inventory, pilot, recovery, smoke, state, surfaces, window
from .state import Stop

PROG = "relay-cutover-bootstrap"
REHEARSE_PROG = "relay-cutover-rehearse"
REHEARSE = "tools/relay-cutover-rehearse"
LIMIT = 500
SHOWN = 40
TTY = "/dev/tty"
PROC = "/proc"
ANSWER_BYTES = 200
DECISION_BYTES = 65536
RECEIPT_BYTES = 1 << 20
APPROVE = ("y", "yes")
DECISION_PLACEHOLDER = "<decision-file>"
# Why an invocation has no operator's terminal (`_unanswerable`), and what each command does then.
NO_TTY = "this invocation has no terminal for the operator's answer"
NO_TERMINAL = ("run is operator-run and {reason}: the operator launches it from an ordinary "
               "terminal, with every Claude and Codex session closed on both hosts")
RECOVER_NO_TERMINAL = ("recover is operator-run and {reason}: the operator runs it from an "
                       "ordinary terminal, with every Claude and Codex session closed on both "
                       "hosts")
NO_DECISION = ("restart-surfaces needs this invocation's human decision and {reason}: preview its "
               "subject with restart-surfaces --preview, ask the user in the session naming those "
               "hosts, surfaces, impact and duration, record the actual ask and reply in a "
               "private decision file and pass it with --decision-file")
NO_ATTESTATION = ("record-smoke needs the human's own attestation of this receipt's trust and "
                  "permission verdicts and {reason}: preview it with record-smoke --preview "
                  "--receipt FILE, ask the user in the session naming its host, home, session, "
                  "cases and human verdicts, record the actual ask and reply in a private "
                  "decision file and pass it with --decision-file")
ASK_TAIL = "nothing has changed yet; any answer but yes stops before any change"
RECOVER_TAIL = ("recover restores native settings, source and dependencies either way; any "
                "answer but yes restarts no surface, and recover stops before its surface "
                "restart, for a later recover")
NO_PROOF = ("an agent's session decision for restart-surfaces needs the controller's fresh row "
            "proven first: resume the controller with its printed held command and run "
            "record-smoke --observe titan; a window whose migration is not yet verified is "
            "reconciled by run first. The operator may instead answer restart-surfaces at the "
            "terminal")
HOLD_STATES = ("migrated-surfaces-pending", "ready-for-smokes", "finishing")
# The commands that act on a live window: each refuses while a pilot window is open.
LIVE_COMMANDS = ("run", "recover", "restart-surfaces", "record-smoke", "finish")
# Before run, and in every parked wait: ordinary use stays allowed, and the agent's bounded
# refresh before each request to close sessions.
CLOSURE = (
    "  ordinary use: until run opens the window, ordinary Claude and Codex use stays allowed, "
    "including cl, clw and review sessions, while this preparation waits",
    "  before closure: immediately before each request to close every Claude and Codex session, "
    "run check again; its held version and doctor probes are the fresh held check on titan and "
    "europa, and unchanged versions keep the existing proof with no preparation repeated",
    "  surface drift: if check reports only the desktop (surface) drift, run prepare again, then "
    "check",
    "  familiar: from run until finish make no familiar commit on europa; on titan a familiar "
    "commit before the merge aborts the run cleanly before it (a task-record commit after it is "
    "tolerated), so pause task-record commits until run reports the merge",
    "  version moved: if Claude moved on either host, repeat only Task 9 Steps 5–7 (the held "
    "re-probe and its independent review, the reviewed proof's delivery and both hosts' "
    "installer acceptance, refreshed inputs and prepare), then run check again before asking; "
    "rerun the pilot only if helper or toolchain bytes changed from its recorded identities",
    "  refresh: the agent performs and reviews any refresh; this tool runs no refresh or retry "
    "loop",
)


def _clean(text):
    return "".join(ch if ch.isprintable() else " " for ch in str(text))[:LIMIT]


def _words(entry, argv):
    words = [shlex.quote(str(window.CHECKOUT / entry))]
    words += [arg if arg in (window.SESSION_PLACEHOLDER, DECISION_PLACEHOLDER)
              else shlex.quote(arg) for arg in argv]
    return " ".join(words)


def command_line(argv):
    """A complete command for the operator: this checkout's bootstrap and its arguments, or its
    rehearse entry for a next command that starts with `rehearse`."""
    if argv[:1] == [window.REHEARSE]:
        return rehearse_line(argv[1:])
    return _words(window.BOOTSTRAP, argv)


def rehearse_line(argv):
    """A complete command: this checkout's rehearse entry and its arguments."""
    return _words(REHEARSE, argv)


def _failure(command, failed, handoff=(), prog=PROG):
    lines = [f"{prog}: {command} stopped", f"  step: {failed.step}", f"  host: {failed.host}",
             f"  status: {failed.status}", f"  error: {_clean(failed.error)}",
             f"  log: {failed.log or 'none'}",
             f"  observed: {_clean(failed.observed or 'unknown; run status')}"]
    if failed.blockers:
        lines.append("  blockers:")
        lines += [f"    - {_clean(blocker)}" for blocker in failed.blockers[:SHOWN]]
        if len(failed.blockers) > SHOWN:
            lines.append(f"    - and {len(failed.blockers) - SHOWN} more")
    lines += handoff
    lines.append(f"  next: {command_line(failed.next_command or ['status'])}")
    print("\n".join(lines), file=sys.stderr)


def _sessions(sessions):
    if not sessions:
        return "no live Claude or Codex process"
    return (f"{len(sessions)} live Claude or Codex process(es) (pids "
            f"{', '.join(str(entry['pid']) for entry in sessions)}); run refuses until every "
            "session on both hosts is closed")


def _base(report):
    """familiar's base on one host, as prepare and check observed it."""
    if not report:
        return "familiar's base was not observed"
    return (f"familiar base {report['base'][:12]}: {len(report['commits'])} tasks-only "
            "commit(s) past PRE, and its merge with the feature tip equals T0 outside tasks/")


def _prepare(session):
    prepared = preparation.prepare(session)
    print(f"{PROG}: prepared {window._root() / window.PREPARED} "
          f"(sha256 {window.prepared_sha256(prepared)})")
    print(f"  inputs: generation {prepared['manifest']['generation']}; Claude picks "
          f"({', '.join(prepared['filter']['keys'])}) recorded as found")
    for host in window.HOST_ORDER:
        print(f"  {host}: {_sessions(prepared['hosts'][host]['sessions'])}")
        print(f"  {host}: {_base(prepared['hosts'][host]['familiar'])}")
    print("  observed: no window is open; only the prepared record and private operation "
          "records were written")
    print("\n".join(CLOSURE))
    print(f"  next: {command_line(['check'])}")
    return 0


def _check():
    prepared = preparation.load_prepared()
    result = preparation.check(prepared)
    if not result["eligible"]:
        host = preparation.blocking_host(result)
        raise window.Failed(
            "check", host, "blocked", f"{len(result['blockers'])} blocker(s) since preparation",
            log=result["logs"].get(host), blockers=result["blockers"],
            observed="nothing was changed",
            next_command=["prepare", "--controller-session",
                          prepared["controller"]["session_id"]])
    print(f"{PROG}: check: eligible (prepared {result['prepared_sha256']})")
    for host in window.HOST_ORDER:
        print(f"  {host}: {_sessions(result['sessions'][host])}")
        print(f"  {host}: {_base(result['familiar'][host])}")
    print("  observed: nothing was changed")
    print("\n".join(CLOSURE))
    print(f"  next: {command_line(['run'])}")
    return 0


def _preview(opened, subject, title=None, changes=None):
    """The bounded subject an operator approves: each host's surfaces, impact and duration."""
    lines = [title or f"{PROG}: run {opened['id']} asks for this invocation's desktop consent"]
    restart = subject.get("restart")
    for host, desktop in subject["hosts"].items():
        if desktop["state"] != "present":
            reason = desktop["absence_reason"] or "no familiar surface is configured or running"
            lines.append(f"  {host}: nothing restarts ({_clean(reason)})")
            continue
        names = restart[host] if restart is not None else [
            surface["name"] for surface in desktop["surfaces"]]
        if not names:
            lines.append(f"  {host}: nothing restarts (its surfaces were already restarted)")
            continue
        for change in (changes or {}).get(host, []):
            lines.append(f"  {host}: changed since the recording: {_clean(change)}; approving "
                         "adopts this new inventory")
        lines.append(f"  {host}: through niri socket {_clean(desktop['socket'])}, restart:")
        for surface in desktop["surfaces"]:
            if surface["name"] not in names:
                continue
            processes = ", ".join(f"pid {process['pid']}: {_clean(shlex.join(process['argv']))}"
                                  for process in surface["processes"]) or (
                "not running; its startup command starts it")
            lines.append(f"    {surface['name']} ({processes})")
    lines.append(f"  impact: {subject['impact']}; about {subject['duration_seconds']} s per host")
    return "\n".join(lines) + "\n"


def _ask(opened, action, attempt_id, subject, digest, *, title=None, prompt=None,
         changes=None, kind="desktop", shown=None, tail=ASK_TAIL):
    """One explicit answer on the operator's terminal, as a decision record. `shown` replaces
    the desktop preview with another bounded subject, such as a smoke receipt's."""
    agent = _agent_ancestor()
    if agent is not None:
        raise Stop(NO_TERMINAL.format(reason=_under(agent)))
    try:
        fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC)
    except OSError:
        raise Stop(NO_TERMINAL.format(reason=NO_TTY)) from None
    prompt = prompt or (f"Restart these familiar surfaces during run {opened['id']}? Type yes "
                        "to approve: ")
    try:
        if not os.isatty(fd):
            raise Stop(NO_TERMINAL.format(reason=NO_TTY))
        shown = shown if shown is not None else _preview(opened, subject, title, changes)
        os.write(fd, (shown + f"  {tail}\n" + prompt).encode("utf-8"))
        try:
            answer = os.read(fd, ANSWER_BYTES).decode("utf-8", "replace").strip()
        except KeyboardInterrupt:
            raise Stop("interrupted before an answer; nothing is authorized") from None
    finally:
        os.close(fd)
    if not answer:
        raise Stop("no answer was given; nothing is authorized")
    return {"schema": 1, "kind": kind, "action": action, "window_id": opened["id"],
            "attempt_id": attempt_id, "subject_sha256": digest,
            "verdict": "approved" if answer.lower() in APPROVE else "declined",
            "source": {"type": "tty", "prompt": prompt.strip(), "response": answer,
                       "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}}


def _terminal():
    """Whether this invocation has a terminal for the operator's answer."""
    try:
        fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC)
    except OSError:
        return False
    try:
        return os.isatty(fd)
    finally:
        os.close(fd)


def _agent_ancestor(pid=None, proc=PROC):
    """The nearest ancestor of this process (from `pid`'s parent chain, this process's parent by
    default) that is a Claude or Codex process, as {pid, name}, or None. Each is known by its
    comm or by an executable inside its release family under HOME, as inventory resolves them.
    A terminal reached from one is that agent's own, never the operator's."""
    home = Path.home()
    families = (("claude", home / ".local/share/claude/versions", inventory.CLAUDE_FAMILY),
                ("codex", home / ".codex/packages/standalone/releases", inventory.CODEX_FAMILY))
    pid, seen = os.getppid() if pid is None else pid, set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        base = Path(proc) / str(pid)
        try:
            comm = (base / "comm").read_text().strip()
            parent = int((base / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return None  # it exited meanwhile, ending the chain this process can still read
        try:
            exe = os.path.realpath(os.readlink(base / "exe"))
        except OSError:
            exe = None  # another user's process
        for name, family, pattern in families:
            root = os.path.realpath(family) + "/"
            if comm == name or (exe is not None and exe.startswith(root)
                                and pattern.fullmatch(exe[len(root):]) is not None):
                return {"pid": pid, "name": name}
        pid = parent
    return None


def _under(agent):
    return (f"this invocation runs under {agent['name']} (pid {agent['pid']}), whose terminal is "
            "that agent's own, never the operator's")


def _unanswerable():
    """Why this invocation cannot ask the operator at a terminal, or None when it can."""
    agent = _agent_ancestor()
    if agent is not None:
        return _under(agent)
    return None if _terminal() else NO_TTY


def _private_json(path, what, limit):
    """One private JSON record: this user's regular file, closed to writes by others."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise Stop(f"the {what} file cannot be opened ({error.strerror})") from None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise Stop(f"the {what} file must be this user's regular file, closed to writes "
                       "by others")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise Stop(f"the {what} file is too large to be one {what} record")
    try:
        return json.loads(data, object_pairs_hook=state._unique,
                          parse_constant=state._constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Stop(f"the {what} file is not one JSON {what} record") from None


def _decision_file(path):
    return _private_json(path, "decision", DECISION_BYTES)


def acquire_decision(opened: dict, *, action: str, attempt_id: str, subject: dict,
                     decision_file: str | None, title: str | None = None,
                     prompt: str | None = None, changes: dict | None = None,
                     kind: str = "desktop", shown: str | None = None,
                     tail: str = ASK_TAIL) -> dict:
    """This invocation's one human decision of `kind` for `opened`, consumed before it
    authorizes: the decision file's record, or the operator's answer to the bounded preview on
    the terminal. A declined verdict raises `state.Declined`."""
    digest = state._digest(subject)
    record = (_decision_file(decision_file) if decision_file is not None
              else _ask(opened, action, attempt_id, subject, digest, title=title, prompt=prompt,
                        changes=changes, kind=kind, shown=shown, tail=tail))
    return state.consume_decision(opened, record, kind=kind, action=action,
                                  attempt_id=attempt_id, subject_sha256=digest)


def _restarted(restarted):
    for host in window.HOST_ORDER:
        found = restarted.get(host) or {}
        print(f"  {host}: " + (", ".join(f"{name} pid {process['pid']}"
                                        for name, process in found.items())
                               or "nothing restarted (none recorded, or an explained absence)"))


def _existing(current):
    """run beside an unfinished window: reconcile it, report it and repeat none of its writes."""
    report = recovery.reconcile_window(current)
    if report["class"] in ("verified", "migrated"):
        print(f"{PROG}: run: window {current['id']} already verified its migration; nothing "
              "was repeated")
        print("\n".join(smoke.handoff(state.current_window(window._root()))))
        print(f"  observed: {_clean(report['observed'])}")
        print(f"  next: {command_line(report['next'])}")
        return 0
    raise window.Failed("run", "titan", "blocked", f"window {current['id']} is "
                        f"{report['state']}; run opens no new window beside it and repeats "
                        "none of its writes", blockers=report["blockers"],
                        observed=report["observed"], next_command=report["next"])


def _run():
    current = state.current_window(window._root())
    if current is not None and current["state"] not in state.TERMINAL:
        return _existing(current)
    prepared = preparation.load_prepared()
    agent = _agent_ancestor()
    if agent is not None:  # before any window is allocated
        raise window.Failed("decision", "titan", "refused",
                            NO_TERMINAL.format(reason=_under(agent)),
                            observed="nothing was changed", next_command=["run"])
    opened = window.open_window(prepared)
    try:
        decision = acquire_decision(opened, action=window.RUN_ACTION,
                                    attempt_id=window.RUN_ATTEMPT,
                                    subject=window.run_subject(prepared), decision_file=None)
    except Stop as stop:
        outcome = window.abort_window(state.current_window(window._root()))
        raise window.Failed("decision", "titan", "refused", str(stop),
                            observed=f"nothing was changed; window {opened['id']} is "
                            f"{outcome['state']}", next_command=["run"]) from None
    migrated = window.run_window(prepared, decision)
    merge = migrated["familiar"]["merge"]
    print(f"{PROG}: run {migrated['id']}: migration verified and familiar's surfaces restarted")
    print(f"  familiar: merged {merge} once on titan; each host installed and proved its relay "
          "dependency after the merge reached it")
    print("  settings: claude, claude-work, codex and codex-work applied once on titan to the "
          "sealed dry-run bytes; europa's Claude copies verified after synchronization")
    print("  surfaces: restarted with this run's consent, each replacement recorded:")
    _restarted(surfaces.restarted(migrated, surfaces.FORWARD))
    print("\n".join(smoke.handoff(migrated)))
    print(f"  observed: window {migrated['id']} is {migrated['state']}")
    print(f"  next: {command_line(window.status()['next'])}")
    return 0


def _surface_window(current):
    """The window restart-surfaces may act on, or Failed naming why not, before any ask."""
    report = window.status()
    if current is None or current["state"] in state.TERMINAL:
        raise window.Failed("restart-surfaces", "titan", "refused", "no window has familiar "
                            "surfaces pending", observed=report["detail"],
                            next_command=report["next"])
    owner = current.get("owner")
    if owner is not None and owner != window._me() and hosts._alive(owner):
        raise window.Failed("restart-surfaces", "titan", "refused", f"window {current['id']} "
                            f"belongs to a running invocation (pid {owner['pid']})",
                            observed=report["detail"], next_command=["status"])
    if (current["state"] in ("migrated-surfaces-pending", *surfaces.RECHECKED)
            or recovery.reconcilable(current)):
        return current
    reason = "familiar's surfaces restart only after a verified migration"
    raise window.Failed("restart-surfaces", "titan", "blocked", f"window {current['id']} is "
                        f"{current['state']}; {reason}", observed=report["detail"],
                        next_command=report["next"])


def _surface_preview(current):
    """Read-only: the subject a decision for the next restart-surfaces must approve."""
    offered = surfaces.preview(current, surfaces.RESTART_ACTION)
    changes = {host: found["changes"] for host, found in offered["observed"].items()}
    print(_preview(current, offered["subject"], f"{PROG}: restart-surfaces preview for window "
                   f"{current['id']} (read-only)", changes), end="")
    if current["state"] not in ("migrated-surfaces-pending", *surfaces.RECHECKED):
        print("  migration: not yet verified from actual state; restart-surfaces verifies it "
              "first and restarts nothing unless it holds")
    print(f"  decision: kind desktop, action {surfaces.RESTART_ACTION}, window_id "
          f"{current['id']}, attempt_id {offered['attempt_id']}, subject_sha256 "
          f"{offered['sha256']}")
    print("  ask: the user, in the session, naming these hosts, surfaces, impact and duration; "
          "record the actual ask and the human's reply (schema 1, verdict, and a session source "
          "with session_id, ask, reply and answered_at) in a private decision file")
    print("  observed: nothing was changed")
    print(f"  next: {command_line(['restart-surfaces', '--decision-file', DECISION_PLACEHOLDER])}")
    return 0


def _restart_surfaces(preview_only, decision_file):
    root = window._root()
    current = _surface_window(state.current_window(root))
    if preview_only:
        return _surface_preview(current)
    reason = _unanswerable() if decision_file is None else None
    if reason is not None:
        raise window.Failed("decision", "titan", "refused", NO_DECISION.format(reason=reason),
                            observed="nothing was changed",
                            next_command=["restart-surfaces", "--preview"])
    if decision_file is not None and "controller" not in (current.get("smokes") or {}):
        raise window.Failed("controller-check", "titan", "refused", NO_PROOF,
                            observed="nothing was changed",
                            next_command=["record-smoke", "--observe", "titan"])
    if current["state"] not in ("migrated-surfaces-pending", *surfaces.RECHECKED):
        report = recovery.reconcile_window(current)
        if report["class"] != "verified":
            raise window.Failed("reconcile", "titan", "blocked", f"window {current['id']}'s "
                                "migration is not verified from actual state; no surface was "
                                "restarted", blockers=report["blockers"],
                                observed=report["observed"], next_command=report["next"])
        current = state.current_window(root)
    offered = surfaces.preview(current, surfaces.RESTART_ACTION)
    try:
        consumed = acquire_decision(
            current, action=surfaces.RESTART_ACTION, attempt_id=offered["attempt_id"],
            subject=offered["subject"], decision_file=decision_file,
            title=f"{PROG}: restart-surfaces {current['id']} asks for this invocation's "
            "desktop consent", prompt=f"Restart these familiar surfaces for window "
            f"{current['id']}? Type yes to approve: ",
            changes={host: found["changes"] for host, found in offered["observed"].items()})
    except Stop as stop:
        raise window.Failed("decision", "titan", "refused", str(stop), observed=(
            f"nothing was changed; window {current['id']} is {current['state']}"),
            next_command=["restart-surfaces", "--preview"] if decision_file is not None
            else ["restart-surfaces"]) from None
    current = surfaces.bind(state.current_window(root), consumed, offered["subject"])
    result = surfaces.restart_surfaces(current, consumed)
    print(f"{PROG}: restart-surfaces {current['id']}: familiar's surfaces restarted, each "
          "replacement recorded:")
    _restarted(result["restarted"])
    print("\n".join(smoke.handoff(result["window"])))
    print(f"  observed: {_clean(result['observed'])}")
    print(f"  next: {command_line(result['next'])}")
    return 0


def _recover():
    root = window._root()
    current = state.current_window(root)
    if current is None or current["state"] in state.TERMINAL:
        report = window.status()
        raise window.Failed("recover", "titan", "refused", "no window needs recovery",
                            observed=report["detail"], next_command=report["next"])
    if recovery._running_elsewhere(current):
        raise window.Failed("recover", "titan", "refused", f"window {current['id']} belongs to "
                            f"a running invocation (pid {current['owner']['pid']}); let it "
                            "finish, or interrupt it", observed="nothing was changed",
                            next_command=["status"])
    if recovery.pre_merge(current):
        result = recovery.recover_window(current, None)
        print(f"{PROG}: recover {current['id']}: {_clean(result['observed'])}")
        print(f"  observed: window {current['id']} is {result['state']}")
        print(f"  next: {command_line(result['next'])}")
        return 0 if result["state"] == "aborted" else 1
    reason = _unanswerable()
    if reason is not None:
        raise window.Failed("decision", "titan", "refused",
                            RECOVER_NO_TERMINAL.format(reason=reason),
                            observed="nothing was changed", next_command=["recover"])
    held, consumed = None, None
    try:
        offered = surfaces.preview(current, surfaces.RECOVER_ACTION)
    except window.Failed as failed:
        if (failed.step, failed.status) != ("surface-preview", "blocked"):
            raise
        held = failed  # restoration does not wait for the desktop (ruling R36)
    if held is None and any(offered["subject"]["restart"].values()):
        try:
            consumed = acquire_decision(
                current, action=surfaces.RECOVER_ACTION, attempt_id=offered["attempt_id"],
                subject=offered["subject"], decision_file=None,
                title=f"{PROG}: recover {current['id']} asks for this invocation's desktop "
                "consent, once native settings, source and dependencies are restored",
                prompt=f"Restart these familiar surfaces while recovering window "
                f"{current['id']}? Type yes to approve: ",
                changes={host: found["changes"] for host, found in offered["observed"].items()},
                tail=RECOVER_TAIL)
        except state.Declined:  # a decline holds back only the surfaces (ruling R46)
            held = window.Failed("decision", "titan", "declined", "the operator declined "
                                 "recovery's surface restarts at the terminal; nothing about "
                                 "familiar's surfaces is authorized", next_command=["recover"])
        except Stop as stop:
            raise window.Failed("decision", "titan", "refused", str(stop), observed=(
                f"nothing was changed; window {current['id']} is {current['state']}"),
                next_command=["recover"]) from None
        else:
            current = surfaces.bind(state.current_window(root), consumed, offered["subject"])
    result = recovery.recover_window(current, consumed, held=held)
    print(f"{PROG}: recover {current['id']}: native recovery complete")
    print("  settings: every touched target holds its native bytes on titan and, synchronized, "
          "on europa")
    print("  familiar: source and dependencies native on titan and europa; its surfaces "
          "restarted from them")
    print("  timers: familiar-reap.timer restored to its original state and "
          "familiar-reap.service succeeded on titan and europa")
    print(f"  observed: {_clean(result['observed'])}")
    print(f"  next: {command_line(result['next'])}")
    return 0


def _status():
    report = window.status()
    print(f"{PROG}: status")
    prepared = report["prepared"]
    print("  prepared: " + (f"{prepared['sha256']} at {prepared['prepared_at']} (generation "
                            f"{prepared['generation']})" if prepared else "none"))
    current = report["window"]
    print("  window: " + (f"{current['id']} {current['state']} ({current['mode']})"
                          if current else "none"))
    print(f"  observed: {_clean(report['detail'])}")
    lines = _handoff("status")
    if not lines and report["next"] == ["check"]:
        lines = CLOSURE  # a parked preparation: ordinary use, and the refresh before closure
    if lines:
        print("\n".join(lines))
    print(f"  next: {command_line(report['next'])}")
    return 0


def _no_pilot():
    """Live commands refuse beside an open pilot window and name the rehearse entry."""
    current = state.current_window(window._root())
    if current is not None and current["mode"] == "pilot" and current["state"] not in \
            state.TERMINAL:
        raise window.Failed("pilot", "titan", "refused", window.pilot_open(current),
                            observed="nothing was changed",
                            next_command=[window.REHEARSE, "--controller-session",
                                          window.SESSION_PLACEHOLDER])


def _handoff(command):
    """What a report adds from the verified migration until finish: the hold, the pick freeze
    and the held commands; for check, the bounded refresh before a closure request."""
    if command == "check":
        return CLOSURE
    try:
        current = state.current_window(window._root())
    except Stop:
        return ()
    if current is None or current["state"] not in HOLD_STATES:
        return ()
    return smoke.handoff(current)


def _shown(current, receipt):
    """The bounded smoke attestation an operator or user answers: the receipt's binding, its
    case verdicts and the human verdicts it claims, asked as the human's own."""
    key = (receipt["host"], receipt["harness"], receipt["home"])
    cases = receipt["cases"]
    lines = [f"{PROG}: record-smoke {current['id']} asks for the human's attestation of "
             f"{smoke.label(*key, receipt['matrix'])}",
             f"  session: {receipt['session_id']} (row {receipt['row_id']}, pid "
             f"{receipt['pid']}) in {_clean(receipt['cwd'])}",
             f"  versions: installed {receipt['versions']['installed']}; evidence "
             f"{receipt['versions']['evidence']}",
             "  cases: " + ", ".join(f"{name} {cases[name]['verdict']} "
                                     f"({len(cases[name]['evidence'])} recorded observation(s))"
                                     for name in cases)]
    denial = cases.get("attribution-denial") or {}
    lines.append(f"  denial: {denial.get('outcome')}: {_clean(denial.get('refusal'))}")
    if "abrupt-death" in cases:
        lines.append(f"  abrupt death: session {cases['abrupt-death']['session_id']}, pid "
                     f"{cases['abrupt-death']['pid']}")
    lines.append("  human: trust approved: you, the operator, completed this home's trust "
                 "review yourself (Codex: its hook review)")
    if "permission" in receipt["human"]:
        lines.append("  human: permission approved: you answered the needs-approval permission "
                     "prompt yourself; no agent or auto-review answered it")
    return "\n".join(lines) + "\n"


def _smoke_window():
    current = state.current_window(window._root())
    if current is None or current["state"] in state.TERMINAL:
        report = window.status()
        raise window.Failed("record-smoke", "titan", "refused", "no window takes smokes",
                            observed=report["detail"], next_command=report["next"])
    return current


def _observe(host, cwd):
    """record-smoke --observe: one recorded observation, the controller proven first."""
    current = _smoke_window()
    if cwd is not None:
        cwd = os.path.realpath(cwd)
    result = smoke.observe_step(current, host, cwd)
    seen, proof = result["observation"], result["controller"]
    print(f"{PROG}: record-smoke {current['id']}: observed {host}")
    if proof is not None:
        print(f"  controller: {proof['row_id']} pid {proof['pid']} on titan, live and updated "
              "since the verified migration")
    print(f"  evidence: {result['ref']['path']} (sha256 {result['ref']['sha256']})")
    rows = sorted(seen["agents"].items())
    if cwd is not None:
        rows = [(row_id, row) for row_id, row in rows if row["cwd"] == cwd]
    for row_id, row in rows:
        print(f"  row: {row_id} {row['state']} pid {(row['process'] or {}).get('pid')} "
              f"{row['liveness']}")
    intent = seen["intent"]
    print("  intent: " + (f"{len(intent['sessions'])} session(s)" if intent["present"]
                          else "absent (moved aside)"))
    scratch = seen["scratch"]
    if scratch is not None:
        print(f"  scratch: allowed.marker {'present' if scratch['allowed_marker'] else 'absent'}"
              f"; denied.marker {'present' if scratch['denied_marker'] else 'absent'}; "
              f"{scratch['commits']} commit(s); Git identity "
              f"{'set' if scratch['identity'] else 'missing'}")
    if result["unheld"]:
        print(f"  warning: unheld Claude pid(s) {', '.join(map(str, result['unheld']))} on "
              f"{host}: close them; until finish use only the held commands")
    print("\n".join(smoke.handoff(result["window"])))
    print(f"  observed: {_clean(window.status()['detail'])}")
    print(f"  next: {command_line(window.status()['next'])}")
    return 0


def _record_smoke(path, preview_only, decision_file):
    current = _smoke_window()
    receipt = _private_json(path, "receipt", RECEIPT_BYTES)
    digest = smoke.check_receipt(current, receipt)
    attempt = smoke.next_attempt(current)
    shown = _shown(current, receipt)
    path = os.path.realpath(path)
    if preview_only:
        print(shown.replace("asks for", "previews").rstrip("\n") + " (read-only)")
        print(f"  decision: kind {smoke.KIND}, action {smoke.ACTION}, window_id {current['id']}, "
              f"attempt_id {attempt}, subject_sha256 {digest}")
        print("  ask: the user, in the session, whether they themselves gave these human "
              "verdicts, naming the host, home, session, cases and verdicts; record the actual "
              "ask and the human's reply (schema 1, verdict, and a session source with "
              "session_id, ask, reply and answered_at) in a private decision file")
        print("  observed: nothing was changed")
        following = ["record-smoke", "--receipt", path, "--decision-file", DECISION_PLACEHOLDER]
        print(f"  next: {command_line(following)}")
        return 0
    reason = _unanswerable() if decision_file is None else None
    if reason is not None:
        raise window.Failed("decision", receipt["host"], "refused",
                            NO_ATTESTATION.format(reason=reason), observed="nothing was recorded",
                            next_command=["record-smoke", "--preview", "--receipt", path])
    try:
        consumed = acquire_decision(
            current, action=smoke.ACTION, attempt_id=attempt, subject=receipt,
            decision_file=decision_file, kind=smoke.KIND, shown=shown,
            prompt=f"Do you attest that you yourself gave these trust and permission answers "
            f"for {receipt['session_id']}? Type yes to attest: ")
    except Stop as stop:
        raise window.Failed("decision", receipt["host"], "refused", str(stop),
                            observed="nothing was recorded",
                            next_command=["record-smoke", "--preview", "--receipt", path]) \
            from None
    smoke.record_smoke(state.current_window(window._root()), receipt, consumed)
    key = (receipt["host"], receipt["harness"], receipt["home"])
    print(f"{PROG}: record-smoke {current['id']}: recorded {smoke.label(*key, receipt['matrix'])}"
          f" with attestation {attempt} ({consumed['decision']['source']['type']})")
    print("\n".join(smoke.handoff(state.current_window(window._root()))))
    print(f"  observed: {_clean(window.status()['detail'])}")
    print(f"  next: {command_line(window.status()['next'])}")
    return 0


def _finish():
    current = state.current_window(window._root())
    if current is None or current["state"] in state.TERMINAL:
        report = window.status()
        raise window.Failed("finish", "titan", "refused", "no window is open to finish",
                            observed=report["detail"], next_command=report["next"])
    result = finishing.finish_window(current)
    record = result["window"]["finish"]
    print(f"{PROG}: finish {current['id']}: complete")
    print(f"  receipts: {len(smoke.REQUIRED)} smoke receipts validated: "
          + ", ".join(smoke.label(*key, matrix) for key, matrix in smoke.REQUIRED.items()))
    print("  checks: hooks, statusLine, installer and evidence verified on titan and europa "
          "(Claude pick keys may differ); familiar is the merge with its pinned relay")
    for host in window.HOST_ORDER:
        service = record["services"][host]
        print(f"  {host}: familiar-reap.timer restored to its original record; "
              f"{service['service']} Result={service['result']} "
              f"ExecMainStatus={service['exec_main_status']}")
    for host in window.HOST_ORDER:
        checked = record["checks"]["hosts"][host]["surfaces"]
        if checked is None:
            print(f"  {host}: familiar's surfaces: none (an explained absence)")
            continue
        verdicts = ", ".join(f"{name} {verdict}" for name, verdict in checked["verdicts"].items())
        print(f"  {host}: familiar's surfaces: {verdicts}")
    closure = record["closure"]
    print(f"  closure: recorded dead rows and their intent entries absent; the controller "
          f"{'kept its row' if closure['controller'] == 'kept' else 'had exited'}")
    print(f"  hold: {finishing.RELEASE}")
    print(f"  observed: {_clean(result['observed'])}")
    print(f"  next: {command_line(result['next'])}")
    return 0


def _reconcile_operations(host):
    """reconcile-operations: every unfinished operation on host, the owner-lost ones cancelled."""
    report = recovery.reconcile_operations(host)
    print(f"{PROG}: reconcile-operations {host}: {len(report['operations'])} unfinished "
          "operation(s)")
    for entry in report["operations"]:
        print(f"  {entry['operation_id']} ({entry['operation'] or 'unrecorded'}, window "
              f"{entry['window_id'] or 'none'}): {_clean(entry['outcome'])}")
    print(f"  observed: {_clean(report['observed'])}")
    print(f"  next: {command_line(report['next'])}")
    return 0 if report["settled"] else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=PROG, description="Prepare and check hq's closed-harness relay cutover.")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="record eligibility and the current inputs")
    prepare.add_argument("--controller-session", required=True,
                         help="the controller's native personal-home session ID")
    sub.add_parser("check", help="compare both hosts with the prepared record (read-only)")
    sub.add_parser("run", help="run the cutover through the verified migration and restart "
                   "familiar's surfaces (operator-run, from an ordinary terminal)")
    restart = sub.add_parser("restart-surfaces", help="restart familiar's surfaces still pending "
                             "after a verified migration, with this invocation's human decision")
    chosen = restart.add_mutually_exclusive_group()
    chosen.add_argument("--preview", action="store_true",
                        help="show the decision subject and its digest, changing nothing")
    chosen.add_argument("--decision-file", metavar="FILE",
                        help="the private record of the session ask and the human's reply")
    smoked = sub.add_parser("record-smoke", help="observe a smoke step, or record one home's "
                            "smoke receipt with the human's attestation")
    source = smoked.add_mutually_exclusive_group(required=True)
    source.add_argument("--observe", choices=window.HOST_ORDER, metavar="HOST",
                        help="record one read-only observation of HOST as smoke evidence")
    source.add_argument("--receipt", metavar="FILE", help="the private smoke receipt")
    smoked.add_argument("--cwd", metavar="DIR", help="the scratch repo an observation reads")
    answer = smoked.add_mutually_exclusive_group()
    answer.add_argument("--preview", action="store_true",
                        help="validate the receipt and show its attestation, changing nothing")
    answer.add_argument("--decision-file", metavar="FILE",
                        help="the private record of the session ask and the human's reply")
    sub.add_parser("finish", help="restore the original timers, run the scheduled "
                   "reconciliation and verify closure, once every smoke is recorded")
    sub.add_parser("recover", help="roll the window back to native (operator-run, from an "
                   "ordinary terminal)")
    sub.add_parser("status", help="report the prepared record, the window and the next command")
    reconcile = sub.add_parser("reconcile-operations", help="report every unfinished operation "
                               "on HOST and cancel only those whose owner died")
    reconcile.add_argument("--host", required=True, choices=window.HOST_ORDER)
    args = parser.parse_args(argv)
    try:
        if args.command in LIVE_COMMANDS:
            _no_pilot()
        if args.command == "prepare":
            return _prepare(args.controller_session)
        if args.command == "run":
            return _run()
        if args.command == "restart-surfaces":
            return _restart_surfaces(args.preview, args.decision_file)
        if args.command == "record-smoke":
            if args.observe is not None:
                if args.preview or args.decision_file is not None:
                    parser.error("--preview and --decision-file take --receipt")
                return _observe(args.observe, args.cwd)
            if args.cwd is not None:
                parser.error("--cwd takes --observe")
            return _record_smoke(args.receipt, args.preview, args.decision_file)
        if args.command == "finish":
            return _finish()
        if args.command == "recover":
            return _recover()
        if args.command == "reconcile-operations":
            return _reconcile_operations(args.host)
        return _check() if args.command == "check" else _status()
    except window.Failed as failed:
        _failure(args.command, failed, _handoff(args.command))
    except Stop as stop:
        _failure(args.command, window.Failed(args.command, "titan", "failed", str(stop),
                                             observed="unknown; run status",
                                             next_command=["status"]))
    return 1


# --- the rehearsal entry: tools/relay-cutover-rehearse --------------------------------------


def _pilot_hosts(offer):
    lines = []
    for host in window.HOST_ORDER:
        entry = offer["subject"]["hosts"].get(host)
        if entry is not None:
            lines.append(f"  {host}: through niri socket {_clean(entry['socket'])}, spawn the "
                         f"fixed command {surfaces.PROBE_COMMAND} (niri msg action spawn-sh -- "
                         f"{surfaces.PROBE_COMMAND})")
        else:
            lines.append(f"  {host}: exempt: {_clean(offer['exempt'].get(host))}")
    return lines


def _pilot_subject(record, offer):
    """The bounded consent subject of the pilot's spawn, as the preview and the terminal ask
    show it."""
    return [f"  pilot: window {record['id']} rehearses the cutover once in owned scratch roots on "
            "titan and europa, through the real host protocol", *_pilot_hosts(offer),
            f"  effect: {surfaces.PROBE_IMPACT}; the fixed command true exits at once",
            f"  duration: the rehearsal takes at most {surfaces.PROBE_SECONDS // 60} minutes",
            "  scratch: every application change stays in the scratch roots, removed at the end; "
            "real timers are only queried; live targets, surfaces, relay registries and "
            "harnesses are not touched; the prepared caches take writes"]


def _rehearse_preview(session):
    offer = pilot.preview(session)
    record = offer["window"]
    lines = [f"{REHEARSE_PROG}: preview of pilot window {record['id']}: it asks for this "
             "invocation's consent to one fixed no-window spawn", *_pilot_subject(record, offer),
             f"  decision: kind desktop, action {surfaces.PROBE_ACTION}, window_id {record['id']}, "
             f"attempt_id {offer['attempt_id']}, subject_sha256 {offer['sha256']}",
             "  ask: the user, in the session, naming these hosts, the fixed true spawn through "
             "niri IPC, that no window opens and the duration; record the actual ask and the "
             "human's reply (schema 1, verdict, and a session source with session_id, ask, reply "
             "and answered_at) in a private decision file. Without an approval the rehearsal "
             "runs every part but the spawn, whose gate stays pending",
             f"  observed: pilot window {record['id']} is open and prepared; no host was "
             "contacted",
             "  next: " + rehearse_line(["--controller-session", session, "--decision-file",
                                         DECISION_PLACEHOLDER])]
    print("\n".join(lines))
    return 0


def _rehearse_answer(current, decision_file):
    """This invocation's answer for an open pilot preview: the decision file's record, the
    operator's terminal answer, or none."""
    offer = current["pilot"]
    if decision_file is not None:
        record = _decision_file(decision_file)
    elif _unanswerable() is None:
        record = _ask(current, surfaces.PROBE_ACTION, offer["attempt_id"], offer["subject"],
                      offer["sha256"], shown="\n".join([
                          f"{REHEARSE_PROG}: pilot {current['id']} asks for this invocation's "
                          "consent to one fixed no-window spawn",
                          *_pilot_subject(current, offer)]) + "\n",
                      prompt=f"Spawn the fixed command true through niri for pilot "
                      f"{current['id']}? Type yes to approve: ",
                      tail="any answer but yes runs the rehearsal without the spawn")
    else:
        return None
    return pilot.answer(current, record)


def _gates(verdict):
    return ", ".join(f"{name} {gate['verdict']}" for name, gate in verdict["gates"].items())


def _rehearse_run(session, decision_file):
    current = state.current_window(window._root())
    answered = None
    if current is not None and current["mode"] == "pilot" and current["state"] == "prepared":
        try:
            answered = _rehearse_answer(current, decision_file)
        except Stop as stop:
            raise window.Failed("decision", "titan", "refused", str(stop),
                                observed=f"nothing was changed; pilot window {current['id']} "
                                "is prepared",
                                next_command=[window.REHEARSE, "--controller-session", session,
                                              "--preview"]) from None
    elif decision_file is not None:
        raise window.Failed("decision", "titan", "refused", "a decision file answers only an "
                            "open pilot preview", observed="nothing was changed",
                            next_command=[window.REHEARSE, "--controller-session", session,
                                          "--preview"])
    verdict = pilot.rehearse(session, answered)
    record = verdict["window"]
    lines = [f"{REHEARSE_PROG}: pilot {record['id']}: {verdict['verdict']}"]
    failure = verdict["failure"]
    if failure is not None:
        lines += [f"  step: {failure['step']}", f"  host: {failure['host']}",
                  f"  status: {failure['status']}", f"  error: {_clean(failure['error'])}",
                  f"  log: {failure['log'] or 'none'}"]
    spawn = verdict["gates"]["spawn"]
    lines.append("  spawn: " + ", ".join(
        f"{host} {entry['verdict']}" for host, entry in spawn.get("hosts", {}).items())
        + (f" ({spawn['reason']})" if spawn.get("reason") else ""))
    lines.append(f"  gates: {_gates(verdict)}")
    lines.append("  caches: " + "; ".join(
        f"{host} " + ", ".join(f"{key}={_clean(value)}" for key, value in sorted(prefixes.items()))
        for host, prefixes in verdict["permitted_writes"]["caches"].items()))
    lines.append(f"  unexercised: {', '.join(verdict['unexercised'])} (fixtures and the live "
                 "window cover them; the whole host is not claimed byte-equal)")
    observed = (f"pilot window {record['id']} is {record['state']}; every scratch root was "
                "removed" if verdict["closed"] else f"pilot window {record['id']} is "
                f"{record['state']}: its scratch roots are not all removed; rehearse reconciles "
                "it again")
    lines.append(f"  observed: {observed}")
    lines.append(f"  verdict: {verdict['verdict']} ({verdict['path']})")
    if not verdict["closed"]:
        following = [window.REHEARSE, "--controller-session", session]
    elif verdict["verdict"] == "passed":
        following = window.status()["next"]
    else:
        following = [window.REHEARSE, "--controller-session", session, "--preview"]
    lines.append(f"  next: {command_line(following)}")
    print("\n".join(lines))
    return 0 if verdict["verdict"] == "passed" else 1


def rehearse_main(argv: list[str]) -> int:
    """tools/relay-cutover-rehearse: the pilot's preview, then its run."""
    parser = argparse.ArgumentParser(
        prog=REHEARSE_PROG, description="Rehearse hq's relay cutover once in owned scratch roots "
        "on both hosts, through the real host protocol.")
    parser.add_argument("--controller-session", required=True,
                        help="the calling agent's native session ID")
    chosen = parser.add_mutually_exclusive_group()
    chosen.add_argument("--preview", action="store_true",
                        help="allocate the pilot window and show its spawn's consent subject")
    chosen.add_argument("--decision-file", metavar="FILE",
                        help="the private record of the session ask and the human's reply")
    args = parser.parse_args(argv)
    try:
        if args.preview:
            return _rehearse_preview(args.controller_session)
        return _rehearse_run(args.controller_session, args.decision_file)
    except window.Failed as failed:
        _failure("rehearse", failed, prog=REHEARSE_PROG)
    except Stop as stop:
        _failure("rehearse", window.Failed("rehearse", "titan", "failed", str(stop),
                                           observed="unknown; run status",
                                           next_command=["status"]), prog=REHEARSE_PROG)
    return 1
