"""Argument parsing, the human decision and phase messages for tools/relay-cutover-bootstrap.

`prepare --controller-session ID` records eligibility and the current inputs; `check`
compares both hosts with that record without changing them; `run` opens a window, takes this
invocation's desktop decision, runs through the verified migration and restarts familiar's
surfaces with that same decision; `restart-surfaces` retries surfaces still pending after a
verified migration; `recover` rolls a window back to native; `status` reads the local records and
names the one next command. A stopped command prints its step, host, status, private log,
observed state and one next command, then returns 1 to the calling shell. It never prints
settings, plans, environments, credentials or child output.

`run` and `recover` are operator-run: their desktop decision comes only from the operator's
terminal (`/dev/tty`: a bounded preview of its subject, then an explicit answer recorded as a
`tty` source), and they take no decision file. Without a terminal they stop with instructions
before any change. `restart-surfaces` takes the operator's terminal answer too, or a decision
file: the private record of an actual session ask and the human's reply, about the subject that
`restart-surfaces --preview` shows read-only. Without either it stops with those instructions
before any change. Each invocation consumes its one decision before the first authorized action;
no flag or default answers for the operator."""
import argparse
import json
import os
import shlex
import stat
import sys
from datetime import datetime, timezone

from . import prepare as preparation
from . import hosts, recovery, state, surfaces, window
from .state import Stop

PROG = "relay-cutover-bootstrap"
LIMIT = 500
SHOWN = 40
TTY = "/dev/tty"
ANSWER_BYTES = 200
DECISION_BYTES = 65536
APPROVE = ("y", "yes")
DECISION_PLACEHOLDER = "<decision-file>"
NO_TERMINAL = ("run is operator-run and this invocation has no terminal for the operator's "
               "answer: the operator launches it from an ordinary terminal, with every Claude "
               "and Codex session closed on both hosts")
RECOVER_NO_TERMINAL = ("recover is operator-run and this invocation has no terminal for the "
                       "operator's answer: the operator runs it from an ordinary terminal, with "
                       "every Claude and Codex session closed on both hosts")
NO_DECISION = ("restart-surfaces needs this invocation's human decision and has no terminal to "
               "ask on: preview its subject with restart-surfaces --preview, ask the user in the "
               "session naming those hosts, surfaces, impact and duration, record the actual ask "
               "and reply in a private decision file and pass it with --decision-file")


def _clean(text):
    return "".join(ch if ch.isprintable() else " " for ch in str(text))[:LIMIT]


def command_line(argv):
    """A complete command for the operator: this checkout's bootstrap and its arguments."""
    words = [shlex.quote(str(window.CHECKOUT / window.BOOTSTRAP))]
    words += [arg if arg in (window.SESSION_PLACEHOLDER, DECISION_PLACEHOLDER)
              else shlex.quote(arg) for arg in argv]
    return " ".join(words)


def _failure(command, failed, handoff=()):
    lines = [f"{PROG}: {command} stopped", f"  step: {failed.step}", f"  host: {failed.host}",
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


def _prepare(session):
    prepared = preparation.prepare(session)
    print(f"{PROG}: prepared {window._root() / window.PREPARED} "
          f"(sha256 {window.prepared_sha256(prepared)})")
    print(f"  inputs: generation {prepared['manifest']['generation']}; Claude picks "
          f"({', '.join(prepared['filter']['keys'])}) recorded as found")
    for host in window.HOST_ORDER:
        print(f"  {host}: {_sessions(prepared['hosts'][host]['sessions'])}")
    print("  observed: no window is open; only the prepared record and private operation "
          "records were written")
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
    print("  observed: nothing was changed")
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
         changes=None):
    """One explicit answer on the operator's terminal, as a decision record."""
    try:
        fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC)
    except OSError:
        raise Stop(NO_TERMINAL) from None
    prompt = prompt or (f"Restart these familiar surfaces during run {opened['id']}? Type yes "
                        "to approve: ")
    try:
        if not os.isatty(fd):
            raise Stop(NO_TERMINAL)
        shown = _preview(opened, subject, title, changes)
        os.write(fd, (shown + "  nothing has changed yet; any answer but yes stops before any "
                      "change\n" + prompt).encode("utf-8"))
        try:
            answer = os.read(fd, ANSWER_BYTES).decode("utf-8", "replace").strip()
        except KeyboardInterrupt:
            raise Stop("interrupted before an answer; nothing is authorized") from None
    finally:
        os.close(fd)
    if not answer:
        raise Stop("no answer was given; nothing is authorized")
    return {"schema": 1, "kind": "desktop", "action": action, "window_id": opened["id"],
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


def _decision_file(path):
    """A private decision record: this user's regular file, closed to writes by others."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise Stop(f"the decision file cannot be opened ({error.strerror})") from None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise Stop("the decision file must be this user's regular file, closed to writes "
                       "by others")
        data = stream.read(DECISION_BYTES + 1)
    if len(data) > DECISION_BYTES:
        raise Stop("the decision file is too large to be one decision record")
    try:
        return json.loads(data, object_pairs_hook=state._unique,
                          parse_constant=state._constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Stop("the decision file is not one JSON decision record") from None


def acquire_decision(opened: dict, *, action: str, attempt_id: str, subject: dict,
                     decision_file: str | None, title: str | None = None,
                     prompt: str | None = None, changes: dict | None = None) -> dict:
    """This invocation's one desktop decision for `opened`, consumed before it authorizes: the
    decision file's record, or the operator's answer to the bounded preview on the terminal."""
    digest = state._digest(subject)
    record = (_decision_file(decision_file) if decision_file is not None
              else _ask(opened, action, attempt_id, subject, digest, title=title, prompt=prompt,
                        changes=changes))
    return state.consume_decision(opened, record, kind="desktop", action=action,
                                  attempt_id=attempt_id, subject_sha256=digest)


HANDOFF = (
    "  timers: familiar-reap.timer stays paused on titan and europa until finish",
    "  hold: until finish, use only the bootstrap's printed held commands; avoid cl, clw, "
    "unheld Claude or IDE clients, and update or install commands",
    "  picks: until finish reports complete, do not change or save Claude model or effort "
    "defaults in either home on either host, including through /model or /effort",
)


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
        print("\n".join(HANDOFF))
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
    print("\n".join(HANDOFF))
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
    if current["state"] == "migrated-surfaces-pending" or recovery.reconcilable(current):
        return current
    reason = ("its surfaces were already restarted" if current["state"] == "ready-for-smokes"
              else "familiar's surfaces restart only after a verified migration")
    raise window.Failed("restart-surfaces", "titan", "blocked", f"window {current['id']} is "
                        f"{current['state']}; {reason}", observed=report["detail"],
                        next_command=report["next"])


def _surface_preview(current):
    """Read-only: the subject a decision for the next restart-surfaces must approve."""
    offered = surfaces.preview(current, surfaces.RESTART_ACTION)
    changes = {host: found["changes"] for host, found in offered["observed"].items()}
    print(_preview(current, offered["subject"], f"{PROG}: restart-surfaces preview for window "
                   f"{current['id']} (read-only)", changes), end="")
    if current["state"] != "migrated-surfaces-pending":
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
    if decision_file is None and not _terminal():
        raise window.Failed("decision", "titan", "refused", NO_DECISION,
                            observed="nothing was changed",
                            next_command=["restart-surfaces", "--preview"])
    if current["state"] != "migrated-surfaces-pending":
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
    print("\n".join(HANDOFF))
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
    if not _terminal():
        raise window.Failed("decision", "titan", "refused", RECOVER_NO_TERMINAL,
                            observed="nothing was changed", next_command=["recover"])
    offered = surfaces.preview(current, surfaces.RECOVER_ACTION)
    consumed = None
    if any(offered["subject"]["restart"].values()):
        try:
            consumed = acquire_decision(
                current, action=surfaces.RECOVER_ACTION, attempt_id=offered["attempt_id"],
                subject=offered["subject"], decision_file=None,
                title=f"{PROG}: recover {current['id']} asks for this invocation's desktop "
                "consent, once native settings, source and dependencies are restored",
                prompt=f"Restart these familiar surfaces while recovering window "
                f"{current['id']}? Type yes to approve: ",
                changes={host: found["changes"] for host, found in offered["observed"].items()})
        except Stop as stop:
            raise window.Failed("decision", "titan", "refused", str(stop), observed=(
                f"nothing was changed; window {current['id']} is {current['state']}"),
                next_command=["recover"]) from None
        current = surfaces.bind(state.current_window(root), consumed, offered["subject"])
    result = recovery.recover_window(current, consumed)
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
    print(f"  next: {command_line(report['next'])}")
    return 0


def _handoff(command):
    """The handoff a stopped run or restart-surfaces prints while only surfaces are pending."""
    if command not in ("run", "restart-surfaces"):
        return ()
    try:
        current = state.current_window(window._root())
    except Stop:
        return ()
    if current is None or current["state"] != "migrated-surfaces-pending":
        return ()
    return HANDOFF


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
    sub.add_parser("recover", help="roll the window back to native (operator-run, from an "
                   "ordinary terminal)")
    sub.add_parser("status", help="report the prepared record, the window and the next command")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args.controller_session)
        if args.command == "run":
            return _run()
        if args.command == "restart-surfaces":
            return _restart_surfaces(args.preview, args.decision_file)
        if args.command == "recover":
            return _recover()
        return _check() if args.command == "check" else _status()
    except window.Failed as failed:
        _failure(args.command, failed, _handoff(args.command))
    except Stop as stop:
        _failure(args.command, window.Failed(args.command, "titan", "failed", str(stop),
                                             observed="unknown; run status",
                                             next_command=["status"]))
    return 1
