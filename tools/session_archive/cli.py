"""session-archive command line (spec docs/specs/2026-09-30-session-archive-design.md)."""
import argparse
import sys
from contextlib import nullcontext
from pathlib import Path

from . import config

LOCKED = frozenset({"capture", "prune", "promote", "probe-codex"})


def config_path() -> Path:
    return Path.home() / ".config" / "session-archive" / "config.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="session-archive")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capture", help="copy every transcript into the archive")
    prune = sub.add_parser("prune", help="report eligible units; delete them with --apply")
    prune.add_argument("--apply", action="store_true")
    sub.add_parser("status", help="print archive health as JSON")
    promote = sub.add_parser("promote", help="make a diverged file's latest version the mirror")
    promote.add_argument("source")
    promote.add_argument("relpath")
    sub.add_parser("probe-codex", help="check Codex lock and delete behaviour in a throwaway home")
    return parser


# command name -> handler(cfg, sources, args) -> exit code; later tasks add entries.
COMMANDS = {}


def main(argv) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config.load_config(config_path())
        table = config.sources(Path.home())
        config.check_sources(table)
        with config.archive_lock(cfg.archive_root) if args.command in LOCKED else nullcontext():
            return COMMANDS[args.command](cfg, table, args)
    except config.HostGateError as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return config.EX_HOST
    except config.LockHeld as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return config.EX_TEMPFAIL
