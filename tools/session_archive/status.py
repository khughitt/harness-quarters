"""status: one JSON object on archive health; unhealthy exits 1 (docs/session-archive.md)."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import replica
from .manifest import Manifest
from .quarantine import leftovers

STALE = timedelta(hours=48)


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def status_report(
    manifest: Manifest,
    homes,
    now: datetime,
    replica_root: Path | None = None,
) -> tuple[dict, bool]:
    capture = manifest.last_run("capture")
    successful_capture = manifest.last_run("capture", ok_only=True)
    prune = manifest.last_run("prune")
    quarantines = [str(path) for path in leftovers(homes)]
    fresh = successful_capture is not None and now - _parse(successful_capture.finished_at) <= STALE
    ok = fresh and (prune is None or prune.ok) and not quarantines
    report = {
        "capture": asdict(capture) if capture else None,
        "prune": asdict(prune) if prune else None,
        "archive_bytes": manifest.total_size(),
        "diverged": [f"{v.source}/{v.relpath}" for v in manifest.diverged()],
        "quarantines": quarantines,
        "ok": ok,
    }
    if replica_root is not None:
        rep = replica.replica_status(replica_root, manifest, now)
        ok = ok and rep["ok"]
        report["replica"] = rep
        report["ok"] = ok
    return report, ok
