"""session-archive command line (spec docs/specs/2026-09-30-session-archive-design.md)."""
import argparse
import json
import sys
import uuid
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

from . import capture, config
from .manifest import Manifest, Run, utc_now

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


def cmd_capture(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    try:
        started = utc_now()
        try:
            report, ok = capture.capture_run(cfg.archive_root, manifest, table)
        except OSError as error:
            report, ok = {"error": f"{type(error).__name__}: {error}"}, False
        manifest.record_run(Run(uuid.uuid4().hex, "capture", "apply", started, utc_now(), ok, report))
    finally:
        manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


def cmd_promote(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    try:
        promoted = capture.promote(cfg.archive_root, manifest, args.source, args.relpath)
    except capture.PromoteError as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return 1
    finally:
        manifest.close()
    print(json.dumps(asdict(promoted), sort_keys=True))
    return 0


COMMANDS = {"capture": cmd_capture, "promote": cmd_promote}


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
