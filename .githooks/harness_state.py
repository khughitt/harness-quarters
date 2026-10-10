"""Mechanics shared by the tools that keep host state in this checkout's live harness configs.

codex-trust and live-picks both rewrite codex/config.toml, so they take one host lock,
local/harness-state.lock, around every read-modify-write of a live file or a saved copy.
Separate locks would let a trust restore and a pick restore read the same starting file
and each overwrite the other's insert. Each tool works on the checkout it lives in and
names itself in its failures. Design:
docs/specs/2026-10-10-live-model-preservation-design.md §3.3.
"""
import contextlib
import fcntl
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LOCAL = REPO / "local"
LOCK = LOCAL / "harness-state.lock"
GIT_HOOKS = ("post-checkout", "post-merge", "post-rewrite")
# A rebase runs post-checkout after checking out the new base, then replays commits
# from its in-memory index, which drops a restage made there; the file keeps its new
# size, and the replay of a commit that touches it stops with "local changes would be
# overwritten". post-rewrite restores when the rebase ends.
REBASE_STATE = ("rebase-merge", "rebase-apply")


def write(path, text):
    """Replace path by one rename, keeping its mode: the live configs are private (0600)."""
    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as out:
            out.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


class Checkout:
    """This checkout's git state as one tool sees it: failures carry the tool's name."""

    def __init__(self, tool):
        self.tool = tool

    def fail(self, message):
        sys.exit(f"{self.tool}: {message}")

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(REPO), *args], text=True, capture_output=True)
        if result.returncode != 0:
            self.fail(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout.strip()

    def git_path(self, name):
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-path", name))

    def linked_worktree(self):
        return (self.git("rev-parse", "--path-format=absolute", "--git-dir")
                != self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))

    def rebasing(self):
        return any(self.git_path(state).exists() for state in REBASE_STATE)

    def restage(self, name):
        """Stage a restored file when its filtered diff is empty, as harness-state-refresh does.

        The insert changes the file's size, and git calls a file of another size modified
        without running the filter; a rebase refuses to start on that mark. While another
        git process holds the index, the next turn end's refresh stages it instead.
        """
        if self.git_path("index.lock").exists():
            return
        diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "--", name],
                              text=True, capture_output=True)
        if diff.returncode not in (0, 1):
            self.fail(f"git diff {name}: {diff.stderr.strip()}")
        if diff.returncode == 0:
            self.git("add", "--", name)

    @contextlib.contextmanager
    def locked(self):
        """Hold the host lock every tool that rewrites a live harness config takes."""
        if not LOCAL.is_dir():
            self.fail("local/ is missing; run `just setup`")
        with open(LOCK, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
