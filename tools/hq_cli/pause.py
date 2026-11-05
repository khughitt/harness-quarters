"""`hq pause status|limits|history|list`: the agent and reporting surface of the turn pause.

Allowed even while paused (`status` and `limits` as bookkeeping; `history` and `list` as
grace-spending reads), so it only reads state. Imports stay light: the turn_pause
modules it needs are the hook's own cheap ones.
"""
from datetime import datetime, timezone
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turn_pause import adapters, history as hist_mod, limits  # noqa: E402
from turn_pause.state import (  # noqa: E402
    ENDED_SECONDS,
    IDLE_SECONDS,
    MAX_BYTES,
    MAX_ENDED,
    MAX_EVENTS,
    MAX_MAINTENANCE,
    StateError,
    Store,
    state_dir,
)

HARNESSES = ("claude-code", "codex")
COUNTS = ("calls", "spawns", "compactions")
GUIDANCE = ("Calls count root attempts only; spawns count the whole tree; compactions count the root. "
            "Active time includes in-flight worker tools. Use the hook snapshot for counted metrics; "
            "keep unhooked counts separate. A warning calls for a concise status update and preparation "
            "while authorized work continues; it is not a pause or a new approval gate. "
            "A count pauses the turn only when strictly above its limit; reaching a limit is allowed. "
            "Other genuine human gates still apply.")


class PauseError(Exception):
    pass


def _add_history_filters(parser) -> None:
    parser.add_argument("--session", help="root session id (default: all locally available root records)")
    parser.add_argument("--harness", choices=HARNESSES, help="filter by harness")
    parser.add_argument("--since", help="inclusive lower bound (RFC 3339 timestamp with UTC offset)")
    parser.add_argument("--until", help="exclusive upper bound (RFC 3339 timestamp with UTC offset)")
    parser.add_argument("-n", dest="limit", type=int, default=50, help="maximum rows to return (1..1000, default: 50)")
    parser.add_argument("--json", action="store_true")


def add_parser(commands) -> None:
    pause = commands.add_parser("pause", help="show the turn pause counters, limits and transition history",
                                description="Turn pause: counters, limits and durable transition history. " + GUIDANCE)
    sub = pause.add_subparsers(dest="pause_command", required=True)
    status = sub.add_parser("status", help="this tree's counts, limits, pause and notification state",
                            description=GUIDANCE)
    status.add_argument("--session", help="root or worker session id (default: $CODEX_THREAD_ID, "
                                          "else the newest state for the current directory)")
    status.add_argument("--json", action="store_true")
    show = sub.add_parser("limits", help="the default turn limits", description=GUIDANCE)
    show.add_argument("--json", action="store_true")
    hist = sub.add_parser("history", help="bounded turn-pause transition events across local root records",
                          description=GUIDANCE)
    _add_history_filters(hist)
    lst = sub.add_parser("list", help="root/generation/turn summaries across local root records",
                         description=GUIDANCE)
    _add_history_filters(lst)


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
    compactions = (f"{turn.compactions}/{lim.compactions} (advisory)" if kept["compactions"]
                   else f"-/{lim.compactions} (advisory, unhooked)")
    return (f"active {limits.duration(turn.active)}/{limits.duration(lim.active_seconds)} root calls {turn.calls}/{lim.calls} "
            f"tree spawns {turn.spawns}/{lim.spawns} root compactions {compactions} "
            f"paused:{state.paused or 'no'} budget:{state.budget_note or 'none'} notify:{notify_text(state)}")


def show_limits(args) -> str:
    lim, _ = limits.load(limits.DEFAULTS_PATH)
    if args.json:
        return json.dumps(lim._asdict())
    return (f"active {limits.duration(lim.active_seconds)} root calls {lim.calls} tree spawns {lim.spawns} "
            f"root compactions {lim.compactions} (advisory)")


def _fmt_ts(epoch: float | None) -> str:
    if epoch is None:
        return "none"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_rfc3339(raw: str | None, flag: str) -> tuple[float | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, str) or raw.strip() != raw or ("T" not in raw and "t" not in raw):
        raise PauseError(f"invalid {flag} timestamp {raw!r}: must be RFC 3339 with an explicit UTC offset")
    norm = raw[:-1] + "+00:00" if raw[-1:] in ("Z", "z") else raw
    try:
        dt = datetime.fromisoformat(norm)
    except ValueError as e:
        raise PauseError(f"invalid {flag} timestamp {raw!r}: {e}") from e
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise PauseError(f"invalid {flag} timestamp {raw!r}: explicit UTC offset required")
    utc_dt = dt.astimezone(timezone.utc)
    return float(utc_dt.timestamp()), utc_dt.isoformat().replace("+00:00", "Z")


def _validate_query(args) -> tuple[str | None, str | None, float | None, str | None, float | None, str | None, int]:
    limit = getattr(args, "limit", 50)
    if type(limit) is not int or not (1 <= limit <= 1000):
        raise PauseError(f"limit -n must be between 1 and 1000, got {limit!r}")
    session = getattr(args, "session", None)
    if session is not None:
        if not isinstance(session, str) or not session or "/" in session or session in (".", "..") or "\0" in session:
            raise PauseError(f"invalid root session id {session!r}")
    harness = getattr(args, "harness", None)
    if harness is not None and harness not in HARNESSES:
        raise PauseError(f"invalid harness {harness!r}")
    since_at, since_iso = _parse_rfc3339(getattr(args, "since", None), "--since")
    until_at, until_iso = _parse_rfc3339(getattr(args, "until", None), "--until")
    if since_at is not None and until_at is not None and since_at >= until_at:
        raise PauseError("--since must be earlier than --until")
    return session, harness, since_at, since_iso, until_at, until_iso, limit


def _fmt_snap(snap: dict | None) -> str:
    if snap is None:
        return "snapshot:none"
    act = snap["active"]
    calls = snap["calls"]
    spawns = snap["spawns"]
    comp = snap["compactions"]
    comp_txt = (f"{comp['used']}/{comp['limit']}" if snap["counted"]["compactions"]
                else f"-/{comp['limit']} (unhooked)")
    return (f"active {limits.duration(act['used'])}/{limits.duration(act['limit'])} "
            f"root calls {calls['used']}/{calls['limit']} "
            f"tree spawns {spawns['used']}/{spawns['limit']} "
            f"root compactions {comp_txt}")


def _collect(args, env, mode: str) -> str:
    session, harness, since_at, since_iso, until_at, until_iso, limit = _validate_query(args)
    now = time.time()
    directory = str(state_dir(env))
    store = Store(directory)
    diagnostics: list[str] = []
    matching = []
    disappeared = 0
    idle_all = []
    ended_all = []

    store_exists = os.path.exists(directory)
    if not store_exists:
        diagnostics.append("local pause state directory does not exist")
    else:
        if not os.path.isdir(directory):
            raise PauseError(f"pause state path is not a directory: {directory}")
        try:
            names = sorted(n for n in os.listdir(directory) if n.endswith(".json") and not n.startswith("."))
        except OSError as e:
            raise StateError(f"cannot list {directory}: {e}") from e
        for name in names:
            path = os.path.join(directory, name)
            record = store._load(path)
            if record is None:
                disappeared += 1
                diagnostics.append(f"catalog entry disappeared during scan: {name}")
                continue
            if record.state is None:
                if record.ended_at is None:
                    raise StateError("ended pause record has no ended_at")
                ended_all.append((record.ended_at, path, record.generation))
            else:
                try:
                    mtime = os.stat(path).st_mtime
                except FileNotFoundError:
                    mtime = now
                if now - mtime > IDLE_SECONDS:
                    idle_all.append((mtime, path, record.generation))
            if (harness is None or record.harness == harness) and (session is None or record.root == session):
                matching.append(record)

    ended_all.sort()
    excess = max(0, len(ended_all) - MAX_ENDED)
    deletions = [row for i, row in enumerate(ended_all) if i < excess or now - row[0] > ENDED_SECONDS]
    cleanup_debt = len(idle_all) + len(deletions)

    active_roots = sum(1 for r in matching if r.state is not None)
    ended_roots = sum(1 for r in matching if r.state is None)
    created_min = min((r.created_at for r in matching), default=None)
    retained_ats = [e["at"] for r in matching for e in r.events]
    retained_min = min(retained_ats, default=None)
    retained_max = max(retained_ats, default=None)

    dropped_total = 0
    dropped_through_max = None
    dropped_roots = []
    unobserved_roots = 0
    for r in matching:
        if r.dropped_count > 0:
            dropped_total += r.dropped_count
            if r.dropped_through is not None:
                dropped_through_max = r.dropped_through if dropped_through_max is None else max(dropped_through_max, r.dropped_through)
            dropped_roots.append({
                "harness": r.harness,
                "root": r.root,
                "generation": r.generation,
                "dropped_count": r.dropped_count,
                "dropped_through": r.dropped_through,
            })
            diagnostics.append(
                f"{r.harness}:{r.root} generation {r.generation} dropped {r.dropped_count} oldest event(s) through {_fmt_ts(r.dropped_through)}"
            )
        if r.turn_serial == 0 or not r.events:
            unobserved_roots += 1
            diagnostics.append(
                f"{r.harness}:{r.root} generation {r.generation} has no observed turn or transition events"
            )

    def in_window(at: float) -> bool:
        return (since_at is None or at >= since_at) and (until_at is None or at < until_at)

    if mode == "history":
        all_events = [dict(e) for r in matching for e in r.events if in_window(e["at"])]
        all_events.sort(
            key=lambda e: (e["at"], e["harness"], e["root"], e["generation"], e["turn"], e["sequence"]),
            reverse=True,
        )
        truncated_by_limit = len(all_events) > limit
        rows = all_events[:limit]
        truncated = bool(truncated_by_limit or dropped_total > 0)
        if truncated_by_limit:
            diagnostics.append(f"events truncated to {limit} of {len(all_events)} matching rows")
        row_key = "events"
    else:
        all_summaries = []
        for r in matching:
            by_turn: dict[int, list[dict]] = {}
            for e in r.events:
                if in_window(e["at"]):
                    by_turn.setdefault(e["turn"], []).append(e)
            for turn_num, turn_events in by_turn.items():
                first_ev, last_ev = turn_events[0], turn_events[-1]
                start_ev = next((e for e in turn_events if e["kind"] == "turn_start"), None)
                end_ev = next(
                    (e for e in reversed(turn_events) if e["kind"] in ("turn_reset", "turn_resume", "session_end")),
                    None,
                )
                last_snap = next((e["snapshot"] for e in reversed(turn_events) if e["snapshot"] is not None), None)
                last_notice = next((e["notification"] for e in reversed(turn_events) if e["notification"] is not None), None)
                pause_reason = next((e["reason"] for e in turn_events if e["kind"] == "enforced_pause"), None)
                warnings = [e["reason"] for e in turn_events if e["kind"] == "warning"]
                turn_truncated = bool(
                    start_ev is None or (r.dropped_count > 0 and first_ev["sequence"] <= r.dropped_count + 1)
                )
                all_summaries.append({
                    "harness": r.harness,
                    "root": r.root,
                    "generation": r.generation,
                    "turn": turn_num,
                    "host": last_ev["host"],
                    "started_at": None if start_ev is None else start_ev["at"],
                    "origin": None if start_ev is None else start_ev["reason"],
                    "ended_at": None if end_ev is None else end_ev["at"],
                    "end_kind": None if end_ev is None else end_ev["kind"],
                    "end_reason": None if end_ev is None else end_ev["reason"],
                    "first_event_at": first_ev["at"],
                    "last_event_at": last_ev["at"],
                    "last_sequence": last_ev["sequence"],
                    "event_count": len(turn_events),
                    "event_kinds": [e["kind"] for e in turn_events],
                    "warnings": warnings,
                    "enforced_pause": pause_reason,
                    "notification": last_notice,
                    "snapshot": last_snap,
                    "root_active": r.state is not None and r.ended_at is None,
                    "root_ended_at": r.ended_at,
                    "truncated": turn_truncated,
                })
        all_summaries.sort(
            key=lambda s: (s["last_event_at"], s["harness"], s["root"], s["generation"], s["turn"], s["last_sequence"]),
            reverse=True,
        )
        truncated_by_limit = len(all_summaries) > limit
        rows = all_summaries[:limit]
        truncated = bool(truncated_by_limit or dropped_total > 0 or any(s["truncated"] for s in rows))
        if truncated_by_limit:
            diagnostics.append(f"summaries truncated to {limit} of {len(all_summaries)} matching rows")
        row_key = "summaries"

    if not store_exists:
        cov_status = "unavailable"
    elif disappeared > 0 or dropped_total > 0 or unobserved_roots > 0:
        cov_status = "partial"
    else:
        cov_status = "available"

    envelope = {
        "version": 1,
        "observed_at": now,
        "host": os.uname().nodename,
        "coverage": {
            "status": cov_status,
            "scope": "local_store",
            "observation": "per_root_atomic",
            "store_exists": store_exists,
            "roots_observed": len(matching),
            "active_roots": active_roots,
            "ended_roots": ended_roots,
            "created_at_min": created_min,
            "retained_event_min_at": retained_min,
            "retained_event_max_at": retained_max,
            "dropped_events": dropped_total,
            "dropped_through_max": dropped_through_max,
            "unobserved_roots": unobserved_roots,
            "disappeared_files": disappeared,
        },
        "window": {
            "session": session,
            "harness": harness,
            "since": since_iso,
            "until": until_iso,
            "since_at": since_at,
            "until_at": until_at,
            "limit": limit,
        },
        row_key: rows,
        "truncated": truncated,
        "retention": {
            "idle_seconds": IDLE_SECONDS,
            "ended_seconds": ENDED_SECONDS,
            "max_ended": MAX_ENDED,
            "max_events_per_root": MAX_EVENTS,
            "max_bytes_per_root": MAX_BYTES,
            "max_maintenance_mutations": MAX_MAINTENANCE,
            "ended_roots": len(ended_all),
            "dropped_count": dropped_total,
            "dropped_through": dropped_through_max,
            "dropped_roots": dropped_roots,
        },
        "cleanup_debt": cleanup_debt,
        "diagnostics": diagnostics,
    }
    if getattr(args, "json", False):
        return json.dumps(envelope)

    scopes_str = " ".join(f"{k}={v}" for k, v in hist_mod.SCOPES.items())
    header = (
        f"coverage:{cov_status} observation:per_root_atomic roots:{len(matching)} "
        f"truncated:{'yes' if truncated else 'no'} cleanup_debt:{cleanup_debt} scopes: {scopes_str}"
    )
    lines = [header]
    if mode == "history":
        for e in rows:
            lines.append(
                f"{_fmt_ts(e['at'])} {e['harness']}:{e['root']} gen:{e['generation'][:8]} "
                f"turn:{e['turn']} seq:{e['sequence']} {e['kind']}:{e['reason'] or 'none'} "
                f"{_fmt_snap(e['snapshot'])}"
            )
    else:
        for s in rows:
            pause_lbl = s["enforced_pause"] or "no"
            warn_lbl = ",".join(s["warnings"]) if s["warnings"] else "none"
            kinds_lbl = ",".join(s["event_kinds"])
            lines.append(
                f"{_fmt_ts(s['last_event_at'])} {s['harness']}:{s['root']} gen:{s['generation'][:8]} "
                f"turn:{s['turn']} start:{_fmt_ts(s['started_at'])} end:{_fmt_ts(s['ended_at'])} "
                f"paused:{pause_lbl} warnings:{warn_lbl} kinds:{kinds_lbl} {_fmt_snap(s['snapshot'])}"
            )
    for d in diagnostics:
        lines.append(f"diagnostic: {d}")
    return "\n".join(lines)


def history(args, env) -> str:
    return _collect(args, env, "history")


def listing(args, env) -> str:
    return _collect(args, env, "list")


def run(args) -> int:
    try:
        if args.pause_command == "status":
            text = status(args, os.environ)
        elif args.pause_command == "limits":
            text = show_limits(args)
        elif args.pause_command == "history":
            text = history(args, os.environ)
        elif args.pause_command == "list":
            text = listing(args, os.environ)
        else:
            raise PauseError(f"unknown pause subcommand {args.pause_command!r}")
    except (PauseError, StateError, OSError, ValueError, KeyError) as error:
        print(f"hq: {error}", file=sys.stderr)
        return 1
    print(text)
    return 0
