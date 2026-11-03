"""`hq pause status` and `hq pause limits`: the agent-visible surface of the turn pause.

Allowed even while paused, so it only reads state. Imports stay light: the turn_pause
modules it needs are the hook's own cheap ones.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turn_pause import adapters, limits  # noqa: E402
from turn_pause.state import StateError, Store, state_dir  # noqa: E402

HARNESSES = ("claude-code", "codex")
COUNTS = ("calls", "spawns", "compactions")


class PauseError(Exception):
    pass


def add_parser(commands) -> None:
    pause = commands.add_parser("pause", help="show the turn pause counters and limits",
                                description="Turn pause: counters and limits for the current root session.")
    sub = pause.add_subparsers(dest="pause_command", required=True)
    status = sub.add_parser("status", help="this tree's counts, limits, pause and notification state")
    status.add_argument("--session", help="root or worker session id (default: $CODEX_THREAD_ID, "
                                          "else the newest state for the current directory)")
    status.add_argument("--json", action="store_true")
    show = sub.add_parser("limits", help="the default turn limits")
    show.add_argument("--json", action="store_true")


def find(store: Store, session: str | None, env, cwd: str):
    """(state, what was looked for). A session id may be a root or a worker of a root."""
    session = session or env.get("CODEX_THREAD_ID") or None
    if session is not None:
        for harness in HARNESSES:
            root = store.root_for_agent(harness, session) or session
            state = store.read(harness, root)
            if state is not None:
                return state, ""
        return None, f"session {session!r}"
    found = store.latest_for_cwd(cwd)
    if found is not None:
        return store.read(*found), ""
    return None, f"a state for cwd {cwd!r}"


def notify_text(state) -> str:
    if state.notify_error:
        return "error: " + " ".join(state.notify_error.split())
    return "pending" if state.paused and not state.notified else "ok"


def counted(state) -> dict:
    """Whether the harness's hook keeps each count; compactions only when it has a compact event."""
    events = adapters.load_facts().compact_events[state.harness]
    return {"compactions": bool(events)}


def status(args, env) -> str:
    directory = str(state_dir(env))
    state, looked = find(Store(directory), args.session, env, os.getcwd())
    if state is None:
        raise PauseError(f"no pause state in {directory} for {looked}")
    if state.turn is None:
        raise PauseError(f"{state.harness} session {state.root} has pause state but no turn started")
    turn, lim = state.turn, state.turn.limits
    kept = counted(state)
    if args.json:
        data = {"harness": state.harness, "root": state.root,
                "active": {"used": turn.active, "limit": lim.active_seconds}}
        for name in COUNTS:
            used = getattr(turn, name) if kept.get(name, True) else None
            data[name] = {"used": used, "limit": getattr(lim, name)}
        data.update(paused=state.paused, budget=state.budget_note, notify=notify_text(state))
        return json.dumps(data)
    compactions = (f"{turn.compactions}/{lim.compactions}" if kept["compactions"]
                   else f"-/{lim.compactions} (count your own)")
    return (f"active {limits.duration(turn.active)}/{limits.duration(lim.active_seconds)} calls {turn.calls}/{lim.calls} "
            f"spawns {turn.spawns}/{lim.spawns} compactions {compactions} "
            f"paused:{state.paused or 'no'} budget:{state.budget_note or 'none'} notify:{notify_text(state)}")


def show_limits(args) -> str:
    lim, _ = limits.load(limits.DEFAULTS_PATH)
    if args.json:
        return json.dumps(lim._asdict())
    return (f"active {limits.duration(lim.active_seconds)} calls {lim.calls} spawns {lim.spawns} "
            f"compactions {lim.compactions}")


def run(args) -> int:
    try:
        text = status(args, os.environ) if args.pause_command == "status" else show_limits(args)
    except (PauseError, StateError, OSError, ValueError, KeyError) as error:
        print(f"hq: {error}", file=sys.stderr)
        return 1
    print(text)
    return 0
