"""Standalone evidence decoded from harness session stores."""
import os
import subprocess
from pathlib import Path

SCHEMA = "harness-evidence/1"
DECODER_VERSION = "22"

__all__ = ["SCHEMA", "DECODER_VERSION", "RevisionUnknown", "revision", "index_adapters", "index_claude", "index_pi", "index_events", "index_stream", "index_coverage", "header"]


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
    # Git's repository and index environment overrides -C, so inherit none of it.
    git_env = {"PATH": os.defpath, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0"}
    try:
        root = subprocess.run(["git", "-C", str(package), "rev-parse", "--show-toplevel"],
                              env=git_env, capture_output=True, text=True, check=True).stdout.strip()
        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                              env=git_env, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--",
                                "tools/harness_evidence"],
                               env=git_env, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        raise RevisionUnknown("decoder revision unknown") from None
    return head + ("+dirty" if dirty else "")
