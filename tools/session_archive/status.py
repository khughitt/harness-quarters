"""status: one JSON object on archive health; unhealthy exits 1 (spec §3.5)."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .manifest import Manifest
from .quarantine import leftovers

STALE = timedelta(hours=48)


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def status_report(manifest: Manifest, homes, now: datetime) -> tuple[dict, bool]:
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
    return report, ok
