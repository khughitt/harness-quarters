"""Argument parsing and phase messages for tools/relay-cutover-bootstrap.

`prepare --controller-session ID` records eligibility and the current inputs; `check`
compares both hosts with that record without changing them; `status` reads the local records
and names the one next command. A stopped command prints its step, host, status, private log,
observed state and one next command, then returns 1 to the calling shell. It never prints
settings, plans, environments, credentials or child output."""
import argparse
import shlex
import sys

from . import prepare as preparation
from . import window
from .state import Stop

PROG = "relay-cutover-bootstrap"
LIMIT = 500
SHOWN = 40


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
    sub.add_parser("status", help="report the prepared record, the window and the next command")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args.controller_session)
        return _check() if args.command == "check" else _status()
    except window.Failed as failed:
        _failure(args.command, failed)
    except Stop as stop:
        _failure(args.command, window.Failed(args.command, "titan", "failed", str(stop),
                                             observed="unknown; run status",
                                             next_command=["status"]))
    return 1
