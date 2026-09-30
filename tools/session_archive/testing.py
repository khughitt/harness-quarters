"""Helpers shared by the session-archive tests."""
import os
import subprocess
import sys
import time
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "session-archive"
DAY_NS = 86_400 * 10**9


def write(path: Path, data: bytes, age_days: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if age_days is not None:
        age(path, age_days)
    return path


def age(path: Path, days: float) -> None:
    stamp = time.time_ns() - int(days * DAY_NS)
    os.utime(path, ns=(stamp, stamp))


def write_config(home: Path, archive: Path, obs_command=("true",), uninspectable_ok=()) -> Path:
    path = home / ".config" / "session-archive" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    command = ", ".join(f'"{part}"' for part in obs_command)
    allowed = ", ".join(f'"{name}"' for name in uninspectable_ok)
    path.write_text(f'archive_root = "{archive}"\nobs_command = [{command}]\nuninspectable_ok = [{allowed}]\n')
    return path


def run_tool(*args: str, home: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], env={**os.environ, "HOME": str(home)},
                          capture_output=True, text=True)
