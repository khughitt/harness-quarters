"""The archive manifest: one row per archived file version, plus the run and Codex probe
logs (spec §3.3, §3.5)."""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIRROR = "mirror"
FILENAME = "manifest.sqlite"
SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
  source TEXT NOT NULL, relpath TEXT NOT NULL, location TEXT NOT NULL,
  size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL,
  captured_at TEXT NOT NULL, PRIMARY KEY (source, relpath, location));
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, mode TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL, ok INTEGER NOT NULL, report TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS codex_probe (version TEXT PRIMARY KEY, passed_at TEXT NOT NULL);
"""
COLUMNS = "source, relpath, location, size, mtime_ns, sha256, captured_at"
NEWEST = "ORDER BY captured_at DESC, location = 'mirror' DESC"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class Version:
    source: str
    relpath: str
    location: str      # MIRROR, or a path under versions/ relative to the archive root
    size: int
    mtime_ns: int
    sha256: str
    captured_at: str


@dataclass(frozen=True)
class Run:
    run_id: str
    kind: str          # "capture" or "prune"
    mode: str          # "apply" or "dry-run"
    started_at: str
    finished_at: str
    ok: bool
    report: dict


class Manifest:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def open(cls, archive_root: Path) -> "Manifest":
        conn = sqlite3.connect(archive_root / FILENAME)
        conn.executescript(SCHEMA)
        return cls(conn)

    @classmethod
    def open_readonly(cls, archive_root: Path) -> "Manifest":
        uri = (archive_root / FILENAME).resolve().as_uri() + "?mode=ro"
        return cls(sqlite3.connect(uri, uri=True))

    def close(self) -> None:
        self.conn.close()

    def put(self, version: Version) -> None:
        with self.conn:
            self.conn.execute(f"INSERT OR REPLACE INTO versions ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (version.source, version.relpath, version.location, version.size,
                               version.mtime_ns, version.sha256, version.captured_at))

    def rows(self, source: str, relpath: str) -> list[Version]:
        cursor = self.conn.execute(
            f"SELECT {COLUMNS} FROM versions WHERE source = ? AND relpath = ? {NEWEST}", (source, relpath))
        return [Version(*row) for row in cursor]

    def mirror(self, source: str, relpath: str) -> Version | None:
        row = self.conn.execute(
            f"SELECT {COLUMNS} FROM versions WHERE source = ? AND relpath = ? AND location = ?",
            (source, relpath, MIRROR)).fetchone()
        return Version(*row) if row else None

    def latest(self, source: str, relpath: str) -> Version | None:
        row = self.conn.execute(
            f"SELECT {COLUMNS} FROM versions WHERE source = ? AND relpath = ? {NEWEST} LIMIT 1",
            (source, relpath)).fetchone()
        return Version(*row) if row else None

    def diverged(self) -> list[Version]:
        """Files whose newest version is not the mirrored one (spec §3.3)."""
        cursor = self.conn.execute(f"""
            SELECT {COLUMNS} FROM (
              SELECT *, ROW_NUMBER() OVER (PARTITION BY source, relpath {NEWEST}) AS n FROM versions)
            WHERE n = 1 AND location != 'mirror' ORDER BY source, relpath""")
        return [Version(*row) for row in cursor]

    def total_size(self) -> int:
        return self.conn.execute("SELECT COALESCE(SUM(size), 0) FROM versions").fetchone()[0]

    def record_run(self, run: Run) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (run.run_id, run.kind, run.mode, run.started_at, run.finished_at,
                               int(run.ok), json.dumps(run.report, sort_keys=True)))

    def last_run(self, kind: str, ok_only: bool = False) -> Run | None:
        row = self.conn.execute(
            "SELECT run_id, kind, mode, started_at, finished_at, ok, report FROM runs "
            f"WHERE kind = ? {'AND ok = 1' if ok_only else ''} ORDER BY finished_at DESC LIMIT 1",
            (kind,)).fetchone()
        if row is None:
            return None
        return Run(*row[:5], bool(row[5]), json.loads(row[6]))

    def record_probe(self, version: str, passed_at: str) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO codex_probe VALUES (?, ?)", (version, passed_at))

    def probe_passed(self, version: str) -> bool:
        return self.conn.execute("SELECT 1 FROM codex_probe WHERE version = ?", (version,)).fetchone() is not None
