"""`hq sessions`: list recent sessions across harness homes; `-i` picks one and resumes it."""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import launch, sessions

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "hq.toml"
LABEL_WIDTH = 60


class UsageError(Exception):
    pass


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="hq", description="A command line over the harness homes.")
    commands = top.add_subparsers(dest="command", required=True)
    listing = commands.add_parser(
        "sessions", help="list recent agent sessions; -i resumes one",
        description="Recent Claude Code and Codex sessions across personal and work homes, newest first.")
    listing.add_argument("-i", "--interactive", action="store_true",
                         help="pick a session (fzf when on PATH, else a numbered prompt) and resume it")
    listing.add_argument("--harness", choices=("claude", "codex"))
    listing.add_argument("--home", choices=("personal", "work"))
    listing.add_argument("--here", action="store_true",
                         help="only sessions whose cwd is in this checkout or one of its worktrees")
    listing.add_argument("--archived", action="store_true", help="include archived Codex threads")
    listing.add_argument("-n", "--limit", type=positive, default=20, help="rows to show (default 20)")
    return top


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def checkout_roots(cwd: str) -> set[str]:
    """Every worktree of the checkout holding cwd, as recorded and resolved, plus the
    resolved `.worktrees/` directory, so a removed worktree's sessions still match."""
    result = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=cwd,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise UsageError(f"--here needs a git checkout: {result.stderr.strip()}")
    paths = [line[len("worktree "):] for line in result.stdout.splitlines() if line.startswith("worktree ")]
    roots = set(paths) | {os.path.realpath(path) for path in paths}
    roots.add(os.path.realpath(os.path.join(paths[0], ".worktrees")))
    return roots


def here_filter(roots: set[str]):
    def keep(session: sessions.Session) -> bool:
        candidates = {os.path.normpath(session.cwd), os.path.realpath(session.cwd)}
        return any(inside(path, root) for path in candidates for root in roots)
    return keep


def collect(args, user_home: Path):
    """Rows to show, sorted newest first, and the footer line describing the rest."""
    chosen = [home for home in sessions.homes(user_home)
              if (args.harness is None or home.harness == args.harness)
              and (args.home is None or home.kind == args.home)]
    keep = here_filter(checkout_roots(os.getcwd())) if args.here else (lambda session: True)
    absent = [home.name for home in chosen if not home.path.is_dir()]
    present = [home for home in chosen if home.path.is_dir()]
    found: list[sessions.Session] = []
    skipped = sessions.Skipped()
    for home in present:
        if home.harness == "claude":
            read, home_skipped = sessions.read_claude(home)
            skipped.without_id += home_skipped.without_id
            skipped.malformed += home_skipped.malformed
        else:
            read = sessions.read_codex(home, args.archived)
        found.extend(session for session in read if keep(session))
    listed = sorted((s for s in found if s.excluded is None), key=lambda s: s.recency_ms, reverse=True)
    harnesses = {home.harness for home in present}

    def count(harness: str, reason: str) -> int:
        return sum(1 for s in found if s.home.harness == harness and s.excluded == reason)

    parts = [f"{min(len(listed), args.limit)} of {len(listed)} shown"]
    if "claude" in harnesses:
        parts.append(f"skipped claude history lines: {skipped.without_id} without sessionId, "
                     f"{skipped.malformed} malformed")
    excluded = []
    if "claude" in harnesses:
        excluded.append(f"claude {count('claude', 'transcript gone')} transcript gone")
    if "codex" in harnesses:
        excluded.append(f"codex {count('codex', 'non-interactive')} non-interactive, "
                        f"{count('codex', 'transcript gone')} transcript gone")
    if excluded:
        parts.append("excluded: " + "; ".join(excluded))
    if absent:
        parts.append("absent: " + ", ".join(absent))
    return listed[:args.limit], " · ".join(parts)


def age(recency_ms: int, now_ms: int) -> str:
    seconds = max(0, (now_ms - recency_ms) // 1000)
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86_400:
        return f"{seconds // 3600}h"
    if seconds < 30 * 86_400:
        return f"{seconds // 86_400}d"
    return datetime.fromtimestamp(recency_ms / 1000).strftime("%Y-%m-%d")


def tilde(path: str, user_home: Path) -> str:
    home = str(user_home)
    return "~" + path[len(home):] if inside(path, home) else path


def label(text: str) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= LABEL_WIDTH else flat[:LABEL_WIDTH - 1] + "…"


def format_rows(shown: list[sessions.Session], user_home: Path) -> list[str]:
    now_ms = int(time.time() * 1000)
    places = [tilde(s.cwd, user_home) + ("" if os.path.isdir(s.cwd) else " (cwd missing)") for s in shown]
    width = max((len(place) for place in places), default=0)
    return [f"{s.home.harness:<6}  {s.home.kind:<8}  {s.id[:8]}  {age(s.recency_ms, now_ms):>10}  "
            f"{place:<{width}}  {label(s.label)}".rstrip()
            for s, place in zip(shown, places)]


def pick(lines: list[str], footer: str) -> int:
    """The 0-based index of the chosen row."""
    fzf = shutil.which("fzf")
    if fzf:
        numbered = "".join(f"{n}\t{line}\n" for n, line in enumerate(lines, 1))
        result = subprocess.run([fzf, "--delimiter=\t", "--with-nth=2..", "--no-sort", "--header", footer,
                                 "--prompt", "session> "], input=numbered, stdout=subprocess.PIPE, text=True)
        if result.returncode in (1, 130):
            raise UsageError("no session picked")
        if result.returncode != 0:
            raise UsageError(f"fzf exited {result.returncode}")
        answer = result.stdout.split("\t", 1)[0]
    else:
        for n, line in enumerate(lines, 1):
            print(f"{n:>3}  {line}")
        print(footer)
        print("session number: ", end="", file=sys.stderr, flush=True)
        answer = sys.stdin.readline().strip()
    if not (answer.isdigit() and 1 <= int(answer) <= len(lines)):
        raise UsageError(f"no session picked: expected 1-{len(lines)}, got {answer!r}")
    return int(answer) - 1


def sessions_command(args) -> int:
    user_home = Path.home()
    config = Path(os.environ.get("HQ_CONFIG", DEFAULT_CONFIG))
    flags = launch.load_flags(config) if args.interactive else None
    shown, footer = collect(args, user_home)
    lines = format_rows(shown, user_home)
    if not args.interactive:
        for line in lines:
            print(line)
        print(footer)
        return 0
    if not shown:
        raise UsageError(f"no sessions to pick ({footer})")
    launch.launch(shown[pick(lines, footer)], flags, config)
    return 0   # not reached: launch replaces this process


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv)
    try:
        code = sessions_command(args)
        sys.stdout.flush()   # inside the try: a short listing is otherwise written at exit
        return code
    except (UsageError, sessions.SourceError, launch.LaunchError) as error:
        print(f"hq: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        if args.interactive:
            print("hq: output closed before the launch; nothing launched", file=sys.stderr)
            return 1
        return 0   # the reader (`| head`) closed early: stop quietly, as other listing tools do
