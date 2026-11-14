"""session-archive command line (contract docs/session-archive.md)."""
import argparse
import json
import sqlite3
import sys
import tempfile
import time
import uuid
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import harness_stores

from . import capture, config, inputs, probe, prune, replica, status
from .manifest import FILENAME, Manifest, Run, utc_now

LOCKED = frozenset({"capture", "prune", "promote", "probe-codex"})
REPLICA = frozenset({"replicate", "verify-replica"})
REPLICA_LOCK_WAIT = 7200.0
DISKS = replica.disks_of
CLOCK = lambda: datetime.now(timezone.utc)
CODEX = "codex"


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
    sub.add_parser("replicate", help="copy the archive into a verified generation on the replica disk")
    sub.add_parser("verify-replica", help="check the current replica generation in scratch")
    return parser


def cmd_capture(cfg, table, args, skipped) -> int:
    manifest = Manifest.open(cfg.archive_root)
    try:
        started = utc_now()
        try:
            report, ok = capture.capture_run(cfg.archive_root, manifest, table, skipped)
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


def cmd_probe_codex(cfg, table, args) -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="session-archive-probe-") as workdir:
            result = probe.probe_codex(CODEX, Path(workdir), lambda: inputs.open_inodes(allow=cfg.uninspectable_ok))
    except (probe.CodexUnavailable, inputs.InspectionFailed) as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return 1
    if result.passed:
        manifest = Manifest.open(cfg.archive_root)
        try:
            manifest.record_probe(result.version, utc_now())
        finally:
            manifest.close()
    print(json.dumps({"version": result.version, "checks": result.checks, "passed": result.passed},
                     sort_keys=True))
    return 0 if result.passed else 1


def cmd_prune(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    run_id, started = uuid.uuid4().hex, utc_now()
    report = {}
    try:
        try:
            codex_probed = (not args.apply) or manifest.probe_passed(probe.codex_version(CODEX))
            if not codex_probed:
                report["codex_gate"] = "the installed codex has not passed probe-codex; run `session-archive probe-codex`"
            ctx = prune.Context(cfg.archive_root, manifest, inputs.load_obs_state(cfg.obs_command),
                                lambda: inputs.open_inodes(allow=cfg.uninspectable_ok), time.time_ns(),
                                run_id, codex_bin=CODEX)
            ok = prune.prune_run(ctx, table, args.apply, codex_probed, report)
        except (inputs.ObsUnavailable, inputs.InspectionFailed, prune.ArchiveUnreadable,
                prune.LeftoverQuarantine, probe.CodexUnavailable, OSError) as error:
            report["error"] = f"{type(error).__name__}: {error}"
            ok = False
        manifest.record_run(Run(run_id, "prune", "apply" if args.apply else "dry-run", started, utc_now(), ok, report))
    finally:
        manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


def cmd_status(cfg, table, args) -> int:
    try:
        manifest = Manifest.open_readonly(cfg.archive_root)
        try:
            report, ok = status.status_report(manifest, [source.home for source in table],
                                              CLOCK(), replica_root=cfg.replica_root)
        finally:
            manifest.close()
    except (sqlite3.Error, OSError, ValueError) as error:
        report, ok = {"ok": False, "error": f"{type(error).__name__}: {error}"}, False
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


def _clock_stamp() -> str:
    return CLOCK().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def cmd_replicate(cfg, table, args) -> int:
    disks = replica.check_replica(cfg, DISKS)
    with config.archive_lock(cfg.archive_root, wait=REPLICA_LOCK_WAIT):
        manifest = Manifest.open(cfg.archive_root)
        try:
            started = _clock_stamp()
            try:
                report = replica.replicate(cfg.archive_root, cfg.replica_root, manifest, disks, now=CLOCK)
                ok = True
                started = report.get("started_at", started)
                finished = report.get("finished_at", _clock_stamp())
            except replica.ReplicateFailed as error:
                report, ok = error.report, False
                started = report.get("started_at", started)
                finished = _clock_stamp()
            try:
                manifest.record_run(Run(uuid.uuid4().hex, "replicate", "apply", started, finished, ok, report))
            except (sqlite3.Error, OSError):
                if ok:
                    raise
        finally:
            manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


def cmd_verify_replica(cfg, table, args) -> int:
    replica.check_replica(cfg, DISKS)
    with config.archive_lock(cfg.archive_root, wait=REPLICA_LOCK_WAIT):
        manifest = Manifest.open(cfg.archive_root)
        try:
            started = _clock_stamp()
            try:
                with tempfile.TemporaryDirectory(prefix="session-archive-verify-") as scratch:
                    report = replica.verify_replica(cfg.replica_root, Path(scratch))
                ok = True
            except replica.VerifyFailed as error:
                report, ok = error.report, False
            except (OSError, sqlite3.Error) as error:
                report, ok = {"error": f"{type(error).__name__}: {error}", "failures": [str(error)]}, False
            finished = _clock_stamp()
            manifest.record_run(Run(uuid.uuid4().hex, "verify-replica", "apply", started, finished, ok, report))
        finally:
            manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


COMMANDS = {"promote": cmd_promote, "probe-codex": cmd_probe_codex,
            "prune": cmd_prune, "status": cmd_status,
            "replicate": cmd_replicate, "verify-replica": cmd_verify_replica}


class CapturedSources:
    """Whether a source has ever been captured; opens the manifest read-only on first use."""

    def __init__(self, archive_root: Path):
        self.archive_root = archive_root
        self.manifest = None

    def __call__(self, source: str) -> bool:
        if self.manifest is None:
            if not (self.archive_root / FILENAME).exists():
                return False
            self.manifest = Manifest.open_readonly(self.archive_root)
        return self.manifest.has_source(source)

    def close(self) -> None:
        if self.manifest is not None:
            self.manifest.close()


def main(argv) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config.load_config(config_path())
        if args.command in REPLICA:
            table, skipped = (), {}
        else:
            table = harness_stores.archive_sources(Path.home())
            captured = CapturedSources(cfg.archive_root)
            try:
                skipped = config.check_sources(table, captured)
            finally:
                captured.close()
        with config.archive_lock(cfg.archive_root) if args.command in LOCKED else nullcontext():
            if args.command == "capture":
                return cmd_capture(cfg, table, args, skipped)
            return COMMANDS[args.command](cfg, table, args)
    except config.HostGateError as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return config.EX_HOST
    except config.LockHeld as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return config.EX_TEMPFAIL
