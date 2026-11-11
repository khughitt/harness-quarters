"""Standalone evidence decoded from harness session stores."""
import subprocess
from pathlib import Path

SCHEMA = "harness-evidence/1"
DECODER_VERSION = "1"

__all__ = ["SCHEMA", "DECODER_VERSION", "RevisionUnknown", "revision"]


class RevisionUnknown(Exception):
    """The decoder has no pinned or checkout revision to report."""


def revision() -> str:
    """Identify a pinned package first, otherwise its containing Git checkout."""
    package = Path(__file__).resolve().parent
    pinned = package / "REVISION"
    if pinned.exists():
        try:
            value = pinned.read_text(encoding="utf-8").strip()
        except OSError:
            raise RevisionUnknown("decoder revision unknown") from None
        if not value:
            raise RevisionUnknown("decoder revision unknown")
        return value
    try:
        root = subprocess.run(["git", "-C", str(package), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, check=True).stdout.strip()
        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--",
                                "tools/harness_evidence"],
                               capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        raise RevisionUnknown("decoder revision unknown") from None
    return head + ("+dirty" if dirty else "")
