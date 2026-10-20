"""Argument parsing, the human decision and phase messages for tools/relay-cutover-bootstrap.

`prepare --controller-session ID` records eligibility and the current inputs; `check`
compares both hosts with that record without changing them; `run` opens a window, takes this
invocation's desktop decision and runs through the verified migration; `status` reads the local
records and names the one next command. A stopped command prints its step, host, status, private
log, observed state and one next command, then returns 1 to the calling shell. It never prints
settings, plans, environments, credentials or child output.

A decision comes from the operator's terminal (`/dev/tty`: a bounded preview of its subject,
then an explicit answer recorded as a `tty` source) or from `--decision-file FILE`, the private
record of an actual session ask and reply for this window. Without either, the command stops
with instructions before any change. `acquire_decision` consumes it once, before the first
authorized action; no flag or default answers for the operator."""
import argparse
import json
import os
import shlex
import stat
import sys
from datetime import datetime, timezone

from . import prepare as preparation
from . import state, window
from .state import Stop

PROG = "relay-cutover-bootstrap"
LIMIT = 500
SHOWN = 40
TTY = "/dev/tty"
ANSWER_BYTES = 200
DECISION_BYTES = 65536
APPROVE = ("y", "yes")
NO_TERMINAL = ("this invocation has no terminal for the operator's answer; run it from the "
               "operator's own shell, or ask in the session, record the actual reply for this "
               "window and pass --decision-file")


def _clean(text):
    return "".join(ch if ch.isprintable() else " " for ch in str(text))[:LIMIT]


def command_line(argv):
    """A complete command for the operator: this checkout's bootstrap and its arguments."""
    words = [shlex.quote(str(window.CHECKOUT / window.BOOTSTRAP))]
    words += [arg if arg == window.SESSION_PLACEHOLDER else shlex.quote(arg) for arg in argv]
    return " ".join(words)


def _failure(command, failed):
    lines = [f"{PROG}: {command} stopped", f"  step: {failed.step}", f"  host: {failed.host}",
             f"  status: {failed.status}", f"  error: {_clean(failed.error)}",
             f"  log: {failed.log or 'none'}",
             f"  observed: {_clean(failed.observed or 'unknown; run status')}"]
    if failed.blockers:
        lines.append("  blockers:")
        lines += [f"    - {_clean(blocker)}" for blocker in failed.blockers[:SHOWN]]
        if len(failed.blockers) > SHOWN:
            lines.append(f"    - and {len(failed.blockers) - SHOWN} more")
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


def _preview(opened, subject):
    """The bounded subject an operator approves: each host's surfaces, impact and duration."""
    lines = [f"{PROG}: run {opened['id']} asks for this invocation's desktop consent"]
    for host, desktop in subject["hosts"].items():
        if desktop["state"] != "present":
            reason = desktop["absence_reason"] or "no familiar surface is configured or running"
            lines.append(f"  {host}: nothing restarts ({_clean(reason)})")
            continue
        lines.append(f"  {host}: through niri socket {_clean(desktop['socket'])}, restart:")
        for surface in desktop["surfaces"]:
            processes = ", ".join(f"pid {process['pid']}: {_clean(shlex.join(process['argv']))}"
                                  for process in surface["processes"]) or "not running"
            lines.append(f"    {surface['name']} ({processes})")
    lines.append(f"  impact: {subject['impact']}; about {subject['duration_seconds']} s per host")
    lines.append("  nothing has changed yet; any answer but yes stops before any change")
    return "\n".join(lines) + "\n"


def _ask(opened, action, attempt_id, subject, digest):
    """One explicit answer on the operator's terminal, as a decision record."""
    try:
        fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC)
    except OSError:
        raise Stop(NO_TERMINAL) from None
    prompt = f"Restart these familiar surfaces during run {opened['id']}? Type yes to approve: "
    try:
        if not os.isatty(fd):
            raise Stop(NO_TERMINAL)
        os.write(fd, (_preview(opened, subject) + prompt).encode("utf-8"))
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
                     decision_file: str | None) -> dict:
    """This invocation's one desktop decision for `opened`, consumed before it authorizes."""
    digest = state._digest(subject)
    record = (_decision_file(decision_file) if decision_file is not None
              else _ask(opened, action, attempt_id, subject, digest))
    return state.consume_decision(opened, record, kind="desktop", action=action,
                                  attempt_id=attempt_id, subject_sha256=digest)


HANDOFF = (
    "  timers: familiar-reap.timer stays paused on titan and europa until finish",
    "  hold: until finish, use only the bootstrap's printed held commands; avoid cl, clw, "
    "unheld Claude or IDE clients, and update or install commands",
    "  picks: until finish reports complete, do not change or save Claude model or effort "
    "defaults in either home on either host, including through /model or /effort",
)


def _run(decision_file):
    prepared = preparation.load_prepared()
    opened = window.open_window(prepared)
    try:
        decision = acquire_decision(opened, action=window.RUN_ACTION,
                                    attempt_id=window.RUN_ATTEMPT,
                                    subject=window.run_subject(prepared),
                                    decision_file=decision_file)
    except Stop as stop:
        outcome = window.abort_window(state.current_window(window._root()))
        raise window.Failed("decision", "titan", "refused", str(stop),
                            observed=f"nothing was changed; window {opened['id']} is "
                            f"{outcome['state']}", next_command=["run"]) from None
    migrated = window.run_window(prepared, decision)
    merge = migrated["familiar"]["merge"]
    print(f"{PROG}: run {migrated['id']}: migration verified; familiar's surfaces are pending")
    print(f"  familiar: merged {merge} once on titan; each host installed and proved its relay "
          "dependency after the merge reached it")
    print("  settings: claude, claude-work, codex and codex-work applied once on titan to the "
          "sealed dry-run bytes; europa's Claude copies verified after synchronization")
    print("\n".join(HANDOFF))
    print(f"  observed: window {migrated['id']} is {migrated['state']}")
    print(f"  next: {command_line(['restart-surfaces'])}")
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=PROG, description="Prepare and check hq's closed-harness relay cutover.")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="record eligibility and the current inputs")
    prepare.add_argument("--controller-session", required=True,
                         help="the controller's native personal-home session ID")
    sub.add_parser("check", help="compare both hosts with the prepared record (read-only)")
    run = sub.add_parser("run", help="run the cutover through the verified migration")
    run.add_argument("--decision-file", help="the recorded session ask and reply for this "
                     "run's desktop decision, when no operator terminal answers")
    sub.add_parser("status", help="report the prepared record, the window and the next command")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args.controller_session)
        if args.command == "run":
            return _run(args.decision_file)
        return _check() if args.command == "check" else _status()
    except window.Failed as failed:
        _failure(args.command, failed)
    except Stop as stop:
        _failure(args.command, window.Failed(args.command, "titan", "failed", str(stop),
                                             observed="unknown; run status",
                                             next_command=["status"]))
    return 1
